from typing import AsyncIterator

from data_models.mode_responses import TranslationResponse
from data_models.session_states import SessionState, TranslationModeState
from llm.prompts import (
    STATE_UPDATE_SYSTEM_PROMPT,
    TRANSLATION_STATE_UPDATE_TASK_PROMPT,
    TRANSLATION_SYSTEM_PROMPT,
    TRANSLATION_TASK_PROMPT,
)
from llm.schemas import TRANSLATION_RESPONSE_SCHEMA, TRANSLATION_STATE_SCHEMA
from orchestration.modes.base import ModeHandler


class TranslationHandler(ModeHandler):
    async def update_session_state(
        self,
        user_input: str,
        session_state: SessionState,
        conversation_history: str,
    ) -> SessionState:
        prompt = TRANSLATION_STATE_UPDATE_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session_state.translation.model_dump(),
        )

        response = await self.llm_service.ask_llm(
            system_prompt=STATE_UPDATE_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=TRANSLATION_STATE_SCHEMA,
        )

        session_state.translation = TranslationModeState(**response)
        return session_state

    async def handle(
        self, 
        user_input: str, 
        session_state: SessionState, 
        conversation_history: str
    ) -> TranslationResponse:
        prompt = TRANSLATION_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session_state.translation.model_dump(),
        )

        response = await self.llm_service.ask_llm(
            system_prompt=TRANSLATION_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=TRANSLATION_RESPONSE_SCHEMA,
        )

        return TranslationResponse(**response)

    async def stream(
        self, 
        user_input: str, 
        session_state: SessionState, 
        conversation_history: str
    ) -> AsyncIterator[str]:
        prompt = TRANSLATION_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session_state.translation.model_dump(),
        )

        async for token in self.llm_service.stream_llm(
            system_prompt=TRANSLATION_SYSTEM_PROMPT,
            user_prompt=prompt,
        ):
            yield token
