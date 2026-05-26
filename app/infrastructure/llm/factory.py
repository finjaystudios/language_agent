from __future__ import annotations

from typing import Any

from app.core.config import AppSettings
from app.infrastructure.llm.llama_server_gateway import LlamaServerGateway


def create_llm_service(settings: AppSettings | None = None) -> Any:
    resolved_settings = settings or AppSettings.from_env()
    if resolved_settings.llm_backend == "llama_server":
        return LlamaServerGateway(resolved_settings)
    raise RuntimeError("Unsupported LLM_BACKEND. Only 'llama_server' is supported.")
