from llm.schemas import LITE_LANGUAGE_RESPONSE_SCHEMA
from orchestration.modes.base import ModeHandler
from orchestration.session import SessionState


TASK_PROMPT = """
You are in Definition Mode.

Conversation history:
{conversation_history}

Definition mode state:
{mode_state}

User input:
{user_input}

Provide a dictionary-style answer.
Include meaning, part of speech, examples, synonyms, antonyms, and etymology if available.
Ask for clarification if the word has multiple likely meanings.
"""


class DefinitionHandler(ModeHandler):
    def handle(self, 
        user_input: str, 
        session: SessionState, 
        conversation_history: str
    ):
        prompt = TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session.definition.model_dump(),
        )

        response = self.llm_service.ask_llm(
            system_prompt="You are a multilingual dictionary assistant.",
            user_prompt=prompt,
            schema=LITE_LANGUAGE_RESPONSE_SCHEMA,
        )

        return {
            "mode": "definition",
            "response": response["response"],
        }
