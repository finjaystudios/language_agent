from types import SimpleNamespace

from webui.client import (
    BackendAuthConfigurationError,
    BackendAuthenticationError,
    format_ui_error,
)
from webui.modes import starter_mode_for_values


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
