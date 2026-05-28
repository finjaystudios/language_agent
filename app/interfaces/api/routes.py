import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.params import Depends as DependsMarker
from fastapi.responses import StreamingResponse

from app.application.agent_service import AgentService
from app.application.models import ChatCommand, RequestMetadata
from app.application.user_auth_service import (
    UsernameAlreadyExistsError,
    UserSignupCommand,
    authenticate_password_user,
    signup_user,
)
from app.core.config import AppSettings
from app.infrastructure.redis.queue_service import LLMQueueService
from app.interfaces.api.auth import require_api_key
from app.interfaces.api.dependencies import (
    get_agent_service,
    get_job_store,
    get_queue_client,
    get_settings,
    get_user_repository,
)
from app.interfaces.api.models import (
    AuthenticatedUserResponse,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    LLMJobStatusResponse,
    QueueStatusResponse,
    StreamChatRequest,
    UserPasswordLoginRequest,
    UserSignupRequest,
    UserSignupResponse,
    authenticated_user_response_from_profile,
    chat_response_from_result,
    user_signup_response_from_profile,
)
from app.ports.job_store import JobStore
from app.ports.queue_client import QueueClient
from app.ports.user_repository import UserRepository

router = APIRouter(
    prefix="/api", tags=["chat"], dependencies=[Depends(require_api_key)]
)
logger = logging.getLogger(__name__)
SETTINGS_DEP = Depends(get_settings)
QUEUE_CLIENT_DEP = Depends(get_queue_client)
JOB_STORE_DEP = Depends(get_job_store)
USER_REPOSITORY_DEP = Depends(get_user_repository)


async def get_job_status(
    job_id: str,
    *,
    settings: AppSettings | None = None,
    queue_client: QueueClient | None = None,
    job_store: JobStore | None = None,
):
    return await LLMQueueService(
        settings or get_settings(),
        queue_client or get_queue_client(),
        job_store or get_job_store(),
    ).get_job_status(job_id)


async def cancel_llm_call(
    job_id: str,
    *,
    settings: AppSettings | None = None,
    queue_client: QueueClient | None = None,
    job_store: JobStore | None = None,
):
    return await LLMQueueService(
        settings or get_settings(),
        queue_client or get_queue_client(),
        job_store or get_job_store(),
    ).cancel_llm_call(job_id)


async def get_queue_status(
    *,
    settings: AppSettings | None = None,
    queue_client: QueueClient | None = None,
    job_store: JobStore | None = None,
):
    return await LLMQueueService(
        settings or get_settings(),
        queue_client or get_queue_client(),
        job_store or get_job_store(),
    ).get_queue_status()


@router.post(
    "/internal/auth/login",
    response_model=AuthenticatedUserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid API key."},
        403: {
            "model": ErrorResponse,
            "description": "Invalid username/password credentials.",
        },
    },
    summary="Authenticate a Web UI user over the internal API boundary",
)
async def internal_user_login(
    request: UserPasswordLoginRequest,
    user_repository: UserRepository = USER_REPOSITORY_DEP,
) -> AuthenticatedUserResponse:
    user = await authenticate_password_user(
        request.username,
        request.password,
        user_repository,
    )
    if user is None:
        logger.warning(
            "api_internal_auth_login_failed username=%s reason=invalid_credentials",
            request.username.strip(),
        )
        raise HTTPException(
            status_code=403,
            detail={
                "error": "invalid_credentials",
                "message": "Invalid username or password.",
            },
        )

    logger.info(
        "api_internal_auth_login_success username=%s user_id=%s role=%s admin=%s",
        user.username,
        user.id,
        user.role,
        user.is_admin,
    )
    return authenticated_user_response_from_profile(user)


@router.post(
    "/auth/signup",
    response_model=UserSignupResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Sign-up validation failed."},
        401: {"model": ErrorResponse, "description": "Missing or invalid API key."},
        404: {"model": ErrorResponse, "description": "Sign-up is disabled."},
        409: {"model": ErrorResponse, "description": "Username is unavailable."},
    },
    summary="Create a new Web UI user account over the internal API boundary",
)
async def user_signup(
    request: UserSignupRequest,
    settings: AppSettings = SETTINGS_DEP,
    user_repository: UserRepository = USER_REPOSITORY_DEP,
) -> UserSignupResponse:
    resolved_settings = (
        get_settings() if isinstance(settings, DependsMarker) else settings
    )
    if not resolved_settings.signup_enabled:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "signup_disabled",
                "message": "Account sign-up is not available right now.",
            },
        )

    try:
        user = await signup_user(
            UserSignupCommand(
                username=request.username,
                password=request.password,
                confirm_password=request.confirm_password,
                display_name=request.display_name,
                preferred_language=request.preferred_language,
            ),
            user_repository,
            require_strong_password=resolved_settings.auth_require_strong_password,
            min_password_length=resolved_settings.auth_min_password_length,
            default_role=resolved_settings.signup_default_role,
            require_admin_approval=resolved_settings.signup_require_admin_approval,
        )
    except UsernameAlreadyExistsError as error:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "username_unavailable",
                "message": "That username is unavailable.",
            },
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_signup",
                "message": str(error),
            },
        ) from error

    logger.info(
        "api_auth_signup_success username=%s user_id=%s active=%s role=%s",
        user.username,
        user.id,
        user.is_active,
        user.role,
    )
    message = (
        "Account created. Please wait for approval before signing in."
        if resolved_settings.signup_require_admin_approval
        else "Account created. Please sign in."
    )
    return user_signup_response_from_profile(user, message=message)


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid client input."},
        401: {"model": ErrorResponse, "description": "Missing or invalid API key."},
        429: {"model": ErrorResponse, "description": "Queue is saturated."},
        422: {
            "model": ErrorResponse,
            "description": "Request schema validation failed.",
        },
        500: {
            "model": ErrorResponse,
            "description": "LLM, authentication configuration, or internal service failure.",
        },
    },
    summary="Create a full language-agent response",
    description=(
        "Processes one user message and returns a complete structured response. "
        "If `mode` is omitted, the existing intent router selects the active mode."
    ),
)
async def chat_full(
    request: ChatRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> ChatResponse:
    logger.info(
        "api_chat_full_request mode=%s message_length=%d session_id=%s",
        request.mode,
        len(request.message),
        request.metadata.session_id if request.metadata else None,
    )
    response = await agent_service.chat_full(
        ChatCommand(
            message=request.message,
            mode=request.mode.value if request.mode is not None else None,
            metadata=RequestMetadata(**request.metadata.model_dump())
            if request.metadata
            else None,
        )
    )
    logger.info("api_chat_full_response mode=%s", response.mode)
    return chat_response_from_result(response)


@router.post(
    "/chat/stream",
    response_class=StreamingResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid API key."},
        429: {"model": ErrorResponse, "description": "Queue is saturated."},
        422: {
            "model": ErrorResponse,
            "description": "Request schema validation failed.",
        },
        500: {
            "model": ErrorResponse,
            "description": "LLM, authentication configuration, or internal service failure.",
        },
    },
    summary="Stream a language-agent response as Server-Sent Events",
    description=(
        "Streams token events for any mode. Events are emitted "
        'as `data: {"mode": "translation", "token": "..."}` and end '
        'with `data: {"mode": "translation", "done": true}`.'
    ),
)
async def chat_stream(
    request: StreamChatRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> StreamingResponse:
    logger.info(
        "api_chat_stream_request mode=%s message_length=%d session_id=%s",
        request.mode,
        len(request.message),
        request.metadata.session_id if request.metadata else None,
    )
    event_stream = await agent_service.chat_stream(
        ChatCommand(
            message=request.message,
            mode=request.mode.value if request.mode is not None else None,
            metadata=RequestMetadata(**request.metadata.model_dump())
            if request.metadata
            else None,
        )
    )
    logger.info("api_chat_stream_response_started")
    return StreamingResponse(event_stream, media_type="text/event-stream")


@router.get(
    "/llm/jobs/{job_id}",
    response_model=LLMJobStatusResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid API key."},
        404: {"model": ErrorResponse, "description": "Job was not found."},
    },
    summary="Get LLM queue job status",
)
async def llm_job_status(job_id: str) -> LLMJobStatusResponse:
    try:
        job = await get_job_status(job_id)
    except Exception as error:
        raise HTTPException(status_code=404, detail="LLM job not found.") from error
    return LLMJobStatusResponse.from_job(job)


@router.post(
    "/llm/jobs/{job_id}/cancel",
    response_model=LLMJobStatusResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid API key."},
        404: {"model": ErrorResponse, "description": "Job was not found."},
    },
    summary="Cancel an LLM queue job",
)
async def cancel_llm_job(
    job_id: str,
    settings: AppSettings = SETTINGS_DEP,
    queue_client: QueueClient = QUEUE_CLIENT_DEP,
    job_store: JobStore = JOB_STORE_DEP,
) -> LLMJobStatusResponse:
    resolved_settings = (
        get_settings() if isinstance(settings, DependsMarker) else settings
    )
    resolved_queue_client = (
        get_queue_client() if isinstance(queue_client, DependsMarker) else queue_client
    )
    resolved_job_store = (
        get_job_store() if isinstance(job_store, DependsMarker) else job_store
    )
    try:
        if (
            isinstance(settings, DependsMarker)
            and isinstance(queue_client, DependsMarker)
            and isinstance(job_store, DependsMarker)
        ):
            job = await cancel_llm_call(job_id)
        else:
            job = await cancel_llm_call(
                job_id,
                settings=resolved_settings,
                queue_client=resolved_queue_client,
                job_store=resolved_job_store,
            )
    except Exception as error:
        raise HTTPException(status_code=404, detail="LLM job not found.") from error
    return LLMJobStatusResponse.from_job(job)


@router.get(
    "/queue/status",
    response_model=QueueStatusResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Missing or invalid API key."},
        500: {"model": ErrorResponse, "description": "Queue status check failed."},
    },
    summary="Get LLM queue health and depth",
)
async def queue_status(
    settings: AppSettings = SETTINGS_DEP,
    queue_client: QueueClient = QUEUE_CLIENT_DEP,
    job_store: JobStore = JOB_STORE_DEP,
) -> QueueStatusResponse:
    resolved_settings = (
        get_settings() if isinstance(settings, DependsMarker) else settings
    )
    resolved_queue_client = (
        get_queue_client() if isinstance(queue_client, DependsMarker) else queue_client
    )
    resolved_job_store = (
        get_job_store() if isinstance(job_store, DependsMarker) else job_store
    )
    if (
        isinstance(settings, DependsMarker)
        and isinstance(queue_client, DependsMarker)
        and isinstance(job_store, DependsMarker)
    ):
        queue = await get_queue_status()
    else:
        queue = await get_queue_status(
            settings=resolved_settings,
            queue_client=resolved_queue_client,
            job_store=resolved_job_store,
        )
    return QueueStatusResponse(queue=queue)
