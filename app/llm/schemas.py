INTENT_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "mode": {
            "type": "string",
            "enum": ["translation", "definition", "learning", "general"],
            "description": "The mode that should handle the user's current input."
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "How confident the classifier is."
        },
        "should_switch_mode": {
            "type": "boolean",
            "description": "Whether the app should change from the current mode to the selected mode."
        },
        "reason": {
            "type": "string",
            "description": "Brief reason for the classification."
        },
        "clarification_question": {
            "type": "string",
            "description": "Question to ask if the user's intent is ambiguous."
        }
    },
    "required": [
        "mode",
        "confidence",
        "should_switch_mode",
        "reason",
        "clarification_question"
    ]
}

TRANSLATION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "source_language": {
            "type": "string",
            "description": "Detected or provided source language. Use 'unknown' if unclear."
        },
        "target_language": {
            "type": "string",
            "description": "Target language used for the translation. Use 'unknown' if unclear."
        },
        "translated_text": {
            "type": "string",
            "description": "The translated text only, without filler words or labels."
        },
        "response": {
            "type": "string",
            "description": "The user-facing response. For translation mode, this should usually equal translated_text."
        },
    },
    "required": [
        "source_language",
        "target_language",
        "translated_text",
        "response",
    ]
}

DEFINITION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "term": {
            "type": "string",
            "description": "The word or phrase being defined."
        },
        "language": {
            "type": "string",
            "description": "Language of the term. Use 'unknown' if unclear."
        },
        "part_of_speech": {
            "type": "string",
            "description": "Grammatical category, such as noun, verb, adjective, phrase, etc."
        },
        "pronunciation": {
            "type": "string",
            "description": "Pronunciation using IPA or simple phonetic guidance, if known."
        },
        "meaning": {
            "type": "string",
            "description": "Clear definition of the term."
        },
        "examples": {
            "type": "array",
            "description": "Example sentences showing the term in use.",
            "items": {"type": "string"}
        },
        "synonyms": {
            "type": "array",
            "description": "Words or phrases with similar meaning.",
            "items": {"type": "string"}
        },
        "antonyms": {
            "type": "array",
            "description": "Words or phrases with opposite meaning.",
            "items": {"type": "string"}
        },
        "etymology": {
            "type": "string",
            "description": "Brief origin/history of the term, if known."
        },
        "response": {
            "type": "string",
            "description": "Markdown-formatted user-facing dictionary response."
        },
    },
    "required": [
        "term",
        "language",
        "part_of_speech",
        "pronunciation",
        "meaning",
        "examples",
        "synonyms",
        "antonyms",
        "etymology",
        "response",
    ]
}

LEARNING_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "target_language": {
            "type": "string",
            "description": "Language the user is learning. Use 'unknown' if unclear."
        },
        "native_language": {
            "type": "string",
            "description": "User's native or preferred explanation language. Use 'unknown' if unclear."
        },
        "level": {
            "type": "string",
            "enum": ["beginner", "intermediate", "advanced", "unknown"],
            "description": "Estimated learner level."
        },
        "topic": {
            "type": "string",
            "description": "Current learning topic."
        },
        "teaching_point": {
            "type": "string",
            "description": "Main concept taught in this response."
        },
        "examples": {
            "type": "array",
            "description": "Examples used to teach the concept.",
            "items": {"type": "string"}
        },
        "corrections": {
            "type": "array",
            "description": "Corrections to the user's language usage, if applicable.",
            "items": {"type": "string"}
        },
        "new_vocabulary": {
            "type": "array",
            "description": "New words or phrases introduced in the response.",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "language": {"type": "string"},
                    "meaning": {"type": "string"},
                    "example": {"type": "string"}
                },
                "required": ["term", "language", "meaning", "example"]
            }
        },
        "exercise": {
            "type": "string",
            "description": "One short practice exercise for the user."
        },
        "next_suggested_step": {
            "type": "string",
            "description": "Suggested next learning step."
        },
        "response": {
            "type": "string",
            "description": "Markdown-formatted user-facing tutor response."
        },
    },
    "required": [
        "target_language",
        "native_language",
        "level",
        "topic",
        "teaching_point",
        "response",
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
