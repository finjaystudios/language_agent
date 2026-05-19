from rich.console import Console
import time

from llm.service import LLMService
from memory.short_term import ConversationMemory
from orchestration.router import IntentRouter
from orchestration.session import SessionOrchestrator
from processor_selection import (
    MODEL_PATH,
    N_CTX,
    assert_nvidia_gpu_visible, 
    assert_llama_cpp_gpu_offload_supported, 
    choose_gpu_layers,
)


console = Console()


def main():
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
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        
        start_time = time.perf_counter()
        _ = orchestrator.handle_turn(user_input, console)
        end_time = time.perf_counter() - start_time
        console.print(f"time: {end_time}")

        # JSON Prompt
        # result = ask_llm(SYSTEM_PROMPT, prompt)
        # end_time = time.perf_counter() - start_time

        # assistant_reply = result.get("response", "")
        # memory.add_turn(user_text, assistant_reply)
        
        # console.print_json(data=result)

        # STREAM Prompt
        # assistant_reply = ""
        # console.print("[bold cyan]Assistant:[/bold cyan] ", end="")

        # for token in stream_llm(SYSTEM_PROMPT, prompt):
        #     assistant_reply += token
        #     console.print(token, end="")

        # console.print()
        # memory.add_turn(user_text, assistant_reply)


if __name__ == "__main__":
    main()
