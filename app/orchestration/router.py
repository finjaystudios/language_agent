from llm.prompts import INTENT_SYSTEM_PROMPT, INTENT_TASK_PROMPT
from llm.schemas import INTENT_RESPONSE_SCHEMA
from llm.service import LLMService
from models.prompt_schemas import IntentResult, SessionState


class IntentRouter:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service

    def classify(
        self,
        user_input: str,
        session: SessionState,
        conversation_history: str,
    ) -> IntentResult:
        prompt = INTENT_TASK_PROMPT.format(
            active_mode=session.active_mode,
            conversation_history=conversation_history,
            user_input=user_input,
        )

        raw = self.llm_service.ask_llm(
            system_prompt=INTENT_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=INTENT_RESPONSE_SCHEMA,
        )

        return IntentResult(**raw)

    def apply_intent(self, session: SessionState, intent: IntentResult) -> SessionState:
        if intent.should_switch_mode and intent.mode != session.active_mode:
            session.previous_mode = session.active_mode
            session.active_mode = intent.mode

        return session
