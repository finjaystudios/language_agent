import asyncio
import logging
import os
import sys
from pathlib import Path

import chainlit as cl
from chainlit.input_widget import Select
from chainlit.server import app as chainlit_app
from chainlit.types import ThreadDict
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from webui.auth import authenticate_user  # noqa: E402
from webui.auth_rate_limit import close_auth_attempt_store  # noqa: E402
from webui.client import (  # noqa: E402
    BackendClientError,
    BackendConfig,
    BackendConflictError,
    BackendFeatureDisabledError,
    BackendInvalidResponseError,
    BackendStreamError,
    BackendValidationError,
    FastAPIClient,
    format_ui_error,
)
from webui.config import WebUISettings  # noqa: E402
from webui.login_page import render_login_page  # noqa: E402
from webui.modes import starter_mode_for_values  # noqa: E402
from webui.persistence import (  # noqa: E402
    apply_user_profile_to_session,
    chainlit_history_enabled,
    get_chainlit_data_layer,
    restore_profile_from_thread,
    thread_belongs_to_user,
)
from webui.renderer import render_chat_response  # noqa: E402

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
AUTH_ENABLED = WebUISettings.from_env().auth_enabled
STREAMING_MODES = {"translation", "definition", "learning"}
STREAM_STATUS_MESSAGES = {
    "queued": "Your request is queued and waiting for the model worker.",
    "processing": "The worker is preparing your response with llama-server.",
    "streaming": "The worker is streaming your response from llama-server.",
    "cancelled": "This response was cancelled before completion.",
}
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


if AUTH_ENABLED:

    @cl.password_auth_callback
    async def password_auth_callback(username: str, password: str) -> cl.User | None:
        return await authenticate_user(username, password)


@cl.data_layer
def chainlit_data_layer():
    if not chainlit_history_enabled():
        return None
    return get_chainlit_data_layer()


@cl.on_app_startup
async def on_app_startup() -> None:
    settings = WebUISettings.from_env()
    settings.validate_for_auth()
    logger.info(
        "webui_startup auth_enabled=%s signup_enabled=%s persistence_enabled=%s cookie_samesite=%s cookie_secure=%s auth_max_failed_attempts=%s auth_lockout_seconds=%s auth_rate_limit_window_seconds=%s",
        settings.auth_enabled,
        settings.signup_enabled,
        chainlit_history_enabled(settings),
        settings.session_cookie_samesite,
        settings.session_cookie_secure,
        settings.auth_max_failed_attempts,
        settings.auth_lockout_seconds,
        settings.auth_rate_limit_window_seconds,
    )


@cl.on_app_shutdown
async def on_app_shutdown() -> None:
    settings = WebUISettings.from_env()
    if chainlit_history_enabled(settings):
        await get_chainlit_data_layer().close()
    await close_auth_attempt_store()


def get_current_user() -> cl.User | None:
    user = cl.user_session.get("user")
    if isinstance(user, cl.User):
        return user
    return None


def current_user_identifier() -> str:
    user = get_current_user()
    return user.identifier if user else "anonymous"


def current_user_id() -> str:
    user = get_current_user()
    metadata = user.metadata if user else {}
    return str(metadata.get("user_id", "unknown"))


def current_session_id() -> str:
    return str(cl.user_session.get("id", "unknown"))


@chainlit_app.get("/login", response_class=HTMLResponse)
async def login_page() -> HTMLResponse:
    return HTMLResponse(render_login_page(WebUISettings.from_env()))


@chainlit_app.middleware("http")
async def custom_login_page_middleware(request: Request, call_next):
    if request.method == "GET" and request.url.path == "/login":
        return HTMLResponse(render_login_page(WebUISettings.from_env()))
    return await call_next(request)


@chainlit_app.get("/webui/auth/config")
async def auth_ui_config() -> dict[str, object]:
    settings = WebUISettings.from_env()
    return {
        "signupEnabled": settings.signup_enabled,
        "minPasswordLength": settings.auth_min_password_length,
        "requireAdminApproval": settings.signup_require_admin_approval,
    }


@chainlit_app.post("/webui/auth/signup")
async def auth_signup(request: Request) -> JSONResponse:
    settings = WebUISettings.from_env()
    if not settings.signup_enabled:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "Account sign-up is not available right now.",
                "error": "signup_disabled",
            },
        )

    payload = await request.json()
    username = str(payload.get("username", "")).strip()
    display_name = payload.get("display_name")
    preferred_language = payload.get("preferred_language")

    logger.info(
        "service=webui event_type=signup outcome=requested username=%s",
        username,
    )
    client = get_backend_client()
    try:
        result = await client.signup_user(
            username=username,
            password=str(payload.get("password", "")),
            confirm_password=(
                str(payload["confirm_password"])
                if payload.get("confirm_password") is not None
                else None
            ),
            display_name=(str(display_name) if display_name is not None else None),
            preferred_language=(
                str(preferred_language) if preferred_language is not None else None
            ),
        )
    except BackendFeatureDisabledError:
        logger.warning(
            "service=webui event_type=signup outcome=disabled username=%s",
            username,
        )
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "Account sign-up is not available right now.",
                "error": "signup_disabled",
            },
        )
    except BackendConflictError:
        logger.warning(
            "service=webui event_type=signup outcome=failure username=%s reason=username_unavailable",
            username,
        )
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": "That username is unavailable.",
                "error": "username_unavailable",
            },
        )
    except BackendValidationError as error:
        logger.warning(
            "service=webui event_type=signup outcome=failure username=%s reason=invalid_signup",
            username,
        )
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "message": str(error),
                "error": error.error_code or "invalid_signup",
            },
        )
    except BackendClientError as error:
        logger.warning(
            "service=webui event_type=signup outcome=error username=%s reason=%s",
            username,
            error.category,
        )
        return JSONResponse(
            status_code=502,
            content={
                "success": False,
                "message": "Account sign-up is unavailable right now. Please try again shortly.",
                "error": "signup_unavailable",
            },
        )

    logger.info(
        "service=webui event_type=signup outcome=success username=%s user_id=%s",
        result.username,
        result.user_id,
    )
    return JSONResponse(
        status_code=201,
        content={
            "success": result.success,
            "message": result.message,
            "username": result.username,
            "user_id": result.user_id,
            "created_at": result.created_at,
        },
    )


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


def prioritize_webui_routes() -> None:
    managed_paths = {
        "/login",
        "/webui/backend-status",
        "/webui/auth/config",
        "/webui/auth/signup",
    }
    catch_all_index = None
    managed_routes = []
    for index, route in enumerate(chainlit_app.routes):
        path = getattr(route, "path", "")
        if path in managed_paths:
            managed_routes.append((index, route))
        elif path == "/{full_path:path}" and catch_all_index is None:
            catch_all_index = index

    if catch_all_index is None or not managed_routes:
        return

    for index, _route in sorted(managed_routes, reverse=True):
        if index > catch_all_index:
            chainlit_app.routes.pop(index)

    insert_index = catch_all_index
    for _index, route in sorted(managed_routes, key=lambda item: item[0]):
        chainlit_app.routes.insert(insert_index, route)
        insert_index += 1


prioritize_webui_routes()


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
                    "responses are used for Translation, Definition, and Learning."
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
    session_profile = apply_user_profile_to_session(get_current_user())
    cl.user_session.set(SESSION_MODE_KEY, MODE_AUTO)
    cl.user_session.set(LAST_USER_MESSAGE_KEY, "")
    logger.info(
        "webui_chat_start default_mode=%s username=%s user_id=%s preferred_language=%s ui_theme=%s session_id=%s",
        MODE_AUTO,
        current_user_identifier(),
        current_user_id(),
        session_profile.get("preferred_language"),
        session_profile.get("ui_theme"),
        current_session_id(),
    )
    await send_mode_settings()


@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict) -> None:
    user = get_current_user()
    if not thread_belongs_to_user(thread, user):
        logger.warning(
            "webui_chat_resume_rejected username=%s thread_id=%s reason=thread_owner_mismatch",
            current_user_identifier(),
            thread.get("id"),
        )
        return

    session_profile = apply_user_profile_to_session(user)
    restored_profile = restore_profile_from_thread(thread)
    selected_mode = get_selected_mode()
    logger.info(
        "webui_chat_resume thread_id=%s mode=%s username=%s user_id=%s preferred_language=%s ui_theme=%s session_id=%s",
        thread.get("id"),
        selected_mode,
        current_user_identifier(),
        current_user_id(),
        restored_profile.get(
            "preferred_language",
            session_profile.get("preferred_language"),
        ),
        restored_profile.get("ui_theme", session_profile.get("ui_theme")),
        current_session_id(),
    )
    await send_mode_settings(selected_mode)


@cl.on_logout
def on_logout(request, response) -> None:
    logger.info(
        "service=webui event_type=auth outcome=logout username=%s user_id=%s session_id=%s",
        current_user_identifier(),
        current_user_id(),
        current_session_id(),
    )


@cl.on_settings_update
async def on_settings_update(settings: dict[str, object]) -> None:
    selected_mode = normalize_mode_value(settings.get(SESSION_MODE_KEY, MODE_AUTO))

    cl.user_session.set(SESSION_MODE_KEY, selected_mode)
    logger.info(
        "webui_mode_settings_update mode=%s username=%s user_id=%s session_id=%s",
        selected_mode,
        current_user_identifier(),
        current_user_id(),
        current_session_id(),
    )
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
    logger.info(
        "webui_mode_action_update mode=%s username=%s user_id=%s session_id=%s",
        selected_mode,
        current_user_identifier(),
        current_user_id(),
        current_session_id(),
    )
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
    logger.info(
        "webui_retry_response mode=%s username=%s user_id=%s session_id=%s",
        selected_mode,
        current_user_identifier(),
        current_user_id(),
        current_session_id(),
    )
    await action.remove()
    await send_mode_settings(selected_mode)
    await handle_user_text(user_text, echo_user=True)


@cl.action_callback("feedback_good")
async def on_feedback_good(action: cl.Action) -> None:
    user_text = str(action.payload.get("message", "")).strip()
    logger.info(
        "webui_feedback_submitted rating=positive username=%s user_id=%s session_id=%s message_length=%d",
        current_user_identifier(),
        current_user_id(),
        current_session_id(),
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
        "webui_feedback_submitted rating=negative category=%s username=%s user_id=%s session_id=%s message_length=%d",
        category,
        current_user_identifier(),
        current_user_id(),
        current_session_id(),
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
        logger.info(
            "webui_starter_mode_selected mode=%s username=%s user_id=%s session_id=%s",
            starter_mode,
            current_user_identifier(),
            current_user_id(),
            current_session_id(),
        )

    cl.user_session.set(LAST_USER_MESSAGE_KEY, user_text)
    selected_mode = get_selected_mode()
    api_mode = api_mode_value(selected_mode)
    client = get_backend_client()
    use_streaming = should_stream(api_mode)
    logger.info(
        "webui_message_received mode=%s api_mode=%s streaming=%s username=%s user_id=%s session_id=%s message_length=%d",
        selected_mode,
        api_mode,
        use_streaming,
        current_user_identifier(),
        current_user_id(),
        current_session_id(),
        len(user_text),
    )

    status_message = cl.Message(
        content=(
            f"Sending request to `{client.config.base_url}` using "
            f"**{mode_label(selected_mode)}** mode..."
        )
    )
    await status_message.send()

    try:
        if use_streaming:
            await stream_backend_response(client, status_message, user_text, api_mode)
        else:
            await send_full_backend_response(
                client,
                status_message,
                user_text,
                api_mode,
            )
    except BackendClientError as error:
        logger.warning(
            "webui_message_backend_error category=%s mode=%s username=%s user_id=%s session_id=%s",
            error.category,
            api_mode,
            current_user_identifier(),
            current_user_id(),
            current_session_id(),
        )
        status_message.content = format_ui_error(error)
        status_message.actions = response_actions(user_text, selected_mode)
        await status_message.update()


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
    status_message: cl.Message,
    user_text: str,
    api_mode: str | None,
) -> None:
    response = cl.Message(content="")
    response.content = ""
    streamed_text = ""
    token_buffer = ""
    received_token = False
    response_started = False
    response_mode = api_mode
    done_received = False
    latest_status = "queued"

    try:
        async for event in client.chat_stream(user_text, api_mode):
            if done_received:
                continue

            response_mode = str(event.get("mode", response_mode or ""))
            status = event.get("status")
            if isinstance(status, str):
                latest_status = status
                if not received_token and status in STREAM_STATUS_MESSAGES:
                    status_message.content = STREAM_STATUS_MESSAGES[status]
                    await status_message.update()

            if event.get("cancelled") is True or status == "cancelled":
                if token_buffer:
                    if not response_started:
                        await status_message.remove()
                        await response.send()
                        response_started = True
                    await response.stream_token(token_buffer)
                response.content = (
                    f"{streamed_text}\n\n{STREAM_STATUS_MESSAGES['cancelled']}"
                    if streamed_text
                    else STREAM_STATUS_MESSAGES["cancelled"]
                )
                response.actions = response_actions(user_text, get_selected_mode())
                if response_started:
                    await response.update()
                else:
                    status_message.content = response.content
                    status_message.actions = response.actions
                    await status_message.update()
                return

            error_message = event.get("message") if event.get("error") else None
            if isinstance(error_message, str):
                if token_buffer:
                    if not response_started:
                        await status_message.remove()
                        await response.send()
                        response_started = True
                    await response.stream_token(token_buffer)
                response.content = (
                    f"{streamed_text}\n\n{error_message}"
                    if streamed_text
                    else error_message
                )
                response.actions = response_actions(user_text, get_selected_mode())
                if response_started:
                    await response.update()
                else:
                    status_message.content = response.content
                    status_message.actions = response.actions
                    await status_message.update()
                return

            token = event.get("token")
            if isinstance(token, str) and token:
                received_token = True
                if not response_started:
                    await status_message.remove()
                    await response.send()
                    response_started = True
                streamed_text += token
                token_buffer += token
                if should_flush_stream_buffer(token_buffer, streamed_text):
                    await response.stream_token(token_buffer)
                    token_buffer = ""

            if event.get("done") is True:
                done_received = True
    except BackendClientError:
        if received_token:
            logger.warning(
                "webui_stream_interrupted_after_tokens mode=%s username=%s user_id=%s session_id=%s",
                api_mode,
                current_user_identifier(),
                current_user_id(),
                current_session_id(),
            )
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
        status_message.content = format_ui_error(
            BackendStreamError(
                STREAM_STATUS_MESSAGES.get(
                    latest_status, "The response stream was interrupted."
                )
            )
        )
        status_message.actions = response_actions(user_text, get_selected_mode())
        await status_message.update()
        return

    if not streamed_text:
        logger.info("webui_stream_empty_fallback mode=%s", api_mode)
        await send_full_backend_response(client, status_message, user_text, api_mode)
        return
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
