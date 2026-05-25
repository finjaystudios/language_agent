import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import AppSettings  # noqa: E402


def test_app_settings_default_llama_server_config(monkeypatch):
    for key in (
        "LLM_BACKEND",
        "LLAMA_SERVER_URL",
        "LLAMA_SERVER_API_KEY",
        "LLAMA_SERVER_TIMEOUT_SECONDS",
        "LLAMA_SERVER_STREAM_TIMEOUT_SECONDS",
        "LLAMA_SERVER_MODEL_NAME",
        "LLAMA_SERVER_HEALTH_PATH",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = AppSettings.from_env()

    assert settings.llm_backend == "llama_server"
    assert settings.llama_server_url == "http://localhost:8080"
    assert settings.llama_server_api_key == ""
    assert settings.llama_server_timeout_seconds == 180
    assert settings.llama_server_stream_timeout_seconds == 180
    assert settings.llama_server_model_name == ""
    assert settings.llama_server_health_path == "/health"


def test_app_settings_reads_llama_server_env(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "llama_server")
    monkeypatch.setenv("LLAMA_SERVER_URL", "http://llama-server:8080")
    monkeypatch.setenv("LLAMA_SERVER_API_KEY", "test-key")
    monkeypatch.setenv("LLAMA_SERVER_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("LLAMA_SERVER_STREAM_TIMEOUT_SECONDS", "90")
    monkeypatch.setenv("LLAMA_SERVER_MODEL_NAME", "qwen2.5-7b-instruct")
    monkeypatch.setenv("LLAMA_SERVER_HEALTH_PATH", "/v1/models")

    settings = AppSettings.from_env()

    assert settings.llm_backend == "llama_server"
    assert settings.llama_server_url == "http://llama-server:8080"
    assert settings.llama_server_api_key == "test-key"
    assert settings.llama_server_timeout_seconds == 45
    assert settings.llama_server_stream_timeout_seconds == 90
    assert settings.llama_server_model_name == "qwen2.5-7b-instruct"
    assert settings.llama_server_health_path == "/v1/models"
