from typing import Iterator

from llm.prompts import TRANSLATION_SYSTEM_PROMPT, TRANSLATION_TASK_PROMPT
from llm.schemas import LITE_LANGUAGE_RESPONSE_SCHEMA
from orchestration.modes.base import ModeHandler
from orchestration.session import SessionState


class TranslationHandler(ModeHandler):
    def handle(
        self, 
        user_input: str, 
        session: SessionState, 
        conversation_history: str
    ):
        prompt = TRANSLATION_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session.translation.model_dump(),
        )

        response = self.llm_service.ask_llm(
            system_prompt=TRANSLATION_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=LITE_LANGUAGE_RESPONSE_SCHEMA,
        )

        return {
            "mode": "translation",
            "response": response["response"],
        }

    def stream(
        self, 
        user_input: str, 
        session: SessionState, 
        conversation_history: str
    ) -> Iterator[str]:
        prompt = TRANSLATION_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session.translation.model_dump(),
        )

        return self.llm_service.stream_llm(
            system_prompt=TRANSLATION_SYSTEM_PROMPT,
            user_prompt=prompt,
        )
