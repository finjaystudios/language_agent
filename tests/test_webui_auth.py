from __future__ import annotations

import asyncio

from app.infrastructure.database.models import Base
from app.infrastructure.database.repositories import SQLAlchemyUserRepository
from app.infrastructure.security.passwords import hash_password
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from webui.auth import authenticate_user


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


def test_valid_username_password_authenticates_and_updates_last_login():
    repository = create_repository()
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
        )
    )

    refreshed = asyncio.run(repository.get_by_id(created.id))

    assert authenticated_user is not None
    assert authenticated_user.identifier == "alice"
    assert authenticated_user.display_name == "Alice"
    assert authenticated_user.metadata == {
        "user_id": str(created.id),
        "role": "user",
        "is_admin": True,
    }
    assert refreshed is not None
    assert refreshed.last_login_at is not None


def test_invalid_password_fails():
    repository = create_repository()
    asyncio.run(
        repository.create_user(
            username="alice",
            password_hash=hash_password("correct-password"),
        )
    )

    authenticated_user = asyncio.run(
        authenticate_user(
            "alice",
            "wrong-password",
            repository=repository,
        )
    )

    assert authenticated_user is None


def test_unknown_username_fails():
    repository = create_repository()

    authenticated_user = asyncio.run(
        authenticate_user(
            "unknown-user",
            "secret",
            repository=repository,
        )
    )

    assert authenticated_user is None


def test_inactive_user_fails():
    repository = create_repository()
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
        )
    )
    refreshed = asyncio.run(repository.get_by_id(created.id))

    assert authenticated_user is None
    assert refreshed is not None
    assert refreshed.last_login_at is None


def test_password_is_never_returned_from_auth_response():
    repository = create_repository()
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
        )
    )

    assert authenticated_user is not None
    serialized = authenticated_user.to_dict()
    assert "password" not in serialized
    assert "password_hash" not in serialized
    assert "correct-password" not in str(serialized)
