import asyncio

from app.api.models import ChatRequest
from app.data_models.intent_result import IntentResult
from app.data_models.mode_responses import DefinitionResponse, TranslationResponse
from app.memory.short_term import ConversationMemory
from app.services.agent_service import AgentService


class FakeRouter:
    def __init__(self, intent):
        self.intent = intent

    async def classify(self, user_input, session_state, conversation_history):
        return self.intent

    def apply_intent(self, session_state, intent):
        if intent.should_switch_mode:
            session_state.active_mode = intent.mode
        return session_state


class FakeDefinitionHandler:
    def __init__(self):
        self.calls = []

    async def update_session_state(
        self, user_input, session_state, conversation_history
    ):
        self.calls.append("update")
        return session_state

    async def handle(self, user_input, session_state, conversation_history):
        self.calls.append("handle")
        return DefinitionResponse(
            response="Recursion is a function calling itself.",
            term="recursion",
            language="English",
            meaning="A process that refers back to itself.",
        )


class FakeTranslationHandler:
    def __init__(self):
        self.calls = []

    async def update_session_state(
        self, user_input, session_state, conversation_history
    ):
        self.calls.append("update")
        return session_state

    async def handle(self, user_input, session_state, conversation_history):
        self.calls.append("handle")
        return TranslationResponse(
            response="bonjour",
            source_language="English",
            target_language="French",
            translated_text="bonjour",
        )

    async def stream(self, user_input, session_state, conversation_history):
        self.calls.append("stream")
        yield "bonjour"


def make_service(intent):
    return AgentService(
        llm_service=None,
        router=FakeRouter(intent),
        memory=ConversationMemory(),
    )


def test_chat_full_uses_supplied_mode_without_intent_classification():
    intent = IntentResult(
        mode="general",
        confidence="high",
        should_switch_mode=False,
        reason="Should not be used when mode is supplied.",
    )
    service = make_service(intent)
    handler = FakeDefinitionHandler()
    service.handlers = {"definition": handler}

    response = asyncio.run(
        service.chat_full(
            ChatRequest(
                message="Define recursion in simple terms",
                mode="definition",
                metadata={"session_id": "session-1"},
            )
        )
    )

    assert response.mode == "definition"
    assert response.response == "Recursion is a function calling itself."
    assert response.metadata.session_id == "session-1"
    assert handler.calls == ["update", "handle"]
    assert service.memory.turns[0].assistant_reply == response.response


def test_chat_full_uses_intent_routing_when_mode_is_omitted():
    intent = IntentResult(
        mode="definition",
        confidence="high",
        should_switch_mode=True,
        reason="Definition request.",
    )
    service = make_service(intent)
    service.handlers = {"definition": FakeDefinitionHandler()}

    response = asyncio.run(
        service.chat_full(ChatRequest(message="Define recursion in simple terms"))
    )

    assert response.mode == "definition"
    assert response.intent.reason == "Definition request."


def test_chat_full_calls_handle_not_stream_for_streaming_cli_modes():
    intent = IntentResult(
        mode="general",
        confidence="high",
        should_switch_mode=False,
        reason="Should not be used when mode is supplied.",
    )
    service = make_service(intent)
    handler = FakeTranslationHandler()
    service.handlers = {"translation": handler}

    response = asyncio.run(
        service.chat_full(ChatRequest(message="Translate hello", mode="translation"))
    )

    assert response.mode == "translation"
    assert response.response == "bonjour"
    assert handler.calls == ["update", "handle"]


def test_chat_full_returns_clarification_without_calling_handler():
    intent = IntentResult(
        mode="definition",
        confidence="low",
        should_switch_mode=True,
        reason="Ambiguous request.",
        clarification_question="Which term should I define?",
    )
    service = make_service(intent)
    handler = FakeDefinitionHandler()
    service.handlers = {"definition": handler}

    response = asyncio.run(service.chat_full(ChatRequest(message="Define it")))

    assert response.mode == "definition"
    assert response.response == "Which term should I define?"
    assert handler.calls == []
