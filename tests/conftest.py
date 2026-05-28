from __future__ import annotations

import asyncio
import logging

import pytest
from app.infrastructure.database.models import Base
from app.infrastructure.database.repositories import SQLAlchemyUserRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from webui.auth_rate_limit import AuthRateLimitSettings, InMemoryAuthAttemptStore


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


async def _create_schema(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    items.sort(key=lambda item: item.get_closest_marker("e2e") is not None)


@pytest.fixture
def user_repository() -> SQLAlchemyUserRepository:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    asyncio.run(_create_schema(engine))
    factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return SQLAlchemyUserRepository(factory)


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def auth_attempt_store(fake_clock: FakeClock) -> InMemoryAuthAttemptStore:
    return InMemoryAuthAttemptStore(
        AuthRateLimitSettings(
            max_failed_attempts=3,
            lockout_seconds=30,
            rate_limit_window_seconds=60,
        ),
        now=fake_clock.now,
    )


@pytest.fixture
def webui_auth_logger():
    logger = logging.getLogger("webui.auth")
    original_level = logger.level
    original_propagate = logger.propagate
    original_disabled = logger.disabled

    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    logger.disabled = False
    yield logger

    logger.setLevel(original_level)
    logger.propagate = original_propagate
    logger.disabled = original_disabled
