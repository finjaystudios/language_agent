import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.core.errors import LLMServiceError
from app.domain.jobs import LLMCallJob
from app.infrastructure.redis.errors import (
    GenerationTimeoutError,
    QueueWaitTimeoutError,
    StreamingTimeoutError,
)
from app.infrastructure.redis.queue_service import (
    cancel_llm_call,
    enqueue_llm_call,
    stream_llm_events,
    wait_for_job_result,
)

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
        await enqueue_llm_call(job)
        try:
            result = await wait_for_job_result(job.job_id)
        except TimeoutError as error:
            raise QueueWaitTimeoutError() from error
        if result.status != "completed":
            if result.status == "cancelled":
                raise LLMServiceError("The language model request was cancelled.")
            if result.last_error and "timeout" in result.last_error.lower():
                raise GenerationTimeoutError() from None
            raise LLMServiceError(
                "The language model failed while generating a response."
            )
        if not isinstance(result.result, dict):
            raise LLMServiceError("The language model returned an invalid response.")
        return result.result

    async def stream_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        mode: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        job = LLMCallJob(
            job_id=str(uuid.uuid4()),
            call_type="streaming_text_generation",
            prompt=user_prompt,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            mode=mode,
            generation_parameters={"temperature": 0.1, "max_tokens": 2000},
        )
        logger.info("queued_llm_stream_enqueue job_id=%s mode=%s", job.job_id, mode)
        await enqueue_llm_call(job)
        try:
            async for event in stream_llm_events(job.job_id):
                yield event
        except TimeoutError as error:
            raise StreamingTimeoutError() from error

    async def cancel_job(self, job_id: str) -> LLMCallJob:
        return await cancel_llm_call(job_id)
