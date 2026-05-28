from __future__ import annotations

import pytest
from app.infrastructure.security.password_policy import (
    MIN_PASSWORD_LENGTH,
    validate_password_strength,
)
from scripts.create_user import validate_create_user_password


def test_strong_password_is_accepted():
    validate_password_strength(
        "correct horse battery staple",
        username="alice",
    )


@pytest.mark.parametrize(
    ("password", "username", "expected_message"),
    [
        ("", "alice", "must not be empty"),
        ("short", "alice", str(MIN_PASSWORD_LENGTH)),
        ("password123", "alice", "too weak"),
        ("alice", "alice", "must not match the username"),
    ],
)
def test_weak_passwords_are_rejected(password, username, expected_message):
    with pytest.raises(ValueError, match=expected_message):
        validate_password_strength(password, username=username)


def test_password_policy_can_be_relaxed_but_not_to_empty_password():
    validate_password_strength(
        "simple-but-non-empty",
        username="alice",
        require_strong_password=False,
    )

    with pytest.raises(ValueError, match="must not be empty"):
        validate_password_strength(
            "   ",
            username="alice",
            require_strong_password=False,
        )


def test_create_user_command_rejects_weak_password(monkeypatch):
    monkeypatch.setenv("AUTH_REQUIRE_STRONG_PASSWORD", "true")

    with pytest.raises(ValueError, match="too weak"):
        validate_create_user_password("alice", "password123")
