import json
from typing import Iterator

from llama_cpp import Llama

from app.llm.schemas import LANGUAGE_RESPONSE_SCHEMA, LITE_LANGUAGE_RESPONSE_SCHEMA
from processor_selection import (
    MODEL_PATH,
    N_CTX,
    assert_nvidia_gpu_visible, 
    assert_llama_cpp_gpu_offload_supported, 
    choose_gpu_layers,
)


assert_nvidia_gpu_visible()
assert_llama_cpp_gpu_offload_supported()

N_GPU_LAYERS = choose_gpu_layers(MODEL_PATH)

class LLMService:
    def __init__(
        self,
        model_path: str,
        n_ctx: int = 4096,
        n_threads: int = 4,
        n_gpu_layers: int = 35,
    ):
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            offload_kqv=True,
            verbose=False,
        )

    def ask_llm(self, system_prompt: str, user_prompt: str, schema: dict) -> dict:
        result = self.llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=500,
            response_format={
                "type": "json_object",
                "schema": schema,
            },
        )

        content = result["choices"][0]["message"]["content"]
        return json.loads(content)


    def stream_llm(self, system_prompt: str, user_prompt: str) -> Iterator[str]:
        """
        Stream raw model text chunks.
        """
        stream = self.llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=500,
            stream=True,
        )

        for chunk in stream:
            delta = chunk["choices"][0].get("delta", {})
            token = delta.get("content")
            if token:
                yield token
