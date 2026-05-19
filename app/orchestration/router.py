from typing import TYPE_CHECKING

from data_models.intent_result import IntentResult
from data_models.session_states import SessionState
from llm.prompts import INTENT_SYSTEM_PROMPT, INTENT_TASK_PROMPT
from llm.schemas import INTENT_RESPONSE_SCHEMA

if TYPE_CHECKING:
    from llm.service import LLMService


class IntentRouter:
    def __init__(self, llm_service: "LLMService"):
        self.llm_service = llm_service

    async def classify(
        self,
        user_input: str,
        session_state: SessionState,
        conversation_history: str,
    ) -> IntentResult:
        prompt = INTENT_TASK_PROMPT.format(
            active_mode=session_state.active_mode,
            conversation_history=conversation_history,
            user_input=user_input,
        )

        response = await self.llm_service.ask_llm(
            system_prompt=INTENT_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=INTENT_RESPONSE_SCHEMA,
        )

        return IntentResult(**response)

    def apply_intent(self, session_state: SessionState, intent: IntentResult) -> SessionState:
        if intent.should_switch_mode and intent.mode != session_state.active_mode:
            session_state.previous_mode = session_state.active_mode
            session_state.active_mode = intent.mode

        return session_state
