from __future__ import annotations

# ruff: noqa: E402
import logging
import sys
from functools import lru_cache
from pathlib import Path

import chainlit as cl
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
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
from webui.config import WebUISettings  # noqa: E402

logger = logging.getLogger(__name__)


def get_user_repository() -> UserRepository:
    return SQLAlchemyUserRepository(get_session_factory())


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    database_url = WebUISettings.from_env().database_url
    if not database_url:
        raise RuntimeError("Web UI database URL is not configured.")

    url = make_url(database_url)
    engine_kwargs: dict[str, object] = {"future": True}
    if url.get_backend_name() == "sqlite":
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        if url.database in {None, "", ":memory:"}:
            engine_kwargs["poolclass"] = StaticPool

    return create_engine(url, **engine_kwargs)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


def authenticate_user(
    username: str,
    password: str,
    *,
    repository: UserRepository | None = None,
) -> cl.User | None:
    normalized_username = username.strip()
    user_repository = repository or get_user_repository()
    user = user_repository.get_by_username(normalized_username)
    if user is None:
        logger.warning(
            "webui_login_failed username=%s reason=invalid_credentials",
            normalized_username,
        )
        return None

    if not user.is_active:
        logger.warning(
            "webui_login_failed username=%s user_id=%s reason=inactive_user",
            normalized_username,
            user.id,
        )
        return None

    if not verify_password(password, user.password_hash):
        logger.warning(
            "webui_login_failed username=%s reason=invalid_credentials",
            normalized_username,
        )
        return None

    authenticated_user = user_repository.update_last_login(user.id) or user
    logger.info(
        "webui_login_success username=%s user_id=%s role=%s admin=%s",
        authenticated_user.username,
        authenticated_user.id,
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
            "role": user.role,
            "is_admin": user.is_admin,
        },
    )
