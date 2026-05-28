from types import SimpleNamespace

from webui.client import (
    BackendAuthConfigurationError,
    BackendAuthenticationError,
    format_ui_error,
)
from webui.modes import starter_mode_for_values
from webui.ui_app import (
    has_unclosed_markdown_fence,
    normalize_mode_value,
    should_flush_stream_buffer,
    stream_backend_response,
)


def test_starter_mode_uses_chainlit_command():
    message = SimpleNamespace(command="definition", content="Define recursion.")

    assert starter_mode_for_values(message.command, message.content) == "definition"


def test_starter_mode_falls_back_to_starter_content():
    message = SimpleNamespace(
        command=None,
        content="Teach me three useful French greetings.",
    )

    assert starter_mode_for_values(message.command, message.content) == "learning"


def test_starter_mode_ignores_regular_message():
    message = SimpleNamespace(command=None, content="Workshop")

    assert starter_mode_for_values(message.command, message.content) is None


def test_authentication_error_message_is_readable_and_safe():
    error = BackendAuthenticationError(
        "The Web UI could not authenticate with the backend.",
        status_code=401,
        error_code="authentication_failed",
    )

    message = format_ui_error(error)

    assert "could not authenticate with the backend" in message
    assert "secret" not in message
    assert "Traceback" not in message


def test_missing_webui_api_key_message_is_readable_and_safe():
    message = format_ui_error(
        BackendAuthConfigurationError("The Web UI is missing the backend API key.")
    )

    assert "missing the backend API key" in message
    assert "change-me" not in message
    assert "Traceback" not in message


def test_normalize_mode_value_accepts_mode_ids_and_labels():
    assert normalize_mode_value("definition") == "definition"
    assert normalize_mode_value("Definition") == "definition"
    assert normalize_mode_value("Translation") == "translation"
    assert normalize_mode_value("Auto") == "auto"


def test_normalize_mode_value_falls_back_to_auto():
    assert normalize_mode_value("unknown") == "auto"
    assert normalize_mode_value(None) == "auto"


def test_stream_buffer_waits_inside_markdown_fence():
    assert (
        should_flush_stream_buffer("done. ", "```python\nprint('hi')\ndone. ") is False
    )


def test_stream_buffer_flushes_sentence_outside_markdown_fence():
    assert should_flush_stream_buffer("done. ", "The answer is done. ") is True


def test_unclosed_markdown_fence_detection():
    assert has_unclosed_markdown_fence("```python\nprint('hi')") is True
    assert has_unclosed_markdown_fence("```python\nprint('hi')\n```") is False


def test_stream_backend_response_falls_back_to_full_response_when_empty(monkeypatch):
    import asyncio

    class FakeClient:
        async def chat_stream(self, message, mode):
            assert (
                message
                == "Translate this sentence to isiXhosa: Good morning, how are you?"
            )
            assert mode == "translation"
            yield {"mode": "translation", "done": True}

    class FakeMessage:
        def __init__(self, content="", **kwargs):
            self.content = content
            self.metadata = kwargs.get("metadata")
            self.actions = kwargs.get("actions")

        async def send(self):
            return None

        async def update(self):
            return None

        async def remove(self):
            return None

        async def stream_token(self, token):
            self.content += token

    fallback = {}

    async def fake_send_full_backend_response(client, response, user_text, api_mode):
        fallback["called"] = True
        fallback["client"] = client
        fallback["response"] = response
        fallback["user_text"] = user_text
        fallback["api_mode"] = api_mode

    monkeypatch.setattr("webui.ui_app.cl.Message", FakeMessage)
    monkeypatch.setattr(
        "webui.ui_app.send_full_backend_response",
        fake_send_full_backend_response,
    )

    status_message = FakeMessage(content="Sending request")

    asyncio.run(
        stream_backend_response(
            FakeClient(),
            status_message,
            "Translate this sentence to isiXhosa: Good morning, how are you?",
            "translation",
        )
    )

    assert fallback["called"] is True
    assert fallback["response"] is status_message
    assert (
        fallback["user_text"]
        == "Translate this sentence to isiXhosa: Good morning, how are you?"
    )
    assert fallback["api_mode"] == "translation"
