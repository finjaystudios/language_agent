from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_agent_service
from app.api.models import ChatRequest, ChatResponse, ErrorResponse, StreamChatRequest
from app.services.agent_service import AgentService, UnsupportedStreamingModeError

router = APIRouter(prefix="/api", tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={500: {"model": ErrorResponse}},
    summary="Create a full language-agent response",
)
async def chat_full(
    request: ChatRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> ChatResponse:
    return await agent_service.chat_full(request)


@router.post(
    "/chat/stream",
    response_class=StreamingResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    summary="Stream a language-agent response as Server-Sent Events",
)
async def chat_stream(
    request: StreamChatRequest,
    agent_service: Annotated[AgentService, Depends(get_agent_service)],
) -> StreamingResponse:
    try:
        event_stream = await agent_service.chat_stream(request)
    except UnsupportedStreamingModeError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return StreamingResponse(event_stream, media_type="text/event-stream")
