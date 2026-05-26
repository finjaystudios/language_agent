import asyncio

from app.application.session_orchestrator import SessionOrchestrator
from app.domain.intent_result import IntentResult
from app.memory.short_term import ConversationMemory


class FakeConsole:
    def print(self, *args, **kwargs):
        pass


class FakeRouter:
    def __init__(self, intent):
        self.intent = intent

    async def classify(self, user_input, session_state, conversation_history):
        return self.intent

    def apply_intent(self, session_state, intent):
        if intent.should_switch_mode:
            session_state.active_mode = intent.mode
        return session_state


class FakeStreamHandler:
    def __init__(self, order):
        self.order = order

    async def update_session_state(
        self, user_input, session_state, conversation_history
    ):
        self.order.append("update")
        return session_state

    async def stream(self, user_input, session_state, conversation_history):
        self.order.append("stream")
        yield "hola"


def test_handle_turn_returns_clarification_without_calling_mode_handler():
    intent = IntentResult(
        mode="translation",
        confidence="low",
        should_switch_mode=True,
        reason="Ambiguous.",
        clarification_question="Which language?",
    )
    orchestrator = SessionOrchestrator(None, FakeRouter(intent), ConversationMemory())

    result = asyncio.run(orchestrator.handle_turn("translate this", FakeConsole()))

    assert result["response"] == "Which language?"


def test_handle_turn_returns_general_fallback_for_unsupported_mode():
    intent = IntentResult(
        mode="general",
        confidence="high",
        should_switch_mode=False,
        reason="General request.",
    )
    orchestrator = SessionOrchestrator(None, FakeRouter(intent), ConversationMemory())

    result = asyncio.run(orchestrator.handle_turn("hello", FakeConsole()))

    assert result["mode"] == "general"


def test_handle_turn_updates_session_state_before_streaming_response():
    order = []
    intent = IntentResult(
        mode="translation",
        confidence="high",
        should_switch_mode=True,
        reason="Translation request.",
    )
    orchestrator = SessionOrchestrator(None, FakeRouter(intent), ConversationMemory())
    orchestrator.handlers = {"translation": FakeStreamHandler(order)}

    asyncio.run(orchestrator.handle_turn("translate hello", FakeConsole()))

    assert order == ["update", "stream"]


def test_handle_turn_updates_session_state_before_definition_streaming_response():
    order = []
    intent = IntentResult(
        mode="definition",
        confidence="high",
        should_switch_mode=True,
        reason="Definition request.",
    )
    orchestrator = SessionOrchestrator(None, FakeRouter(intent), ConversationMemory())
    orchestrator.handlers = {"definition": FakeStreamHandler(order)}

    asyncio.run(orchestrator.handle_turn("define bonjour", FakeConsole()))

    assert order == ["update", "stream"]


def test_handle_turn_stores_streamed_assistant_reply_in_memory():
    intent = IntentResult(
        mode="translation",
        confidence="high",
        should_switch_mode=True,
        reason="Translation request.",
    )
    memory = ConversationMemory()
    orchestrator = SessionOrchestrator(None, FakeRouter(intent), memory)
    orchestrator.handlers = {"translation": FakeStreamHandler([])}

    asyncio.run(orchestrator.handle_turn("translate hello", FakeConsole()))

    assert memory.turns[0].assistant_reply == "hola"
