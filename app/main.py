import asyncio
import logging
import sys
import time
from pathlib import Path

from rich.console import Console

ROOT_DIR = Path(__file__).resolve().parents[1]
if __package__ in {None, ""} and str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.llm.service import LLMService  # noqa: E402
from app.logging_config import configure_logging  # noqa: E402
from app.memory.short_term import ConversationMemory  # noqa: E402
from app.orchestration.router import IntentRouter  # noqa: E402
from app.orchestration.session import SessionOrchestrator  # noqa: E402
from app.processor_selection import (  # noqa: E402
    MODEL_PATH,
    N_CTX,
    assert_llama_cpp_gpu_offload_supported,
    assert_nvidia_gpu_visible,
    choose_gpu_layers,
)

console = Console()
logger = logging.getLogger(__name__)


async def main():
    configure_logging()
    logger.info("cli_start")
    logger.info("cli_gpu_visibility_check_start")
    assert_nvidia_gpu_visible()
    logger.info("cli_gpu_visibility_check_complete")
    logger.info("cli_llama_cpp_gpu_offload_check_start")
    assert_llama_cpp_gpu_offload_supported()
    logger.info("cli_llama_cpp_gpu_offload_check_complete")

    logger.info("cli_gpu_layer_selection_start")
    n_gpu_layers = choose_gpu_layers(MODEL_PATH)
    logger.info("cli_gpu_layer_selection_complete n_gpu_layers=%s", n_gpu_layers)
    logger.info("cli_llm_service_initialization_start")
    llm_service = LLMService(
        model_path=MODEL_PATH,
        n_ctx=N_CTX,
        n_threads=4,
        n_gpu_layers=n_gpu_layers,
    )
    logger.info("cli_llm_service_initialization_complete")

    memory = ConversationMemory(max_turns=5)
    router = IntentRouter(llm_service)
    orchestrator = SessionOrchestrator(llm_service, router, memory)

    console.print("[bold green]Private Language Agent[/bold green]")
    console.print("Modes: translation, definition, learning")
    console.print("Type 'exit' to quit.\n")

    while True:
        user_input = (await asyncio.to_thread(input, "You: ")).strip()
        if user_input.lower() in {"exit", "quit"}:
            logger.info("cli_exit_requested")
            break

        start_time = time.perf_counter()
        logger.info("cli_turn_start message_length=%d", len(user_input))
        _ = await orchestrator.handle_turn(user_input, console)
        end_time = time.perf_counter() - start_time
        logger.info("cli_turn_complete elapsed_seconds=%.3f", end_time)
        console.print(f"time: {end_time}")


if __name__ == "__main__":
    asyncio.run(main())
