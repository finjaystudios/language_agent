import logging
from typing import TYPE_CHECKING

from app.application.conversation_memory import ConversationMemory
from app.application.intent_router import IntentRouter
from app.application.modes.base import ModeHandler
from app.application.modes.definition import DefinitionHandler
from app.application.modes.learning import LearningHandler
from app.application.modes.translation import TranslationHandler
from app.application.output_modes import ModeOutputConfig
from app.domain.session_states import SessionState

if TYPE_CHECKING:
    from rich.console import Console

    from app.ports.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)


class SessionOrchestrator:
    def __init__(
        self,
        llm_service: "LLMGateway",
        router: IntentRouter,
        memory: ConversationMemory,
    ):
        self.llm_service = llm_service
        self.router = router
        self.memory = memory
        self.session_state = SessionState()

        self.handlers: dict[str, ModeHandler] = {
            "translation": TranslationHandler(llm_service),
            "definition": DefinitionHandler(llm_service),
            "learning": LearningHandler(llm_service),
        }
        logger.info("session_orchestrator_initialized handlers=%s", list(self.handlers))

    async def handle_turn(self, user_input: str, console: "Console") -> dict:
        logger.info(
            "session_turn_start active_mode=%s message_length=%d",
            self.session_state.active_mode,
            len(user_input),
        )
        history = self.memory.format_for_prompt()
        logger.debug("session_history_prepared length=%d", len(history))

        intent = await self.router.classify(
            user_input=user_input,
            session_state=self.session_state,
            conversation_history=history,
        )

        self.session_state = self.router.apply_intent(self.session_state, intent)
        logger.info(
            "session_intent_applied active_mode=%s confidence=%s",
            self.session_state.active_mode,
            intent.confidence,
        )
        console.print(
            f"\n[bold cyan]Mode:[/bold cyan] {self.session_state.active_mode}"
        )

        if intent.confidence == "low" and intent.clarification_question:
            logger.info(
                "session_clarification_returned mode=%s", self.session_state.active_mode
            )
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
            logger.warning("session_no_handler mode=%s", self.session_state.active_mode)
            response = {
                "mode": "general",
                "response": "I can help with translation, definitions, or language learning. Which would you like?",
                "intent": intent.model_dump(),
            }
            self.memory.add_turn(user_input, response["response"])
            console.print(f"[bold cyan]Agent:[/bold cyan] {response['response']}\n")
            return response

        logger.info(
            "session_state_update_start mode=%s", self.session_state.active_mode
        )
        self.session_state = await handler.update_session_state(
            user_input=user_input,
            session_state=self.session_state,
            conversation_history=history,
        )
        logger.info(
            "session_state_update_complete mode=%s", self.session_state.active_mode
        )

        output_mode = ModeOutputConfig[self.session_state.active_mode]
        logger.info(
            "session_output_mode_selected mode=%s output_mode=%s",
            self.session_state.active_mode,
            output_mode,
        )

        if output_mode != "stream":
            logger.info(
                "session_full_response_start mode=%s", self.session_state.active_mode
            )
            response = await handler.handle(
                user_input=user_input,
                session_state=self.session_state,
                conversation_history=history,
            )

            self.memory.add_turn(user_input, response.response)
            logger.info(
                "session_full_response_complete mode=%s response_length=%d",
                self.session_state.active_mode,
                len(response.response),
            )
            console.print(
                f"[bold cyan]Answer:[/bold cyan] {response.model_dump_json()}"
            )
            console.print(f"[bold cyan]Assistant:[/bold cyan] {response.response}\n")

        else:
            assistant_reply = ""
            token_count = 0
            logger.info("session_stream_start mode=%s", self.session_state.active_mode)
            console.print("[bold cyan]Assistant:[/bold cyan] ", end="")

            async for token in handler.stream(
                user_input=user_input,
                session_state=self.session_state,
                conversation_history=history,
            ):
                assistant_reply += token
                token_count += 1
                logger.debug(
                    "session_stream_token mode=%s token_length=%d token_count=%d",
                    self.session_state.active_mode,
                    len(token),
                    token_count,
                )
                console.print(token, end="")

            console.print()
            self.memory.add_turn(user_input, assistant_reply)
            logger.info(
                "session_stream_complete mode=%s token_count=%d response_length=%d",
                self.session_state.active_mode,
                token_count,
                len(assistant_reply),
            )

            response = {
                "mode": self.session_state.active_mode,
                "response": assistant_reply,
                "intent": intent.model_dump(),
            }

        logger.info("session_turn_complete mode=%s", self.session_state.active_mode)
        return response
