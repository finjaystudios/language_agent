from __future__ import annotations

import logging

import chainlit as cl
from webui.auth_rate_limit import AuthAttemptStore, get_auth_attempt_store
from webui.client import (
    AuthenticatedBackendUser,
    BackendClientError,
    BackendUserAuthenticationError,
    FastAPIClient,
)
from webui.config import WebUISettings

logger = logging.getLogger(__name__)


async def authenticate_user(
    username: str,
    password: str,
    *,
    backend_client: FastAPIClient | None = None,
    auth_attempt_store: AuthAttemptStore | None = None,
) -> cl.User | None:
    normalized_username = username.strip()
    client = backend_client or FastAPIClient()
    attempt_store = auth_attempt_store or get_auth_attempt_store()
    session_id = _current_auth_session_id()

    if await attempt_store.is_locked(normalized_username):
        logger.warning(
            "service=webui event_type=auth outcome=locked username=%s session_id=%s reason=too_many_failures",
            normalized_username,
            session_id,
        )
        return None

    try:
        authenticated_user = await client.authenticate_user(
            normalized_username,
            password,
        )
    except BackendUserAuthenticationError:
        failures = await attempt_store.record_failure(normalized_username)
        settings = WebUISettings.from_env()
        outcome = (
            "locked" if failures >= settings.auth_max_failed_attempts else "failure"
        )
        logger.warning(
            "service=webui event_type=auth outcome=%s username=%s session_id=%s reason=invalid_credentials",
            outcome,
            normalized_username,
            session_id,
        )
        return None
    except BackendClientError as error:
        logger.warning(
            "service=webui event_type=auth outcome=error username=%s session_id=%s reason=%s",
            normalized_username,
            session_id,
            error.category,
        )
        return None

    await attempt_store.clear(normalized_username)
    logger.info(
        "service=webui event_type=auth outcome=success username=%s user_id=%s session_id=%s role=%s admin=%s",
        authenticated_user.username,
        authenticated_user.user_id,
        session_id,
        authenticated_user.role,
        authenticated_user.is_admin,
    )
    return to_chainlit_user(authenticated_user)


def to_chainlit_user(user: AuthenticatedBackendUser) -> cl.User:
    display_name = user.display_name or user.username
    return cl.User(
        identifier=user.username,
        display_name=display_name,
        metadata={
            "user_id": str(user.user_id),
            "username": user.username,
            "display_name": display_name,
            "role": user.role,
            "is_admin": user.is_admin,
            "preferred_language": user.preferred_language,
            "ui_theme": user.ui_theme,
        },
    )


def _current_auth_session_id() -> str:
    try:
        return str(cl.user_session.get("id", "unknown"))
    except Exception:
        return "unknown"
