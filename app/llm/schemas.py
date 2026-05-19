from llm.schema_loader import load_schema


INTENT_RESPONSE_SCHEMA = load_schema("intent_response")
TRANSLATION_RESPONSE_SCHEMA = load_schema("translation_response")
TRANSLATION_STATE_SCHEMA = load_schema("translation_state")
DEFINITION_RESPONSE_SCHEMA = load_schema("definition_response")
DEFINITION_STATE_SCHEMA = load_schema("definition_state")
LEARNING_RESPONSE_SCHEMA = load_schema("learning_response")
LEARNING_STATE_SCHEMA = load_schema("learning_state")
LITE_LANGUAGE_RESPONSE_SCHEMA = load_schema("lite_language_response")
