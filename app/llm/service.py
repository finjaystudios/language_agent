import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from llama_cpp import Llama

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
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            offload_kqv=True,
            verbose=False,
        )
        logger.info("llm_service_create_complete")

    async def ask_llm(self, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        logger.info(
            "llm_ask_start system_prompt_length=%d user_prompt_length=%d",
            len(system_prompt),
            len(user_prompt),
        )
        result = await asyncio.to_thread(
            self.llm.create_chat_completion,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=1200,
            response_format={
                "type": "json_object",
                "schema": schema,
            },
        )

        content = result["choices"][0]["message"]["content"]
        logger.info("llm_ask_complete response_length=%d", len(content))
        return json.loads(content)

    async def stream_llm(
        self, system_prompt: str, user_prompt: str
    ) -> AsyncIterator[str]:
        """
        Stream raw model text chunks.
        """
        logger.info(
            "llm_stream_start system_prompt_length=%d user_prompt_length=%d",
            len(system_prompt),
            len(user_prompt),
        )
        queue: asyncio.Queue[Any] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        done = object()

        def collect_tokens() -> None:
            try:
                stream = self.llm.create_chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.1,
                    max_tokens=1200,
                    stream=True,
                )

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
