import asyncio
from collections.abc import Callable

from redis import Redis
from rq import Queue
from rq.job import Job

from app.queue.config import (
    LLM_MAX_QUEUE_SIZE,
    LLM_QUEUE_NAME,
    LLM_QUEUE_POLL_INTERVAL_SECONDS,
    LLM_QUEUE_TIMEOUT_SECONDS,
    LLM_RESULT_TTL_SECONDS,
    REDIS_URL,
)
from app.queue.models import LLMCallJob


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


def enqueue_llm_call(job_request: LLMCallJob, queue: Queue | None = None) -> Job:
    llm_queue = queue or get_llm_queue()
    if llm_queue.count >= LLM_MAX_QUEUE_SIZE:
        raise RuntimeError("LLM queue is full.")

    job = llm_queue.enqueue(
        "app.queue.worker.process_llm_call",
        job_request.model_dump(mode="json"),
        job_id=job_request.job_id,
        result_ttl=LLM_RESULT_TTL_SECONDS,
        job_timeout=LLM_QUEUE_TIMEOUT_SECONDS,
    )
    job.meta["llm_call"] = job_request.model_dump(mode="json")
    job.save_meta()
    return job


def get_job_status(
    job_id: str,
    connection: Redis | None = None,
) -> str:
    job = Job.fetch(job_id, connection=connection or get_redis_connection())
    return job.get_status(refresh=True)


def get_job_result(
    job_id: str,
    connection: Redis | None = None,
) -> LLMCallJob:
    job = Job.fetch(job_id, connection=connection or get_redis_connection())
    payload = job.result or job.meta.get("llm_call")
    if payload is None:
        raise RuntimeError(f"LLM job '{job_id}' has no result payload.")
    return LLMCallJob.model_validate(payload)


async def wait_for_job_result(
    job_id: str,
    *,
    connection_factory: Callable[[], Redis] | None = None,
    timeout_seconds: int = LLM_QUEUE_TIMEOUT_SECONDS,
    poll_interval_seconds: float = LLM_QUEUE_POLL_INTERVAL_SECONDS,
) -> LLMCallJob:
    connection_factory = connection_factory or get_redis_connection
    deadline = asyncio.get_running_loop().time() + timeout_seconds

    while True:
        status = await asyncio.to_thread(get_job_status, job_id, connection_factory())
        if status in {"finished", "failed", "stopped", "canceled"}:
            result = await asyncio.to_thread(
                get_job_result,
                job_id,
                connection_factory(),
            )
            if status != "finished" and result.status != "failed":
                result.status = "failed"
                result.error = result.error or f"LLM job ended with status '{status}'."
            return result

        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError(f"Timed out waiting for LLM job '{job_id}'.")

        await asyncio.sleep(poll_interval_seconds)
