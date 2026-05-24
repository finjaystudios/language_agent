import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.core.config import AppSettings
from app.core.errors import LLMServiceError
from app.domain.jobs import LLMCallJob
from app.infrastructure.llm.queued_gateway import QueuedLLMGateway
from app.infrastructure.redis.errors import (
    GenerationTimeoutError,
    QueueWaitTimeoutError,
    StreamingTimeoutError,
)
from app.infrastructure.redis.queue_service import (
    cancel_llm_call,
    create_queue_service,
    enqueue_llm_call,
    stream_llm_events,
    wait_for_job_result,
)


class QueuedLLMService(QueuedLLMGateway):
    def __init__(self, queue_service=None):
        super().__init__(queue_service or create_queue_service(AppSettings.from_env()))
        self._uses_compat_wrappers = queue_service is None

    async def ask_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
        mode: str | None = None,
    ) -> dict:
        if not self._uses_compat_wrappers:
            return await super().ask_llm(system_prompt, user_prompt, schema, mode=mode)

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
        if not self._uses_compat_wrappers:
            async for event in super().stream_llm(
                system_prompt, user_prompt, mode=mode
            ):
                yield event
            return

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
        await enqueue_llm_call(job)
        try:
            async for event in stream_llm_events(job.job_id):
                yield event
        except TimeoutError as error:
            raise StreamingTimeoutError() from error

    async def cancel_job(self, job_id: str) -> LLMCallJob:
        if not self._uses_compat_wrappers:
            return await super().cancel_job(job_id)
        return await cancel_llm_call(job_id)


__all__ = [
    "QueuedLLMService",
    "cancel_llm_call",
    "enqueue_llm_call",
    "stream_llm_events",
    "wait_for_job_result",
]
