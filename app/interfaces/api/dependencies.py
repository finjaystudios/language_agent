import logging
from functools import lru_cache

from app.application.agent_service import AgentService
from app.application.conversation_memory import ConversationMemory
from app.application.intent_router import IntentRouter
from app.core.config import AppSettings
from app.core.errors import LLMServiceError
from app.infrastructure.database.repositories import SQLAlchemyUserRepository
from app.infrastructure.database.session import get_session_factory
from app.infrastructure.redis.job_store import RedisJobStore
from app.infrastructure.redis.queue_service import create_queue_service
from app.infrastructure.redis.queued_gateway import QueuedLLMService
from app.infrastructure.redis.rq_queue import RQQueueClient
from app.ports.job_store import JobStore
from app.ports.llm_gateway import LLMGateway
from app.ports.queue_client import QueueClient
from app.ports.user_repository import UserRepository

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings.from_env()


@lru_cache(maxsize=1)
def get_queue_client() -> QueueClient:
    return RQQueueClient(get_settings())


@lru_cache(maxsize=1)
def get_job_store() -> JobStore:
    return RedisJobStore(get_settings(), get_queue_client())


@lru_cache(maxsize=1)
def get_llm_gateway() -> LLMGateway:
    queue_service = create_queue_service(
        settings=get_settings(),
        queue_client=get_queue_client(),
        job_store=get_job_store(),
    )
    return QueuedLLMService(queue_service)


def create_queue_agent_service() -> AgentService:
    return AgentService(
        llm_service=get_llm_gateway(),
        router=IntentRouter(get_llm_gateway()),
        memory=ConversationMemory(max_turns=5),
    )


@lru_cache(maxsize=1)
def get_agent_service() -> AgentService:
    logger.info("agent_service_dependency_resolve_start")
    try:
        service = create_queue_agent_service()
        logger.info("agent_service_dependency_resolve_complete")
        return service
    except Exception as error:
        logger.exception("agent_service_dependency_resolve_failed")
        raise LLMServiceError(str(error)) from error


@lru_cache(maxsize=1)
def get_user_repository() -> UserRepository:
    return SQLAlchemyUserRepository(get_session_factory())
