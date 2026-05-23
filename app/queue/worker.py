import logging
import os
import threading
from typing import Any

from redis import Redis
from rq import SimpleWorker, Worker
from rq.job import get_current_job

from app.llm.service import LLMService, create_local_llm_service
from app.queue.config import LLM_QUEUE_NAME, LLM_WORKER_CONCURRENCY
from app.queue.models import LLMCallJob, utcnow
from app.queue.service import (
    append_stream_event,
    get_redis_connection,
    is_cancel_requested,
    serialize_llm_call,
    set_job_payload,
)

logger = logging.getLogger(__name__)
_MODEL_SERVICE: LLMService | None = None
_MODEL_LOCK = threading.Lock()


class LLMJobCancelledError(RuntimeError):
    pass


def get_worker_class() -> type[Worker]:
    if os.name == "nt":
        return SimpleWorker
    return Worker


def get_worker_llm_service() -> LLMService:
    global _MODEL_SERVICE
    if _MODEL_SERVICE is None:
        _MODEL_SERVICE = create_local_llm_service()
        logger.info("llm_worker_model_ready")
    return _MODEL_SERVICE


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


def process_llm_call(payload: dict) -> dict:
    llm_call = LLMCallJob.model_validate(payload)
    job = get_current_job()
    connection = job.connection if job is not None else get_redis_connection()

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
                llm_call.result = service.ask_llm_sync(
                    messages=llm_call.messages,
                    schema=llm_call.response_schema or {},
                    **llm_call.generation_parameters,
                )
            elif llm_call.call_type == "text_generation":
                llm_call.result = service.generate_text_sync(
                    messages=llm_call.messages,
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
                for chunk in service.stream_llm_sync(
                    messages=llm_call.messages,
                    **llm_call.generation_parameters,
                ):
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
        if job is not None:
            set_job_payload(job, llm_call)
        if llm_call.call_type == "streaming_text_generation":
            append_stream_event(
                llm_call.job_id,
                build_stream_event(llm_call, done=True),
                connection,
            )
        return serialize_llm_call(llm_call)
    except LLMJobCancelledError as error:
        return finalize_cancelled_job(llm_call, job, connection, str(error))
    except Exception as error:
        llm_call.status = "failed"
        llm_call.completed_at = utcnow()
        llm_call.error = str(error)
        if job is not None:
            set_job_payload(job, llm_call)
        if llm_call.call_type == "streaming_text_generation":
            append_stream_event(
                llm_call.job_id,
                build_stream_event(
                    llm_call,
                    error="llm_service_error",
                    message="The language model failed while streaming a response.",
                    done=True,
                ),
                connection,
            )
        raise


def create_worker(connection: Redis | None = None) -> Worker:
    if LLM_WORKER_CONCURRENCY != 1:
        raise RuntimeError(
            "LLM_WORKER_CONCURRENCY must remain 1 for the local GPU worker."
        )
    redis_connection = connection or get_redis_connection()
    worker_class = get_worker_class()
    return worker_class([LLM_QUEUE_NAME], connection=redis_connection)


def main() -> None:
    worker = create_worker()
    logger.info(
        "llm_worker_start queue=%s worker_class=%s",
        LLM_QUEUE_NAME,
        type(worker).__name__,
    )
    worker.work()


if __name__ == "__main__":
    main()
