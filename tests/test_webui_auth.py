from __future__ import annotations

import asyncio
import logging

from webui.auth import authenticate_user
from webui.auth_rate_limit import InMemoryAuthAttemptStore
from webui.client import (
    AuthenticatedBackendUser,
    BackendTimeoutError,
    BackendUserAuthenticationError,
)

AUTH_LOGGER_NAME = "webui.auth"


def test_valid_username_password_authenticates(
    authenticated_backend_user: AuthenticatedBackendUser,
    auth_attempt_store: InMemoryAuthAttemptStore,
    backend_auth_client_factory,
):
    backend_client = backend_auth_client_factory(user=authenticated_backend_user)

    authenticated_user = asyncio.run(
        authenticate_user(
            "alice",
            "correct horse battery staple",
            backend_client=backend_client,
            auth_attempt_store=auth_attempt_store,
        )
    )

    assert backend_client.calls == [("alice", "correct horse battery staple")]
    assert authenticated_user is not None
    assert authenticated_user.identifier == "alice"
    assert authenticated_user.display_name == "Alice"
    assert authenticated_user.metadata == {
        "user_id": "42",
        "username": "alice",
        "display_name": "Alice",
        "role": "user",
        "is_admin": True,
        "preferred_language": None,
        "ui_theme": None,
    }


def test_invalid_password_fails_without_revealing_password(
    auth_attempt_store: InMemoryAuthAttemptStore,
    webui_auth_logger,
    caplog,
    backend_auth_client_factory,
):
    backend_client = backend_auth_client_factory(
        error=BackendUserAuthenticationError(
            "Invalid username or password.",
            status_code=403,
            error_code="invalid_credentials",
        )
    )

    with caplog.at_level(logging.WARNING, logger=AUTH_LOGGER_NAME):
        caplog.clear()
        authenticated_user = asyncio.run(
            authenticate_user(
                "alice",
                "wrong-password",
                backend_client=backend_client,
                auth_attempt_store=auth_attempt_store,
            )
        )

    assert authenticated_user is None
    combined_logs = " ".join(record.getMessage() for record in caplog.records)
    assert "outcome=failure" in combined_logs
    assert "wrong-password" not in combined_logs
    assert "$argon2id$" not in combined_logs


def test_unknown_username_fails_with_generic_credentials_reason(
    auth_attempt_store: InMemoryAuthAttemptStore,
    webui_auth_logger,
    caplog,
    backend_auth_client_factory,
):
    backend_client = backend_auth_client_factory(
        error=BackendUserAuthenticationError(
            "Invalid username or password.",
            status_code=403,
            error_code="invalid_credentials",
        )
    )

    with caplog.at_level(logging.WARNING, logger=AUTH_LOGGER_NAME):
        caplog.clear()
        authenticated_user = asyncio.run(
            authenticate_user(
                "unknown-user",
                "secret",
                backend_client=backend_client,
                auth_attempt_store=auth_attempt_store,
            )
        )

    assert authenticated_user is None
    combined_logs = " ".join(record.getMessage() for record in caplog.records)
    assert "reason=invalid_credentials" in combined_logs
    assert "reason=user_not_found" not in combined_logs
    assert "secret" not in combined_logs


def test_inactive_user_fails(
    auth_attempt_store: InMemoryAuthAttemptStore,
    backend_auth_client_factory,
):
    backend_client = backend_auth_client_factory(
        error=BackendUserAuthenticationError(
            "Invalid username or password.",
            status_code=403,
            error_code="invalid_credentials",
        )
    )

    authenticated_user = asyncio.run(
        authenticate_user(
            "disabled",
            "disabled-password",
            backend_client=backend_client,
            auth_attempt_store=auth_attempt_store,
        )
    )

    assert authenticated_user is None


def test_repeated_failed_attempts_trigger_lockout_and_expiry(
    authenticated_backend_user: AuthenticatedBackendUser,
    auth_attempt_store: InMemoryAuthAttemptStore,
    fake_clock,
    webui_auth_logger,
    caplog,
    backend_auth_client_factory,
):
    failing_client = backend_auth_client_factory(
        error=BackendUserAuthenticationError(
            "Invalid username or password.",
            status_code=403,
            error_code="invalid_credentials",
        )
    )

    for _ in range(3):
        asyncio.run(
            authenticate_user(
                "alice",
                "wrong-password",
                backend_client=failing_client,
                auth_attempt_store=auth_attempt_store,
            )
        )

    successful_client = backend_auth_client_factory(user=authenticated_backend_user)
    with caplog.at_level(logging.WARNING, logger=AUTH_LOGGER_NAME):
        caplog.clear()
        locked_user = asyncio.run(
            authenticate_user(
                "alice",
                "correct-password",
                backend_client=successful_client,
                auth_attempt_store=auth_attempt_store,
            )
        )

    assert locked_user is None
    assert successful_client.calls == []
    assert "outcome=locked" in " ".join(
        record.getMessage() for record in caplog.records
    )

    fake_clock.advance(31)

    authenticated_user = asyncio.run(
        authenticate_user(
            "alice",
            "correct-password",
            backend_client=successful_client,
            auth_attempt_store=auth_attempt_store,
        )
    )

    assert authenticated_user is not None


def test_backend_errors_fail_closed_without_logging_sensitive_values(
    auth_attempt_store: InMemoryAuthAttemptStore,
    webui_auth_logger,
    caplog,
    backend_auth_client_factory,
):
    backend_client = backend_auth_client_factory(
        error=BackendTimeoutError("The FastAPI backend timed out.")
    )

    with caplog.at_level(logging.WARNING, logger=AUTH_LOGGER_NAME):
        caplog.clear()
        authenticated_user = asyncio.run(
            authenticate_user(
                "alice",
                "correct-password",
                backend_client=backend_client,
                auth_attempt_store=auth_attempt_store,
            )
        )

    assert authenticated_user is None
    combined_logs = " ".join(record.getMessage() for record in caplog.records)
    assert "outcome=error" in combined_logs
    assert "correct-password" not in combined_logs


def test_password_is_never_returned_from_auth_response(
    authenticated_backend_user: AuthenticatedBackendUser,
    auth_attempt_store: InMemoryAuthAttemptStore,
    backend_auth_client_factory,
):
    backend_client = backend_auth_client_factory(user=authenticated_backend_user)

    authenticated_user = asyncio.run(
        authenticate_user(
            "alice",
            "correct-password",
            backend_client=backend_client,
            auth_attempt_store=auth_attempt_store,
        )
    )

    assert authenticated_user is not None
    serialized = authenticated_user.to_dict()
    assert "password" not in serialized
    assert "password_hash" not in serialized
    assert "correct-password" not in str(serialized)
