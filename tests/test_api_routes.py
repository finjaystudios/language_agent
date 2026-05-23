import asyncio

import pytest
from app.api.errors import UnsupportedModeError
from app.api.main import create_app
from app.api.models import (
    ChatRequest,
    ChatResponse,
    LLMJobStatusResponse,
    ResponseMetadata,
    StreamChatRequest,
)
from app.api.routes import cancel_llm_job, chat_full, chat_stream, llm_job_status
from app.queue.models import LLMCallJob


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
        raise UnsupportedModeError("definition")


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

    with pytest.raises(UnsupportedModeError) as error:
        asyncio.run(
            chat_stream(
                request=request,
                agent_service=FakeUnsupportedStreamService(),
            )
        )

    assert error.value.status_code == 400
    assert "definition" in str(error.value)


def test_chat_stream_endpoint_is_in_openapi_schema():
    app = create_app()

    schema = app.openapi()

    assert "/api/chat/stream" in schema["paths"]
    assert "post" in schema["paths"]["/api/chat/stream"]


def test_llm_job_status_route_returns_job_details(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.get_job_status",
        lambda job_id: LLMCallJob(
            job_id=job_id,
            call_type="streaming_text_generation",
            messages=[],
            status="queued",
        ),
    )

    response = asyncio.run(llm_job_status("job-123"))

    assert isinstance(response, LLMJobStatusResponse)
    assert response.job.job_id == "job-123"


def test_cancel_llm_job_route_returns_job_details(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.cancel_llm_call",
        lambda job_id: LLMCallJob(
            job_id=job_id,
            call_type="streaming_text_generation",
            messages=[],
            status="cancelled",
            cancel_requested=True,
        ),
    )

    response = asyncio.run(cancel_llm_job("job-123"))

    assert response.job.status == "cancelled"
    assert response.job.cancel_requested is True
