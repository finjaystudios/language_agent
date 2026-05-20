import os

import chainlit as cl

FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")


@cl.on_chat_start
async def on_chat_start() -> None:
    await cl.Message(
        content=(
            "Welcome to the Local Language Agent Web UI.\n\n"
            f"FastAPI backend URL: `{FASTAPI_BASE_URL}`\n\n"
            "This initial Chainlit app is ready for HTTP integration with the "
            "backend. It does not call the LLM directly or load a local model."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    await cl.Message(
        content=(
            "The Web UI scaffold is running. Backend chat calls will be added "
            "over HTTP in a later step."
        )
    ).send()
