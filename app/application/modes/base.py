from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from app.domain.mode_responses import BaseModeResponse
from app.domain.session_states import SessionState

if TYPE_CHECKING:
    from app.ports.llm_gateway import LLMGateway


class ModeHandler(ABC):
    def __init__(self, llm_service: "LLMGateway"):
        self.llm_service = llm_service

    @abstractmethod
    async def update_session_state(
        self,
        user_input: str,
        session_state: SessionState,
        conversation_history: str,
    ) -> SessionState:
        pass

    @abstractmethod
    async def handle(
        self,
        user_input: str,
        session_state: SessionState,
        conversation_history: str,
    ) -> BaseModeResponse:
        pass

    @abstractmethod
    async def stream(
        self,
        user_input: str,
        session_state: SessionState,
        conversation_history: str,
    ) -> AsyncIterator[str]:
        pass
