import asyncio
import time

from rich.console import Console

from llm.service import LLMService
from memory.short_term import ConversationMemory
from orchestration.router import IntentRouter
from orchestration.session import SessionOrchestrator
from processor_selection import (
    MODEL_PATH,
    N_CTX,
    assert_llama_cpp_gpu_offload_supported,
    assert_nvidia_gpu_visible,
    choose_gpu_layers,
)

console = Console()


async def main():
    assert_nvidia_gpu_visible()
    assert_llama_cpp_gpu_offload_supported()

    n_gpu_layers = choose_gpu_layers(MODEL_PATH)
    llm_service = LLMService(
        model_path=MODEL_PATH,
        n_ctx=N_CTX,
        n_threads=4,
        n_gpu_layers=n_gpu_layers,
    )

    memory = ConversationMemory(max_turns=5)
    router = IntentRouter(llm_service)
    orchestrator = SessionOrchestrator(llm_service, router, memory)

    console.print("[bold green]Private Language Agent[/bold green]")
    console.print("Modes: translation, definition, learning")
    console.print("Type 'exit' to quit.\n")

    while True:
        user_input = (await asyncio.to_thread(input, "You: ")).strip()
        if user_input.lower() in {"exit", "quit"}:
            break

        start_time = time.perf_counter()
        _ = await orchestrator.handle_turn(user_input, console)
        end_time = time.perf_counter() - start_time
        console.print(f"time: {end_time}")


if __name__ == "__main__":
    asyncio.run(main())
