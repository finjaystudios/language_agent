import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(
        self,
        model_path: str,
        n_ctx: int = 4096,
        n_threads: int = 4,
        n_gpu_layers: int = 35,
    ):
        logger.info(
            "llm_service_create_start model_path=%s n_ctx=%d n_threads=%d n_gpu_layers=%s",
            model_path,
            n_ctx,
            n_threads,
            n_gpu_layers,
        )
        from llama_cpp import Llama

        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            offload_kqv=True,
            verbose=False,
        )
        logger.info("llm_service_create_complete")

    def ask_llm_sync(
        self,
        *,
        messages: list[dict[str, str]],
        schema: dict,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> dict:
        result = self.llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={
                "type": "json_object",
                "schema": schema,
            },
        )
        content = result["choices"][0]["message"]["content"]
        return json.loads(content)

    def generate_text_sync(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        result = self.llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return result["choices"][0]["message"]["content"]

    def stream_llm_sync(
        self,
        *,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1200,
    ):
        return self.llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

    async def ask_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: dict,
        mode: str | None = None,
    ) -> dict:
        logger.info(
            "llm_ask_start mode=%s system_prompt_length=%d user_prompt_length=%d",
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
        )
        logger.info("llm_ask_complete mode=%s", mode)
        return result

    async def stream_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        mode: str | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream raw model text chunks.
        """
        logger.info(
            "llm_stream_start mode=%s system_prompt_length=%d user_prompt_length=%d",
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
                stream = self.stream_llm_sync(messages=messages)

                for chunk in stream:
                    delta = chunk["choices"][0].get("delta", {})
                    token = delta.get("content")
                    if token:
                        loop.call_soon_threadsafe(queue.put_nowait, token)
            except Exception as error:
                logger.exception("llm_stream_collect_tokens_failed")
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
            logger.debug("llm_stream_token token_length=%d", len(item))
            yield item

        await worker
        logger.info("llm_stream_complete")


def create_local_llm_service() -> LLMService:
    from app.processor_selection import (
        N_CTX,
        N_THREADS,
        assert_llama_cpp_gpu_offload_supported,
        assert_model_file_exists,
        assert_nvidia_gpu_visible,
        choose_gpu_layers,
        require_model_path,
    )

    model_path = require_model_path()
    assert_model_file_exists(model_path)
    logger.info(
        "local_llm_service_create_start model_path=%s n_ctx=%s n_threads=%s",
        model_path,
        N_CTX,
        N_THREADS,
    )
    logger.info("gpu_visibility_check_start")
    assert_nvidia_gpu_visible()
    logger.info("gpu_visibility_check_complete")
    logger.info("llama_cpp_gpu_offload_check_start")
    assert_llama_cpp_gpu_offload_supported()
    logger.info("llama_cpp_gpu_offload_check_complete")
    logger.info("gpu_layer_selection_start")
    n_gpu_layers = choose_gpu_layers(model_path)
    logger.info("gpu_layer_selection_complete n_gpu_layers=%s", n_gpu_layers)
    logger.info("llm_service_initialization_start")
    return LLMService(
        model_path=model_path,
        n_ctx=N_CTX,
        n_threads=N_THREADS,
        n_gpu_layers=n_gpu_layers,
    )
