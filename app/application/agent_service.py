import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from app.application.conversation_memory import ConversationMemory
from app.application.intent_router import IntentRouter
from app.application.models import ChatCommand, ChatResult, ResponseMetadata
from app.application.modes.base import ModeHandler
from app.application.modes.definition import DefinitionHandler
from app.application.modes.learning import LearningHandler
from app.application.modes.translation import TranslationHandler
from app.core.errors import APIError, LLMServiceError
from app.domain.intent_result import IntentResult
from app.domain.mode_responses import BaseModeResponse
from app.domain.session_states import SessionState
from app.ports.llm_gateway import LLMGateway

GENERAL_RESPONSE = "I can help with translation, definitions, or language learning. Which would you like?"
logger = logging.getLogger(__name__)


class AgentService:
    def __init__(
        self,
        llm_service: LLMGateway,
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
        logger.info("agent_service_initialized handlers=%s", list(self.handlers))

    @classmethod
    def from_queue(cls) -> "AgentService":
        logger.info("agent_service_from_queue_start")
        from app.infrastructure.redis.queued_gateway import QueuedLLMService

        llm_service = QueuedLLMService()
        memory = ConversationMemory(max_turns=5)
        router = IntentRouter(llm_service)
        return cls(llm_service=llm_service, router=router, memory=memory)

    async def chat_full(self, request: ChatCommand) -> ChatResult:
        session_id = request.metadata.session_id if request.metadata else None
        logger.info(
            "chat_full_start requested_mode=%s session_id=%s message_length=%d",
            request.mode,
            session_id,
            len(request.message),
        )
        try:
            history = self.memory.format_for_prompt()
            logger.debug("chat_full_history_prepared length=%d", len(history))
            intent = await self._resolve_intent(request=request, history=history)
            logger.info(
                "chat_full_intent_resolved mode=%s confidence=%s should_switch=%s",
                intent.mode,
                intent.confidence,
                intent.should_switch_mode,
            )
            self.session_state = self.router.apply_intent(self.session_state, intent)
            logger.info("chat_full_active_mode mode=%s", self.session_state.active_mode)

            metadata = ResponseMetadata(
                session_id=request.metadata.session_id if request.metadata else None
            )

            if intent.confidence == "low" and intent.clarification_question:
                logger.info(
                    "chat_full_clarification_returned mode=%s",
                    self.session_state.active_mode,
                )
                self.memory.add_turn(request.message, intent.clarification_question)
                return ChatResult(
                    mode=self.session_state.active_mode,
                    response=intent.clarification_question,
                    intent=intent,
                    metadata=metadata,
                )

            handler = self.handlers.get(self.session_state.active_mode)

            if handler is None:
                logger.warning(
                    "chat_full_no_handler mode=%s", self.session_state.active_mode
                )
                self.memory.add_turn(request.message, GENERAL_RESPONSE)
                return ChatResult(
                    mode="general",
                    response=GENERAL_RESPONSE,
                    intent=intent,
                    metadata=metadata,
                )

            logger.info(
                "chat_full_state_update_start mode=%s", self.session_state.active_mode
            )
            self.session_state = await handler.update_session_state(
                user_input=request.message,
                session_state=self.session_state,
                conversation_history=history,
            )
            logger.info(
                "chat_full_state_update_complete mode=%s",
                self.session_state.active_mode,
            )
            logger.info(
                "chat_full_handler_start mode=%s", self.session_state.active_mode
            )
            mode_response = await handler.handle(
                user_input=request.message,
                session_state=self.session_state,
                conversation_history=history,
            )
            logger.info(
                "chat_full_handler_complete mode=%s response_length=%d",
                self.session_state.active_mode,
                len(mode_response.response),
            )
            self.memory.add_turn(request.message, mode_response.response)

            logger.info("chat_full_complete mode=%s", mode_response.mode)
            return self._to_chat_result(
                mode_response=mode_response,
                intent=intent,
                metadata=metadata,
            )
        except APIError:
            logger.exception("chat_full_llm_service_error")
            raise
        except Exception as error:
            logger.exception("chat_full_unexpected_failure")
            raise LLMServiceError(
                "The language model failed while generating a response."
            ) from error

    async def chat_stream(self, request: ChatCommand) -> AsyncIterator[str]:
        session_id = request.metadata.session_id if request.metadata else None
        logger.info(
            "chat_stream_start requested_mode=%s session_id=%s message_length=%d",
            request.mode,
            session_id,
            len(request.message),
        )
        try:
            history = self.memory.format_for_prompt()
            logger.debug("chat_stream_history_prepared length=%d", len(history))
            intent = await self._resolve_intent(request=request, history=history)
            logger.info(
                "chat_stream_intent_resolved mode=%s confidence=%s should_switch=%s",
                intent.mode,
                intent.confidence,
                intent.should_switch_mode,
            )
            self.session_state = self.router.apply_intent(self.session_state, intent)
            logger.info(
                "chat_stream_active_mode mode=%s", self.session_state.active_mode
            )

            if intent.confidence == "low" and intent.clarification_question:
                logger.info(
                    "chat_stream_clarification_returned mode=%s",
                    self.session_state.active_mode,
                )
                return self._stream_static_response(
                    message=request.message,
                    mode=self.session_state.active_mode,
                    response=intent.clarification_question,
                )

            handler = self.handlers.get(self.session_state.active_mode)
            if handler is None:
                logger.warning(
                    "chat_stream_no_handler mode=%s", self.session_state.active_mode
                )
                return self._stream_static_response(
                    message=request.message,
                    mode="general",
                    response=GENERAL_RESPONSE,
                )

            logger.info(
                "chat_stream_state_update_start mode=%s", self.session_state.active_mode
            )
            self.session_state = await handler.update_session_state(
                user_input=request.message,
                session_state=self.session_state,
                conversation_history=history,
            )
            logger.info(
                "chat_stream_state_update_complete mode=%s",
                self.session_state.active_mode,
            )
            logger.info(
                "chat_stream_handler_ready mode=%s", self.session_state.active_mode
            )
            return self._stream_handler_response(
                handler=handler,
                request=request,
                history=history,
            )
        except APIError:
            logger.exception("chat_stream_llm_service_error")
            raise
        except Exception as error:
            logger.exception("chat_stream_unexpected_failure")
            raise LLMServiceError(
                "The language model failed while starting a stream."
            ) from error

    async def _resolve_intent(self, request: ChatCommand, history: str) -> IntentResult:
        if request.mode is not None:
            logger.info("intent_resolution_skipped supplied_mode=%s", request.mode)
            return IntentResult(
                mode=request.mode,
                confidence="high",
                should_switch_mode=True,
                reason="Mode supplied by API request.",
            )

        logger.info(
            "intent_resolution_start active_mode=%s", self.session_state.active_mode
        )
        intent = await self.router.classify(
            user_input=request.message,
            session_state=self.session_state,
            conversation_history=history,
        )
        resolved_intent = IntentResult(**intent.model_dump())
        logger.info(
            "intent_resolution_complete mode=%s confidence=%s",
            resolved_intent.mode,
            resolved_intent.confidence,
        )
        return resolved_intent

    def _to_chat_result(
        self,
        mode_response: BaseModeResponse,
        intent: IntentResult,
        metadata: ResponseMetadata,
    ) -> ChatResult:
        return ChatResult(
            mode=mode_response.mode,
            response=mode_response.response,
            intent=intent,
            data=mode_response.model_dump(),
            metadata=metadata,
        )

    async def _stream_static_response(
        self,
        message: str,
        mode: str,
        response: str,
    ) -> AsyncIterator[str]:
        logger.info(
            "stream_static_response mode=%s response_length=%d", mode, len(response)
        )
        self.memory.add_turn(message, response)
        yield self._sse_data({"mode": mode, "token": response})
        yield self._sse_data({"mode": mode, "done": True})

    async def _stream_handler_response(
        self,
        handler: ModeHandler,
        request: ChatCommand,
        history: str,
    ) -> AsyncIterator[str]:
        active_job_id: str | None = None
        try:
            if not hasattr(handler, "stream"):
                mode_response = await handler.handle(
                    user_input=request.message,
                    session_state=self.session_state,
                    conversation_history=history,
                )
                async for event in self._stream_mode_response(
                    message=request.message,
                    mode_response=mode_response,
                ):
                    yield event
                return

            assistant_reply = ""
            token_count = 0
            done_sent = False
            logger.info("stream_handler_start mode=%s", self.session_state.active_mode)
            async for item in handler.stream(
                user_input=request.message,
                session_state=self.session_state,
                conversation_history=history,
            ):
                if isinstance(item, str):
                    event: dict[str, Any] = {"token": item}
                else:
                    event = dict(item)

                if isinstance(event.get("job_id"), str):
                    active_job_id = event["job_id"]

                token = event.get("token")
                if isinstance(token, str) and token:
                    assistant_reply += token
                    token_count += 1
                    logger.debug(
                        "stream_token_received mode=%s token_length=%d token_count=%d",
                        self.session_state.active_mode,
                        len(token),
                        token_count,
                    )

                payload = {"mode": self.session_state.active_mode, **event}
                yield self._sse_data(payload)

                if event.get("done") is True:
                    done_sent = True
                    break

            if assistant_reply:
                self.memory.add_turn(request.message, assistant_reply)
            logger.info(
                "stream_handler_complete mode=%s token_count=%d response_length=%d",
                self.session_state.active_mode,
                token_count,
                len(assistant_reply),
            )
            if not done_sent:
                yield self._sse_data(
                    {"mode": self.session_state.active_mode, "done": True}
                )
        except asyncio.CancelledError:
            if active_job_id and hasattr(self.llm_service, "cancel_job"):
                try:
                    await self.llm_service.cancel_job(active_job_id)
                except Exception:
                    logger.exception(
                        "stream_handler_cancel_job_failed mode=%s job_id=%s",
                        self.session_state.active_mode,
                        active_job_id,
                    )
            raise
        except Exception:
            logger.exception(
                "stream_handler_runtime_failure mode=%s", self.session_state.active_mode
            )
            yield self._sse_data(
                {
                    "error": "llm_service_error",
                    "message": "The language model failed while streaming a response.",
                    "done": True,
                }
            )

    async def _stream_mode_response(
        self,
        *,
        message: str,
        mode_response: BaseModeResponse,
    ) -> AsyncIterator[str]:
        self.memory.add_turn(message, mode_response.response)
        yield self._sse_data(
            {"mode": mode_response.mode, "token": mode_response.response}
        )
        yield self._sse_data({"mode": mode_response.mode, "done": True})

    def _sse_data(self, payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"
