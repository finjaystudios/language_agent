from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppSettings
from app.infrastructure.database.connection import build_engine


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return build_engine(AppSettings.from_env())


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


def create_session() -> Session:
    return get_session_factory()()
