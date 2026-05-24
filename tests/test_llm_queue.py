import asyncio
import threading
import time
from types import SimpleNamespace
from unittest.mock import sentinel

from app.application.agent_service import AgentService
from app.application.models import ChatCommand
from app.data_models.intent_result import IntentResult
from app.domain.jobs import LLMCallJob
from app.infrastructure.redis.queued_gateway import QueuedLLMService
from app.memory.short_term import ConversationMemory
from app.worker.jobs import get_worker_class, process_llm_call


class FakeRouter:
    def __init__(self, intent):
        self.intent = intent

    async def classify(self, user_input, session_state, conversation_history):
        return self.intent

    def apply_intent(self, session_state, intent):
        if intent.should_switch_mode:
            session_state.active_mode = intent.mode
        return session_state


class RecordingGateway:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def ask_llm(self, system_prompt, user_prompt, schema, mode=None):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "schema": schema,
                "mode": mode,
            }
        )
        return self.responses.pop(0)

    async def stream_llm(self, system_prompt, user_prompt, mode=None):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "mode": mode,
            }
        )
        yield "queued response"


def test_queued_gateway_enqueues_and_waits(monkeypatch):
    captured = {}

    async def fake_enqueue(job):
        captured["job"] = job

    async def fake_wait(job_id):
        return LLMCallJob(
            job_id=job_id,
            call_type="structured_json",
            messages=[],
            status="completed",
            result={"response": "hello"},
        )

    monkeypatch.setattr(
        "app.infrastructure.redis.queued_gateway.enqueue_llm_call", fake_enqueue
    )
    monkeypatch.setattr(
        "app.infrastructure.redis.queued_gateway.wait_for_job_result", fake_wait
    )

    service = QueuedLLMService()
    result = asyncio.run(service.ask_llm("system", "user", {"type": "object"}))

    assert result == {"response": "hello"}
    assert captured["job"].call_type == "structured_json"
    assert captured["job"].messages[0]["role"] == "system"
    assert captured["job"].messages[1]["content"] == "user"


def test_chat_full_translation_creates_multiple_llm_jobs():
    gateway = RecordingGateway(
        [
            {
                "participant_a_language": "English",
                "participant_b_language": "French",
                "direction": "auto",
                "style": "single_user",
            },
            {
                "response": "bonjour",
                "source_language": "English",
                "target_language": "French",
                "translated_text": "bonjour",
            },
        ]
    )
    service = AgentService(
        llm_service=gateway,
        router=FakeRouter(
            IntentResult(
                mode="general",
                confidence="high",
                should_switch_mode=False,
                reason="Mode supplied by API request.",
            )
        ),
        memory=ConversationMemory(),
    )

    response = asyncio.run(
        service.chat_full(ChatCommand(message="Translate hello", mode="translation"))
    )

    assert response.response == "bonjour"
    assert [call["mode"] for call in gateway.calls] == ["translation", "translation"]


def test_worker_processes_mocked_llm_call(monkeypatch):
    class FakeService:
        def ask_llm_sync(self, *, messages, schema, temperature, max_tokens):
            assert messages[1]["content"] == "user"
            assert schema == {"type": "object"}
            return {"response": "done"}

    monkeypatch.setattr("app.worker.jobs.get_worker_llm_service", lambda: FakeService())
    monkeypatch.setattr("app.worker.jobs.get_current_job", lambda: None)
    monkeypatch.setattr("app.worker.jobs.is_cancel_requested", lambda *args: False)
    monkeypatch.setattr(
        "app.worker.jobs.record_wait_time", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "app.worker.jobs.record_completion_metrics",
        lambda *args, **kwargs: None,
    )

    result = process_llm_call(
        LLMCallJob(
            job_id="job-1",
            call_type="structured_json",
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            response_schema={"type": "object"},
            generation_parameters={"temperature": 0.1, "max_tokens": 2000},
        ).model_dump(mode="json")
    )

    assert result["status"] == "completed"
    assert result["result"] == {"response": "done"}


def test_worker_serializes_mocked_llm_calls(monkeypatch):
    state = {"active": 0, "max_active": 0}
    state_lock = threading.Lock()

    class FakeService:
        def generate_text_sync(self, *, messages, temperature, max_tokens):
            with state_lock:
                state["active"] += 1
                state["max_active"] = max(state["max_active"], state["active"])
            time.sleep(0.05)
            with state_lock:
                state["active"] -= 1
            return messages[1]["content"]

    monkeypatch.setattr("app.worker.jobs.get_worker_llm_service", lambda: FakeService())
    monkeypatch.setattr("app.worker.jobs.get_current_job", lambda: None)
    monkeypatch.setattr("app.worker.jobs.is_cancel_requested", lambda *args: False)
    monkeypatch.setattr(
        "app.worker.jobs.record_wait_time", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "app.worker.jobs.record_completion_metrics",
        lambda *args, **kwargs: None,
    )

    payloads = [
        LLMCallJob(
            job_id=f"job-{index}",
            call_type="text_generation",
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": f"user-{index}"},
            ],
            generation_parameters={"temperature": 0.1, "max_tokens": 2000},
        ).model_dump(mode="json")
        for index in range(2)
    ]

    threads = [
        threading.Thread(target=process_llm_call, args=(payload,))
        for payload in payloads
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert state["max_active"] == 1


def test_worker_streaming_publishes_mocked_token_chunks(monkeypatch):
    events = []

    class FakeService:
        def stream_llm_sync(self, *, messages, temperature, max_tokens):
            yield {"choices": [{"delta": {"content": "bon"}}]}
            yield {"choices": [{"delta": {"content": "jour"}}]}

    class FakeJob:
        def __init__(self):
            self.connection = object()
            self.meta = {}

        def save_meta(self):
            return None

    monkeypatch.setattr("app.worker.jobs.get_worker_llm_service", lambda: FakeService())
    monkeypatch.setattr("app.worker.jobs.get_current_job", lambda: FakeJob())
    monkeypatch.setattr("app.worker.jobs.is_cancel_requested", lambda *args: False)
    monkeypatch.setattr(
        "app.worker.jobs.record_wait_time", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(
        "app.worker.jobs.record_completion_metrics",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.worker.jobs.append_stream_event",
        lambda _job_id, payload, _connection: events.append(payload),
    )

    result = process_llm_call(
        LLMCallJob(
            job_id="stream-job",
            call_type="streaming_text_generation",
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ],
            generation_parameters={"temperature": 0.1, "max_tokens": 2000},
        ).model_dump(mode="json")
    )

    assert result["status"] == "completed"
    assert result["result"] == "bonjour"
    assert [event.get("status") for event in events[:2]] == ["processing", "streaming"]
    assert [event.get("token") for event in events if event.get("token")] == [
        "bon",
        "jour",
    ]
    assert events[-1]["done"] is True


def test_cancelling_queued_job_marks_it_cancelled(monkeypatch):
    from app.infrastructure.redis.queue_service import cancel_llm_call

    events = []
    fake_job = SimpleNamespace(
        meta={},
        set_status=lambda status: None,
        save_meta=lambda: None,
        get_status=lambda refresh=True: "queued",
    )
    queued_call = LLMCallJob(
        job_id="queued-job",
        call_type="streaming_text_generation",
        messages=[],
        status="queued",
    )
    monkeypatch.setattr(
        "app.infrastructure.redis.rq_queue.RQQueueClient.get_job",
        lambda _self, *_args, **_kwargs: fake_job,
    )
    monkeypatch.setattr(
        "app.infrastructure.redis.job_store.RedisJobStore.get_job_result",
        lambda _self, *_args, **_kwargs: queued_call,
    )
    monkeypatch.setattr(
        "app.infrastructure.redis.rq_queue.RQQueueClient.get_job_status",
        lambda _self, *_args, **_kwargs: "queued",
    )
    monkeypatch.setattr(
        "app.infrastructure.redis.rq_queue.RQQueueClient.remove",
        lambda _self, *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.infrastructure.redis.job_store.RedisJobStore.append_stream_event",
        lambda _self, _job_id, payload: events.append(payload),
    )

    result = asyncio.run(cancel_llm_call("queued-job", connection=object()))

    assert result.status == "cancelled"
    assert result.cancel_requested is True
    assert events[-1]["status"] == "cancelled"


def test_cancelling_running_job_sets_cancel_requested(monkeypatch):
    from app.infrastructure.redis.queue_service import cancel_llm_call

    events = []
    fake_job = SimpleNamespace(
        meta={},
        save_meta=lambda: None,
        get_status=lambda refresh=True: "started",
    )
    running_call = LLMCallJob(
        job_id="running-job",
        call_type="streaming_text_generation",
        messages=[],
        status="streaming",
    )

    monkeypatch.setattr(
        "app.infrastructure.redis.rq_queue.RQQueueClient.get_job",
        lambda _self, *_args, **_kwargs: fake_job,
    )
    monkeypatch.setattr(
        "app.infrastructure.redis.job_store.RedisJobStore.get_job_result",
        lambda _self, *_args, **_kwargs: running_call,
    )
    monkeypatch.setattr(
        "app.infrastructure.redis.rq_queue.RQQueueClient.get_job_status",
        lambda _self, *_args, **_kwargs: "started",
    )
    monkeypatch.setattr(
        "app.infrastructure.redis.job_store.RedisJobStore.append_stream_event",
        lambda _self, _job_id, payload: events.append(payload),
    )

    result = asyncio.run(cancel_llm_call("running-job", connection=object()))

    assert result.cancel_requested is True
    assert result.status == "streaming"
    assert events[-1]["cancel_requested"] is True


def test_agent_service_from_queue_does_not_load_local_model(monkeypatch):
    def fail_local_model_load():
        raise AssertionError("Local model should not load in the API process.")

    monkeypatch.setattr(
        "app.infrastructure.llm.local_model.create_local_llm_service",
        fail_local_model_load,
    )

    service = AgentService.from_queue()

    assert isinstance(service.llm_service, QueuedLLMService)


def test_worker_uses_simpleworker_on_windows(monkeypatch):
    monkeypatch.setattr("app.worker.jobs.SimpleWorker", sentinel.spawn_worker)
    monkeypatch.setattr("app.worker.jobs.Worker", sentinel.worker)

    assert get_worker_class() is sentinel.spawn_worker


def test_worker_uses_simpleworker_off_windows(monkeypatch):
    monkeypatch.setattr("app.worker.jobs.SimpleWorker", sentinel.spawn_worker)
    monkeypatch.setattr("app.worker.jobs.Worker", sentinel.worker)

    assert get_worker_class() is sentinel.spawn_worker
