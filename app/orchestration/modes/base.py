from abc import ABC, abstractmethod
from typing import Iterator

from llm.service import LLMService
from models.prompt_schemas import BaseModeResponse, SessionState


class ModeHandler(ABC):
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    @abstractmethod
    def handle(
        self,
        user_input: str,
        session: SessionState,
        conversation_history: str,
    ) -> BaseModeResponse:
        pass

    @abstractmethod
    def stream(
        self,
        user_input: str,
        session: SessionState,
        conversation_history: str,
    ) -> Iterator[str]:
        pass
