import asyncio
import json

import httpx
from webui.client import (
    BackendClientError,
    BackendConfig,
    BackendHTTPError,
    BackendInvalidResponseError,
    BackendTimeoutError,
    FastAPIClient,
    build_chat_payload,
    parse_sse_line,
)


def client_with_transport(transport: httpx.MockTransport) -> FastAPIClient:
    client = FastAPIClient(
        BackendConfig(
            base_url="http://backend.test",
            timeout_seconds=5,
            streaming_enabled=True,
        )
    )
    client._client = lambda: httpx.AsyncClient(  # noqa: SLF001
        base_url=client.config.base_url,
        transport=transport,
    )
    return client


def test_build_chat_payload_omits_auto_mode():
    assert build_chat_payload("hello", None) == {
        "message": "hello",
        "metadata": {"client": "chainlit-webui"},
    }


def test_build_chat_payload_includes_explicit_mode():
    assert build_chat_payload("hello", "definition") == {
        "message": "hello",
        "mode": "definition",
        "metadata": {"client": "chainlit-webui"},
    }


def test_chat_full_posts_backend_schema_payload():
    seen_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_payload
        seen_payload = json.loads(request.content)
        return httpx.Response(
            200,
            json={"mode": "definition", "response": "A concise definition."},
        )

    client = client_with_transport(httpx.MockTransport(handler))

    result = asyncio.run(client.chat_full("Define recursion", "definition"))

    assert seen_payload == {
        "message": "Define recursion",
        "mode": "definition",
        "metadata": {"client": "chainlit-webui"},
    }
    assert result["response"] == "A concise definition."


def test_chat_stream_yields_sse_events():
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["stream"] is True
        return httpx.Response(
            200,
            content=(
                'data: {"mode": "translation", "token": "hel"}\n\n'
                'data: {"mode": "translation", "token": "lo"}\n\n'
                'data: {"mode": "translation", "done": true}\n\n'
            ),
            headers={"content-type": "text/event-stream"},
        )

    client = client_with_transport(httpx.MockTransport(handler))

    async def collect_events():
        return [
            event
            async for event in client.chat_stream("Translate hello", "translation")
        ]

    assert asyncio.run(collect_events()) == [
        {"mode": "translation", "token": "hel"},
        {"mode": "translation", "token": "lo"},
        {"mode": "translation", "done": True},
    ]


def test_backend_error_uses_api_error_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": "unsupported_mode",
                "message": "Streaming is not supported for definition.",
            },
        )

    client = client_with_transport(httpx.MockTransport(handler))

    async def request_stream():
        return [
            event
            async for event in client.chat_stream("Define recursion", "definition")
        ]

    try:
        asyncio.run(request_stream())
    except BackendHTTPError as error:
        assert (
            str(error)
            == "Streaming is not supported for definition. (unsupported_mode)"
        )
        assert error.status_code == 400
        assert error.error_code == "unsupported_mode"
    else:
        raise AssertionError("Expected BackendHTTPError")


def test_timeout_error_is_readable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow model", request=request)

    client = client_with_transport(httpx.MockTransport(handler))

    try:
        asyncio.run(client.chat_full("Define recursion", "definition"))
    except BackendTimeoutError as error:
        assert "timed out" in str(error)
    else:
        raise AssertionError("Expected BackendTimeoutError")


def test_invalid_json_response_is_readable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content="not json")

    client = client_with_transport(httpx.MockTransport(handler))

    try:
        asyncio.run(client.chat_full("Define recursion", "definition"))
    except BackendInvalidResponseError as error:
        assert "invalid JSON" in str(error)
    else:
        raise AssertionError("Expected BackendInvalidResponseError")


def test_parse_sse_line_rejects_invalid_json():
    try:
        parse_sse_line("data: {bad json")
    except BackendClientError as error:
        assert "invalid streaming event" in str(error)
    else:
        raise AssertionError("Expected BackendClientError")
