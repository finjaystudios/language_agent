from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class LLMGateway(Protocol):
    async def ask_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
        mode: str | None = None,
    ) -> dict: ...

    async def stream_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        mode: str | None = None,
    ) -> AsyncIterator[dict[str, Any] | str]: ...

    async def cancel_job(self, job_id: str) -> Any: ...
