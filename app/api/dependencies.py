from functools import lru_cache

from app.api.errors import LLMServiceError
from app.services.agent_service import AgentService


@lru_cache(maxsize=1)
def get_agent_service() -> AgentService:
    try:
        return AgentService.from_local_model()
    except Exception as error:
        raise LLMServiceError(
            "Failed to initialise the local language model."
        ) from error
