import asyncio
import logging

import pytest
from app.application.agent_service import AgentService
from app.application.models import ChatCommand
from app.core.errors import LLMServiceError
from app.domain.intent_result import IntentResult
from app.domain.mode_responses import DefinitionResponse, TranslationResponse
from app.memory.short_term import ConversationMemory
from pydantic import ValidationError


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

    async def stream(self, user_input, session_state, conversation_history):
        self.calls.append("stream")
        yield "Recursion"
        yield " is a function calling itself."


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


class FakeFailingDefinitionHandler(FakeDefinitionHandler):
    async def handle(self, user_input, session_state, conversation_history):
        raise RuntimeError("model exploded")


class FakeFailingStreamHandler(FakeTranslationHandler):
    async def stream(self, user_input, session_state, conversation_history):
        self.calls.append("stream")
        yield "bon"
        raise RuntimeError("stream exploded")


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
            ChatCommand(
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


def test_chat_full_logs_major_stages(caplog):
    intent = IntentResult(
        mode="general",
        confidence="high",
        should_switch_mode=False,
        reason="Should not be used when mode is supplied.",
    )
    service = make_service(intent)
    service.handlers = {"definition": FakeDefinitionHandler()}

    with caplog.at_level(logging.INFO, logger="app.application.agent_service"):
        asyncio.run(
            service.chat_full(
                ChatCommand(message="Define recursion", mode="definition")
            )
        )

    messages = [record.message for record in caplog.records]
    assert any("chat_full_start" in message for message in messages)
    assert any("intent_resolution_skipped" in message for message in messages)
    assert any("chat_full_handler_complete" in message for message in messages)
    assert any("chat_full_complete" in message for message in messages)


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
        service.chat_full(ChatCommand(message="Define recursion in simple terms"))
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
        service.chat_full(ChatCommand(message="Translate hello", mode="translation"))
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

    response = asyncio.run(service.chat_full(ChatCommand(message="Define it")))

    assert response.mode == "definition"
    assert response.response == "Which term should I define?"
    assert handler.calls == []


def test_chat_stream_yields_sse_tokens_and_done_event():
    intent = IntentResult(
        mode="general",
        confidence="high",
        should_switch_mode=False,
        reason="Should not be used when mode is supplied.",
    )
    service = make_service(intent)
    handler = FakeTranslationHandler()
    service.handlers = {"translation": handler}

    async def collect_events():
        stream = await service.chat_stream(
            ChatCommand(message="Translate hello", mode="translation")
        )
        return [event async for event in stream]

    events = asyncio.run(collect_events())

    assert events == [
        'data: {"mode": "translation", "token": "bonjour"}\n\n',
        'data: {"mode": "translation", "done": true}\n\n',
    ]
    assert handler.calls == ["update", "stream"]
    assert service.memory.turns[0].assistant_reply == "bonjour"


def test_chat_stream_supports_definition_mode():
    intent = IntentResult(
        mode="general",
        confidence="high",
        should_switch_mode=False,
        reason="Should not be used when mode is supplied.",
    )
    service = make_service(intent)
    service.handlers = {"definition": FakeDefinitionHandler()}

    async def collect_events():
        stream = await service.chat_stream(
            ChatCommand(message="Define recursion", mode="definition")
        )
        return [event async for event in stream]

    events = asyncio.run(collect_events())

    assert events == [
        'data: {"mode": "definition", "token": "Recursion"}\n\n',
        'data: {"mode": "definition", "token": " is a function calling itself."}\n\n',
        'data: {"mode": "definition", "done": true}\n\n',
    ]
    assert service.handlers["definition"].calls == ["update", "stream"]


def test_chat_stream_returns_general_fallback_when_no_mode_handler_exists():
    intent = IntentResult(
        mode="general",
        confidence="high",
        should_switch_mode=False,
        reason="General request.",
    )
    service = make_service(intent)
    service.handlers = {}

    async def collect_events():
        stream = await service.chat_stream(ChatCommand(message="Hello"))
        return [event async for event in stream]

    events = asyncio.run(collect_events())

    assert events == [
        'data: {"mode": "general", "token": "I can help with translation, definitions, or language learning. Which would you like?"}\n\n',
        'data: {"mode": "general", "done": true}\n\n',
    ]


def test_chat_command_rejects_empty_message():
    with pytest.raises(ValidationError):
        ChatCommand(message="", mode="translation")


def test_chat_full_wraps_llm_runtime_failure():
    intent = IntentResult(
        mode="general",
        confidence="high",
        should_switch_mode=False,
        reason="Should not be used when mode is supplied.",
    )
    service = make_service(intent)
    service.handlers = {"definition": FakeFailingDefinitionHandler()}

    async def define_with_failure():
        await service.chat_full(
            ChatCommand(message="Define recursion", mode="definition")
        )

    with pytest.raises(LLMServiceError) as error:
        asyncio.run(define_with_failure())

    assert "generating a response" in str(error.value)


def test_chat_stream_runtime_failure_returns_sanitized_sse_error():
    intent = IntentResult(
        mode="general",
        confidence="high",
        should_switch_mode=False,
        reason="Should not be used when mode is supplied.",
    )
    service = make_service(intent)
    service.handlers = {"translation": FakeFailingStreamHandler()}

    async def collect_events():
        stream = await service.chat_stream(
            ChatCommand(message="Translate hello", mode="translation")
        )
        return [event async for event in stream]

    events = asyncio.run(collect_events())

    assert events == [
        'data: {"mode": "translation", "token": "bon"}\n\n',
        'data: {"error": "llm_service_error", "message": "The language model failed while streaming a response.", "done": true}\n\n',
    ]
