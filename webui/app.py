import chainlit as cl
from chainlit.input_widget import Select

from client import BackendClientError, BackendConfig, FastAPIClient
from renderer import render_chat_response

SESSION_MODE_KEY = "selected_mode"
MODE_AUTO = "auto"
STREAMING_MODES = {"translation", "learning"}
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


@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set(SESSION_MODE_KEY, MODE_AUTO)
    client = get_backend_client()
    backend_status = "not checked"
    try:
        health = await client.health()
        backend_status = str(health.get("status", "unknown"))
    except BackendClientError as error:
        backend_status = f"offline or unavailable: {error}"

    await send_mode_settings()
    await cl.Message(
        content=(
            "Welcome to the Local Language Agent.\n\n"
            "Use this chat for translation, definitions, language learning, "
            "general responses, or automatic intent routing.\n\n"
            f"Backend target: `{client.config.base_url}`\n"
            f"Backend health: `{backend_status}`\n\n"
            "Select a response mode, then send a message. Translation and "
            "Learning use streaming when enabled; other modes use the full "
            "response endpoint."
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
    api_mode = api_mode_value(selected_mode)
    client = get_backend_client()

    response = cl.Message(
        content=(
            f"Sending request to `{client.config.base_url}` using "
            f"**{mode_label(selected_mode)}** mode..."
        )
    )
    await response.send()

    try:
        if should_stream(api_mode):
            await stream_backend_response(client, response, user_text, api_mode)
        else:
            await send_full_backend_response(client, response, user_text, api_mode)
    except BackendClientError as error:
        response.content = f"Backend request failed: {error}"
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
        raise BackendClientError("Backend response did not include assistant text.")

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

    try:
        async for event in client.chat_stream(user_text, api_mode):
            response_mode = str(event.get("mode", response_mode or ""))

            error_message = event.get("message") if event.get("error") else None
            if isinstance(error_message, str):
                raise BackendClientError(error_message)

            token = event.get("token")
            if isinstance(token, str) and token:
                received_token = True
                streamed_text += token
                await response.stream_token(token)

            if event.get("done") is True:
                break
    except BackendClientError:
        if received_token:
            raise
        await send_full_backend_response(client, response, user_text, api_mode)
        return

    if not streamed_text:
        raise BackendClientError("Backend stream completed without response text.")

    response.metadata = {
        "mode": response_mode,
        "response_type": "stream",
    }
    await response.update()
