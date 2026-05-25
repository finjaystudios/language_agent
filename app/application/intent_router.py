import logging
from typing import TYPE_CHECKING

from app.domain.intent_result import IntentResult
from app.domain.session_states import SessionState
from app.infrastructure.llm.prompts import INTENT_SYSTEM_PROMPT, INTENT_TASK_PROMPT
from app.infrastructure.llm.schemas import INTENT_RESPONSE_SCHEMA

if TYPE_CHECKING:
    from app.ports.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)


class IntentRouter:
    def __init__(self, llm_service: "LLMGateway"):
        self.llm_service = llm_service

    async def classify(
        self,
        user_input: str,
        session_state: SessionState,
        conversation_history: str,
    ) -> IntentResult:
        logger.info(
            "intent_router_classify_start active_mode=%s history_length=%d message_length=%d",
            session_state.active_mode,
            len(conversation_history),
            len(user_input),
        )
        prompt = INTENT_TASK_PROMPT.format(
            active_mode=session_state.active_mode,
            conversation_history=conversation_history,
            user_input=user_input,
        )

        response = await self.llm_service.ask_llm(
            system_prompt=INTENT_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=INTENT_RESPONSE_SCHEMA,
            mode="intent",
        )

        intent = IntentResult(**response)
        logger.info(
            "intent_router_classify_complete mode=%s confidence=%s should_switch=%s",
            intent.mode,
            intent.confidence,
            intent.should_switch_mode,
        )
        return intent

    def apply_intent(
        self, session_state: SessionState, intent: IntentResult
    ) -> SessionState:
        if intent.should_switch_mode and intent.mode != session_state.active_mode:
            logger.info(
                "intent_router_switch_mode from_mode=%s to_mode=%s",
                session_state.active_mode,
                intent.mode,
            )
            session_state.previous_mode = session_state.active_mode
            session_state.active_mode = intent.mode
        else:
            logger.info("intent_router_keep_mode mode=%s", session_state.active_mode)

        return session_state
