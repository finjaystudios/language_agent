import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.config import AppSettings  # noqa: E402
from app.infrastructure.llm.llama_server_gateway import (  # noqa: E402
    LlamaServerGateway,
    LlamaServerGatewayError,
    LlamaServerInterruptedError,
    LlamaServerMalformedResponseError,
    LlamaServerTimeoutError,
)


def make_settings(**overrides):
    base = AppSettings.from_env().__dict__.copy()
    base.update(
        {
            "llm_backend": "llama_server",
            "llama_server_url": "http://llama-server:8080",
            "llama_server_api_key": "",
            "llama_server_timeout_seconds": 30,
            "llama_server_stream_timeout_seconds": 30,
            "llama_server_model_name": "",
            "llama_server_health_path": "/health",
            "model_profiles_path": "config/model_profiles.yml",
        }
    )
    base.update(overrides)
    return AppSettings(**base)


def make_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, base_url="http://llama-server:8080")


def test_ask_llm_sync_uses_mode_profile_and_parses_structured_response():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"response":"bonjour"}'}}]},
        )

    gateway = LlamaServerGateway(make_settings(), client=make_client(handler))

    result = gateway.ask_llm_sync(
        messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ],
        schema={"type": "object"},
        mode="translation",
        stop=["\n\n"],
        seed=7,
    )

    assert result == {"response": "bonjour"}
    assert captured["payload"]["messages"][0]["content"].endswith("/no_think")
    assert captured["payload"]["messages"][1]["content"] == "user"
    assert captured["payload"]["model"] == "qwen3-4b-q4-k-m"
    assert captured["payload"]["temperature"] == 0.3
    assert captured["payload"]["max_tokens"] == 512
    assert captured["payload"]["top_p"] == 0.8
    assert captured["payload"]["top_k"] == 20
    assert captured["payload"]["min_p"] == 0.0
    assert captured["payload"]["stop"] == ["\n\n"]
    assert captured["payload"]["seed"] == 7
    assert captured["payload"]["response_format"]["json_schema"]["schema"] == {
        "type": "object"
    }


def test_generate_text_sync_strips_think_content():
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["stream"] is False
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "<think>hidden reasoning</think>plain text response"
                        }
                    }
                ]
            },
        )

    gateway = LlamaServerGateway(make_settings(), client=make_client(handler))

    result = gateway.generate_text_sync(
        messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ],
        mode="definition",
    )

    assert result == "plain text response"


def test_stream_llm_sync_yields_openai_compatible_chunks_without_think_content():
    stream_body = (
        'data: {"choices":[{"delta":{"content":"<thi"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"nk>hidden</think>bon"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"jour"}}]}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=stream_body)

    gateway = LlamaServerGateway(make_settings(), client=make_client(handler))

    chunks = list(
        gateway.stream_llm_sync(
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            mode="learning",
        )
    )

    assert chunks == [
        {"choices": [{"delta": {"content": "bon"}}]},
        {"choices": [{"delta": {"content": "jour"}}]},
    ]


def test_stream_llm_sync_timeout_is_sanitized():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("stream stalled")

    gateway = LlamaServerGateway(make_settings(), client=make_client(handler))

    with pytest.raises(LlamaServerTimeoutError) as error:
        list(
            gateway.stream_llm_sync(
                messages=[
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "user"},
                ],
                mode="general",
            )
        )

    assert str(error.value) == "llama-server timed out."


def test_stream_llm_sync_rejects_malformed_stream_event():
    stream_body = "data: {not-json}\n\n"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=stream_body)

    gateway = LlamaServerGateway(make_settings(), client=make_client(handler))

    with pytest.raises(LlamaServerMalformedResponseError) as error:
        list(
            gateway.stream_llm_sync(
                messages=[
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "user"},
                ],
                mode="general",
            )
        )

    assert str(error.value) == "llama-server returned malformed stream data."


def test_stream_llm_sync_detects_interrupted_generation():
    stream_body = 'data: {"choices":[{"delta":{"content":"bon"}}]}\n\n'

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=stream_body)

    gateway = LlamaServerGateway(make_settings(), client=make_client(handler))

    with pytest.raises(LlamaServerInterruptedError) as error:
        list(
            gateway.stream_llm_sync(
                messages=[
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "user"},
                ],
                mode="general",
            )
        )

    assert str(error.value) == "llama-server interrupted generation."


def test_llama_server_timeout_is_sanitized():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("backend timed out")

    gateway = LlamaServerGateway(make_settings(), client=make_client(handler))

    with pytest.raises(LlamaServerTimeoutError) as error:
        gateway.generate_text_sync(
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            mode="general",
        )

    assert str(error.value) == "llama-server timed out."


def test_llama_server_non_200_response_is_sanitized():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "upstream broke"})

    gateway = LlamaServerGateway(make_settings(), client=make_client(handler))

    with pytest.raises(LlamaServerGatewayError) as error:
        gateway.generate_text_sync(
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            mode="general",
        )

    assert str(error.value) == "llama-server returned HTTP 503."


def test_llama_server_malformed_response_is_sanitized():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": []})

    gateway = LlamaServerGateway(make_settings(), client=make_client(handler))

    with pytest.raises(LlamaServerMalformedResponseError) as error:
        gateway.generate_text_sync(
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            mode="general",
        )

    assert "did not contain any choices" in str(error.value)


def test_api_key_header_is_attached_when_configured():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("Authorization")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "plain text response"}}]},
        )

    gateway = LlamaServerGateway(
        make_settings(llama_server_api_key="secret-token"),
        client=make_client(handler),
    )

    gateway.generate_text_sync(
        messages=[
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ],
        mode="general",
    )

    assert captured["authorization"] == "Bearer secret-token"


def test_health_check_uses_lightweight_endpoint():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json={"status": "ok"})

    gateway = LlamaServerGateway(
        make_settings(llama_server_health_path="/readyz"),
        client=make_client(handler),
    )

    assert gateway.check_health() is True
    assert captured["path"] == "/readyz"


def test_async_gateway_preserves_application_facing_interface():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"mode":"translation"}'}}]},
        )

    gateway = LlamaServerGateway(make_settings(), client=make_client(handler))

    result = asyncio.run(
        gateway.ask_llm(
            system_prompt="system",
            user_prompt="user",
            schema={"type": "object"},
            mode="intent",
        )
    )

    assert result == {"mode": "translation"}


def test_prompt_control_is_inserted_when_no_system_message_exists():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "plain text response"}}]},
        )

    gateway = LlamaServerGateway(make_settings(), client=make_client(handler))

    gateway.generate_text_sync(
        messages=[{"role": "user", "content": "user"}],
        mode="learning",
    )

    assert captured["payload"]["messages"][0] == {
        "role": "system",
        "content": "/think",
    }
    assert captured["payload"]["messages"][1]["role"] == "user"
