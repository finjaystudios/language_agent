from llm.schemas import LITE_LANGUAGE_RESPONSE_SCHEMA
from orchestration.modes.base import ModeHandler
from orchestration.session import SessionState


TASK_PROMPT = """
You are in Learning Mode.

Conversation history:
{conversation_history}

Learning mode state:
{mode_state}

User input:
{user_input}

Act as a patient language tutor.
Continue the user's learning journey.
Give explanations, examples, corrections, and a small next exercise when useful.
"""


class LearningHandler(ModeHandler):
    def handle(self, 
        user_input: str, 
        session: SessionState, 
        conversation_history: str
    ):        
        prompt = TASK_PROMPT.format(
            user_input=user_input,
            conversation_history=conversation_history,
            mode_state=session.learning.model_dump(),
        )

        response = self.llm_service.ask_llm(
            system_prompt="You are a private language tutor.",
            user_prompt=prompt,
            schema=LITE_LANGUAGE_RESPONSE_SCHEMA,
        )

        return {
            "mode": "learning",
            "response": response["response"],
        }
