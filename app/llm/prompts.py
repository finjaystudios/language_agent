from llm.prompt_loader import load_prompt


STATE_UPDATE_SYSTEM_PROMPT = load_prompt("state_update_system")

INTENT_SYSTEM_PROMPT = load_prompt("intent_system")
INTENT_TASK_PROMPT = load_prompt("intent_task")

TRANSLATION_SYSTEM_PROMPT = load_prompt("translation_system")
TRANSLATION_TASK_PROMPT = load_prompt("translation_task")
TRANSLATION_STATE_UPDATE_TASK_PROMPT = load_prompt("translation_state_update_task")

DEFINITION_SYSTEM_PROMPT = load_prompt("definition_system")
DEFINITION_TASK_PROMPT = load_prompt("definition_task")
DEFINITION_STATE_UPDATE_TASK_PROMPT = load_prompt("definition_state_update_task")

LEARNING_SYSTEM_PROMPT = load_prompt("learning_system")
LEARNING_TASK_PROMPT = load_prompt("learning_task")
LEARNING_STATE_UPDATE_TASK_PROMPT = load_prompt("learning_state_update_task")
