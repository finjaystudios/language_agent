from __future__ import annotations

import asyncio
import logging

from app.infrastructure.database.models import Base
from app.infrastructure.database.repositories import SQLAlchemyUserRepository
from app.infrastructure.security.passwords import hash_password
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from webui.auth import authenticate_user
from webui.auth_rate_limit import AuthRateLimitSettings, InMemoryAuthAttemptStore


def create_repository() -> SQLAlchemyUserRepository:
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


async def _create_schema(engine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def create_attempt_store(clock: FakeClock) -> InMemoryAuthAttemptStore:
    return InMemoryAuthAttemptStore(
        AuthRateLimitSettings(
            max_failed_attempts=3,
            lockout_seconds=30,
            rate_limit_window_seconds=60,
        ),
        now=clock.now,
    )


def test_valid_username_password_authenticates_and_updates_last_login():
    repository = create_repository()
    clock = FakeClock()
    attempt_store = create_attempt_store(clock)
    created = asyncio.run(
        repository.create_user(
            username="alice",
            password_hash=hash_password("correct horse battery staple"),
            display_name="Alice",
            is_admin=True,
        )
    )

    authenticated_user = asyncio.run(
        authenticate_user(
            "alice",
            "correct horse battery staple",
            repository=repository,
            auth_attempt_store=attempt_store,
        )
    )

    refreshed = asyncio.run(repository.get_by_id(created.id))

    assert authenticated_user is not None
    assert authenticated_user.identifier == "alice"
    assert authenticated_user.display_name == "Alice"
    assert authenticated_user.metadata == {
        "user_id": str(created.id),
        "username": "alice",
        "display_name": "Alice",
        "role": "user",
        "is_admin": True,
        "preferred_language": None,
        "ui_theme": None,
    }
    assert refreshed is not None
    assert refreshed.last_login_at is not None


def test_invalid_password_fails_without_revealing_password(caplog):
    repository = create_repository()
    clock = FakeClock()
    attempt_store = create_attempt_store(clock)
    asyncio.run(
        repository.create_user(
            username="alice",
            password_hash=hash_password("correct-password"),
        )
    )

    with caplog.at_level(logging.WARNING):
        authenticated_user = asyncio.run(
            authenticate_user(
                "alice",
                "wrong-password",
                repository=repository,
                auth_attempt_store=attempt_store,
            )
        )

    assert authenticated_user is None
    combined_logs = " ".join(record.message for record in caplog.records)
    assert "outcome=failure" in combined_logs
    assert "wrong-password" not in combined_logs
    assert "$argon2id$" not in combined_logs


def test_unknown_username_fails_with_generic_credentials_reason(caplog):
    repository = create_repository()
    clock = FakeClock()
    attempt_store = create_attempt_store(clock)

    with caplog.at_level(logging.WARNING):
        authenticated_user = asyncio.run(
            authenticate_user(
                "unknown-user",
                "secret",
                repository=repository,
                auth_attempt_store=attempt_store,
            )
        )

    assert authenticated_user is None
    combined_logs = " ".join(record.message for record in caplog.records)
    assert "reason=invalid_credentials" in combined_logs
    assert "reason=user_not_found" not in combined_logs
    assert "secret" not in combined_logs


def test_inactive_user_fails():
    repository = create_repository()
    clock = FakeClock()
    attempt_store = create_attempt_store(clock)
    created = asyncio.run(
        repository.create_user(
            username="disabled",
            password_hash=hash_password("disabled-password"),
            is_active=False,
        )
    )

    authenticated_user = asyncio.run(
        authenticate_user(
            "disabled",
            "disabled-password",
            repository=repository,
            auth_attempt_store=attempt_store,
        )
    )
    refreshed = asyncio.run(repository.get_by_id(created.id))

    assert authenticated_user is None
    assert refreshed is not None
    assert refreshed.last_login_at is None


def test_repeated_failed_attempts_trigger_lockout_and_expiry(caplog):
    repository = create_repository()
    clock = FakeClock()
    attempt_store = create_attempt_store(clock)
    asyncio.run(
        repository.create_user(
            username="alice",
            password_hash=hash_password("correct-password"),
        )
    )

    for _ in range(3):
        asyncio.run(
            authenticate_user(
                "alice",
                "wrong-password",
                repository=repository,
                auth_attempt_store=attempt_store,
            )
        )

    with caplog.at_level(logging.WARNING):
        locked_user = asyncio.run(
            authenticate_user(
                "alice",
                "correct-password",
                repository=repository,
                auth_attempt_store=attempt_store,
            )
        )

    assert locked_user is None
    assert "outcome=locked" in " ".join(record.message for record in caplog.records)

    clock.advance(31)

    authenticated_user = asyncio.run(
        authenticate_user(
            "alice",
            "correct-password",
            repository=repository,
            auth_attempt_store=attempt_store,
        )
    )

    assert authenticated_user is not None


def test_password_is_never_returned_from_auth_response():
    repository = create_repository()
    clock = FakeClock()
    attempt_store = create_attempt_store(clock)
    asyncio.run(
        repository.create_user(
            username="alice",
            password_hash=hash_password("correct-password"),
        )
    )

    authenticated_user = asyncio.run(
        authenticate_user(
            "alice",
            "correct-password",
            repository=repository,
            auth_attempt_store=attempt_store,
        )
    )

    assert authenticated_user is not None
    serialized = authenticated_user.to_dict()
    assert "password" not in serialized
    assert "password_hash" not in serialized
    assert "correct-password" not in str(serialized)
