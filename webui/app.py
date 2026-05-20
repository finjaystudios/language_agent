import os

import chainlit as cl
from chainlit.input_widget import Select

FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")
SESSION_MODE_KEY = "selected_mode"
MODE_AUTO = "auto"
MODE_OPTIONS = {
    MODE_AUTO: "Auto / intent routed",
    "translation": "Translation",
    "definition": "Definition",
    "learning": "Learning",
    "general": "General",
}


def get_selected_mode() -> str:
    mode = cl.user_session.get(SESSION_MODE_KEY, MODE_AUTO)
    if mode not in MODE_OPTIONS:
        return MODE_AUTO
    return mode


def mode_label(mode: str | None = None) -> str:
    return MODE_OPTIONS.get(mode or get_selected_mode(), MODE_OPTIONS[MODE_AUTO])


def api_mode_value(mode: str | None = None) -> str | None:
    selected_mode = mode or get_selected_mode()
    if selected_mode == MODE_AUTO:
        return None
    return selected_mode


def mode_actions() -> list[cl.Action]:
    return [
        cl.Action(
            name="set_mode",
            label=label,
            tooltip=f"Use {label} mode",
            payload={"mode": mode},
        )
        for mode, label in MODE_OPTIONS.items()
    ]


async def send_mode_settings(initial: str = MODE_AUTO) -> None:
    await cl.ChatSettings(
        [
            Select(
                id=SESSION_MODE_KEY,
                label="Response mode",
                items=MODE_OPTIONS,
                initial=initial,
                tooltip="Select the backend mode to use for future chat requests.",
                description=(
                    "Auto omits the mode so the FastAPI backend can route intent. "
                    "Explicit modes will later be sent as the API request mode."
                ),
            )
        ]
    ).send()


def build_planned_payload(user_message: str) -> dict[str, object]:
    return {
        "message": user_message,
        "mode": api_mode_value(),
        "metadata": {"client": "chainlit-webui"},
    }


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set(SESSION_MODE_KEY, MODE_AUTO)
    await send_mode_settings()
    await cl.Message(
        content=(
            "Welcome to the Local Language Agent.\n\n"
            "Use this chat to prepare language-agent requests for translation, "
            "definition, learning, or automatic intent routing.\n\n"
            f"Backend target: `{FASTAPI_BASE_URL}`\n\n"
            "Select a response mode, then send a message. For now the UI returns "
            "a temporary scaffold response; the FastAPI HTTP client will be added "
            "in a later step."
        ),
        actions=mode_actions(),
    ).send()


@cl.on_settings_update
async def on_settings_update(settings: dict[str, object]) -> None:
    selected_mode = str(settings.get(SESSION_MODE_KEY, MODE_AUTO))
    if selected_mode not in MODE_OPTIONS:
        selected_mode = MODE_AUTO

    cl.user_session.set(SESSION_MODE_KEY, selected_mode)
    await cl.Message(
        content=(
            f"Response mode set to **{mode_label(selected_mode)}**. "
            "Future messages in this chat will use this mode selection."
        )
    ).send()


@cl.action_callback("set_mode")
async def on_set_mode(action: cl.Action) -> None:
    selected_mode = str(action.payload.get("mode", MODE_AUTO))
    if selected_mode not in MODE_OPTIONS:
        selected_mode = MODE_AUTO

    cl.user_session.set(SESSION_MODE_KEY, selected_mode)
    await action.remove()
    await send_mode_settings(selected_mode)
    await cl.Message(
        content=f"Response mode set to **{mode_label(selected_mode)}**."
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    user_text = message.content.strip()
    if not user_text:
        await cl.Message(
            content="Please enter a message before sending.",
            author="Input validation",
        ).send()
        return

    selected_mode = get_selected_mode()
    planned_payload = build_planned_payload(user_text)

    response = cl.Message(
        content=(
            f"Preparing a **{mode_label(selected_mode)}** response...\n\n"
            "The backend HTTP client is not implemented yet."
        )
    )
    await response.send()

    response.content = (
        "Temporary Web UI scaffold response.\n\n"
        f"- Selected mode: **{mode_label(selected_mode)}**\n"
        f"- FastAPI endpoint planned: `{FASTAPI_BASE_URL}/api/chat`\n"
        f"- API mode value to send later: `{planned_payload['mode']}`\n\n"
        "No LLM call was made from the Web UI. No backend service code was "
        "imported. In the next integration step, this message will be replaced "
        "with the HTTP response from the FastAPI backend."
    )
    await response.update()

    await cl.Message(
        author="Error placeholder",
        content=(
            "If the later backend request fails, connection and API errors will "
            "be displayed here without exposing backend stack traces."
        ),
    ).send()
