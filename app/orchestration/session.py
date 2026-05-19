from rich.console import Console
from typing import Dict

from data_models.session_states import SessionState
from llm.service import LLMService
from memory.short_term import ConversationMemory
from orchestration.modes.base import ModeHandler
from orchestration.modes.definition import DefinitionHandler
from orchestration.modes.learning import LearningHandler
from orchestration.modes.translation import TranslationHandler
from orchestration.output_modes import ModeOutputConfig
from orchestration.router import IntentRouter


class SessionOrchestrator:
    def __init__(
        self, 
        llm_service: LLMService, 
        router: IntentRouter, 
        memory: ConversationMemory
    ):
        self.llm_service = llm_service
        self.router = router
        self.memory = memory
        self.session_state = SessionState()

        self.handlers: Dict[str, ModeHandler] = {
            "translation": TranslationHandler(llm_service),
            "definition": DefinitionHandler(llm_service),
            "learning": LearningHandler(llm_service),
        }

    def handle_turn(self, user_input: str, console: Console) -> dict:
        history = self.memory.format_for_prompt()

        intent = self.router.classify(
            user_input=user_input,
            session_state=self.session_state,
            conversation_history=history,
        )

        self.session_state = self.router.apply_intent(self.session_state, intent)
        console.print(f"\n[bold cyan]Mode:[/bold cyan] {self.session_state.active_mode}")

        if intent.confidence == "low" and intent.clarification_question:
            response = {
                "mode": self.session_state.active_mode,
                "response": intent.clarification_question,
                "intent": intent.model_dump(),
            }
            self.memory.add_turn(user_input, response["response"])
            console.print(f"[bold cyan]Agent:[/bold cyan] {response['response']}\n")
            return response

        handler = self.handlers.get(self.session_state.active_mode)
        
        if handler is None:
            response = {
                "mode": "general",
                "response": "I can help with translation, definitions, or language learning. Which would you like?",
                "intent": intent.model_dump(),
            }
            self.memory.add_turn(user_input, response["response"])
            console.print(f"[bold cyan]Agent:[/bold cyan] {response['response']}\n")
            return response

        self.session_state = handler.update_session_state(
            user_input=user_input,
            session_state=self.session_state,
            conversation_history=history,
        )

        output_mode = ModeOutputConfig[self.session_state.active_mode]

        if output_mode != "stream":
            response = handler.handle(
                user_input=user_input,
                session_state=self.session_state,
                conversation_history=history,
            )

            self.memory.add_turn(user_input, response.response)
            console.print(f"[bold cyan]Answer:[/bold cyan] {response.model_dump_json()}")
            console.print(f"[bold cyan]Assistant:[/bold cyan] {response.response}\n")
        
        else:
            assistant_reply = ""
            console.print("[bold cyan]Assistant:[/bold cyan] ", end="")

            for token in handler.stream(user_input=user_input, session_state=self.session_state, conversation_history=history):
                assistant_reply += token
                console.print(token, end="")

            console.print()
            self.memory.add_turn(user_input, assistant_reply)

            response = {
                "mode": self.session_state.active_mode,
                "response": assistant_reply,
                "intent": intent.model_dump(),
            }

        return response
