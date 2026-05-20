import asyncio

import pytest
from app.api.main import create_app
from app.api.models import (
    ChatRequest,
    ChatResponse,
    ResponseMetadata,
    StreamChatRequest,
)
from app.api.routes import chat_full, chat_stream
from app.services.agent_service import UnsupportedStreamingModeError
from fastapi import HTTPException


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

    async def chat_stream(self, request):
        self.request = request

        async def events():
            yield 'data: {"mode": "translation", "token": "hola"}\n\n'
            yield 'data: {"mode": "translation", "done": true}\n\n'

        return events()


class FakeUnsupportedStreamService:
    async def chat_stream(self, request):
        raise UnsupportedStreamingModeError("definition")


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


def test_chat_stream_route_returns_streaming_response():
    service = FakeAgentService()
    request = StreamChatRequest(message="Translate hello", mode="translation")

    response = asyncio.run(chat_stream(request=request, agent_service=service))

    async def collect_events():
        return [event async for event in response.body_iterator]

    assert service.request == request
    assert response.media_type == "text/event-stream"
    assert asyncio.run(collect_events()) == [
        'data: {"mode": "translation", "token": "hola"}\n\n',
        'data: {"mode": "translation", "done": true}\n\n',
    ]


def test_chat_stream_route_maps_unsupported_mode_to_bad_request():
    request = StreamChatRequest(message="Define recursion", mode="definition")

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            chat_stream(
                request=request,
                agent_service=FakeUnsupportedStreamService(),
            )
        )

    assert error.value.status_code == 400
    assert "definition" in error.value.detail


def test_chat_stream_endpoint_is_in_openapi_schema():
    app = create_app()

    schema = app.openapi()

    assert "/api/chat/stream" in schema["paths"]
    assert "post" in schema["paths"]["/api/chat/stream"]
