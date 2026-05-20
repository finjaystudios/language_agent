from typing import Annotated

from fastapi import APIRouter, Depends

from api.dependencies import get_agent_service
from api.models import ChatRequest, ChatResponse, ErrorResponse
from services.agent_service import AgentService

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
