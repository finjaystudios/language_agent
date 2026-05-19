from typing import AsyncIterator

from data_models.mode_responses import DefinitionResponse
from data_models.session_states import DefinitionModeState, SessionState
from llm.prompts import (
    STATE_UPDATE_SYSTEM_PROMPT,
    DEFINITION_STATE_UPDATE_TASK_PROMPT,
    DEFINITION_SYSTEM_PROMPT,
    DEFINITION_TASK_PROMPT,
)
from llm.schemas import DEFINITION_RESPONSE_SCHEMA, DEFINITION_STATE_SCHEMA
from orchestration.modes.base import ModeHandler


class DefinitionHandler(ModeHandler):
    async def update_session_state(
        self,
        user_input: str,
        session_state: SessionState,
        conversation_history: str,
    ) -> SessionState:
        prompt = DEFINITION_STATE_UPDATE_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session_state.definition.model_dump(),
        )

        response = await self.llm_service.ask_llm(
            system_prompt=STATE_UPDATE_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=DEFINITION_STATE_SCHEMA,
        )

        session_state.definition = DefinitionModeState(**response)
        return session_state

    async def handle(self, 
        user_input: str, 
        session_state: SessionState, 
        conversation_history: str
    ) -> DefinitionResponse:
        prompt = DEFINITION_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session_state.definition.model_dump(),
        )

        response = await self.llm_service.ask_llm(
            system_prompt=DEFINITION_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=DEFINITION_RESPONSE_SCHEMA,
        )

        return DefinitionResponse(**response)

    async def stream(
        self, 
        user_input: str, 
        session_state: SessionState, 
        conversation_history: str
    ) -> AsyncIterator[str]:
        prompt = DEFINITION_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session_state.definition.model_dump(),
        )

        async for token in self.llm_service.stream_llm(
            system_prompt=DEFINITION_SYSTEM_PROMPT,
            user_prompt=prompt,
        ):
            yield token
