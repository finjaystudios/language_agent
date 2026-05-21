from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT_SECONDS = 120.0
API_KEY_HEADER_NAME = "X-API-Key"
logger = logging.getLogger(__name__)


class BackendClientError(RuntimeError):
    """Readable backend communication error for the Chainlit UI."""

    category = "backend_error"


class BackendUnavailableError(BackendClientError):
    category = "backend_unavailable"


class BackendTimeoutError(BackendClientError):
    category = "backend_timeout"


class BackendHTTPError(BackendClientError):
    category = "backend_http_error"

    def __init__(self, message: str, *, status_code: int, error_code: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class BackendAuthenticationError(BackendHTTPError):
    category = "backend_authentication"


class BackendAuthConfigurationError(BackendClientError):
    category = "backend_auth_configuration"


class BackendInvalidResponseError(BackendClientError):
    category = "backend_invalid_response"


class BackendStreamError(BackendClientError):
    category = "backend_stream_error"


@dataclass(frozen=True)
class BackendConfig:
    base_url: str
    timeout_seconds: float
    streaming_enabled: bool
    api_key: str

    @classmethod
    def from_env(cls) -> BackendConfig:
        timeout_raw = os.getenv(
            "WEBUI_REQUEST_TIMEOUT_SECONDS",
            str(DEFAULT_TIMEOUT_SECONDS),
        )
        try:
            timeout_seconds = float(timeout_raw)
        except ValueError:
            timeout_seconds = DEFAULT_TIMEOUT_SECONDS

        return cls(
            base_url=os.getenv("FASTAPI_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            timeout_seconds=timeout_seconds,
            streaming_enabled=parse_bool(
                os.getenv("WEBUI_STREAMING_ENABLED", "true"),
                default=True,
            ),
            api_key=os.getenv("FASTAPI_API_KEY", "").strip(),
        )


def parse_bool(value: str, *, default: bool) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def build_chat_payload(message: str, mode: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "message": message,
        "metadata": {"client": "chainlit-webui"},
    }
    if mode is not None:
        payload["mode"] = mode
    return payload


class FastAPIClient:
    def __init__(self, config: BackendConfig | None = None) -> None:
        self.config = config or BackendConfig.from_env()

    async def health(self) -> dict[str, Any]:
        logger.info(
            "webui_backend_health_check_start base_url=%s", self.config.base_url
        )
        try:
            async with self._client() as client:
                response = await client.get("/health")
        except httpx.TimeoutException as error:
            logger.warning(
                "webui_backend_health_timeout base_url=%s", self.config.base_url
            )
            raise BackendTimeoutError(
                "The FastAPI backend did not respond before the request timed out."
            ) from error
        except httpx.RequestError as error:
            logger.warning(
                "webui_backend_health_unavailable base_url=%s error_type=%s",
                self.config.base_url,
                type(error).__name__,
            )
            raise BackendUnavailableError(format_request_error(error)) from error
        data = self._json_response(response)
        logger.info("webui_backend_health_check_complete status=%s", data.get("status"))
        return data

    async def chat_full(self, message: str, mode: str | None) -> dict[str, Any]:
        payload = build_chat_payload(message, mode)
        logger.info(
            "webui_chat_full_request_start base_url=%s mode=%s message_length=%d",
            self.config.base_url,
            mode,
            len(message),
        )
        try:
            async with self._client() as client:
                response = await client.post(
                    "/api/chat",
                    json=payload,
                    headers=self._auth_headers(),
                )
        except httpx.TimeoutException as error:
            logger.warning("webui_chat_full_timeout mode=%s", mode)
            raise BackendTimeoutError(
                "The FastAPI backend timed out while generating a response."
            ) from error
        except httpx.RequestError as error:
            logger.warning(
                "webui_chat_full_unavailable mode=%s error_type=%s",
                mode,
                type(error).__name__,
            )
            raise BackendUnavailableError(format_request_error(error)) from error
        data = self._json_response(response)
        logger.info(
            "webui_chat_full_request_complete mode=%s response_mode=%s",
            mode,
            data.get("mode"),
        )
        return data

    async def chat_stream(
        self,
        message: str,
        mode: str | None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = build_chat_payload(message, mode)
        payload["stream"] = True

        logger.info(
            "webui_chat_stream_request_start base_url=%s mode=%s message_length=%d",
            self.config.base_url,
            mode,
            len(message),
        )
        try:
            async with self._client() as client:
                async with client.stream(
                    "POST",
                    "/api/chat/stream",
                    json=payload,
                    headers=self._auth_headers(),
                ) as response:
                    if response.is_error:
                        await response.aread()
                    self._raise_for_error(response)
                    async for line in response.aiter_lines():
                        event = parse_sse_line(line)
                        if event is not None:
                            yield event
            logger.info("webui_chat_stream_request_complete mode=%s", mode)
        except httpx.TimeoutException as error:
            logger.warning("webui_chat_stream_timeout mode=%s", mode)
            raise BackendTimeoutError(
                "The FastAPI backend timed out while streaming a response."
            ) from error
        except httpx.RequestError as error:
            logger.warning(
                "webui_chat_stream_unavailable mode=%s error_type=%s",
                mode,
                type(error).__name__,
            )
            raise BackendUnavailableError(format_request_error(error)) from error

    def _client(self) -> httpx.AsyncClient:
        timeout = httpx.Timeout(self.config.timeout_seconds)
        return httpx.AsyncClient(base_url=self.config.base_url, timeout=timeout)

    def _auth_headers(self) -> dict[str, str]:
        if not self.config.api_key:
            raise BackendAuthConfigurationError(
                "The Web UI is missing the backend API key."
            )
        return {API_KEY_HEADER_NAME: self.config.api_key}

    def _json_response(self, response: httpx.Response) -> dict[str, Any]:
        self._raise_for_error(response)
        try:
            data = response.json()
        except ValueError as error:
            raise BackendInvalidResponseError(
                "Backend returned an invalid JSON response."
            ) from error
        if not isinstance(data, dict):
            raise BackendInvalidResponseError(
                "Backend returned an unexpected response shape."
            )
        return data

    def _raise_for_error(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            message, error_code = format_backend_error(error.response)
            if error.response.status_code == 401:
                raise BackendAuthenticationError(
                    "The Web UI could not authenticate with the backend.",
                    status_code=error.response.status_code,
                    error_code=error_code,
                ) from error
            raise BackendHTTPError(
                message,
                status_code=error.response.status_code,
                error_code=error_code,
            ) from error


def parse_sse_line(line: str) -> dict[str, Any] | None:
    if not line.startswith("data:"):
        return None

    raw_data = line.removeprefix("data:").strip()
    if not raw_data:
        return None

    try:
        event = json.loads(raw_data)
    except json.JSONDecodeError as error:
        raise BackendStreamError(
            "Backend returned an invalid streaming event."
        ) from error

    if not isinstance(event, dict):
        raise BackendStreamError("Backend returned an unexpected streaming event.")
    return event


def format_backend_error(response: httpx.Response) -> tuple[str, str]:
    fallback = f"Backend request failed with HTTP {response.status_code}."
    try:
        data = response.json()
    except ValueError:
        return fallback, ""

    if not isinstance(data, dict):
        return fallback, ""

    message = data.get("message")
    error = data.get("error")
    if isinstance(message, str) and isinstance(error, str):
        return f"{message} ({error})", error
    if isinstance(message, str):
        return message, ""
    return fallback, ""


def format_request_error(error: httpx.RequestError) -> str:
    message = str(error).strip()
    if message:
        return f"Could not connect to the FastAPI backend: {message}"
    return "Could not connect to the FastAPI backend."


def format_ui_error(error: BackendClientError) -> str:
    if isinstance(error, BackendUnavailableError):
        return (
            "**Service unavailable**\n\n"
            "The language service is not reachable right now. Start the local "
            "service, then try again."
        )
    if isinstance(error, BackendTimeoutError):
        return (
            "**Service timeout**\n\n"
            "The language service took too long to answer. It may still be "
            "loading or working on your request. Try again in a moment."
        )
    if isinstance(error, BackendHTTPError):
        if isinstance(error, BackendAuthenticationError):
            return (
                "**Backend authentication failed**\n\n"
                "The Web UI could not authenticate with the backend. Check that "
                "the Web UI and FastAPI backend use the same API key."
            )
        if error.error_code == "unsupported_mode":
            return (
                "**Unsupported mode**\n\n"
                "This response mode is not available for that request. Try Auto "
                "or choose a different mode."
            )
        return (
            "**Request failed**\n\n"
            "The language service could not complete the request. Try again, or "
            "choose a different response mode."
        )
    if isinstance(error, BackendInvalidResponseError):
        return (
            "**Response could not be displayed**\n\n"
            "The language service answered in a format this chat could not "
            "display. Try again."
        )
    if isinstance(error, BackendStreamError):
        return (
            "**Streaming error**\n\n"
            "The response was interrupted while it was being displayed. Try "
            "again, or choose a full-response mode."
        )
    if isinstance(error, BackendAuthConfigurationError):
        return (
            "**Backend authentication is not configured**\n\n"
            "The Web UI is missing the backend API key. Configure it on the "
            "server and try again."
        )
    return "**Request failed**\n\nThe chat could not complete the request. Try again."
