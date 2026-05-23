import asyncio
import logging
import os

import chainlit as cl
from chainlit.input_widget import Select
from chainlit.server import app as chainlit_app

from client import (
    BackendClientError,
    BackendConfig,
    BackendInvalidResponseError,
    BackendStreamError,
    FastAPIClient,
    format_ui_error,
)
from modes import starter_mode_for_values
from renderer import render_chat_response

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
BACKEND_STATUS_ATTEMPTS = 3
BACKEND_STATUS_RETRY_COOLDOWN_SECONDS = 1
SESSION_MODE_KEY = "selected_mode"
LAST_USER_MESSAGE_KEY = "last_user_message"
STREAM_FLUSH_CHAR_LIMIT = 96
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
FEEDBACK_CATEGORIES = {
    "not_relevant": "Not relevant",
    "incorrect": "Incorrect",
    "offensive": "Offensive",
}


@chainlit_app.get("/webui/backend-status")
async def backend_status() -> dict[str, str]:
    client = get_backend_client()
    last_error: BackendClientError | None = None
    for attempt in range(1, BACKEND_STATUS_ATTEMPTS + 1):
        try:
            health = await client.health()
        except BackendClientError as error:
            last_error = error
            logger.warning(
                "webui_landing_backend_status_failed attempt=%d attempts=%d category=%s",
                attempt,
                BACKEND_STATUS_ATTEMPTS,
                error.category,
            )
            if attempt < BACKEND_STATUS_ATTEMPTS:
                await asyncio.sleep(BACKEND_STATUS_RETRY_COOLDOWN_SECONDS)
            continue

        status = str(health.get("status", "unknown"))
        return {
            "status": "online" if status == "ok" else "offline",
            "target": client.config.base_url,
            "message": "Online" if status == "ok" else "Offline",
        }

    if last_error:
        logger.info(
            "webui_landing_backend_status_offline attempts=%d category=%s",
            BACKEND_STATUS_ATTEMPTS,
            last_error.category,
        )

    return {
        "status": "offline",
        "target": client.config.base_url,
        "message": "Offline",
    }


def prioritize_backend_status_route() -> None:
    status_index = None
    catch_all_index = None
    for index, route in enumerate(chainlit_app.routes):
        path = getattr(route, "path", "")
        if path == "/webui/backend-status":
            status_index = index
        elif path == "/{full_path:path}" and catch_all_index is None:
            catch_all_index = index

    if (
        status_index is not None
        and catch_all_index is not None
        and status_index > catch_all_index
    ):
        route = chainlit_app.routes.pop(status_index)
        chainlit_app.routes.insert(catch_all_index, route)


prioritize_backend_status_route()


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


def normalize_mode_value(value: object) -> str:
    selected_mode = str(value or MODE_AUTO).strip()
    if selected_mode in MODE_OPTIONS:
        return selected_mode

    normalized_labels = {label.casefold(): mode for mode, label in MODE_OPTIONS.items()}
    return normalized_labels.get(selected_mode.casefold(), MODE_AUTO)


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


def response_actions(user_text: str, selected_mode: str) -> list[cl.Action]:
    return [
        cl.Action(
            name="retry_response",
            label="Retry",
            tooltip="Retry the last request.",
            icon="rotate-ccw",
            payload={"message": user_text, "mode": selected_mode},
        ),
        cl.Action(
            name="feedback_good",
            label="Helpful",
            tooltip="Mark this response as helpful.",
            icon="thumbs-up",
            payload={"message": user_text, "rating": "positive"},
        ),
        cl.Action(
            name="feedback_needs_category",
            label="Needs improvement",
            tooltip="Tell us what went wrong.",
            icon="thumbs-down",
            payload={"message": user_text, "rating": "negative"},
        ),
    ]


async def send_mode_settings(initial: str = MODE_AUTO) -> None:
    await cl.ChatSettings(
        [
            Select(
                id=SESSION_MODE_KEY,
                label="Response mode",
                values=list(MODE_OPTIONS.values()),
                initial_value=MODE_OPTIONS.get(initial, MODE_OPTIONS[MODE_AUTO]),
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
    cl.user_session.set(LAST_USER_MESSAGE_KEY, "")
    logger.info("webui_chat_start default_mode=%s", MODE_AUTO)
    await send_mode_settings()


@cl.on_settings_update
async def on_settings_update(settings: dict[str, object]) -> None:
    selected_mode = normalize_mode_value(settings.get(SESSION_MODE_KEY, MODE_AUTO))

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
    selected_mode = normalize_mode_value(action.payload.get("mode", MODE_AUTO))

    cl.user_session.set(SESSION_MODE_KEY, selected_mode)
    logger.info("webui_mode_action_update mode=%s", selected_mode)
    await action.remove()
    await send_mode_settings(selected_mode)
    await cl.Message(
        content=f"Response mode set to **{mode_label(selected_mode)}**."
    ).send()


@cl.action_callback("retry_response")
async def on_retry_response(action: cl.Action) -> None:
    user_text = str(action.payload.get("message", "")).strip()
    selected_mode = normalize_mode_value(
        action.payload.get("mode", get_selected_mode())
    )
    if not user_text:
        await action.remove()
        return

    cl.user_session.set(SESSION_MODE_KEY, selected_mode)
    logger.info("webui_retry_response mode=%s", selected_mode)
    await action.remove()
    await send_mode_settings(selected_mode)
    await handle_user_text(user_text, echo_user=True)


@cl.action_callback("feedback_good")
async def on_feedback_good(action: cl.Action) -> None:
    user_text = str(action.payload.get("message", "")).strip()
    logger.info(
        "webui_feedback_submitted rating=positive message_length=%d",
        len(user_text),
    )
    await action.remove()
    await cl.Message(content="Thanks for the feedback.", author="Feedback").send()


@cl.action_callback("feedback_needs_category")
async def on_feedback_needs_category(action: cl.Action) -> None:
    user_text = str(action.payload.get("message", "")).strip()
    res = await cl.AskActionMessage(
        content="What should be improved?",
        author="Feedback",
        actions=[
            cl.Action(
                name="feedback_category",
                label=label,
                payload={"category": category, "message": user_text},
            )
            for category, label in FEEDBACK_CATEGORIES.items()
        ],
        timeout=60,
        raise_on_timeout=False,
    ).send()
    if not res:
        return
    payload = res.get("payload", {})
    category = str(payload.get("category", "uncategorized"))
    logger.info(
        "webui_feedback_submitted rating=negative category=%s message_length=%d",
        category,
        len(user_text),
    )
    await cl.Message(
        content="Thanks. I logged that feedback.", author="Feedback"
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

    starter_mode = starter_mode_for_message(message)
    await handle_user_text(user_text, starter_mode=starter_mode)


async def handle_user_text(
    user_text: str,
    *,
    starter_mode: str | None = None,
    echo_user: bool = False,
) -> None:
    if echo_user:
        await cl.Message(content=user_text, author="You", type="user_message").send()

    if starter_mode:
        cl.user_session.set(SESSION_MODE_KEY, starter_mode)
        await send_mode_settings(starter_mode)
        logger.info("webui_starter_mode_selected mode=%s", starter_mode)

    cl.user_session.set(LAST_USER_MESSAGE_KEY, user_text)
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
        response.actions = response_actions(user_text, selected_mode)
        await response.update()


def starter_mode_for_message(message: cl.Message) -> str | None:
    return starter_mode_for_values(getattr(message, "command", None), message.content)


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
    response.actions = response_actions(user_text, get_selected_mode())
    await response.update()


async def stream_backend_response(
    client: FastAPIClient,
    response: cl.Message,
    user_text: str,
    api_mode: str | None,
) -> None:
    response.content = ""
    streamed_text = ""
    token_buffer = ""
    received_token = False
    response_mode = api_mode
    done_received = False

    try:
        async for event in client.chat_stream(user_text, api_mode):
            if done_received:
                continue

            response_mode = str(event.get("mode", response_mode or ""))

            error_message = event.get("message") if event.get("error") else None
            if isinstance(error_message, str):
                raise BackendStreamError(error_message)

            token = event.get("token")
            if isinstance(token, str) and token:
                received_token = True
                streamed_text += token
                token_buffer += token
                if should_flush_stream_buffer(token_buffer, streamed_text):
                    await response.stream_token(token_buffer)
                    token_buffer = ""

            if event.get("done") is True:
                done_received = True
    except BackendClientError:
        if received_token:
            logger.warning("webui_stream_interrupted_after_tokens mode=%s", api_mode)
            if token_buffer:
                await response.stream_token(token_buffer)
            response.content = (
                f"{streamed_text}\n\n"
                "The response was interrupted before it completed. The partial "
                "answer above is all that was received."
            )
            response.actions = response_actions(user_text, get_selected_mode())
            await response.update()
            return
        await send_full_backend_response(client, response, user_text, api_mode)
        return

    if not streamed_text:
        raise BackendStreamError("Backend stream completed without response text.")
    if token_buffer:
        await response.stream_token(token_buffer)
    if not done_received:
        response.content = (
            f"{streamed_text}\n\n"
            "The response ended before the completion signal arrived. The "
            "partial answer above is all that was received."
        )
        response.actions = response_actions(user_text, get_selected_mode())
        await response.update()
        return

    response.metadata = {
        "mode": response_mode,
        "response_type": "stream",
    }
    response.actions = response_actions(user_text, get_selected_mode())
    await response.update()


def should_flush_stream_buffer(token_buffer: str, streamed_text: str) -> bool:
    if len(token_buffer) >= STREAM_FLUSH_CHAR_LIMIT:
        return True
    if token_buffer.endswith(("\n\n", ". ", "? ", "! ")):
        return not has_unclosed_markdown_fence(streamed_text)
    return False


def has_unclosed_markdown_fence(text: str) -> bool:
    return text.count("```") % 2 == 1
