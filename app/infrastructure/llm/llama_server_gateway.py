from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncIterator, Iterator
from contextlib import suppress
from typing import Any

import httpx

from app.core.config import AppSettings
from app.core.model_profiles import ModelProfile, ModelProfiles, get_model_profiles

logger = logging.getLogger(__name__)
_THINK_OPEN_TAG = "<think>"
_THINK_CLOSE_TAG = "</think>"
_THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


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
        model_profiles: ModelProfiles | None = None,
    ) -> None:
        self.settings = settings
        self.base_url = settings.llama_server_url.rstrip("/")
        self.client = client or httpx.Client(base_url=self.base_url)
        self.model_profiles = model_profiles or get_model_profiles(
            settings.model_profiles_path
        )

    def _request_timeout(self, timeout_seconds: int) -> httpx.Timeout:
        return httpx.Timeout(
            timeout_seconds,
            connect=timeout_seconds,
            read=timeout_seconds,
            write=timeout_seconds,
            pool=timeout_seconds,
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.settings.llama_server_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llama_server_api_key}"
        return headers

    def _apply_prompt_control(
        self,
        messages: list[dict[str, str]],
        prompt_control: str,
    ) -> list[dict[str, str]]:
        normalized_messages = [dict(message) for message in messages]
        if not prompt_control:
            return normalized_messages
        for message in normalized_messages:
            if message.get("role") == "system":
                content = message.get("content", "")
                if prompt_control not in content.splitlines():
                    message["content"] = (
                        f"{content.rstrip()}\n\n{prompt_control}"
                        if content.strip()
                        else prompt_control
                    )
                return normalized_messages
        return [{"role": "system", "content": prompt_control}, *normalized_messages]

    def _profile_for_mode(self, mode: str | None) -> ModelProfile:
        return self.model_profiles.select(mode)

    def _merge_generation_parameters(
        self,
        profile: ModelProfile,
        generation_parameters: dict[str, Any],
        *,
        stream: bool,
    ) -> dict[str, Any]:
        resolved = profile.generation_parameters()
        for key, value in generation_parameters.items():
            if value is not None:
                resolved[key] = value
        resolved["stream"] = stream
        if "model" not in resolved or not resolved["model"]:
            if self.settings.llama_server_model_name:
                resolved["model"] = self.settings.llama_server_model_name
            else:
                resolved.pop("model", None)
        return resolved

    def _build_payload(
        self,
        *,
        messages: list[dict[str, str]],
        mode: str | None,
        stream: bool,
        schema: dict[str, Any] | None = None,
        **generation_parameters: Any,
    ) -> dict[str, Any]:
        profile = self._profile_for_mode(mode)
        payload: dict[str, Any] = self._merge_generation_parameters(
            profile,
            generation_parameters,
            stream=stream,
        )
        payload["messages"] = self._apply_prompt_control(
            messages,
            profile.prompt_control,
        )
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
                timeout=self._request_timeout(timeout_seconds),
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
        return self._strip_think_blocks(content).strip()

    def _strip_think_blocks(self, content: str) -> str:
        stripped = _THINK_BLOCK_PATTERN.sub("", content)
        stripped = stripped.replace(_THINK_OPEN_TAG, "").replace(_THINK_CLOSE_TAG, "")
        return stripped

    def ask_llm_sync(
        self,
        *,
        messages: list[dict[str, str]],
        schema: dict[str, Any],
        mode: str | None = None,
        **generation_parameters: Any,
    ) -> dict[str, Any]:
        payload = self._build_payload(
            messages=messages,
            mode=mode,
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
        mode: str | None = None,
        **generation_parameters: Any,
    ) -> str:
        payload = self._build_payload(
            messages=messages,
            mode=mode,
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
        mode: str | None = None,
        **generation_parameters: Any,
    ) -> Iterator[dict[str, Any]]:
        payload = self._build_payload(
            messages=messages,
            mode=mode,
            stream=True,
            **generation_parameters,
        )
        saw_terminal_event = False
        think_filter = _ThinkStreamFilter()
        try:
            with self.client.stream(
                "POST",
                "/v1/chat/completions",
                json=payload,
                headers=self._headers(),
                timeout=self._request_timeout(
                    self.settings.llama_server_stream_timeout_seconds
                ),
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
                        visible_token = think_filter.feed(token)
                        if visible_token:
                            yield {"choices": [{"delta": {"content": visible_token}}]}
        except httpx.TimeoutException as error:
            raise LlamaServerTimeoutError("llama-server timed out.") from error
        except httpx.ConnectError as error:
            raise LlamaServerUnavailableError("llama-server is unavailable.") from error
        except httpx.RequestError as error:
            raise LlamaServerGatewayError("llama-server request failed.") from error

        if not saw_terminal_event:
            raise LlamaServerInterruptedError("llama-server interrupted generation.")
        trailing_content = think_filter.flush()
        if trailing_content:
            yield {"choices": [{"delta": {"content": trailing_content}}]}

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
            mode=mode,
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
                    mode=mode,
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

    def close(self) -> None:
        with suppress(Exception):
            self.client.close()


class _ThinkStreamFilter:
    def __init__(self) -> None:
        self._buffer = ""
        self._inside_think = False

    def _overlap_suffix(self, text: str, tag: str) -> str:
        limit = min(len(text), len(tag) - 1)
        for size in range(limit, 0, -1):
            if text[-size:].lower() == tag[:size]:
                return text[-size:]
        return ""

    def feed(self, chunk: str) -> str:
        text = self._buffer + chunk
        self._buffer = ""
        visible_parts: list[str] = []

        while text:
            if self._inside_think:
                close_index = text.lower().find(_THINK_CLOSE_TAG)
                if close_index == -1:
                    self._buffer = self._overlap_suffix(text, _THINK_CLOSE_TAG)
                    return ""
                text = text[close_index + len(_THINK_CLOSE_TAG) :]
                self._inside_think = False
                continue

            open_index = text.lower().find(_THINK_OPEN_TAG)
            if open_index == -1:
                tail = self._overlap_suffix(text, _THINK_OPEN_TAG)
                if tail:
                    visible_parts.append(text[: -len(tail)])
                    self._buffer = tail
                else:
                    visible_parts.append(text)
                return "".join(visible_parts)

            visible_parts.append(text[:open_index])
            text = text[open_index + len(_THINK_OPEN_TAG) :]
            self._inside_think = True

        return "".join(visible_parts)

    def flush(self) -> str:
        if self._inside_think:
            self._buffer = ""
            return ""
        trailing = self._buffer
        self._buffer = ""
        return trailing
