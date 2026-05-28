from __future__ import annotations

import asyncio
import logging

from app.infrastructure.database.repositories import SQLAlchemyUserRepository
from app.infrastructure.security.passwords import hash_password
from webui.auth import authenticate_user
from webui.auth_rate_limit import InMemoryAuthAttemptStore

AUTH_LOGGER_NAME = "webui.auth"


def test_valid_username_password_authenticates_and_updates_last_login(
    user_repository: SQLAlchemyUserRepository,
    auth_attempt_store: InMemoryAuthAttemptStore,
):
    created = asyncio.run(
        user_repository.create_user(
            username="alice",
            password_hash=hash_password("correct horse battery staple"),
            display_name="Alice",
            is_admin=True,
        )
    )

    authenticated_user = asyncio.run(
        authenticate_user(
            "alice",
            "correct horse battery staple",
            repository=user_repository,
            auth_attempt_store=auth_attempt_store,
        )
    )

    refreshed = asyncio.run(user_repository.get_by_id(created.id))

    assert authenticated_user is not None
    assert authenticated_user.identifier == "alice"
    assert authenticated_user.display_name == "Alice"
    assert authenticated_user.metadata == {
        "user_id": str(created.id),
        "username": "alice",
        "display_name": "Alice",
        "role": "user",
        "is_admin": True,
        "preferred_language": None,
        "ui_theme": None,
    }
    assert refreshed is not None
    assert refreshed.last_login_at is not None


def test_invalid_password_fails_without_revealing_password(
    user_repository: SQLAlchemyUserRepository,
    auth_attempt_store: InMemoryAuthAttemptStore,
    webui_auth_logger,
    caplog,
):
    asyncio.run(
        user_repository.create_user(
            username="alice",
            password_hash=hash_password("correct-password"),
        )
    )

    with caplog.at_level(logging.WARNING, logger=AUTH_LOGGER_NAME):
        caplog.clear()
        authenticated_user = asyncio.run(
            authenticate_user(
                "alice",
                "wrong-password",
                repository=user_repository,
                auth_attempt_store=auth_attempt_store,
            )
        )

    assert authenticated_user is None
    combined_logs = " ".join(record.getMessage() for record in caplog.records)
    assert "outcome=failure" in combined_logs
    assert "wrong-password" not in combined_logs
    assert "$argon2id$" not in combined_logs


def test_unknown_username_fails_with_generic_credentials_reason(
    user_repository: SQLAlchemyUserRepository,
    auth_attempt_store: InMemoryAuthAttemptStore,
    webui_auth_logger,
    caplog,
):
    with caplog.at_level(logging.WARNING, logger=AUTH_LOGGER_NAME):
        caplog.clear()
        authenticated_user = asyncio.run(
            authenticate_user(
                "unknown-user",
                "secret",
                repository=user_repository,
                auth_attempt_store=auth_attempt_store,
            )
        )

    assert authenticated_user is None
    combined_logs = " ".join(record.getMessage() for record in caplog.records)
    assert "reason=invalid_credentials" in combined_logs
    assert "reason=user_not_found" not in combined_logs
    assert "secret" not in combined_logs


def test_inactive_user_fails(
    user_repository: SQLAlchemyUserRepository,
    auth_attempt_store: InMemoryAuthAttemptStore,
):
    created = asyncio.run(
        user_repository.create_user(
            username="disabled",
            password_hash=hash_password("disabled-password"),
            is_active=False,
        )
    )

    authenticated_user = asyncio.run(
        authenticate_user(
            "disabled",
            "disabled-password",
            repository=user_repository,
            auth_attempt_store=auth_attempt_store,
        )
    )
    refreshed = asyncio.run(user_repository.get_by_id(created.id))

    assert authenticated_user is None
    assert refreshed is not None
    assert refreshed.last_login_at is None


def test_repeated_failed_attempts_trigger_lockout_and_expiry(
    user_repository: SQLAlchemyUserRepository,
    auth_attempt_store: InMemoryAuthAttemptStore,
    fake_clock,
    webui_auth_logger,
    caplog,
):
    asyncio.run(
        user_repository.create_user(
            username="alice",
            password_hash=hash_password("correct-password"),
        )
    )

    for _ in range(3):
        asyncio.run(
            authenticate_user(
                "alice",
                "wrong-password",
                repository=user_repository,
                auth_attempt_store=auth_attempt_store,
            )
        )

    with caplog.at_level(logging.WARNING, logger=AUTH_LOGGER_NAME):
        caplog.clear()
        locked_user = asyncio.run(
            authenticate_user(
                "alice",
                "correct-password",
                repository=user_repository,
                auth_attempt_store=auth_attempt_store,
            )
        )

    assert locked_user is None
    assert "outcome=locked" in " ".join(
        record.getMessage() for record in caplog.records
    )

    fake_clock.advance(31)

    authenticated_user = asyncio.run(
        authenticate_user(
            "alice",
            "correct-password",
            repository=user_repository,
            auth_attempt_store=auth_attempt_store,
        )
    )

    assert authenticated_user is not None


def test_password_is_never_returned_from_auth_response(
    user_repository: SQLAlchemyUserRepository,
    auth_attempt_store: InMemoryAuthAttemptStore,
):
    asyncio.run(
        user_repository.create_user(
            username="alice",
            password_hash=hash_password("correct-password"),
        )
    )

    authenticated_user = asyncio.run(
        authenticate_user(
            "alice",
            "correct-password",
            repository=user_repository,
            auth_attempt_store=auth_attempt_store,
        )
    )

    assert authenticated_user is not None
    serialized = authenticated_user.to_dict()
    assert "password" not in serialized
    assert "password_hash" not in serialized
    assert "correct-password" not in str(serialized)
