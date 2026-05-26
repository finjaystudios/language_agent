import asyncio

from app.application.modes.definition import DefinitionHandler
from app.application.modes.learning import LearningHandler
from app.application.modes.translation import TranslationHandler
from app.domain.session_states import SessionState


class FakeLLM:
    def __init__(self, response):
        self.response = response
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
        return self.response

    async def stream_llm(self, system_prompt, user_prompt, mode=None):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "mode": mode,
            }
        )
        yield "bonjour"


async def collect_async(async_iterable):
    return [item async for item in async_iterable]


def test_translation_update_session_state_sets_translation_mode_state():
    handler = TranslationHandler(
        FakeLLM(
            {
                "participant_a_language": "English",
                "participant_b_language": "French",
                "direction": "auto",
                "style": "single_user",
            }
        )
    )

    result = asyncio.run(
        handler.update_session_state(
            "translate hello to French", SessionState(), "history"
        )
    )

    assert result.translation.participant_b_language == "French"


def test_definition_update_session_state_sets_current_term():
    handler = DefinitionHandler(
        FakeLLM(
            {
                "current_term": "bonjour",
                "language": "French",
                "sense": None,
            }
        )
    )

    result = asyncio.run(
        handler.update_session_state("define bonjour", SessionState(), "history")
    )

    assert result.definition.current_term == "bonjour"


def test_learning_update_session_state_sets_lesson_step():
    handler = LearningHandler(
        FakeLLM(
            {
                "target_language": "Spanish",
                "native_language": "English",
                "level": "beginner",
                "current_topic": "present tense",
                "lesson_step": 2,
            }
        )
    )

    result = asyncio.run(
        handler.update_session_state("continue", SessionState(), "history")
    )

    assert result.learning.lesson_step == 2


def test_definition_handle_returns_definition_response_model():
    handler = DefinitionHandler(
        FakeLLM(
            {
                "term": "bonjour",
                "language": "French",
                "part_of_speech": "interjection",
                "pronunciation": "",
                "meaning": "hello",
                "examples": [],
                "synonyms": [],
                "antonyms": [],
                "etymology": "",
                "response": "bonjour means hello",
            }
        )
    )

    result = asyncio.run(handler.handle("define bonjour", SessionState(), "history"))

    assert result.response == "bonjour means hello"


def test_translation_stream_returns_model_tokens():
    handler = TranslationHandler(FakeLLM({}))

    result = asyncio.run(
        collect_async(handler.stream("hello", SessionState(), "history"))
    )

    assert result == ["bonjour"]
