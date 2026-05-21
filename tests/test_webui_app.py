from types import SimpleNamespace

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
