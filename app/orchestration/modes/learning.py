from typing import Iterator

from data_models.mode_responses import LearningResponse
from data_models.session_states import LearningModeState, SessionState
from llm.prompts import (
    STATE_UPDATE_SYSTEM_PROMPT,
    LEARNING_STATE_UPDATE_TASK_PROMPT,
    LEARNING_SYSTEM_PROMPT,
    LEARNING_TASK_PROMPT,
)
from llm.schemas import LEARNING_RESPONSE_SCHEMA, LEARNING_STATE_SCHEMA
from orchestration.modes.base import ModeHandler


class LearningHandler(ModeHandler):
    def update_session_state(
        self,
        user_input: str,
        session_state: SessionState,
        conversation_history: str,
    ) -> SessionState:
        prompt = LEARNING_STATE_UPDATE_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session_state.learning.model_dump(),
        )

        response = self.llm_service.ask_llm(
            system_prompt=STATE_UPDATE_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=LEARNING_STATE_SCHEMA,
        )

        session_state.learning = LearningModeState(**response)
        return session_state

    def handle(self, 
        user_input: str, 
        session_state: SessionState, 
        conversation_history: str
    ) -> LearningResponse:        
        prompt = LEARNING_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session_state.learning.model_dump(),
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
        session_state: SessionState, 
        conversation_history: str
    ) -> Iterator[str]:
        prompt = LEARNING_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session_state.learning.model_dump(),
        )

        return self.llm_service.stream_llm(
            system_prompt=LEARNING_SYSTEM_PROMPT,
            user_prompt=prompt,
        )
