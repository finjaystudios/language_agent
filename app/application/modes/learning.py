from collections.abc import AsyncIterator

from app.application.modes.base import ModeHandler
from app.domain.mode_responses import LearningResponse
from app.domain.session_states import LearningModeState, SessionState
from app.infrastructure.llm.prompts import (
    LEARNING_STATE_UPDATE_TASK_PROMPT,
    LEARNING_SYSTEM_PROMPT,
    LEARNING_TASK_PROMPT,
    STATE_UPDATE_SYSTEM_PROMPT,
)
from app.infrastructure.llm.schemas import (
    LEARNING_RESPONSE_SCHEMA,
    LEARNING_STATE_SCHEMA,
)


class LearningHandler(ModeHandler):
    async def update_session_state(
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

        response = await self.llm_service.ask_llm(
            system_prompt=STATE_UPDATE_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=LEARNING_STATE_SCHEMA,
            mode="session_state",
        )

        session_state.learning = LearningModeState(**response)
        return session_state

    async def handle(
        self, user_input: str, session_state: SessionState, conversation_history: str
    ) -> LearningResponse:
        prompt = LEARNING_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session_state.learning.model_dump(),
        )

        response = await self.llm_service.ask_llm(
            system_prompt=LEARNING_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=LEARNING_RESPONSE_SCHEMA,
            mode="learning",
        )

        return LearningResponse(**response)

    async def stream(
        self, user_input: str, session_state: SessionState, conversation_history: str
    ) -> AsyncIterator[str]:
        prompt = LEARNING_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session_state.learning.model_dump(),
        )

        async for token in self.llm_service.stream_llm(
            system_prompt=LEARNING_SYSTEM_PROMPT,
            user_prompt=prompt,
            mode="learning",
        ):
            yield token
