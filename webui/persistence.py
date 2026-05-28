from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from typing import Any

import chainlit as cl
from chainlit.data.chainlit_data_layer import ChainlitDataLayer
from chainlit.types import ThreadDict
from webui.config import WebUISettings

SESSION_PROFILE_KEYS = (
    "user_id",
    "username",
    "display_name",
    "preferred_language",
    "ui_theme",
    "role",
    "is_admin",
)


@lru_cache(maxsize=1)
def get_chainlit_data_layer() -> ChainlitDataLayer:
    settings = WebUISettings.from_env()
    if not settings.database_url:
        raise RuntimeError(
            "WEBUI_DATABASE_URL or DATABASE_URL must be configured when Chainlit persistence is enabled."
        )
    return ChainlitDataLayer(database_url=settings.database_url)


def apply_user_profile_to_session(user: cl.User | None) -> dict[str, object]:
    if user is None:
        return {}

    metadata = user.metadata or {}
    session_profile = {
        "user_id": str(metadata.get("user_id", "")),
        "username": str(metadata.get("username", user.identifier)),
        "display_name": str(
            metadata.get("display_name", user.display_name or user.identifier)
        ),
        "preferred_language": metadata.get("preferred_language"),
        "ui_theme": metadata.get("ui_theme"),
        "role": str(metadata.get("role", "user")),
        "is_admin": bool(metadata.get("is_admin", False)),
    }
    for key, value in session_profile.items():
        cl.user_session.set(key, value)
    return session_profile


def restore_profile_from_thread(thread: ThreadDict) -> dict[str, object]:
    metadata = thread.get("metadata") or {}
    restored = {
        key: metadata[key]
        for key in SESSION_PROFILE_KEYS
        if isinstance(metadata, Mapping) and key in metadata
    }
    for key, value in restored.items():
        cl.user_session.set(key, value)
    return restored


def thread_belongs_to_user(
    thread: Mapping[str, Any] | None,
    user: cl.User | None,
) -> bool:
    if thread is None or user is None:
        return False
    return str(thread.get("userIdentifier") or "") == user.identifier
