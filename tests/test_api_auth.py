import asyncio
from collections.abc import AsyncIterator

from app.application.models import ChatResult, ResponseMetadata
from app.infrastructure.database.repositories import SQLAlchemyUserRepository
from app.infrastructure.security.passwords import hash_password
from app.interfaces.api.dependencies import get_agent_service, get_user_repository
from app.interfaces.api.main import create_app
from fastapi.testclient import TestClient


class FakeAgentService:
    async def chat_full(self, request):
        return ChatResult(
            mode=request.mode or "general",
            response="Authenticated response.",
            metadata=ResponseMetadata(session_id="auth-test"),
        )

    async def chat_stream(self, request) -> AsyncIterator[str]:
        async def events() -> AsyncIterator[str]:
            yield 'data: {"mode": "translation", "token": "hola"}\n\n'
            yield 'data: {"mode": "translation", "done": true}\n\n'

        return events()


def test_health_endpoint_allows_missing_api_key(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("FASTAPI_API_KEY", "test-secret")
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_endpoint_allows_missing_api_key(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("FASTAPI_API_KEY", "test-secret")
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["service"] == "local-language-agent"


def test_chat_endpoint_rejects_missing_api_key(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("FASTAPI_API_KEY", "test-secret")
    client = TestClient(create_app())

    response = client.post("/api/chat", json={"message": "Define recursion"})

    assert response.status_code == 401
    assert response.json() == {
        "error": "authentication_failed",
        "message": "A valid API key is required.",
        "details": None,
    }


def test_chat_endpoint_rejects_wrong_api_key(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("FASTAPI_API_KEY", "test-secret")
    client = TestClient(create_app())

    response = client.post(
        "/api/chat",
        headers={"X-API-Key": "wrong-secret"},
        json={"message": "Define recursion"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "authentication_failed"


def test_chat_endpoint_accepts_correct_api_key(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("FASTAPI_API_KEY", "test-secret")
    app = create_app()
    app.dependency_overrides[get_agent_service] = lambda: FakeAgentService()
    client = TestClient(app)

    response = client.post(
        "/api/chat",
        headers={"X-API-Key": "test-secret"},
        json={"message": "Define recursion", "mode": "definition"},
    )

    assert response.status_code == 200
    assert response.json()["response"] == "Authenticated response."


def test_streaming_endpoint_requires_api_key(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("FASTAPI_API_KEY", "test-secret")
    client = TestClient(create_app())

    response = client.post(
        "/api/chat/stream",
        json={"message": "Translate hello", "mode": "translation"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "authentication_failed"


def test_streaming_endpoint_accepts_correct_api_key(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("FASTAPI_API_KEY", "test-secret")
    app = create_app()
    app.dependency_overrides[get_agent_service] = lambda: FakeAgentService()
    client = TestClient(app)

    response = client.post(
        "/api/chat/stream",
        headers={"X-API-Key": "test-secret"},
        json={"message": "Translate hello", "mode": "translation"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "hola" in response.text


def test_queue_status_endpoint_requires_api_key(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("FASTAPI_API_KEY", "test-secret")
    client = TestClient(create_app())

    response = client.get("/api/queue/status")

    assert response.status_code == 401
    assert response.json()["error"] == "authentication_failed"


def test_auth_enabled_false_allows_unauthenticated_chat(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.delenv("FASTAPI_API_KEY", raising=False)
    app = create_app()
    app.dependency_overrides[get_agent_service] = lambda: FakeAgentService()
    client = TestClient(app)

    response = client.post("/api/chat", json={"message": "Define recursion"})

    assert response.status_code == 200
    assert response.json()["response"] == "Authenticated response."


def test_auth_enabled_with_missing_config_returns_safe_error(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.delenv("FASTAPI_API_KEY", raising=False)
    client = TestClient(create_app())

    response = client.post(
        "/api/chat",
        headers={"X-API-Key": "anything"},
        json={"message": "Define recursion"},
    )

    body = response.json()
    assert response.status_code == 500
    assert body == {
        "error": "auth_configuration_error",
        "message": "API authentication is not configured correctly.",
        "details": None,
    }
    assert "anything" not in str(body)


def test_openapi_marks_chat_routes_as_api_key_protected():
    schema = create_app().openapi()

    assert schema["components"]["securitySchemes"]["APIKeyHeader"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
    }
    assert schema["paths"]["/api/chat"]["post"]["security"] == [{"APIKeyHeader": []}]
    assert schema["paths"]["/api/chat/stream"]["post"]["security"] == [
        {"APIKeyHeader": []}
    ]


def test_internal_login_accepts_valid_credentials_and_updates_last_login(
    monkeypatch,
    user_repository: SQLAlchemyUserRepository,
):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("FASTAPI_API_KEY", "test-secret")
    created = asyncio.run(
        user_repository.create_user(
            username="alice",
            password_hash=hash_password("correct-password"),
            display_name="Alice",
            is_admin=True,
        )
    )
    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: user_repository
    client = TestClient(app)

    response = client.post(
        "/api/internal/auth/login",
        headers={"X-API-Key": "test-secret"},
        json={"username": "alice", "password": "correct-password"},
    )
    refreshed = asyncio.run(user_repository.get_by_id(created.id))

    assert response.status_code == 200
    assert response.json() == {
        "user_id": created.id,
        "username": "alice",
        "display_name": "Alice",
        "role": "user",
        "is_admin": True,
        "preferred_language": None,
        "ui_theme": None,
    }
    assert "password_hash" not in response.text
    assert refreshed is not None
    assert refreshed.last_login_at is not None


def test_internal_login_rejects_unknown_username_without_leaking_existence(
    monkeypatch,
    user_repository: SQLAlchemyUserRepository,
):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("FASTAPI_API_KEY", "test-secret")
    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: user_repository
    client = TestClient(app)

    response = client.post(
        "/api/internal/auth/login",
        headers={"X-API-Key": "test-secret"},
        json={"username": "unknown-user", "password": "wrong-password"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": "invalid_credentials",
        "message": "Invalid username or password.",
        "details": None,
    }


def test_internal_login_rejects_inactive_user(
    monkeypatch,
    user_repository: SQLAlchemyUserRepository,
):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("FASTAPI_API_KEY", "test-secret")
    asyncio.run(
        user_repository.create_user(
            username="disabled",
            password_hash=hash_password("disabled-password"),
            is_active=False,
        )
    )
    app = create_app()
    app.dependency_overrides[get_user_repository] = lambda: user_repository
    client = TestClient(app)

    response = client.post(
        "/api/internal/auth/login",
        headers={"X-API-Key": "test-secret"},
        json={"username": "disabled", "password": "disabled-password"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": "invalid_credentials",
        "message": "Invalid username or password.",
        "details": None,
    }
