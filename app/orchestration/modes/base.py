from abc import ABC, abstractmethod

from llm.service import LLMService
from models.prompt_schemas import SessionState


class ModeHandler(ABC):
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    @abstractmethod
    def handle(
        self,
        user_input: str,
        session: SessionState,
        conversation_history: str,
    ) -> dict:
        pass
