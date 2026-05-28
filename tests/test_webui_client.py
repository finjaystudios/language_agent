import asyncio
import json

import httpx
from webui.client import (
    API_KEY_HEADER_NAME,
    BackendAuthConfigurationError,
    BackendAuthenticationError,
    BackendClientError,
    BackendConfig,
    BackendConflictError,
    BackendFeatureDisabledError,
    BackendHTTPError,
    BackendInvalidResponseError,
    BackendTimeoutError,
    BackendUserAuthenticationError,
    BackendValidationError,
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
            api_key="test-secret",
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
    seen_api_key = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_api_key, seen_payload
        seen_payload = json.loads(request.content)
        seen_api_key = request.headers.get(API_KEY_HEADER_NAME)
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
    assert seen_api_key == "test-secret"
    assert result["response"] == "A concise definition."


def test_chat_stream_yields_sse_events():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers[API_KEY_HEADER_NAME] == "test-secret"
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


def test_health_does_not_send_api_key():
    def handler(request: httpx.Request) -> httpx.Response:
        assert API_KEY_HEADER_NAME not in request.headers
        return httpx.Response(200, json={"status": "ok"})

    client = client_with_transport(httpx.MockTransport(handler))

    assert asyncio.run(client.health()) == {"status": "ok"}


def test_authenticate_user_posts_internal_login_payload(
    backend_user_payload: dict[str, object],
):
    seen_payload = {}
    seen_api_key = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_api_key, seen_payload
        seen_payload = json.loads(request.content)
        seen_api_key = request.headers.get(API_KEY_HEADER_NAME)
        return httpx.Response(200, json=backend_user_payload)

    client = client_with_transport(httpx.MockTransport(handler))

    result = asyncio.run(client.authenticate_user("alice", "correct-password"))

    assert seen_payload == {
        "username": "alice",
        "password": "correct-password",
    }
    assert seen_api_key == "test-secret"
    assert result.username == "alice"
    assert result.user_id == 42


def test_authenticate_user_invalid_credentials_is_safe():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": "invalid_credentials",
                "message": "Invalid username or password.",
            },
        )

    client = client_with_transport(httpx.MockTransport(handler))

    try:
        asyncio.run(client.authenticate_user("alice", "wrong-password"))
    except BackendUserAuthenticationError as error:
        assert str(error) == "Invalid username or password."
        assert error.status_code == 403
        assert error.error_code == "invalid_credentials"
        assert "wrong-password" not in str(error)
    else:
        raise AssertionError("Expected BackendUserAuthenticationError")


def test_signup_user_posts_expected_payload():
    seen_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_payload
        seen_payload = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "success": True,
                "message": "Account created. Please sign in.",
                "user_id": 99,
                "username": "new-user",
                "created_at": "2026-05-28T10:00:00Z",
            },
        )

    client = client_with_transport(httpx.MockTransport(handler))

    result = asyncio.run(
        client.signup_user(
            username="new-user",
            password="correct horse battery staple",
            confirm_password="correct horse battery staple",
            display_name="New User",
        )
    )

    assert seen_payload == {
        "username": "new-user",
        "password": "correct horse battery staple",
        "confirm_password": "correct horse battery staple",
        "display_name": "New User",
    }
    assert result.success is True
    assert result.username == "new-user"


def test_signup_user_maps_duplicate_username_to_safe_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "error": "username_unavailable",
                "message": "That username is unavailable.",
            },
        )

    client = client_with_transport(httpx.MockTransport(handler))

    try:
        asyncio.run(
            client.signup_user(
                username="taken-user",
                password="correct horse battery staple",
                confirm_password="correct horse battery staple",
            )
        )
    except BackendConflictError as error:
        assert str(error) == "That username is unavailable."
        assert error.status_code == 409
    else:
        raise AssertionError("Expected BackendConflictError")


def test_signup_user_maps_weak_password_to_validation_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": "invalid_signup",
                "message": "Password is too weak. Use a longer unique password from a password manager.",
            },
        )

    client = client_with_transport(httpx.MockTransport(handler))

    try:
        asyncio.run(
            client.signup_user(
                username="new-user",
                password="password123",
                confirm_password="password123",
            )
        )
    except BackendValidationError as error:
        assert "too weak" in str(error)
        assert error.status_code == 400
    else:
        raise AssertionError("Expected BackendValidationError")


def test_signup_user_maps_disabled_signup_to_safe_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={
                "error": "signup_disabled",
                "message": "Account sign-up is not available right now.",
            },
        )

    client = client_with_transport(httpx.MockTransport(handler))

    try:
        asyncio.run(
            client.signup_user(
                username="new-user",
                password="correct horse battery staple",
                confirm_password="correct horse battery staple",
            )
        )
    except BackendFeatureDisabledError as error:
        assert str(error) == "Account sign-up is not available right now."
        assert error.status_code == 404
    else:
        raise AssertionError("Expected BackendFeatureDisabledError")


def test_missing_api_key_fails_before_protected_request():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("Protected request should not be sent without a key")

    client = FastAPIClient(
        BackendConfig(
            base_url="http://backend.test",
            timeout_seconds=5,
            streaming_enabled=True,
            api_key="",
        )
    )
    client._client = lambda: httpx.AsyncClient(  # noqa: SLF001
        base_url=client.config.base_url,
        transport=httpx.MockTransport(handler),
    )

    try:
        asyncio.run(client.chat_full("Define recursion", "definition"))
    except BackendAuthConfigurationError as error:
        assert "missing the backend API key" in str(error)
        assert "test-secret" not in str(error)
    else:
        raise AssertionError("Expected BackendAuthConfigurationError")


def test_backend_authentication_error_is_readable_and_safe():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers[API_KEY_HEADER_NAME] == "test-secret"
        return httpx.Response(
            401,
            json={
                "error": "authentication_failed",
                "message": "A valid API key is required.",
            },
        )

    client = client_with_transport(httpx.MockTransport(handler))

    try:
        asyncio.run(client.chat_full("Define recursion", "definition"))
    except BackendAuthenticationError as error:
        assert str(error) == "The Web UI could not authenticate with the backend."
        assert error.status_code == 401
        assert error.error_code == "authentication_failed"
        assert "test-secret" not in str(error)
    else:
        raise AssertionError("Expected BackendAuthenticationError")


def test_streaming_authentication_error_is_readable_and_safe():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers[API_KEY_HEADER_NAME] == "test-secret"
        return httpx.Response(
            401,
            json={
                "error": "authentication_failed",
                "message": "A valid API key is required.",
            },
        )

    client = client_with_transport(httpx.MockTransport(handler))

    async def request_stream():
        return [
            event
            async for event in client.chat_stream("Translate hello", "translation")
        ]

    try:
        asyncio.run(request_stream())
    except BackendAuthenticationError as error:
        assert str(error) == "The Web UI could not authenticate with the backend."
        assert error.status_code == 401
        assert error.error_code == "authentication_failed"
        assert "test-secret" not in str(error)
    else:
        raise AssertionError("Expected BackendAuthenticationError")


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
