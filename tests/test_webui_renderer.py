from webui.renderer import render_chat_response


def test_render_definition_prefers_structured_definition_data():
    result = {
        "mode": "definition",
        "response": "Would you like an example sentence?",
        "data": {
            "mode": "definition",
            "response": "Would you like an example sentence?",
            "term": "recursion",
            "language": "English",
            "part_of_speech": "noun",
            "pronunciation": "ri-KUR-zhun",
            "meaning": "A process where a function calls itself.",
            "examples": ["The recursive function handles nested folders."],
            "synonyms": ["self-reference"],
            "antonyms": ["iteration"],
            "etymology": "From Latin recurrere, to run back.",
        },
    }

    rendered = render_chat_response(result)

    assert "**recursion (noun)**" in rendered
    assert "A process where a function calls itself." in rendered
    assert "The recursive function handles nested folders." in rendered
    assert "self-reference" in rendered
    assert "iteration" in rendered
    assert "Would you like an example sentence?" in rendered


def test_render_chat_response_falls_back_to_top_level_response():
    assert (
        render_chat_response({"mode": "general", "response": "Which mode do you want?"})
        == "Which mode do you want?"
    )


def test_render_translation_uses_translated_text():
    result = {
        "mode": "translation",
        "response": "bonjour",
        "data": {
            "mode": "translation",
            "response": "bonjour",
            "source_language": "English",
            "target_language": "French",
            "translated_text": "bonjour",
        },
    }

    rendered = render_chat_response(result)

    assert rendered.startswith("bonjour")
    assert "`English` -> `French`" in rendered
