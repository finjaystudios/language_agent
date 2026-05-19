from memory.short_term import ConversationMemory


def test_format_for_prompt_returns_no_previous_conversation_when_empty():
    memory = ConversationMemory()

    assert memory.format_for_prompt() == "No previous conversation."


def test_add_turn_keeps_only_last_n_turns():
    memory = ConversationMemory(max_turns=2)
    memory.add_turn("one", "first")
    memory.add_turn("two", "second")
    memory.add_turn("three", "third")

    assert [turn.user_input for turn in memory.turns] == ["two", "three"]


def test_format_for_prompt_includes_turn_numbers_and_messages():
    memory = ConversationMemory()
    memory.add_turn("hola", "hello")

    assert "Turn 1\n                User: hola\n                Assistant: hello" in memory.format_for_prompt()
