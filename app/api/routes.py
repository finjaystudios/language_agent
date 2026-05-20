from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_agent_service
from app.api.models import ChatRequest, ChatResponse, ErrorResponse, StreamChatRequest
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api", tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid client input."},
        422: {
            "model": ErrorResponse,
            "description": "Request schema validation failed.",
        },
        500: {
            "model": ErrorResponse,
            "description": "LLM or internal service failure.",
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
    return await agent_service.chat_full(request)


@router.post(
    "/chat/stream",
    response_class=StreamingResponse,
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Mode does not support streaming.",
        },
        422: {
            "model": ErrorResponse,
            "description": "Request schema validation failed.",
        },
        500: {
            "model": ErrorResponse,
            "description": "LLM or internal service failure.",
        },
    },
    summary="Stream a language-agent response as Server-Sent Events",
    description=(
        "Streams token events for modes that support streaming. Events are emitted "
        'as `data: {"mode": "translation", "token": "..."}` and end '
        'with `data: {"mode": "translation", "done": true}`.'
    ),
)
async def chat_stream(
    request: StreamChatRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> StreamingResponse:
    event_stream = await agent_service.chat_stream(request)
    return StreamingResponse(event_stream, media_type="text/event-stream")
