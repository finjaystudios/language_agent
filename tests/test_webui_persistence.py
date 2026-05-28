from __future__ import annotations

import asyncio

import chainlit as cl
from webui.persistence import (
    apply_user_profile_to_session,
    chainlit_history_enabled,
    restore_profile_from_thread,
    thread_belongs_to_user,
)
from webui.ui_app import MODE_AUTO, SESSION_MODE_KEY, on_chat_resume


class FakeUserSession:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def get(self, key: str, default: object = None) -> object:
        return self.values.get(key, default)

    def set(self, key: str, value: object) -> None:
        self.values[key] = value


def test_apply_user_profile_to_session_sets_safe_profile_fields(monkeypatch):
    fake_session = FakeUserSession()
    monkeypatch.setattr("webui.persistence.cl.user_session", fake_session)
    user = cl.User(
        identifier="alice",
        display_name="Alice",
        metadata={
            "user_id": "42",
            "username": "alice",
            "display_name": "Alice",
            "preferred_language": "fr",
            "ui_theme": "light",
            "role": "user",
            "is_admin": False,
        },
    )

    restored = apply_user_profile_to_session(user)

    assert restored["user_id"] == "42"
    assert restored["username"] == "alice"
    assert restored["display_name"] == "Alice"
    assert restored["preferred_language"] == "fr"
    assert restored["ui_theme"] == "light"
    assert restored["role"] == "user"
    assert restored["is_admin"] is False
    assert fake_session.get("preferred_language") == "fr"
    assert fake_session.get("ui_theme") == "light"


def test_restore_profile_from_thread_sets_only_safe_profile_fields(monkeypatch):
    fake_session = FakeUserSession()
    monkeypatch.setattr("webui.persistence.cl.user_session", fake_session)
    thread = {
        "id": "thread-1",
        "userIdentifier": "alice",
        "metadata": {
            "user_id": "42",
            "username": "alice",
            "display_name": "Alice",
            "preferred_language": "en",
            "ui_theme": "dark",
            "selected_mode": "definition",
        },
    }

    restored = restore_profile_from_thread(thread)

    assert restored == {
        "user_id": "42",
        "username": "alice",
        "display_name": "Alice",
        "preferred_language": "en",
        "ui_theme": "dark",
    }
    assert fake_session.get("selected_mode") is None


def test_thread_belongs_to_user_rejects_other_users():
    thread = {"id": "thread-1", "userIdentifier": "alice"}
    user = cl.User(identifier="bob", metadata={})

    assert thread_belongs_to_user(thread, user) is False


def test_chat_resume_restores_mode_for_next_message(monkeypatch):
    fake_session = FakeUserSession()
    fake_session.set(SESSION_MODE_KEY, "definition")
    calls: list[str] = []

    async def fake_send_mode_settings(mode=MODE_AUTO):
        calls.append(mode)

    monkeypatch.setattr("webui.ui_app.cl.user_session", fake_session)
    monkeypatch.setattr(
        "webui.persistence.cl.user_session",
        fake_session,
    )
    monkeypatch.setattr(
        "webui.ui_app.get_current_user",
        lambda: cl.User(
            identifier="alice",
            display_name="Alice",
            metadata={
                "user_id": "42",
                "username": "alice",
                "display_name": "Alice",
                "preferred_language": "en",
                "ui_theme": "light",
                "role": "user",
                "is_admin": False,
            },
        ),
    )
    monkeypatch.setattr(
        "webui.ui_app.send_mode_settings",
        fake_send_mode_settings,
    )

    asyncio.run(
        on_chat_resume(
            {
                "id": "thread-1",
                "userIdentifier": "alice",
                "metadata": {
                    "user_id": "42",
                    "username": "alice",
                    "display_name": "Alice",
                    "preferred_language": "en",
                    "ui_theme": "light",
                },
            }
        )
    )

    assert calls == ["definition"]
    assert fake_session.get("preferred_language") == "en"
    assert fake_session.get("ui_theme") == "light"


def test_chainlit_history_enabled_reads_env_toggle(monkeypatch):
    monkeypatch.setenv("CHAINLIT_HISTORY_ENABLED", "false")

    assert chainlit_history_enabled() is False
