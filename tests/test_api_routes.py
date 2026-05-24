import asyncio

from app.api.models import (
    ChatRequest,
    LLMJobStatusResponse,
    QueueStatusResponse,
    StreamChatRequest,
)
from app.application.models import ChatResult
from app.application.models import ResponseMetadata as AppResponseMetadata
from app.domain.jobs import LLMCallJob, QueueStatusSnapshot
from app.interfaces.api.main import create_app
from app.interfaces.api.routes import (
    cancel_llm_job,
    chat_full,
    chat_stream,
    llm_job_status,
    queue_status,
)


class FakeAgentService:
    def __init__(self):
        self.request = None

    async def chat_full(self, request):
        self.request = request
        return ChatResult(
            mode="definition",
            response="Recursion is a function calling itself.",
            metadata=AppResponseMetadata(session_id="session-1"),
        )

    async def chat_stream(self, request):
        self.request = request

        async def events():
            yield 'data: {"mode": "translation", "token": "hola"}\n\n'
            yield 'data: {"mode": "translation", "done": true}\n\n'

        return events()


def test_chat_full_route_delegates_to_agent_service():
    service = FakeAgentService()
    request = ChatRequest(
        message="Define recursion in simple terms",
        mode="definition",
        metadata={"session_id": "session-1"},
    )

    response = asyncio.run(chat_full(request=request, agent_service=service))

    assert service.request.message == request.message
    assert service.request.mode == "definition"
    assert service.request.metadata.session_id == "session-1"
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

    assert service.request.message == request.message
    assert service.request.mode == "translation"
    assert response.media_type == "text/event-stream"
    assert asyncio.run(collect_events()) == [
        'data: {"mode": "translation", "token": "hola"}\n\n',
        'data: {"mode": "translation", "done": true}\n\n',
    ]


def test_chat_stream_endpoint_is_in_openapi_schema():
    app = create_app()

    schema = app.openapi()

    assert "/api/chat/stream" in schema["paths"]
    assert "post" in schema["paths"]["/api/chat/stream"]


def test_llm_job_status_route_returns_job_details(monkeypatch):
    async def fake_get_job_status(job_id):
        return LLMCallJob(
            job_id=job_id,
            call_type="streaming_text_generation",
            messages=[],
            status="queued",
        )

    monkeypatch.setattr(
        "app.interfaces.api.routes.get_job_status",
        fake_get_job_status,
    )

    response = asyncio.run(llm_job_status("job-123"))

    assert isinstance(response, LLMJobStatusResponse)
    assert response.job_id == "job-123"


def test_cancel_llm_job_route_returns_job_details(monkeypatch):
    async def fake_cancel_llm_call(job_id):
        return LLMCallJob(
            job_id=job_id,
            call_type="streaming_text_generation",
            messages=[],
            status="cancelled",
            cancel_requested=True,
        )

    monkeypatch.setattr(
        "app.interfaces.api.routes.cancel_llm_call",
        fake_cancel_llm_call,
    )

    response = asyncio.run(cancel_llm_job("job-123"))

    assert response.status == "cancelled"
    assert response.cancel_requested is True


def test_queue_status_route_returns_sanitized_queue_snapshot(monkeypatch):
    async def fake_get_queue_status():
        return QueueStatusSnapshot(
            redis_connected=True,
            queue_depth=2,
            active_job_count=1,
            failed_job_count=0,
            worker_count=1,
            average_wait_time_seconds=1.5,
            estimated_wait_time_seconds=3.0,
        )

    monkeypatch.setattr(
        "app.interfaces.api.routes.get_queue_status",
        fake_get_queue_status,
    )

    response = asyncio.run(queue_status())

    assert isinstance(response, QueueStatusResponse)
    assert response.queue.queue_depth == 2
