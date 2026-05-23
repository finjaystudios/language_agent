import asyncio

import httpx
from app.api.dependencies import get_agent_service
from app.api.errors import QueueSaturatedError
from app.api.main import create_app
from app.data_models.intent_result import IntentResult
from app.memory.short_term import ConversationMemory
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


class SerialGateway:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.active = 0
        self.max_active = 0
        self.call_count = 0

    async def ask_llm(self, system_prompt, user_prompt, schema, mode=None):
        async with self.lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            self.call_count += 1
            await asyncio.sleep(0.02)
            if "participant_a_language" in schema:
                result = {
                    "participant_a_language": "English",
                    "participant_b_language": "French",
                    "direction": "auto",
                    "style": "single_user",
                }
            else:
                result = {
                    "response": "bonjour",
                    "source_language": "English",
                    "target_language": "French",
                    "translated_text": "bonjour",
                }
            self.active -= 1
            return result


def test_chat_endpoint_returns_429_when_queue_is_saturated(monkeypatch):
    from app.llm.queued import QueuedLLMService

    def fail_enqueue(_job):
        raise QueueSaturatedError(retry_after_seconds=9)

    monkeypatch.setattr("app.llm.queued.enqueue_llm_call", fail_enqueue)

    service = QueuedLLMService()

    async def make_call():
        await service.ask_llm("system", "user", {"type": "object"})

    try:
        asyncio.run(make_call())
    except QueueSaturatedError as error:
        assert error.status_code == 429
        assert error.headers["Retry-After"] == "9"
    else:
        raise AssertionError("Expected QueueSaturatedError")


def test_concurrent_endpoint_requests_keep_llm_calls_serialized(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("FASTAPI_API_KEY", "test-secret")

    gateway = SerialGateway()
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

    app = create_app()
    app.dependency_overrides[get_agent_service] = lambda: service

    async def run_test():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            headers={"X-API-Key": "test-secret"},
        ) as client:
            payload = {"message": "Translate hello", "mode": "translation"}
            posts = [client.post("/api/chat", json=payload) for _ in range(3)]
            health = client.get("/health")
            responses = await asyncio.gather(*posts, health)
        return responses

    responses = asyncio.run(run_test())

    assert all(response.status_code == 200 for response in responses[:3])
    assert responses[3].status_code == 200
    assert responses[3].json() == {"status": "ok"}
    assert gateway.call_count == 6
    assert gateway.max_active == 1
