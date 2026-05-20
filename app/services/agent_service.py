from api.models import ApiMode, ChatRequest, ChatResponse, ResponseMetadata
from data_models.intent_result import IntentResult
from data_models.mode_responses import BaseModeResponse
from data_models.session_states import SessionState
from memory.short_term import ConversationMemory
from orchestration.modes.base import ModeHandler
from orchestration.modes.definition import DefinitionHandler
from orchestration.modes.learning import LearningHandler
from orchestration.modes.translation import TranslationHandler
from orchestration.router import IntentRouter

GENERAL_RESPONSE = "I can help with translation, definitions, or language learning. Which would you like?"


class AgentService:
    def __init__(
        self,
        llm_service,
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

    @classmethod
    def from_local_model(cls) -> "AgentService":
        from llm.service import LLMService
        from processor_selection import (
            MODEL_PATH,
            N_CTX,
            assert_llama_cpp_gpu_offload_supported,
            assert_nvidia_gpu_visible,
            choose_gpu_layers,
        )

        assert_nvidia_gpu_visible()
        assert_llama_cpp_gpu_offload_supported()

        llm_service = LLMService(
            model_path=MODEL_PATH,
            n_ctx=N_CTX,
            n_threads=4,
            n_gpu_layers=choose_gpu_layers(MODEL_PATH),
        )
        memory = ConversationMemory(max_turns=5)
        router = IntentRouter(llm_service)
        return cls(llm_service=llm_service, router=router, memory=memory)

    async def chat_full(self, request: ChatRequest) -> ChatResponse:
        history = self.memory.format_for_prompt()
        intent = await self._resolve_intent(request=request, history=history)
        self.session_state = self.router.apply_intent(self.session_state, intent)

        metadata = ResponseMetadata(
            session_id=request.metadata.session_id if request.metadata else None
        )

        if intent.confidence == "low" and intent.clarification_question:
            self.memory.add_turn(request.message, intent.clarification_question)
            return ChatResponse(
                mode=ApiMode(self.session_state.active_mode),
                response=intent.clarification_question,
                intent=intent,
                metadata=metadata,
            )

        handler = self.handlers.get(self.session_state.active_mode)

        if handler is None:
            self.memory.add_turn(request.message, GENERAL_RESPONSE)
            return ChatResponse(
                mode=ApiMode.general,
                response=GENERAL_RESPONSE,
                intent=intent,
                metadata=metadata,
            )

        self.session_state = await handler.update_session_state(
            user_input=request.message,
            session_state=self.session_state,
            conversation_history=history,
        )
        mode_response = await handler.handle(
            user_input=request.message,
            session_state=self.session_state,
            conversation_history=history,
        )
        self.memory.add_turn(request.message, mode_response.response)

        return self._to_chat_response(
            mode_response=mode_response,
            intent=intent,
            metadata=metadata,
        )

    async def _resolve_intent(self, request: ChatRequest, history: str) -> IntentResult:
        if request.mode is not None:
            return IntentResult(
                mode=request.mode.value,
                confidence="high",
                should_switch_mode=True,
                reason="Mode supplied by API request.",
            )

        intent = await self.router.classify(
            user_input=request.message,
            session_state=self.session_state,
            conversation_history=history,
        )
        return IntentResult(**intent.model_dump())

    def _to_chat_response(
        self,
        mode_response: BaseModeResponse,
        intent: IntentResult,
        metadata: ResponseMetadata,
    ) -> ChatResponse:
        return ChatResponse(
            mode=ApiMode(mode_response.mode),
            response=mode_response.response,
            intent=intent,
            data=mode_response.model_dump(),
            metadata=metadata,
        )
