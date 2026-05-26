import pytest
from app.domain.intent_result import IntentResult
from app.interfaces.api.models import (
    ApiMode,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    IntentClassificationRequest,
    StreamChatRequest,
)
from pydantic import ValidationError


def test_chat_request_accepts_supported_mode_and_metadata():
    request = ChatRequest(
        message="Translate hello to French",
        mode="translation",
        metadata={"session_id": "session-1", "client": "web"},
    )

    assert request.mode == ApiMode.translation
    assert request.metadata.session_id == "session-1"


def test_chat_request_rejects_unknown_mode():
    with pytest.raises(ValidationError):
        ChatRequest(message="hello", mode="unsupported")


def test_chat_request_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ChatRequest(message="hello", unexpected=True)


def test_stream_chat_request_requires_stream_true():
    request = StreamChatRequest(message="Teach me French")

    assert request.stream is True

    with pytest.raises(ValidationError):
        StreamChatRequest(message="Teach me French", stream=False)


def test_intent_classification_request_defaults_to_general_mode():
    request = IntentClassificationRequest(message="What does bonjour mean?")

    assert request.active_mode == ApiMode.general
    assert request.conversation_history == ""


def test_chat_response_accepts_structured_translation_payload():
    response = ChatResponse(
        mode="translation",
        response="bonjour",
        intent=IntentResult(
            mode="translation",
            confidence="high",
            should_switch_mode=True,
            reason="The user requested a translation.",
        ),
        data={
            "mode": "translation",
            "response": "bonjour",
            "source_language": "English",
            "target_language": "French",
            "translated_text": "bonjour",
        },
        metadata={"session_id": "session-1"},
    )

    assert response.mode == ApiMode.translation
    assert response.data.translated_text == "bonjour"
    assert response.metadata.session_id == "session-1"


def test_error_response_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ErrorResponse(error="bad_request", message="Invalid request.", extra=True)
