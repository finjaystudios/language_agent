import asyncio
from typing import Any

from rq.job import JobStatus

from app.core.config import AppSettings
from app.domain.jobs import LLMCallJob, QueueStatusSnapshot, utcnow
from app.infrastructure.redis.job_store import RedisJobStore
from app.infrastructure.redis.rq_queue import RQQueueClient
from app.ports.job_store import JobStore
from app.ports.queue_client import QueueClient


class LLMQueueService:
    def __init__(
        self,
        settings: AppSettings,
        queue_client: QueueClient,
        job_store: JobStore,
    ) -> None:
        self.settings = settings
        self.queue_client = queue_client
        self.job_store = job_store

    def estimate_wait_time_seconds(self) -> float:
        average_generation = self.job_store.read_average_generation_time_seconds()
        per_job_seconds = max(
            1.0,
            average_generation or min(30, self.settings.llm_generation_timeout_seconds),
        )
        return (
            self.queue_client.get_queue_depth()
            + self.queue_client.get_active_job_count()
        ) * per_job_seconds

    async def enqueue_llm_call(self, job_request: LLMCallJob) -> Any:
        estimated_wait_seconds = self.estimate_wait_time_seconds()
        if hasattr(self.queue_client, "check_backpressure"):
            self.queue_client.check_backpressure(estimated_wait_seconds)
        job_request.stream_channel = self.job_store.get_stream_channel(
            job_request.job_id
        )
        payload = self.job_store.serialize_llm_call(job_request)  # type: ignore[attr-defined]
        job = self.queue_client.enqueue(
            payload,
            job_id=job_request.job_id,
            result_ttl=self.settings.llm_result_ttl_seconds,
            job_timeout=self.settings.llm_generation_timeout_seconds,
            retry_max=self.settings.llm_job_max_retries,
        )
        self.job_store.save_job_payload(job, job_request)
        if job_request.call_type == "streaming_text_generation":
            self.job_store.append_stream_event(
                job_request.job_id,
                {
                    "job_id": job_request.job_id,
                    "status": "queued",
                    "queue_position": self.queue_client.get_job_position(
                        job_request.job_id
                    ),
                    "elapsed_seconds": 0.0,
                },
            )
        return job

    async def get_job_result(self, job_id: str) -> LLMCallJob:
        return await asyncio.to_thread(self.job_store.get_job_result, job_id)

    async def get_job_status(self, job_id: str) -> LLMCallJob:
        def load() -> LLMCallJob:
            llm_call = self.job_store.get_job_result(job_id)
            rq_status = self.queue_client.get_job_status(job_id)
            if rq_status in {
                "JobStatus.QUEUED",
                "JobStatus.DEFERRED",
                "JobStatus.SCHEDULED",
                "queued",
                "deferred",
                "scheduled",
            }:
                llm_call.status = "queued"
                llm_call.queue_position = self.queue_client.get_job_position(job_id)
            elif rq_status in {
                str(JobStatus.STARTED),
                "started",
            } and llm_call.status not in {
                "streaming",
                "cancelled",
            }:
                llm_call.status = "processing"
            elif rq_status in {str(JobStatus.CANCELED), "canceled", "cancelled"}:
                llm_call.status = "cancelled"
            elif rq_status in {str(JobStatus.FAILED), "failed"}:
                llm_call.status = "failed"
            llm_call.elapsed_seconds = self.job_store._compute_elapsed_seconds(llm_call)  # type: ignore[attr-defined]
            return llm_call

        return await asyncio.to_thread(load)

    async def cancel_llm_call(self, job_id: str) -> LLMCallJob:
        def cancel() -> LLMCallJob:
            job = self.queue_client.get_job(job_id)
            llm_call = self.job_store.get_job_result(job_id)
            rq_status = self.queue_client.get_job_status(job_id)
            if llm_call.status in {"completed", "failed", "cancelled"}:
                return llm_call
            llm_call.cancel_requested = True
            if rq_status in {
                str(JobStatus.QUEUED),
                str(JobStatus.DEFERRED),
                str(JobStatus.SCHEDULED),
                "queued",
                "deferred",
                "scheduled",
            }:
                self.queue_client.remove(job_id)
                llm_call.status = "cancelled"
                llm_call.completed_at = utcnow()
                llm_call.error = "LLM job was cancelled before execution."
                self.job_store.save_job_payload(job, llm_call)
                if hasattr(job, "set_status"):
                    job.set_status(JobStatus.CANCELED)
                self.job_store.append_stream_event(
                    job_id,
                    {
                        "job_id": job_id,
                        "status": "cancelled",
                        "cancel_requested": True,
                        "message": "LLM job was cancelled before execution.",
                        "done": True,
                    },
                )
                return llm_call

            self.job_store.save_job_payload(job, llm_call)
            self.job_store.append_stream_event(
                job_id,
                {
                    "job_id": job_id,
                    "status": llm_call.status,
                    "cancel_requested": True,
                    "message": "Cancellation requested. Running non-streaming jobs may finish before stopping.",
                },
            )
            return llm_call

        return await asyncio.to_thread(cancel)

    async def stream_llm_events(self, job_id: str):
        async for event in self.job_store.stream_llm_events(
            job_id,
            timeout_seconds=self.settings.llm_stream_timeout_seconds,
        ):
            yield event

    async def wait_for_job_result(self, job_id: str) -> LLMCallJob:
        deadline = (
            asyncio.get_running_loop().time()
            + self.settings.llm_queue_wait_timeout_seconds
        )
        while True:
            status = await self.get_job_status(job_id)
            if status.status in {"completed", "failed", "cancelled"}:
                return await self.get_job_result(job_id)
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(f"Timed out waiting for LLM job '{job_id}'.")
            await asyncio.sleep(self.settings.llm_status_poll_interval_seconds)

    def get_queue_status_sync(self) -> QueueStatusSnapshot:
        redis_connected = self.queue_client.ping()
        return self.queue_client.build_queue_status(
            redis_connected=redis_connected,
            average_wait_time_seconds=self.job_store.read_average_wait_time_seconds()
            if redis_connected
            else None,
            estimated_wait_time_seconds=self.estimate_wait_time_seconds()
            if redis_connected
            else None,
        )

    async def get_queue_status(self) -> QueueStatusSnapshot:
        return await asyncio.to_thread(self.get_queue_status_sync)

    def is_cancel_requested(self, job_id: str) -> bool:
        return self.job_store.is_cancel_requested(job_id)


_SETTINGS = AppSettings.from_env


def create_queue_service(
    settings: AppSettings | None = None,
    queue_client: QueueClient | None = None,
    job_store: JobStore | None = None,
) -> LLMQueueService:
    resolved_settings = settings or _SETTINGS()
    resolved_queue_client = queue_client or RQQueueClient(resolved_settings)
    resolved_job_store = job_store or RedisJobStore(
        resolved_settings,
        resolved_queue_client,
    )
    return LLMQueueService(resolved_settings, resolved_queue_client, resolved_job_store)


def get_redis_connection(url: str | None = None):
    from app.infrastructure.redis.connection import get_redis_connection as _get_redis

    settings = _SETTINGS()
    return _get_redis(url or settings.redis_url)


def get_async_redis_connection(url: str | None = None):
    from app.infrastructure.redis.connection import (
        get_async_redis_connection as _get_async,
    )

    settings = _SETTINGS()
    return _get_async(url or settings.redis_url)


async def close_async_redis_connection(connection):
    from app.infrastructure.redis.connection import (
        close_async_redis_connection as _close,
    )

    await _close(connection)


def get_stream_channel(job_id: str) -> str:
    return create_queue_service().job_store.get_stream_channel(job_id)


def compute_elapsed_seconds(llm_call: LLMCallJob) -> float | None:
    return create_queue_service().job_store._compute_elapsed_seconds(llm_call)  # type: ignore[attr-defined]


def serialize_llm_call(llm_call: LLMCallJob) -> dict[str, Any]:
    return create_queue_service().job_store.serialize_llm_call(llm_call)  # type: ignore[attr-defined]


def set_job_payload(job, llm_call: LLMCallJob) -> None:
    create_queue_service().job_store.save_job_payload(job, llm_call)


def record_wait_time(wait_seconds: float, connection=None) -> None:
    if connection is not None:
        settings = _SETTINGS()
        queue_client = RQQueueClient(settings, connection=connection)
        job_store = RedisJobStore(settings, queue_client, connection=connection)
        job_store.record_wait_time(wait_seconds)
        return
    create_queue_service().job_store.record_wait_time(wait_seconds)


def record_completion_metrics(llm_call: LLMCallJob, connection=None) -> None:
    if connection is not None:
        settings = _SETTINGS()
        queue_client = RQQueueClient(settings, connection=connection)
        job_store = RedisJobStore(settings, queue_client, connection=connection)
        job_store.record_completion_metrics(llm_call)
        return
    create_queue_service().job_store.record_completion_metrics(llm_call)


def read_average_wait_time_seconds(connection=None) -> float | None:
    return create_queue_service().job_store.read_average_wait_time_seconds()


def read_average_generation_time_seconds(connection=None) -> float | None:
    return create_queue_service().job_store.read_average_generation_time_seconds()


def estimate_wait_time_seconds(
    queue_depth: int, active_job_count: int, connection=None
) -> float:
    average_generation = read_average_generation_time_seconds()
    per_job_seconds = max(
        1.0,
        average_generation or min(30, _SETTINGS().llm_generation_timeout_seconds),
    )
    return (queue_depth + active_job_count) * per_job_seconds


def append_stream_event(job_id: str, payload: dict[str, Any], connection=None) -> str:
    if connection is not None:
        settings = _SETTINGS()
        queue_client = RQQueueClient(settings, connection=connection)
        job_store = RedisJobStore(settings, queue_client, connection=connection)
        return job_store.append_stream_event(job_id, payload)
    return create_queue_service().job_store.append_stream_event(job_id, payload)


def get_job_result(job_id: str, connection=None) -> LLMCallJob:
    if connection is not None:
        settings = _SETTINGS()
        queue_client = RQQueueClient(settings, connection=connection)
        job_store = RedisJobStore(settings, queue_client, connection=connection)
        return job_store.get_job_result(job_id)
    return create_queue_service().job_store.get_job_result(job_id)


async def get_job_result_async(job_id: str, connection=None) -> LLMCallJob:
    return await asyncio.to_thread(get_job_result, job_id, connection)


async def enqueue_llm_call(job_request: LLMCallJob, queue=None):
    queue_service = create_queue_service(
        queue_client=queue if isinstance(queue, QueueClient) else None
    )
    return await queue_service.enqueue_llm_call(job_request)


async def get_job_status(job_id: str, connection=None) -> LLMCallJob:
    if connection is not None:
        settings = _SETTINGS()
        queue_client = RQQueueClient(settings, connection=connection)
        job_store = RedisJobStore(settings, queue_client, connection=connection)
        return await LLMQueueService(settings, queue_client, job_store).get_job_status(
            job_id
        )
    return await create_queue_service().get_job_status(job_id)


async def cancel_llm_call(job_id: str, connection=None) -> LLMCallJob:
    if connection is not None:
        settings = _SETTINGS()
        queue_client = RQQueueClient(settings, connection=connection)
        job_store = RedisJobStore(settings, queue_client, connection=connection)
        return await LLMQueueService(settings, queue_client, job_store).cancel_llm_call(
            job_id
        )
    return await create_queue_service().cancel_llm_call(job_id)


def is_cancel_requested(job_id: str, connection=None) -> bool:
    if connection is not None:
        settings = _SETTINGS()
        queue_client = RQQueueClient(settings, connection=connection)
        job_store = RedisJobStore(settings, queue_client, connection=connection)
        return job_store.is_cancel_requested(job_id)
    return create_queue_service().is_cancel_requested(job_id)


def ping_redis(connection=None) -> bool:
    if connection is not None:
        settings = _SETTINGS()
        return RQQueueClient(settings, connection=connection).ping()
    return create_queue_service().queue_client.ping()


async def ping_redis_async(connection=None) -> bool:
    return ping_redis(connection)


async def stream_llm_events(
    job_id: str, *, connection_factory=None, timeout_seconds=None
):
    queue_service = create_queue_service()
    async for event in queue_service.job_store.stream_llm_events(
        job_id,
        timeout_seconds=timeout_seconds
        or queue_service.settings.llm_stream_timeout_seconds,
    ):
        yield event


async def wait_for_job_result(
    job_id: str,
    *,
    connection_factory=None,
    timeout_seconds=None,
    poll_interval_seconds=None,
) -> LLMCallJob:
    queue_service = create_queue_service()
    if timeout_seconds is not None or poll_interval_seconds is not None:
        custom_settings = AppSettings(
            **{
                **queue_service.settings.__dict__,
                "llm_queue_wait_timeout_seconds": timeout_seconds
                or queue_service.settings.llm_queue_wait_timeout_seconds,
                "llm_status_poll_interval_seconds": poll_interval_seconds
                or queue_service.settings.llm_status_poll_interval_seconds,
            }
        )
        queue_service = create_queue_service(
            settings=custom_settings,
            queue_client=queue_service.queue_client,
            job_store=queue_service.job_store,
        )
    return await queue_service.wait_for_job_result(job_id)


def get_queue_status_sync(connection=None) -> QueueStatusSnapshot:
    if connection is not None:
        settings = _SETTINGS()
        queue_client = RQQueueClient(settings, connection=connection)
        job_store = RedisJobStore(settings, queue_client, connection=connection)
        return LLMQueueService(
            settings, queue_client, job_store
        ).get_queue_status_sync()
    return create_queue_service().get_queue_status_sync()


async def get_queue_status(connection=None) -> QueueStatusSnapshot:
    return await create_queue_service().get_queue_status()
