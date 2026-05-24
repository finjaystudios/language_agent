import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.application.agent_service import AgentService
from app.application.models import ChatCommand, RequestMetadata
from app.infrastructure.redis.queue_service import (
    cancel_llm_call,
    get_job_status,
    get_queue_status,
)
from app.interfaces.api.auth import require_api_key
from app.interfaces.api.dependencies import get_agent_service
from app.interfaces.api.models import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    LLMJobStatusResponse,
    QueueStatusResponse,
    StreamChatRequest,
    chat_response_from_result,
)

router = APIRouter(
    prefix="/api", tags=["chat"], dependencies=[Depends(require_api_key)]
)
logger = logging.getLogger(__name__)


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
async def cancel_llm_job(job_id: str) -> LLMJobStatusResponse:
    try:
        job = await cancel_llm_call(job_id)
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
async def queue_status() -> QueueStatusResponse:
    queue = await get_queue_status()
    return QueueStatusResponse(queue=queue)
