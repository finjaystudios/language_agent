from __future__ import annotations

import asyncio

from app.domain.user_profile import UsernameAlreadyExistsError
from app.infrastructure.database.models import Base
from app.infrastructure.database.repositories import SQLAlchemyUserRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


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


def test_create_user_and_get_by_username():
    repository = create_repository()

    created = asyncio.run(
        repository.create_user(
            username="alice",
            password_hash="hashed-password",
            display_name="Alice",
            preferred_language="en",
            ui_theme="light",
            profile_metadata={"timezone": "Africa/Johannesburg"},
        )
    )

    fetched = asyncio.run(repository.get_by_username("alice"))

    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.username == "alice"
    assert fetched.display_name == "Alice"
    assert fetched.preferred_language == "en"
    assert fetched.ui_theme == "light"
    assert fetched.profile_metadata == {"timezone": "Africa/Johannesburg"}


def test_username_must_be_unique():
    repository = create_repository()
    asyncio.run(repository.create_user(username="alice", password_hash="first-hash"))

    try:
        asyncio.run(
            repository.create_user(username="alice", password_hash="second-hash")
        )
    except UsernameAlreadyExistsError as error:
        assert str(error) == "alice"
    else:
        raise AssertionError("Expected UsernameAlreadyExistsError")


def test_get_by_id_returns_inactive_user():
    repository = create_repository()
    created = asyncio.run(
        repository.create_user(
            username="disabled-user",
            password_hash="hash",
            is_active=False,
        )
    )

    fetched = asyncio.run(repository.get_by_id(created.id))

    assert fetched is not None
    assert fetched.username == "disabled-user"
    assert fetched.is_active is False


def test_update_last_login_sets_timestamp():
    repository = create_repository()
    created = asyncio.run(
        repository.create_user(username="login-user", password_hash="hash")
    )

    updated = asyncio.run(repository.update_last_login(created.id))

    assert updated is not None
    assert updated.last_login_at is not None
