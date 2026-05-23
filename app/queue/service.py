import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from redis import Redis
from rq import Queue, Retry
from rq.job import Job, JobStatus
from rq.registry import FailedJobRegistry, StartedJobRegistry
from rq.worker import Worker

from app.queue.config import (
    LLM_GENERATION_TIMEOUT_SECONDS,
    LLM_JOB_MAX_RETRIES,
    LLM_MAX_QUEUE_SIZE,
    LLM_QUEUE_NAME,
    LLM_QUEUE_TIMEOUT_SECONDS,
    LLM_QUEUE_WAIT_TIMEOUT_SECONDS,
    LLM_RESULT_TTL_SECONDS,
    LLM_STATUS_POLL_INTERVAL_SECONDS,
    LLM_STREAM_CHANNEL_PREFIX,
    LLM_STREAM_TIMEOUT_SECONDS,
    REDIS_URL,
)
from app.queue.errors import QueueSaturatedError
from app.queue.models import LLMCallJob, QueueStatusSnapshot, utcnow

QUEUE_METRICS_KEY = "llm:queue:metrics"


def get_redis_connection(url: str | None = None) -> Redis:
    return Redis.from_url(url or REDIS_URL)


def get_llm_queue(
    connection: Redis | None = None,
    queue_name: str | None = None,
) -> Queue:
    return Queue(
        name=queue_name or LLM_QUEUE_NAME,
        connection=connection or get_redis_connection(),
        default_timeout=LLM_QUEUE_TIMEOUT_SECONDS,
    )


def get_started_job_registry(
    connection: Redis | None = None,
    queue_name: str | None = None,
) -> StartedJobRegistry:
    return StartedJobRegistry(
        name=queue_name or LLM_QUEUE_NAME,
        connection=connection or get_redis_connection(),
    )


def get_failed_job_registry(
    connection: Redis | None = None,
    queue_name: str | None = None,
) -> FailedJobRegistry:
    return FailedJobRegistry(
        name=queue_name or LLM_QUEUE_NAME,
        connection=connection or get_redis_connection(),
    )


def get_stream_channel(job_id: str) -> str:
    return f"{LLM_STREAM_CHANNEL_PREFIX}:{job_id}"


def compute_elapsed_seconds(llm_call: LLMCallJob) -> float | None:
    start_time = llm_call.started_at or llm_call.created_at
    if start_time is None:
        return None
    end_time = llm_call.completed_at or datetime.now(UTC)
    return max(0.0, (end_time - start_time).total_seconds())


def serialize_llm_call(llm_call: LLMCallJob) -> dict[str, Any]:
    llm_call.elapsed_seconds = compute_elapsed_seconds(llm_call)
    return llm_call.model_dump(mode="json")


def set_job_payload(job: Job, llm_call: LLMCallJob) -> None:
    job.meta["llm_call"] = serialize_llm_call(llm_call)
    job.save_meta()


def record_wait_time(wait_seconds: float, connection: Redis | None = None) -> None:
    redis_connection = connection or get_redis_connection()
    redis_connection.hincrbyfloat(QUEUE_METRICS_KEY, "total_wait_seconds", wait_seconds)
    redis_connection.hincrby(QUEUE_METRICS_KEY, "started_jobs", 1)


def record_completion_metrics(
    llm_call: LLMCallJob,
    connection: Redis | None = None,
) -> None:
    redis_connection = connection or get_redis_connection()
    if llm_call.started_at is not None and llm_call.completed_at is not None:
        generation_seconds = max(
            0.0,
            (llm_call.completed_at - llm_call.started_at).total_seconds(),
        )
        redis_connection.hincrbyfloat(
            QUEUE_METRICS_KEY,
            "total_generation_seconds",
            generation_seconds,
        )
    redis_connection.hincrby(QUEUE_METRICS_KEY, "completed_jobs", 1)


def read_average_wait_time_seconds(connection: Redis | None = None) -> float | None:
    redis_connection = connection or get_redis_connection()
    metrics = redis_connection.hgetall(QUEUE_METRICS_KEY)
    started_jobs_raw = metrics.get(b"started_jobs") or metrics.get("started_jobs")
    total_wait_raw = metrics.get(b"total_wait_seconds") or metrics.get(
        "total_wait_seconds"
    )
    if not started_jobs_raw or not total_wait_raw:
        return None
    started_jobs = int(
        started_jobs_raw.decode()
        if isinstance(started_jobs_raw, bytes)
        else started_jobs_raw
    )
    if started_jobs <= 0:
        return None
    total_wait = float(
        total_wait_raw.decode() if isinstance(total_wait_raw, bytes) else total_wait_raw
    )
    return total_wait / started_jobs


def read_average_generation_time_seconds(
    connection: Redis | None = None,
) -> float | None:
    redis_connection = connection or get_redis_connection()
    metrics = redis_connection.hgetall(QUEUE_METRICS_KEY)
    completed_jobs_raw = metrics.get(b"completed_jobs") or metrics.get("completed_jobs")
    total_generation_raw = metrics.get(b"total_generation_seconds") or metrics.get(
        "total_generation_seconds"
    )
    if not completed_jobs_raw or not total_generation_raw:
        return None
    completed_jobs = int(
        completed_jobs_raw.decode()
        if isinstance(completed_jobs_raw, bytes)
        else completed_jobs_raw
    )
    if completed_jobs <= 0:
        return None
    total_generation = float(
        total_generation_raw.decode()
        if isinstance(total_generation_raw, bytes)
        else total_generation_raw
    )
    return total_generation / completed_jobs


def estimate_wait_time_seconds(
    queue_depth: int,
    active_job_count: int,
    connection: Redis | None = None,
) -> float:
    average_generation = read_average_generation_time_seconds(connection)
    per_job_seconds = max(
        1.0, average_generation or min(30, LLM_GENERATION_TIMEOUT_SECONDS)
    )
    return (queue_depth + active_job_count) * per_job_seconds


def check_queue_backpressure(queue: Queue) -> None:
    active_job_count = get_started_job_registry(queue.connection, queue.name).count
    queue_depth = queue.count
    if queue_depth >= LLM_MAX_QUEUE_SIZE:
        retry_after_seconds = int(
            max(
                1,
                estimate_wait_time_seconds(
                    queue_depth, active_job_count, queue.connection
                ),
            )
        )
        raise QueueSaturatedError(retry_after_seconds=retry_after_seconds)

    estimated_wait_seconds = estimate_wait_time_seconds(
        queue_depth,
        active_job_count,
        queue.connection,
    )
    if estimated_wait_seconds > LLM_QUEUE_WAIT_TIMEOUT_SECONDS:
        raise QueueSaturatedError(
            message=(
                "The language model queue is too busy to accept this request right now."
            ),
            retry_after_seconds=int(max(1, estimated_wait_seconds)),
        )


def append_stream_event(
    job_id: str,
    payload: dict[str, Any],
    connection: Redis | None = None,
) -> str:
    redis_connection = connection or get_redis_connection()
    stream_name = get_stream_channel(job_id)
    event_id = redis_connection.xadd(stream_name, {"event": json.dumps(payload)})
    redis_connection.expire(stream_name, LLM_RESULT_TTL_SECONDS)
    if isinstance(event_id, bytes):
        return event_id.decode()
    return str(event_id)


def get_job_result(
    job_id: str,
    connection: Redis | None = None,
) -> LLMCallJob:
    redis_connection = connection or get_redis_connection()
    job = Job.fetch(job_id, connection=redis_connection)
    payload = job.result or job.meta.get("llm_call")
    if payload is None:
        raise RuntimeError(f"LLM job '{job_id}' has no result payload.")
    llm_call = LLMCallJob.model_validate(payload)
    if llm_call.stream_channel is None:
        llm_call.stream_channel = get_stream_channel(job_id)
    if llm_call.status == "queued":
        try:
            llm_call.queue_position = get_llm_queue(redis_connection).get_job_position(
                job_id
            )
        except Exception:
            llm_call.queue_position = None
    llm_call.elapsed_seconds = compute_elapsed_seconds(llm_call)
    return llm_call


def enqueue_llm_call(job_request: LLMCallJob, queue: Queue | None = None) -> Job:
    llm_queue = queue or get_llm_queue()
    check_queue_backpressure(llm_queue)
    job_request.stream_channel = get_stream_channel(job_request.job_id)
    retry = (
        Retry(max=LLM_JOB_MAX_RETRIES, interval=0) if LLM_JOB_MAX_RETRIES > 0 else None
    )

    job = llm_queue.enqueue(
        "app.queue.worker.process_llm_call",
        serialize_llm_call(job_request),
        job_id=job_request.job_id,
        result_ttl=LLM_RESULT_TTL_SECONDS,
        job_timeout=LLM_GENERATION_TIMEOUT_SECONDS,
        retry=retry,
    )
    set_job_payload(job, job_request)
    if job_request.call_type == "streaming_text_generation":
        append_stream_event(
            job_request.job_id,
            {
                "job_id": job_request.job_id,
                "status": "queued",
                "queue_position": llm_queue.get_job_position(job_request.job_id),
                "elapsed_seconds": 0.0,
            },
            llm_queue.connection,
        )
    return job


def get_job_status(
    job_id: str,
    connection: Redis | None = None,
) -> LLMCallJob:
    redis_connection = connection or get_redis_connection()
    job = Job.fetch(job_id, connection=redis_connection)
    llm_call = get_job_result(job_id, connection=redis_connection)
    rq_status = job.get_status(refresh=True)

    if rq_status in {JobStatus.QUEUED, JobStatus.DEFERRED, JobStatus.SCHEDULED}:
        llm_call.status = "queued"
        try:
            llm_call.queue_position = get_llm_queue(redis_connection).get_job_position(
                job_id
            )
        except Exception:
            llm_call.queue_position = None
    elif rq_status == JobStatus.STARTED and llm_call.status not in {
        "streaming",
        "cancelled",
    }:
        llm_call.status = "processing"
    elif rq_status == JobStatus.CANCELED:
        llm_call.status = "cancelled"
    elif rq_status == JobStatus.FAILED:
        llm_call.status = "failed"

    llm_call.elapsed_seconds = compute_elapsed_seconds(llm_call)
    return llm_call


def cancel_llm_call(
    job_id: str,
    connection: Redis | None = None,
) -> LLMCallJob:
    redis_connection = connection or get_redis_connection()
    job = Job.fetch(job_id, connection=redis_connection)
    llm_call = get_job_result(job_id, redis_connection)
    rq_status = job.get_status(refresh=True)

    if llm_call.status in {"completed", "failed", "cancelled"}:
        return llm_call

    llm_call.cancel_requested = True

    if rq_status in {
        JobStatus.QUEUED,
        JobStatus.DEFERRED,
        JobStatus.SCHEDULED,
    }:
        get_llm_queue(redis_connection).remove(job_id)
        llm_call.status = "cancelled"
        llm_call.completed_at = utcnow()
        llm_call.error = "LLM job was cancelled before execution."
        set_job_payload(job, llm_call)
        job.set_status(JobStatus.CANCELED)
        append_stream_event(
            job_id,
            {
                "job_id": job_id,
                "status": "cancelled",
                "cancel_requested": True,
                "message": "LLM job was cancelled before execution.",
                "done": True,
            },
            redis_connection,
        )
        return llm_call

    set_job_payload(job, llm_call)
    append_stream_event(
        job_id,
        {
            "job_id": job_id,
            "status": llm_call.status,
            "cancel_requested": True,
            "message": "Cancellation requested. Running non-streaming jobs may finish before stopping.",
        },
        redis_connection,
    )
    return llm_call


def is_cancel_requested(
    job_id: str,
    connection: Redis | None = None,
) -> bool:
    return bool(get_job_result(job_id, connection=connection).cancel_requested)


def ping_redis(connection: Redis | None = None) -> bool:
    redis_connection = connection or get_redis_connection()
    try:
        return bool(redis_connection.ping())
    except Exception:
        return False


def read_stream_batch(
    job_id: str,
    last_id: str,
    connection: Redis | None = None,
    block_ms: int = 1000,
) -> list[dict[str, Any]]:
    redis_connection = connection or get_redis_connection()
    stream_name = get_stream_channel(job_id)
    records = redis_connection.xread({stream_name: last_id}, count=20, block=block_ms)
    events: list[dict[str, Any]] = []
    for _stream_name, stream_records in records:
        for event_id, data in stream_records:
            raw_event = data.get(b"event") if b"event" in data else data.get("event")
            if isinstance(raw_event, bytes):
                raw_event = raw_event.decode()
            event = json.loads(raw_event)
            event["_stream_id"] = (
                event_id.decode() if isinstance(event_id, bytes) else str(event_id)
            )
            events.append(event)
    return events


async def stream_llm_events(
    job_id: str,
    *,
    connection_factory: Callable[[], Redis] | None = None,
    timeout_seconds: int = LLM_STREAM_TIMEOUT_SECONDS,
) -> AsyncIterator[dict[str, Any]]:
    connection_factory = connection_factory or get_redis_connection
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    last_id = "0-0"

    while True:
        events = await asyncio.to_thread(
            read_stream_batch,
            job_id,
            last_id,
            connection_factory(),
        )
        if not events:
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(f"Timed out waiting for LLM stream '{job_id}'.")
            continue

        deadline = asyncio.get_running_loop().time() + timeout_seconds
        for event in events:
            last_id = event.pop("_stream_id")
            yield event
            if event.get("done") is True or event.get("status") in {
                "completed",
                "failed",
                "cancelled",
            }:
                return


async def wait_for_job_result(
    job_id: str,
    *,
    connection_factory: Callable[[], Redis] | None = None,
    timeout_seconds: int = LLM_QUEUE_WAIT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = LLM_STATUS_POLL_INTERVAL_SECONDS,
) -> LLMCallJob:
    connection_factory = connection_factory or get_redis_connection
    deadline = asyncio.get_running_loop().time() + timeout_seconds

    while True:
        status = await asyncio.to_thread(get_job_status, job_id, connection_factory())
        if status.status in {"completed", "failed", "cancelled"}:
            result = await asyncio.to_thread(
                get_job_result,
                job_id,
                connection_factory(),
            )
            return result

        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError(f"Timed out waiting for LLM job '{job_id}'.")

        await asyncio.sleep(poll_interval_seconds)


def get_queue_status(connection: Redis | None = None) -> QueueStatusSnapshot:
    redis_connection = connection or get_redis_connection()
    redis_connected = ping_redis(redis_connection)
    if not redis_connected:
        return QueueStatusSnapshot(
            redis_connected=False,
            queue_depth=0,
            active_job_count=0,
            failed_job_count=0,
            worker_count=0,
        )

    queue = get_llm_queue(redis_connection)
    workers = Worker.all(connection=redis_connection, queue=queue)
    worker_heartbeat_age_seconds: float | None = None
    now = datetime.now(UTC)
    if workers:
        heartbeat_ages: list[float] = []
        for worker in workers:
            last_heartbeat = getattr(worker, "last_heartbeat", None)
            if last_heartbeat is not None:
                heartbeat_ages.append(max(0.0, (now - last_heartbeat).total_seconds()))
        if heartbeat_ages:
            worker_heartbeat_age_seconds = min(heartbeat_ages)

    active_job_count = get_started_job_registry(redis_connection, queue.name).count
    queue_depth = queue.count
    failed_job_count = get_failed_job_registry(redis_connection, queue.name).count

    return QueueStatusSnapshot(
        redis_connected=redis_connected,
        queue_depth=queue_depth,
        active_job_count=active_job_count,
        failed_job_count=failed_job_count,
        worker_count=len(workers),
        worker_heartbeat_age_seconds=worker_heartbeat_age_seconds,
        average_wait_time_seconds=read_average_wait_time_seconds(redis_connection),
        estimated_wait_time_seconds=estimate_wait_time_seconds(
            queue_depth,
            active_job_count,
            redis_connection,
        ),
    )
