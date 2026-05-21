from app.api.config import parse_csv_env
from app.api.main import create_app
from fastapi.testclient import TestClient


def test_parse_csv_env_trims_blank_entries():
    assert parse_csv_env(" http://localhost:8001, ,http://127.0.0.1:8001 ") == [
        "http://localhost:8001",
        "http://127.0.0.1:8001",
    ]


def test_cors_not_enabled_without_allowed_origins(monkeypatch):
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    client = TestClient(create_app())

    response = client.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:8001",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-API-Key,Content-Type",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_cors_allows_configured_origin(monkeypatch):
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:8001,http://127.0.0.1:8001",
    )
    client = TestClient(create_app())

    response = client.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:8001",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-API-Key,Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8001"
    assert "access-control-allow-credentials" not in response.headers
    assert "X-API-Key" in response.headers["access-control-allow-headers"]


def test_cors_rejects_unconfigured_origin(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:8001")
    client = TestClient(create_app())

    response = client.options(
        "/api/chat",
        headers={
            "Origin": "http://evil.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-API-Key,Content-Type",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
