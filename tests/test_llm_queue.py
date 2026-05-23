import asyncio
import threading
import time
from unittest.mock import sentinel

from app.api.models import ChatRequest
from app.data_models.intent_result import IntentResult
from app.memory.short_term import ConversationMemory
from app.queue.models import LLMCallJob
from app.queue.worker import get_worker_class, process_llm_call
from app.services.agent_service import AgentService


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
    from app.llm.queued import QueuedLLMService

    captured = {}

    def fake_enqueue(job):
        captured["job"] = job

    async def fake_wait(job_id):
        return LLMCallJob(
            job_id=job_id,
            call_type="structured_json",
            messages=[],
            status="completed",
            result={"response": "hello"},
        )

    monkeypatch.setattr("app.llm.queued.enqueue_llm_call", fake_enqueue)
    monkeypatch.setattr("app.llm.queued.wait_for_job_result", fake_wait)

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
        service.chat_full(ChatRequest(message="Translate hello", mode="translation"))
    )

    assert response.response == "bonjour"
    assert [call["mode"] for call in gateway.calls] == ["translation", "translation"]


def test_worker_processes_mocked_llm_call(monkeypatch):
    class FakeService:
        def ask_llm_sync(self, *, messages, schema, temperature, max_tokens):
            assert messages[1]["content"] == "user"
            assert schema == {"type": "object"}
            return {"response": "done"}

    monkeypatch.setattr(
        "app.queue.worker.get_worker_llm_service", lambda: FakeService()
    )
    monkeypatch.setattr("app.queue.worker.get_current_job", lambda: None)

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

    monkeypatch.setattr(
        "app.queue.worker.get_worker_llm_service", lambda: FakeService()
    )
    monkeypatch.setattr("app.queue.worker.get_current_job", lambda: None)

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


def test_worker_uses_simpleworker_on_windows(monkeypatch):
    monkeypatch.setattr("app.queue.worker.os.name", "nt")
    monkeypatch.setattr("app.queue.worker.SimpleWorker", sentinel.spawn_worker)
    monkeypatch.setattr("app.queue.worker.Worker", sentinel.worker)

    assert get_worker_class() is sentinel.spawn_worker


def test_worker_uses_standard_worker_off_windows(monkeypatch):
    monkeypatch.setattr("app.queue.worker.os.name", "posix")
    monkeypatch.setattr("app.queue.worker.SimpleWorker", sentinel.spawn_worker)
    monkeypatch.setattr("app.queue.worker.Worker", sentinel.worker)

    assert get_worker_class() is sentinel.worker
