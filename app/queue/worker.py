import logging
import os
import threading

from redis import Redis
from rq import SimpleWorker, Worker
from rq.job import get_current_job

from app.llm.service import LLMService, create_local_llm_service
from app.queue.config import LLM_QUEUE_NAME, LLM_WORKER_CONCURRENCY
from app.queue.models import LLMCallJob, utcnow
from app.queue.service import get_redis_connection

logger = logging.getLogger(__name__)
_MODEL_SERVICE: LLMService | None = None
_MODEL_LOCK = threading.Lock()


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


def process_llm_call(payload: dict) -> dict:
    llm_call = LLMCallJob.model_validate(payload)
    job = get_current_job()

    llm_call.status = "started"
    llm_call.started_at = utcnow()
    if job is not None:
        job.meta["llm_call"] = llm_call.model_dump(mode="json")
        job.save_meta()

    try:
        with _MODEL_LOCK:
            service = get_worker_llm_service()
            if llm_call.call_type == "structured_json":
                llm_call.result = service.ask_llm_sync(
                    messages=llm_call.messages,
                    schema=llm_call.response_schema or {},
                    **llm_call.generation_parameters,
                )
            else:
                llm_call.result = service.generate_text_sync(
                    messages=llm_call.messages,
                    **llm_call.generation_parameters,
                )
        llm_call.status = "completed"
        llm_call.completed_at = utcnow()
    except Exception as error:
        llm_call.status = "failed"
        llm_call.completed_at = utcnow()
        llm_call.error = str(error)
        if job is not None:
            job.meta["llm_call"] = llm_call.model_dump(mode="json")
            job.save_meta()
        raise

    if job is not None:
        job.meta["llm_call"] = llm_call.model_dump(mode="json")
        job.save_meta()
    return llm_call.model_dump(mode="json")


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
