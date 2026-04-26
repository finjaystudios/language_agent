from llm.prompts import INTENT_CLASSIFICATION_PROMPT
from llm.schemas import INTENT_SCHEMA
from models.prompt_schemas import IntentResult, SessionState


SYSTEM_PROMPT = "You are an intent classifier. Return only valid JSON."


class IntentRouter:
    def __init__(self, llm_service):
        self.llm_service = llm_service

    def classify(
        self,
        user_input: str,
        session: SessionState,
        conversation_history: str,
    ) -> IntentResult:
        prompt = INTENT_CLASSIFICATION_PROMPT.format(
            active_mode=session.active_mode,
            conversation_history=conversation_history,
            user_input=user_input,
        )

        raw = self.llm_service.complete_json(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=INTENT_SCHEMA,
        )

        return IntentResult(**raw)

    def apply_intent(self, session: SessionState, intent: IntentResult) -> SessionState:
        if intent.should_switch_mode and intent.mode != session.active_mode:
            session.previous_mode = session.active_mode
            session.active_mode = intent.mode

        return session
