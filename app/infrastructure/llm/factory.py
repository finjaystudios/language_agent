from __future__ import annotations

from typing import Any

from app.core.config import AppSettings
from app.infrastructure.llm.llama_server_gateway import LlamaServerGateway
from app.infrastructure.llm.local_model import create_local_llm_service


def create_llm_service(settings: AppSettings | None = None) -> Any:
    resolved_settings = settings or AppSettings.from_env()
    if resolved_settings.llm_backend == "llama_server":
        return LlamaServerGateway(resolved_settings)
    if resolved_settings.llm_backend == "llama_cpp_python":
        return create_local_llm_service()
    raise RuntimeError(
        "Unsupported LLM_BACKEND. Expected 'llama_cpp_python' or 'llama_server'."
    )
