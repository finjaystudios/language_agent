import asyncio
import logging
import sys
import time
from pathlib import Path

from rich.console import Console

ROOT_DIR = Path(__file__).resolve().parents[1]
if __package__ in {None, ""} and str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.application.conversation_memory import ConversationMemory  # noqa: E402
from app.application.intent_router import IntentRouter  # noqa: E402
from app.application.session_orchestrator import SessionOrchestrator  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.infrastructure.llm.runtime_config import (  # noqa: E402
    N_CTX,
    N_THREADS,
    assert_llama_cpp_gpu_offload_supported,
    assert_model_file_exists,
    assert_nvidia_gpu_visible,
    choose_gpu_layers,
    require_model_path,
)

console = Console()
logger = logging.getLogger(__name__)


async def main():
    configure_logging()
    logger.info("cli_start")
    try:
        from app.infrastructure.llm.local_model import LLMService  # noqa: E402
    except ImportError as error:
        raise RuntimeError(
            "The legacy embedded llama-cpp-python CLI runtime is not installed. "
            "Use llama-server for the default runtime, or install the optional "
            "legacy dependency to keep using `python -m app.cli.main`."
        ) from error
    model_path = require_model_path()
    assert_model_file_exists(model_path)
    logger.info("cli_gpu_visibility_check_start")
    assert_nvidia_gpu_visible()
    logger.info("cli_gpu_visibility_check_complete")
    logger.info("cli_llama_cpp_gpu_offload_check_start")
    assert_llama_cpp_gpu_offload_supported()
    logger.info("cli_llama_cpp_gpu_offload_check_complete")

    logger.info("cli_gpu_layer_selection_start")
    n_gpu_layers = choose_gpu_layers(model_path)
    logger.info("cli_gpu_layer_selection_complete n_gpu_layers=%s", n_gpu_layers)
    logger.info("cli_llm_service_initialization_start")
    llm_service = LLMService(
        model_path=model_path,
        n_ctx=N_CTX,
        n_threads=N_THREADS,
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
