from __future__ import annotations

# ruff: noqa: E402
import logging
import sys
from functools import lru_cache
from pathlib import Path

import chainlit as cl
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.domain.user_profile import UserProfile  # noqa: E402
from app.infrastructure.database.repositories import (
    SQLAlchemyUserRepository,  # noqa: E402
)
from app.infrastructure.security.passwords import verify_password  # noqa: E402
from app.ports.user_repository import UserRepository  # noqa: E402
from webui.auth_rate_limit import AuthAttemptStore, get_auth_attempt_store  # noqa: E402
from webui.config import WebUISettings  # noqa: E402

logger = logging.getLogger(__name__)


def get_user_repository() -> UserRepository:
    return SQLAlchemyUserRepository(get_async_session_factory())


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    database_url = WebUISettings.from_env().database_url
    url = make_url(database_url)
    engine_kwargs: dict[str, object] = {}
    if url.get_backend_name() == "sqlite":
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        if url.database in {None, "", ":memory:"}:
            engine_kwargs["poolclass"] = StaticPool

    return create_async_engine(database_url, **engine_kwargs)


@lru_cache(maxsize=1)
def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_async_engine(),
        class_=AsyncSession,
        autoflush=False,
        expire_on_commit=False,
    )


async def authenticate_user(
    username: str,
    password: str,
    *,
    repository: UserRepository | None = None,
    auth_attempt_store: AuthAttemptStore | None = None,
) -> cl.User | None:
    normalized_username = username.strip()
    user_repository = repository or get_user_repository()
    attempt_store = auth_attempt_store or get_auth_attempt_store()
    session_id = _current_auth_session_id()

    if await attempt_store.is_locked(normalized_username):
        logger.warning(
            "service=webui event_type=auth outcome=locked username=%s session_id=%s reason=too_many_failures",
            normalized_username,
            session_id,
        )
        return None

    user = await user_repository.get_by_username(normalized_username)
    if user is None:
        await attempt_store.record_failure(normalized_username)
        logger.warning(
            "service=webui event_type=auth outcome=failure username=%s session_id=%s reason=invalid_credentials",
            normalized_username,
            session_id,
        )
        return None

    if not user.is_active:
        await attempt_store.record_failure(normalized_username)
        logger.warning(
            "service=webui event_type=auth outcome=failure username=%s user_id=%s session_id=%s reason=inactive_user",
            normalized_username,
            user.id,
            session_id,
        )
        return None

    if not verify_password(password, user.password_hash):
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

    await attempt_store.clear(normalized_username)
    authenticated_user = await user_repository.update_last_login(user.id) or user
    logger.info(
        "service=webui event_type=auth outcome=success username=%s user_id=%s session_id=%s role=%s admin=%s",
        authenticated_user.username,
        authenticated_user.id,
        session_id,
        authenticated_user.role,
        authenticated_user.is_admin,
    )
    return to_chainlit_user(authenticated_user)


def to_chainlit_user(user: UserProfile) -> cl.User:
    return cl.User(
        identifier=user.username,
        display_name=user.display_name or user.username,
        metadata={
            "user_id": str(user.id),
            "username": user.username,
            "display_name": user.display_name or user.username,
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
