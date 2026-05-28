import logging
import threading
from typing import Any

from redis import Redis
from rq import SimpleWorker, Worker
from rq.job import get_current_job

from app.core.config import AppSettings
from app.core.logging import configure_logging
from app.domain.jobs import LLMCallJob, utcnow
from app.infrastructure.llm.factory import create_llm_service
from app.infrastructure.redis.config import (
    LLM_JOB_MAX_RETRIES,
    LLM_QUEUE_NAME,
    LLM_WORKER_CONCURRENCY,
)
from app.infrastructure.redis.connection import get_redis_connection
from app.infrastructure.redis.job_store import RedisJobStore
from app.infrastructure.redis.rq_queue import RQQueueClient

logger = logging.getLogger(__name__)
_MODEL_SERVICE: Any | None = None
_MODEL_LOCK = threading.Lock()
_SETTINGS = AppSettings.from_env()


class LLMJobCancelledError(RuntimeError):
    pass


class NonRetryableLLMJobError(RuntimeError):
    pass


def get_worker_class() -> type[SimpleWorker]:
    # Keep queued LLM execution inside one long-lived process so one worker
    # serializes model-server calls and stream publishing across jobs.
    return SimpleWorker


def get_worker_llm_service() -> Any:
    global _MODEL_SERVICE
    if _MODEL_SERVICE is None:
        _MODEL_SERVICE = create_llm_service(_SETTINGS)
        logger.info("llm_worker_model_ready")
    return _MODEL_SERVICE


def get_worker_job_store(connection: Redis | None = None) -> RedisJobStore:
    resolved_connection = connection or get_redis_connection(_SETTINGS.redis_url)
    queue_client = RQQueueClient(_SETTINGS, connection=resolved_connection)
    return RedisJobStore(_SETTINGS, queue_client, connection=resolved_connection)


def serialize_llm_call(llm_call: LLMCallJob) -> dict[str, Any]:
    return get_worker_job_store().serialize_llm_call(llm_call)


def set_job_payload(job, llm_call: LLMCallJob) -> None:
    get_worker_job_store(job.connection if job is not None else None).save_job_payload(
        job,
        llm_call,
    )


def record_wait_time(wait_seconds: float, connection: Redis | None = None) -> None:
    get_worker_job_store(connection).record_wait_time(wait_seconds)


def record_completion_metrics(
    llm_call: LLMCallJob,
    connection: Redis | None = None,
) -> None:
    get_worker_job_store(connection).record_completion_metrics(llm_call)


def append_stream_event(
    job_id: str,
    payload: dict[str, Any],
    connection: Redis | None = None,
) -> str:
    return get_worker_job_store(connection).append_stream_event(job_id, payload)


def is_cancel_requested(job_id: str, connection: Redis | None = None) -> bool:
    return get_worker_job_store(connection).is_cancel_requested(job_id)


def safe_error_message(error: Exception) -> str:
    name = type(error).__name__.lower()
    message = str(error).lower()
    if "unavailable" in name or "unavailable" in message:
        return "The external llama-server is unavailable."
    if "interrupt" in name or "interrupt" in message:
        return "The model server interrupted generation."
    if "timeout" in name:
        return "The language model job timed out."
    return "The language model worker hit an internal execution error."


def build_stream_event(llm_call: LLMCallJob, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "job_id": llm_call.job_id,
        "status": llm_call.status,
        "cancel_requested": llm_call.cancel_requested,
        "elapsed_seconds": llm_call.elapsed_seconds,
    }
    payload.update(extra)
    return payload


def finalize_cancelled_job(
    llm_call: LLMCallJob,
    job,
    connection: Redis,
    message: str,
) -> dict:
    llm_call.status = "cancelled"
    llm_call.completed_at = utcnow()
    llm_call.error = message
    if job is not None:
        set_job_payload(job, llm_call)
    append_stream_event(
        llm_call.job_id,
        build_stream_event(
            llm_call,
            message=message,
            cancelled=True,
            done=True,
        ),
        connection,
    )
    return serialize_llm_call(llm_call)


def close_stream_iterator(stream) -> None:
    close = getattr(stream, "close", None)
    if callable(close):
        close()


def process_llm_call(payload: dict) -> dict:
    job = get_current_job()
    connection = (
        job.connection if job is not None else get_redis_connection(_SETTINGS.redis_url)
    )
    if job is not None and job.meta.get("llm_call") is not None:
        llm_call = LLMCallJob.model_validate(job.meta["llm_call"])
    else:
        llm_call = LLMCallJob.model_validate(payload)
    if job is not None:
        llm_call.retry_count = int(job.meta.get("retry_count", llm_call.retry_count))
        llm_call.last_error = job.meta.get("last_error", llm_call.last_error)

    if is_cancel_requested(llm_call.job_id, connection):
        llm_call.cancel_requested = True
        return finalize_cancelled_job(
            llm_call,
            job,
            connection,
            "LLM job was cancelled before processing started.",
        )

    llm_call.status = "processing"
    llm_call.started_at = utcnow()
    if llm_call.started_at is not None:
        wait_seconds = max(
            0.0,
            (llm_call.started_at - llm_call.created_at).total_seconds(),
        )
        record_wait_time(wait_seconds, connection)
    if job is not None:
        set_job_payload(job, llm_call)
    if llm_call.call_type == "streaming_text_generation":
        append_stream_event(
            llm_call.job_id,
            build_stream_event(llm_call),
            connection,
        )

    try:
        with _MODEL_LOCK:
            service = get_worker_llm_service()
            if llm_call.call_type == "structured_json":
                try:
                    llm_call.result = service.ask_llm_sync(
                        messages=llm_call.messages,
                        schema=llm_call.response_schema or {},
                        mode=llm_call.mode,
                        **llm_call.generation_parameters,
                    )
                except (ValueError, TypeError, KeyError) as error:
                    raise NonRetryableLLMJobError(
                        "The language model returned an invalid structured response."
                    ) from error
            elif llm_call.call_type == "text_generation":
                llm_call.result = service.generate_text_sync(
                    messages=llm_call.messages,
                    mode=llm_call.mode,
                    **llm_call.generation_parameters,
                )
            else:
                llm_call.status = "streaming"
                if job is not None:
                    set_job_payload(job, llm_call)
                append_stream_event(
                    llm_call.job_id,
                    build_stream_event(llm_call),
                    connection,
                )
                parts: list[str] = []
                stream = service.stream_llm_sync(
                    messages=llm_call.messages,
                    mode=llm_call.mode,
                    **llm_call.generation_parameters,
                )
                try:
                    for chunk in stream:
                        delta = chunk["choices"][0].get("delta", {})
                        token = delta.get("content")
                        if token:
                            parts.append(token)
                            append_stream_event(
                                llm_call.job_id,
                                build_stream_event(llm_call, token=token),
                                connection,
                            )
                        if is_cancel_requested(llm_call.job_id, connection):
                            llm_call.cancel_requested = True
                            raise LLMJobCancelledError(
                                "LLM streaming job was cancelled during generation."
                            )
                finally:
                    close_stream_iterator(stream)
                llm_call.result = "".join(parts)

        if is_cancel_requested(llm_call.job_id, connection):
            llm_call.cancel_requested = True
            return finalize_cancelled_job(
                llm_call,
                job,
                connection,
                "LLM job was cancelled before the result was returned.",
            )
        llm_call.status = "completed"
        llm_call.completed_at = utcnow()
        llm_call.last_error = None
        if job is not None:
            set_job_payload(job, llm_call)
        record_completion_metrics(llm_call, connection)
        if llm_call.call_type == "streaming_text_generation":
            append_stream_event(
                llm_call.job_id,
                build_stream_event(llm_call, done=True),
                connection,
            )
        return serialize_llm_call(llm_call)
    except LLMJobCancelledError as error:
        return finalize_cancelled_job(llm_call, job, connection, str(error))
    except NonRetryableLLMJobError as error:
        llm_call.status = "failed"
        llm_call.completed_at = utcnow()
        llm_call.last_error = str(error)
        llm_call.error = str(error)
        if job is not None:
            job.meta["retry_count"] = llm_call.retry_count
            job.meta["last_error"] = llm_call.last_error
            set_job_payload(job, llm_call)
        if llm_call.call_type == "streaming_text_generation":
            append_stream_event(
                llm_call.job_id,
                build_stream_event(
                    llm_call,
                    error="llm_service_error",
                    message=str(error),
                    done=True,
                ),
                connection,
            )
        return serialize_llm_call(llm_call)
    except Exception as error:
        llm_call.retry_count += 1
        llm_call.last_error = safe_error_message(error)
        should_retry = llm_call.retry_count <= LLM_JOB_MAX_RETRIES
        llm_call.completed_at = None if should_retry else utcnow()
        llm_call.status = "queued" if should_retry else "failed"
        llm_call.error = None if should_retry else llm_call.last_error
        if job is not None:
            job.meta["retry_count"] = llm_call.retry_count
            job.meta["last_error"] = llm_call.last_error
            set_job_payload(job, llm_call)
        if llm_call.call_type == "streaming_text_generation":
            append_stream_event(
                llm_call.job_id,
                build_stream_event(
                    llm_call,
                    message=(
                        "Retrying after a transient worker failure."
                        if should_retry
                        else llm_call.last_error
                    ),
                    error=None if should_retry else "llm_service_error",
                    done=False if should_retry else True,
                ),
                connection,
            )
        if should_retry:
            raise
        raise


def create_worker(connection: Redis | None = None) -> Worker:
    if LLM_WORKER_CONCURRENCY != 1:
        raise RuntimeError(
            "LLM_WORKER_CONCURRENCY must remain 1 for the queue-backed LLM worker."
        )
    redis_connection = connection or get_redis_connection(_SETTINGS.redis_url)
    worker_class = get_worker_class()
    return worker_class([LLM_QUEUE_NAME], connection=redis_connection)


def main() -> None:
    configure_logging()
    worker = create_worker()
    logger.info(
        "llm_worker_start queue=%s worker_class=%s",
        LLM_QUEUE_NAME,
        type(worker).__name__,
    )
    worker.work()


if __name__ == "__main__":
    main()
