from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx

from app.core.config import AppSettings

logger = logging.getLogger(__name__)


class LlamaServerGatewayError(RuntimeError):
    pass


class LlamaServerUnavailableError(LlamaServerGatewayError):
    pass


class LlamaServerTimeoutError(TimeoutError):
    pass


class LlamaServerMalformedResponseError(LlamaServerGatewayError):
    pass


class LlamaServerInterruptedError(LlamaServerGatewayError):
    pass


class LlamaServerGateway:
    def __init__(
        self,
        settings: AppSettings,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self.base_url = settings.llama_server_url.rstrip("/")
        self.client = client or httpx.Client(base_url=self.base_url)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.settings.llama_server_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llama_server_api_key}"
        return headers

    def _build_payload(
        self,
        *,
        messages: list[dict[str, str]],
        stream: bool,
        schema: dict[str, Any] | None = None,
        **generation_parameters: Any,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"messages": messages, "stream": stream}
        if self.settings.llama_server_model_name:
            payload["model"] = self.settings.llama_server_model_name
        for key, value in generation_parameters.items():
            if value is not None:
                payload[key] = value
        if schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_response",
                    "schema": schema,
                },
            }
        return payload

    def _post_json(
        self, payload: dict[str, Any], timeout_seconds: int
    ) -> dict[str, Any]:
        try:
            response = self.client.post(
                "/v1/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=timeout_seconds,
            )
        except httpx.TimeoutException as error:
            raise LlamaServerTimeoutError("llama-server timed out.") from error
        except httpx.ConnectError as error:
            raise LlamaServerUnavailableError("llama-server is unavailable.") from error
        except httpx.RequestError as error:
            raise LlamaServerGatewayError("llama-server request failed.") from error
        if response.status_code != 200:
            raise LlamaServerGatewayError(
                f"llama-server returned HTTP {response.status_code}."
            )
        try:
            return response.json()
        except ValueError as error:
            raise LlamaServerMalformedResponseError(
                "llama-server returned malformed JSON."
            ) from error

    def _extract_message_content(self, response_payload: dict[str, Any]) -> str:
        choices = response_payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LlamaServerMalformedResponseError(
                "llama-server response did not contain any choices."
            )
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise LlamaServerMalformedResponseError(
                "llama-server response did not contain a message payload."
            )
        content = message.get("content")
        if not isinstance(content, str):
            raise LlamaServerMalformedResponseError(
                "llama-server response did not contain text content."
            )
        return content

    def ask_llm_sync(
        self,
        *,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        **generation_parameters: Any,
    ) -> dict[str, Any]:
        payload = self._build_payload(
            messages=messages,
            stream=False,
            schema=schema,
            **generation_parameters,
        )
        response_payload = self._post_json(
            payload,
            self.settings.llama_server_timeout_seconds,
        )
        content = self._extract_message_content(response_payload)
        try:
            return json.loads(content)
        except json.JSONDecodeError as error:
            raise LlamaServerMalformedResponseError(
                "llama-server returned malformed structured output."
            ) from error

    def generate_text_sync(
        self,
        *,
        messages: list[dict[str, str]],
        **generation_parameters: Any,
    ) -> str:
        payload = self._build_payload(
            messages=messages,
            stream=False,
            **generation_parameters,
        )
        response_payload = self._post_json(
            payload,
            self.settings.llama_server_timeout_seconds,
        )
        return self._extract_message_content(response_payload)

    def stream_llm_sync(
        self,
        *,
        messages: list[dict[str, str]],
        **generation_parameters: Any,
    ) -> Iterator[dict[str, Any]]:
        payload = self._build_payload(
            messages=messages,
            stream=True,
            **generation_parameters,
        )
        saw_terminal_event = False
        try:
            with self.client.stream(
                "POST",
                "/v1/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self.settings.llama_server_stream_timeout_seconds,
            ) as response:
                if response.status_code != 200:
                    raise LlamaServerGatewayError(
                        f"llama-server returned HTTP {response.status_code}."
                    )
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    raw_event = line[5:].strip()
                    if not raw_event:
                        continue
                    if raw_event == "[DONE]":
                        saw_terminal_event = True
                        break
                    try:
                        event = json.loads(raw_event)
                    except json.JSONDecodeError as error:
                        raise LlamaServerMalformedResponseError(
                            "llama-server returned malformed stream data."
                        ) from error
                    choices = event.get("choices")
                    if not isinstance(choices, list) or not choices:
                        raise LlamaServerMalformedResponseError(
                            "llama-server stream event did not contain choices."
                        )
                    choice = choices[0]
                    if choice.get("finish_reason") is not None:
                        saw_terminal_event = True
                    delta = choice.get("delta")
                    if not isinstance(delta, dict):
                        continue
                    token = delta.get("content")
                    if isinstance(token, str) and token:
                        yield {"choices": [{"delta": {"content": token}}]}
        except httpx.TimeoutException as error:
            raise LlamaServerTimeoutError("llama-server timed out.") from error
        except httpx.ConnectError as error:
            raise LlamaServerUnavailableError("llama-server is unavailable.") from error
        except httpx.RequestError as error:
            raise LlamaServerGatewayError("llama-server request failed.") from error

        if not saw_terminal_event:
            raise LlamaServerInterruptedError("llama-server interrupted generation.")

    def check_health(self) -> bool:
        health_path = self.settings.llama_server_health_path or "/health"
        try:
            response = self.client.get(
                health_path,
                headers=self._headers(),
                timeout=self.settings.llama_server_timeout_seconds,
            )
        except httpx.RequestError:
            return False
        return response.status_code == 200

    async def ask_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict[str, Any],
        mode: str | None = None,
    ) -> dict[str, Any]:
        logger.info(
            "llama_server_ask_start mode=%s system_prompt_length=%d user_prompt_length=%d",
            mode,
            len(system_prompt),
            len(user_prompt),
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = await asyncio.to_thread(
            self.ask_llm_sync,
            messages=messages,
            schema=schema,
            temperature=0.1,
            max_tokens=2000,
        )
        logger.info("llama_server_ask_complete mode=%s", mode)
        return result

    async def stream_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        mode: str | None = None,
    ) -> AsyncIterator[str]:
        logger.info(
            "llama_server_stream_start mode=%s system_prompt_length=%d user_prompt_length=%d",
            mode,
            len(system_prompt),
            len(user_prompt),
        )
        queue: asyncio.Queue[Any] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        done = object()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        def collect_tokens() -> None:
            try:
                for chunk in self.stream_llm_sync(
                    messages=messages,
                    temperature=0.1,
                    max_tokens=2000,
                ):
                    delta = chunk["choices"][0].get("delta", {})
                    token = delta.get("content")
                    if token:
                        loop.call_soon_threadsafe(queue.put_nowait, token)
            except Exception as error:
                loop.call_soon_threadsafe(queue.put_nowait, error)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, done)

        worker = asyncio.create_task(asyncio.to_thread(collect_tokens))

        while True:
            item = await queue.get()
            if item is done:
                break
            if isinstance(item, Exception):
                await worker
                raise item
            yield item

        await worker
        logger.info("llama_server_stream_complete mode=%s", mode)

    async def cancel_job(self, job_id: str) -> None:
        logger.info("llama_server_cancel_unsupported job_id=%s", job_id)
        return None
