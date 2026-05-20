import logging
from functools import lru_cache

from app.api.errors import LLMServiceError
from app.services.agent_service import AgentService

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_agent_service() -> AgentService:
    logger.info("agent_service_dependency_resolve_start")
    try:
        service = AgentService.from_local_model()
        logger.info("agent_service_dependency_resolve_complete")
        return service
    except Exception as error:
        logger.exception("agent_service_dependency_resolve_failed")
        raise LLMServiceError(str(error)) from error
