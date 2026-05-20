from functools import lru_cache

from app.services.agent_service import AgentService


@lru_cache(maxsize=1)
def get_agent_service() -> AgentService:
    return AgentService.from_local_model()
