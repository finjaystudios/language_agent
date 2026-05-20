import asyncio

from app.api.main import create_app
from app.api.models import ChatRequest, ChatResponse, ResponseMetadata
from app.api.routes import chat_full


class FakeAgentService:
    def __init__(self):
        self.request = None

    async def chat_full(self, request):
        self.request = request
        return ChatResponse(
            mode="definition",
            response="Recursion is a function calling itself.",
            metadata=ResponseMetadata(session_id="session-1"),
        )


def test_chat_full_route_delegates_to_agent_service():
    service = FakeAgentService()
    request = ChatRequest(
        message="Define recursion in simple terms",
        mode="definition",
        metadata={"session_id": "session-1"},
    )

    response = asyncio.run(chat_full(request=request, agent_service=service))

    assert service.request == request
    assert response.mode == "definition"
    assert response.response == "Recursion is a function calling itself."


def test_chat_endpoint_is_in_openapi_schema():
    app = create_app()

    schema = app.openapi()

    assert "/api/chat" in schema["paths"]
    assert "post" in schema["paths"]["/api/chat"]
