import logging
import os

import chainlit as cl
from chainlit.input_widget import Select

from client import (
    BackendClientError,
    BackendConfig,
    BackendHTTPError,
    BackendInvalidResponseError,
    BackendStreamError,
    BackendTimeoutError,
    BackendUnavailableError,
    FastAPIClient,
)
from renderer import render_chat_response

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
SESSION_MODE_KEY = "selected_mode"
MODE_AUTO = "auto"
STREAMING_MODES = {"translation", "learning"}
MODE_OPTIONS = {
    MODE_AUTO: "Auto",
    "translation": "Translation",
    "definition": "Definition",
    "learning": "Learning",
    "general": "General",
}
MODE_DESCRIPTIONS = {
    MODE_AUTO: "Let the language service choose translation, definition, learning, or general.",
    "translation": "Translate text and show the answer as it is generated.",
    "definition": "Define a term and render structured meaning, examples, and related words.",
    "learning": "Ask for language-learning help with live feedback.",
    "general": "Ask a general language-agent question with a full response.",
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


def get_backend_client() -> FastAPIClient:
    return FastAPIClient(BackendConfig.from_env())


def should_stream(mode: str | None) -> bool:
    config = BackendConfig.from_env()
    return config.streaming_enabled and mode in STREAMING_MODES


def mode_actions() -> list[cl.Action]:
    return [
        cl.Action(
            name="set_mode",
            label=label,
            tooltip=MODE_DESCRIPTIONS[mode],
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
                tooltip="Select the response mode to use for future chat requests.",
                description=(
                    "Auto lets the language service choose the best mode. Live "
                    "responses are used only for Translation and Learning."
                ),
            )
        ]
    ).send()


@cl.set_starters
async def set_starters() -> list[cl.Starter]:
    return [
        cl.Starter(
            label="Translate",
            message="Translate this sentence to isiXhosa: Good morning, how are you?",
            icon="/public/languages.svg",
        ),
        cl.Starter(
            label="Define",
            message="Define recursion in simple terms.",
            icon="/public/book-open.svg",
        ),
        cl.Starter(
            label="Learn",
            message="Teach me three useful French greetings.",
            icon="/public/graduation-cap.svg",
        ),
    ]


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set(SESSION_MODE_KEY, MODE_AUTO)
    client = get_backend_client()
    logger.info("webui_chat_start base_url=%s", client.config.base_url)
    backend_status = "Not checked"
    try:
        health = await client.health()
        backend_status = f"Connected ({health.get('status', 'unknown')})"
    except BackendClientError as error:
        backend_status = f"Unavailable - {error}"
        logger.warning(
            "webui_chat_start_backend_health_failed category=%s",
            error.category,
        )

    await send_mode_settings()
    await cl.Message(
        content=(
            "Welcome to the Local Language Agent.\n\n"
            "Use this chat for translation, definitions, language learning, "
            "general responses, or automatic intent routing.\n\n"
            f"Backend target: `{client.config.base_url}`\n"
            f"Backend health: `{backend_status}`\n\n"
            "Choose a response mode from the selector, or start with one of the "
            "examples below. This chat connects to the local language service "
            "shown above."
        ),
        actions=mode_actions(),
    ).send()


@cl.on_settings_update
async def on_settings_update(settings: dict[str, object]) -> None:
    selected_mode = str(settings.get(SESSION_MODE_KEY, MODE_AUTO))
    if selected_mode not in MODE_OPTIONS:
        selected_mode = MODE_AUTO

    cl.user_session.set(SESSION_MODE_KEY, selected_mode)
    logger.info("webui_mode_settings_update mode=%s", selected_mode)
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
    logger.info("webui_mode_action_update mode=%s", selected_mode)
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
    api_mode = api_mode_value(selected_mode)
    client = get_backend_client()
    use_streaming = should_stream(api_mode)
    logger.info(
        "webui_message_received mode=%s api_mode=%s streaming=%s message_length=%d",
        selected_mode,
        api_mode,
        use_streaming,
        len(user_text),
    )

    response = cl.Message(
        content=(
            f"Sending request to `{client.config.base_url}` using "
            f"**{mode_label(selected_mode)}** mode..."
        )
    )
    await response.send()

    try:
        if use_streaming:
            await stream_backend_response(client, response, user_text, api_mode)
        else:
            await send_full_backend_response(client, response, user_text, api_mode)
    except BackendClientError as error:
        logger.warning(
            "webui_message_backend_error category=%s mode=%s",
            error.category,
            api_mode,
        )
        response.content = format_ui_error(error)
        await response.update()


async def send_full_backend_response(
    client: FastAPIClient,
    response: cl.Message,
    user_text: str,
    api_mode: str | None,
) -> None:
    result = await client.chat_full(user_text, api_mode)
    assistant_text = render_chat_response(result)
    if not assistant_text:
        raise BackendInvalidResponseError(
            "Backend response did not include assistant text."
        )

    response.content = assistant_text
    response.metadata = {
        "mode": result.get("mode"),
        "response_type": "full",
    }
    await response.update()


async def stream_backend_response(
    client: FastAPIClient,
    response: cl.Message,
    user_text: str,
    api_mode: str | None,
) -> None:
    response.content = ""
    streamed_text = ""
    received_token = False
    response_mode = api_mode
    done_received = False

    try:
        async for event in client.chat_stream(user_text, api_mode):
            response_mode = str(event.get("mode", response_mode or ""))

            error_message = event.get("message") if event.get("error") else None
            if isinstance(error_message, str):
                raise BackendStreamError(error_message)

            token = event.get("token")
            if isinstance(token, str) and token:
                received_token = True
                streamed_text += token
                await response.stream_token(token)

            if event.get("done") is True:
                done_received = True
                break
    except BackendClientError:
        if received_token:
            logger.warning("webui_stream_interrupted_after_tokens mode=%s", api_mode)
            response.content = (
                f"{streamed_text}\n\n"
                "The response was interrupted before it completed. The partial "
                "answer above is all that was received."
            )
            await response.update()
            return
        await send_full_backend_response(client, response, user_text, api_mode)
        return

    if not streamed_text:
        raise BackendStreamError("Backend stream completed without response text.")
    if not done_received:
        response.content = (
            f"{streamed_text}\n\n"
            "The response ended before the completion signal arrived. The "
            "partial answer above is all that was received."
        )
        await response.update()
        return

    response.metadata = {
        "mode": response_mode,
        "response_type": "stream",
    }
    await response.update()


def format_ui_error(error: BackendClientError) -> str:
    if isinstance(error, BackendUnavailableError):
        return (
            "**Backend unavailable**\n\n"
            "The language service is not reachable right now. Start the local "
            "service, then try again.\n\n"
            f"`{error}`"
        )
    if isinstance(error, BackendTimeoutError):
        return (
            "**Backend timeout**\n\n"
            "The language service took too long to answer. It may still be "
            "loading or working on your request. Try again in a moment.\n\n"
            f"`{error}`"
        )
    if isinstance(error, BackendHTTPError):
        if error.error_code == "unsupported_mode":
            return (
                "**Unsupported mode**\n\n"
                "This response mode is not available for that request. Try Auto "
                "or choose a different mode.\n\n"
                f"`{error}`"
            )
        return (
            "**Request failed**\n\n"
            "The language service could not complete the request. Try again, or "
            "choose a different response mode.\n\n"
            f"`{error}`"
        )
    if isinstance(error, BackendInvalidResponseError):
        return (
            "**Response could not be displayed**\n\n"
            "The language service answered in a format this chat could not "
            "display. Try again.\n\n"
            f"`{error}`"
        )
    if isinstance(error, BackendStreamError):
        return (
            "**Streaming error**\n\n"
            "The response was interrupted while it was being displayed. Try "
            "again, or choose a full-response mode.\n\n"
            f"`{error}`"
        )
    return (
        "**Backend request failed**\n\n"
        "The chat could not complete the request. Try again.\n\n"
        f"`{error}`"
    )
