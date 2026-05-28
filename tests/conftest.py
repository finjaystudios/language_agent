from __future__ import annotations

import asyncio
import logging

import pytest
from app.infrastructure.database.models import Base
from app.infrastructure.database.repositories import SQLAlchemyUserRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from webui.auth_rate_limit import AuthRateLimitSettings, InMemoryAuthAttemptStore
from webui.client import AuthenticatedBackendUser, BackendUserAuthenticationError


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class FakeBackendAuthClient:
    def __init__(
        self,
        *,
        user: AuthenticatedBackendUser | None = None,
        error: Exception | None = None,
    ) -> None:
        self.user = user
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def authenticate_user(
        self,
        username: str,
        password: str,
    ) -> AuthenticatedBackendUser:
        self.calls.append((username, password))
        if self.error is not None:
            raise self.error
        if self.user is None:
            raise BackendUserAuthenticationError(
                "Invalid username or password.",
                status_code=403,
                error_code="invalid_credentials",
            )
        return self.user


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


@pytest.fixture
def backend_user_payload() -> dict[str, object]:
    return {
        "user_id": 42,
        "username": "alice",
        "display_name": "Alice",
        "role": "user",
        "is_admin": True,
        "preferred_language": None,
        "ui_theme": None,
    }


@pytest.fixture
def authenticated_backend_user(
    backend_user_payload: dict[str, object],
) -> AuthenticatedBackendUser:
    return AuthenticatedBackendUser(**backend_user_payload)


@pytest.fixture
def fake_backend_auth_client(
    authenticated_backend_user: AuthenticatedBackendUser,
) -> FakeBackendAuthClient:
    return FakeBackendAuthClient(user=authenticated_backend_user)


@pytest.fixture
def backend_auth_client_factory():
    def factory(
        *,
        user: AuthenticatedBackendUser | None = None,
        error: Exception | None = None,
    ) -> FakeBackendAuthClient:
        return FakeBackendAuthClient(user=user, error=error)

    return factory
