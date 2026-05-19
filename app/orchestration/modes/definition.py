from typing import Iterator

from llm.prompts import DEFINITION_SYSTEM_PROMPT, DEFINITION_TASK_PROMPT
from llm.schemas import DEFINITION_RESPONSE_SCHEMA
from data_models.prompt_schemas import DefinitionResponse
from orchestration.modes.base import ModeHandler
from orchestration.session import SessionState


class DefinitionHandler(ModeHandler):
    def handle(self, 
        user_input: str, 
        session: SessionState, 
        conversation_history: str
    ) -> DefinitionResponse:
        prompt = DEFINITION_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session.definition.model_dump(),
        )

        response = self.llm_service.ask_llm(
            system_prompt=DEFINITION_SYSTEM_PROMPT,
            user_prompt=prompt,
            schema=DEFINITION_RESPONSE_SCHEMA,
        )

        return DefinitionResponse(**response)

    def stream(
        self, 
        user_input: str, 
        session: SessionState, 
        conversation_history: str
    ) -> Iterator[str]:
        prompt = DEFINITION_TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session.definition.model_dump(),
        )

        return self.llm_service.stream_llm(
            system_prompt=DEFINITION_SYSTEM_PROMPT,
            user_prompt=prompt,
        )
