from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Iterator

from data_models.mode_responses import BaseModeResponse
from data_models.session_states import SessionState

if TYPE_CHECKING:
    from llm.service import LLMService


class ModeHandler(ABC):
    def __init__(self, llm_service: "LLMService"):
        self.llm_service = llm_service

    @abstractmethod
    def update_session_state(
        self,
        user_input: str,
        session_state: SessionState,
        conversation_history: str,
    ) -> SessionState:
        pass

    @abstractmethod
    def handle(
        self,
        user_input: str,
        session_state: SessionState,
        conversation_history: str,
    ) -> BaseModeResponse:
        pass

    @abstractmethod
    def stream(
        self,
        user_input: str,
        session_state: SessionState,
        conversation_history: str,
    ) -> Iterator[str]:
        pass
