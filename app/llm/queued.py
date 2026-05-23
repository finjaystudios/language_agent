import logging
import uuid
from collections.abc import AsyncIterator

from app.queue.models import LLMCallJob
from app.queue.service import enqueue_llm_call, wait_for_job_result

logger = logging.getLogger(__name__)


class QueuedLLMService:
    async def ask_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
        mode: str | None = None,
    ) -> dict:
        job = LLMCallJob(
            job_id=str(uuid.uuid4()),
            call_type="structured_json",
            prompt=user_prompt,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            mode=mode,
            generation_parameters={"temperature": 0.1, "max_tokens": 2000},
            response_schema=schema,
        )
        logger.info("queued_llm_ask_enqueue job_id=%s mode=%s", job.job_id, mode)
        enqueue_llm_call(job)
        result = await wait_for_job_result(job.job_id)
        if result.status != "completed":
            raise RuntimeError(result.error or "LLM job failed.")
        if not isinstance(result.result, dict):
            raise RuntimeError("Structured LLM job returned a non-dict result.")
        return result.result

    async def stream_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        mode: str | None = None,
    ) -> AsyncIterator[str]:
        job = LLMCallJob(
            job_id=str(uuid.uuid4()),
            call_type="text_generation",
            prompt=user_prompt,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            mode=mode,
            generation_parameters={"temperature": 0.1, "max_tokens": 2000},
        )
        logger.info("queued_llm_stream_enqueue job_id=%s mode=%s", job.job_id, mode)
        enqueue_llm_call(job)
        result = await wait_for_job_result(job.job_id)
        if result.status != "completed":
            raise RuntimeError(result.error or "LLM job failed.")
        if not isinstance(result.result, str):
            raise RuntimeError("Text LLM job returned a non-string result.")
        yield result.result
