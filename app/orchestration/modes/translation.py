from llm.schemas import LITE_LANGUAGE_RESPONSE_SCHEMA
from orchestration.modes.base import ModeHandler
from orchestration.session import SessionState


TASK_PROMPT = """
You are in Translation Mode.

Conversation history:
{conversation_history}

Translation mode state:
{mode_state}

User input:
{user_input}

Translate appropriately based on the active mode state.
Return a concise response.
"""


class TranslationHandler(ModeHandler):
    def handle(
        self, 
        user_input: str, 
        session: SessionState, 
        conversation_history: str
    ):
        prompt = TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session.translation.model_dump(),
        )

        response = self.llm_service.ask_llm(
            system_prompt="You are a multilingual translation assistant.",
            user_prompt=prompt,
            schema=LITE_LANGUAGE_RESPONSE_SCHEMA,
        )

        return {
            "mode": "translation",
            "response": response["response"],
        }
