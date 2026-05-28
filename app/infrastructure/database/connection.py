from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import AppSettings


def _build_connect_args(url: URL) -> Mapping[str, Any]:
    if url.get_backend_name() == "sqlite":
        return {"check_same_thread": False}
    return {}


def build_async_engine(settings: AppSettings) -> AsyncEngine:
    url = make_url(settings.database_url)
    engine_kwargs: dict[str, Any] = {
        "echo": settings.database_echo,
        "connect_args": dict(_build_connect_args(url)),
    }

    if url.get_backend_name() == "sqlite":
        if url.database in {None, "", ":memory:"}:
            engine_kwargs["poolclass"] = StaticPool
    else:
        engine_kwargs["pool_size"] = settings.database_pool_size

    return create_async_engine(url, **engine_kwargs)
