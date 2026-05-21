STARTER_MODES = {"translation", "definition", "learning"}
STARTER_MESSAGE_MODES = {
    "Translate this sentence to isiXhosa: Good morning, how are you?": "translation",
    "Define recursion in simple terms.": "definition",
    "Teach me three useful French greetings.": "learning",
}


def starter_mode_for_values(command: object, content: str) -> str | None:
    if isinstance(command, str) and command in STARTER_MODES:
        return command
    return STARTER_MESSAGE_MODES.get(content.strip())
