from __future__ import annotations

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import AppSettings
from app.infrastructure.database.connection import build_async_engine


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    return build_async_engine(AppSettings.from_env())


@lru_cache(maxsize=1)
def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_async_engine(),
        class_=AsyncSession,
        autoflush=False,
        expire_on_commit=False,
    )


def create_async_session() -> AsyncSession:
    return get_async_session_factory()()
