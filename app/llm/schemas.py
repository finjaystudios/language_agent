from llm.schema_loader import load_schema


INTENT_RESPONSE_SCHEMA = load_schema("intent_response")
TRANSLATION_RESPONSE_SCHEMA = load_schema("translation_response")
DEFINITION_RESPONSE_SCHEMA = load_schema("definition_response")
LEARNING_RESPONSE_SCHEMA = load_schema("learning_response")
LITE_LANGUAGE_RESPONSE_SCHEMA = load_schema("lite_language_response")
