import json
from typing import Iterator

from llama_cpp import Llama

from schema import LANGUAGE_RESPONSE_SCHEMA, LITE_LANGUAGE_RESPONSE_SCHEMA
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

llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=N_CTX,
    n_threads=4,
    n_gpu_layers=N_GPU_LAYERS,
    main_gpu=0,
    offload_kqv=True,
    verbose=True,
)


def ask_llm(system_prompt: str, user_prompt: str) -> dict:
    result = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=1000,
        response_format={
            "type": "json_object",
            "schema": LITE_LANGUAGE_RESPONSE_SCHEMA,
        },
    )

    content = result["choices"][0]["message"]["content"]
    return json.loads(content)


def stream_llm(system_prompt: str, user_prompt: str) -> Iterator[str]:
    """
    Stream raw model text chunks.
    """
    stream = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=1000,
        stream=True,
    )

    for chunk in stream:
        delta = chunk["choices"][0].get("delta", {})
        token = delta.get("content")
        if token:
            yield token
