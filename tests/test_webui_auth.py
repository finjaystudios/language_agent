from app.infrastructure.database.models import Base
from app.infrastructure.database.repositories import SQLAlchemyUserRepository
from app.infrastructure.security.passwords import hash_password
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from webui.auth import authenticate_user


def create_repository() -> SQLAlchemyUserRepository:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    return SQLAlchemyUserRepository(factory)


def test_valid_username_password_authenticates_and_updates_last_login():
    repository = create_repository()
    created = repository.create_user(
        username="alice",
        password_hash=hash_password("correct horse battery staple"),
        display_name="Alice",
        is_admin=True,
    )

    authenticated_user = authenticate_user(
        "alice",
        "correct horse battery staple",
        repository=repository,
    )

    refreshed = repository.get_by_id(created.id)

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
    repository.create_user(
        username="alice",
        password_hash=hash_password("correct-password"),
    )

    authenticated_user = authenticate_user(
        "alice",
        "wrong-password",
        repository=repository,
    )

    assert authenticated_user is None


def test_unknown_username_fails():
    repository = create_repository()

    authenticated_user = authenticate_user(
        "unknown-user",
        "secret",
        repository=repository,
    )

    assert authenticated_user is None


def test_inactive_user_fails():
    repository = create_repository()
    created = repository.create_user(
        username="disabled",
        password_hash=hash_password("disabled-password"),
        is_active=False,
    )

    authenticated_user = authenticate_user(
        "disabled",
        "disabled-password",
        repository=repository,
    )
    refreshed = repository.get_by_id(created.id)

    assert authenticated_user is None
    assert refreshed is not None
    assert refreshed.last_login_at is None


def test_password_is_never_returned_from_auth_response():
    repository = create_repository()
    repository.create_user(
        username="alice",
        password_hash=hash_password("correct-password"),
    )

    authenticated_user = authenticate_user(
        "alice",
        "correct-password",
        repository=repository,
    )

    assert authenticated_user is not None
    serialized = authenticated_user.to_dict()
    assert "password" not in serialized
    assert "password_hash" not in serialized
    assert "correct-password" not in str(serialized)
