import asyncio

from app.application.intent_router import IntentRouter
from app.domain.intent_result import IntentResult
from app.domain.session_states import SessionState


class FakeLLM:
    def __init__(self, response):
        self.response = response

    async def ask_llm(self, system_prompt, user_prompt, schema, mode=None):
        return self.response


def test_classify_returns_intent_result_from_llm_response():
    router = IntentRouter(
        FakeLLM(
            {
                "mode": "translation",
                "confidence": "high",
                "should_switch_mode": True,
                "reason": "User asked to translate.",
                "clarification_question": "",
            }
        )
    )

    result = asyncio.run(
        router.classify("translate hello", SessionState(), "No previous conversation.")
    )

    assert result.mode == "translation"


def test_apply_intent_switches_active_mode_when_requested():
    router = IntentRouter(FakeLLM({}))
    session_state = SessionState(active_mode="general")
    intent = IntentResult(
        mode="learning",
        confidence="high",
        should_switch_mode=True,
        reason="User asked to learn.",
    )

    result = router.apply_intent(session_state, intent)

    assert result.active_mode == "learning"


def test_apply_intent_preserves_active_mode_when_switch_not_requested():
    router = IntentRouter(FakeLLM({}))
    session_state = SessionState(active_mode="translation")
    intent = IntentResult(
        mode="definition",
        confidence="medium",
        should_switch_mode=False,
        reason="Follow-up.",
    )

    result = router.apply_intent(session_state, intent)

    assert result.active_mode == "translation"
