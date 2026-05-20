from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT_SECONDS = 120.0


class BackendClientError(RuntimeError):
    """Readable backend communication error for the Chainlit UI."""


@dataclass(frozen=True)
class BackendConfig:
    base_url: str
    timeout_seconds: float
    streaming_enabled: bool

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
        try:
            async with self._client() as client:
                response = await client.get("/health")
        except httpx.RequestError as error:
            raise BackendClientError(format_request_error(error)) from error
        return self._json_response(response)

    async def chat_full(self, message: str, mode: str | None) -> dict[str, Any]:
        payload = build_chat_payload(message, mode)
        try:
            async with self._client() as client:
                response = await client.post("/api/chat", json=payload)
        except httpx.RequestError as error:
            raise BackendClientError(format_request_error(error)) from error
        return self._json_response(response)

    async def chat_stream(
        self,
        message: str,
        mode: str | None,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = build_chat_payload(message, mode)
        payload["stream"] = True

        try:
            async with self._client() as client:
                async with client.stream(
                    "POST",
                    "/api/chat/stream",
                    json=payload,
                ) as response:
                    self._raise_for_error(response)
                    async for line in response.aiter_lines():
                        event = parse_sse_line(line)
                        if event is not None:
                            yield event
        except httpx.RequestError as error:
            raise BackendClientError(format_request_error(error)) from error

    def _client(self) -> httpx.AsyncClient:
        timeout = httpx.Timeout(self.config.timeout_seconds)
        return httpx.AsyncClient(base_url=self.config.base_url, timeout=timeout)

    def _json_response(self, response: httpx.Response) -> dict[str, Any]:
        self._raise_for_error(response)
        try:
            data = response.json()
        except ValueError as error:
            raise BackendClientError(
                "Backend returned an invalid JSON response."
            ) from error
        if not isinstance(data, dict):
            raise BackendClientError("Backend returned an unexpected response shape.")
        return data

    def _raise_for_error(self, response: httpx.Response) -> None:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            raise BackendClientError(format_backend_error(error.response)) from error


def parse_sse_line(line: str) -> dict[str, Any] | None:
    if not line.startswith("data:"):
        return None

    raw_data = line.removeprefix("data:").strip()
    if not raw_data:
        return None

    try:
        event = json.loads(raw_data)
    except json.JSONDecodeError as error:
        raise BackendClientError(
            "Backend returned an invalid streaming event."
        ) from error

    if not isinstance(event, dict):
        raise BackendClientError("Backend returned an unexpected streaming event.")
    return event


def format_backend_error(response: httpx.Response) -> str:
    fallback = f"Backend request failed with HTTP {response.status_code}."
    try:
        data = response.json()
    except ValueError:
        return fallback

    if not isinstance(data, dict):
        return fallback

    message = data.get("message")
    error = data.get("error")
    if isinstance(message, str) and isinstance(error, str):
        return f"{message} ({error})"
    if isinstance(message, str):
        return message
    return fallback


def format_request_error(error: httpx.RequestError) -> str:
    return f"Could not connect to the FastAPI backend: {error}"
