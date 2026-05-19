from data_models.intent_result import IntentResult
from data_models.mode_responses import DefinitionResponse
from memory.short_term import ConversationMemory
from orchestration.session import SessionOrchestrator


class FakeConsole:
    def print(self, *args, **kwargs):
        pass


class FakeRouter:
    def __init__(self, intent):
        self.intent = intent

    def classify(self, user_input, session_state, conversation_history):
        return self.intent

    def apply_intent(self, session_state, intent):
        if intent.should_switch_mode:
            session_state.active_mode = intent.mode
        return session_state


class FakeStreamHandler:
    def __init__(self, order):
        self.order = order

    def update_session_state(self, user_input, session_state, conversation_history):
        self.order.append("update")
        return session_state

    def stream(self, user_input, session_state, conversation_history):
        self.order.append("stream")
        yield "hola"


class FakeAskHandler:
    def __init__(self, order):
        self.order = order

    def update_session_state(self, user_input, session_state, conversation_history):
        self.order.append("update")
        return session_state

    def handle(self, user_input, session_state, conversation_history):
        self.order.append("handle")
        return DefinitionResponse(
            term="bonjour",
            language="French",
            part_of_speech="interjection",
            pronunciation="",
            meaning="hello",
            response="bonjour means hello",
        )


def test_handle_turn_returns_clarification_without_calling_mode_handler():
    intent = IntentResult(
        mode="translation",
        confidence="low",
        should_switch_mode=True,
        reason="Ambiguous.",
        clarification_question="Which language?",
    )
    orchestrator = SessionOrchestrator(None, FakeRouter(intent), ConversationMemory())

    result = orchestrator.handle_turn("translate this", FakeConsole())

    assert result["response"] == "Which language?"


def test_handle_turn_returns_general_fallback_for_unsupported_mode():
    intent = IntentResult(
        mode="general",
        confidence="high",
        should_switch_mode=False,
        reason="General request.",
    )
    orchestrator = SessionOrchestrator(None, FakeRouter(intent), ConversationMemory())

    result = orchestrator.handle_turn("hello", FakeConsole())

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

    orchestrator.handle_turn("translate hello", FakeConsole())

    assert order == ["update", "stream"]


def test_handle_turn_updates_session_state_before_ask_response():
    order = []
    intent = IntentResult(
        mode="definition",
        confidence="high",
        should_switch_mode=True,
        reason="Definition request.",
    )
    orchestrator = SessionOrchestrator(None, FakeRouter(intent), ConversationMemory())
    orchestrator.handlers = {"definition": FakeAskHandler(order)}

    orchestrator.handle_turn("define bonjour", FakeConsole())

    assert order == ["update", "handle"]


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

    orchestrator.handle_turn("translate hello", FakeConsole())

    assert memory.turns[0].assistant_reply == "hola"
