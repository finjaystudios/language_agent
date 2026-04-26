LANGUAGE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "task_type": {
            "type": "string",
            "enum": ["translation", "definition", "learning_support", "general", "clarification"],
            "description": "The main kind of task the user is asking for."
        },
        "source_language": {
            "type": "string",
            "description": "The detected or provided source language. Use 'unknown' if unclear."
        },
        "target_language": {
            "type": "string",
            "description": "The target language for translation, or 'not_applicable'."
        },
        "response": {
            "type": "string",
            "description": "The main answer to show to the user."
        },
        "definition": {
            "type": "object",
            "description": "Dictionary-style details when the task is a word or phrase definition.",
            "properties": {
                "term": {"type": "string"},
                "part_of_speech": {"type": "string"},
                "pronunciation": {"type": "string"},
                "meaning": {"type": "string"},
                "examples": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "synonyms": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "antonyms": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "etymology": {"type": "string"}
            },
            "required": ["term", "meaning"]
        },
        # "notes": {
        #     "type": "array",
        #     "description": "Extra grammar, usage, cultural, or learning notes.",
        #     "items": {"type": "string"}
        # },
        "needs_clarification": {
            "type": "boolean",
            "description": "True if the assistant cannot safely answer without more information."
        },
        "clarification_question": {
            "type": "string",
            "description": "Question to ask the user if the request is ambiguous."
        }
    },
    "required": [
        "task_type",
        "source_language",
        "target_language",
        "response",
        "needs_clarification",
        "clarification_question"
    ]
}

LITE_LANGUAGE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "response": {
            "type": "string",
            "description": "The main answer to show to the user."
        },
    },
    "required": [
        "response",
    ]
}