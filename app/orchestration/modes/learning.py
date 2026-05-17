from typing import Iterator

from llm.prompts import LEARNING_SYSTEM_PROMPT, LEARNING_TASK_PROMPT
from llm.schemas import LEARNING_RESPONSE_SCHEMA
from models.prompt_schemas import LearningResponse
from orchestration.modes.base import ModeHandler
from orchestration.session import SessionState


class LearningHandler(ModeHandler):
    def handle(self, 
        user_input: str, 
        session: SessionState, 
        conversation_history: str
    ) -> LearningResponse:        
        prompt = LEARNING_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session.learning.model_dump(),
        )

        response = self.llm_service.ask_llm(
            system_prompt=LEARNING_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=LEARNING_RESPONSE_SCHEMA,
        )

        return LearningResponse(**response)

    def stream(
        self, 
        user_input: str, 
        session: SessionState, 
        conversation_history: str
    ) -> Iterator[str]:
        prompt = LEARNING_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session.learning.model_dump(),
        )

        return self.llm_service.stream_llm(
            system_prompt=LEARNING_SYSTEM_PROMPT,
            user_prompt=prompt,
        )
