from rich.console import Console
import time

from llm import ask_llm, stream_llm
from memory import ConversationMemory
from prompts import SYSTEM_PROMPT, TASK_PROMPT, LITE_TASK_PROMPT

console = Console()


def main():
    memory = ConversationMemory(max_turns=5)

    console.print("[bold green]Private Language Agent[/bold green]")
    console.print("Type 'exit' to quit.\n")

    while True:
        user_text = input("You: ").strip()
        if user_text.lower() in {"exit", "quit"}:
            break
        
        start_time = time.perf_counter()
        prompt = LITE_TASK_PROMPT.format(
            user_input=user_text,
            conversation_history=memory.format_for_prompt(),
        )

        # JSON Prompt
        # result = ask_llm(SYSTEM_PROMPT, prompt)
        # end_time = time.perf_counter() - start_time

        # assistant_reply = result.get("response", "")
        # memory.add_turn(user_text, assistant_reply)
        
        # console.print_json(data=result)

        # STREAM Prompt
        assistant_reply = ""
        console.print("[bold cyan]Assistant:[/bold cyan] ", end="")

        for token in stream_llm(SYSTEM_PROMPT, prompt):
            assistant_reply += token
            console.print(token, end="")

        console.print()
        memory.add_turn(user_text, assistant_reply)
        end_time = time.perf_counter() - start_time
        console.print(f"time: {end_time}")


if __name__ == "__main__":
    main()
