from llm.prompt_loader import load_prompt


INTENT_SYSTEM_PROMPT = load_prompt("intent_system")
INTENT_TASK_PROMPT = load_prompt("intent_task")

TRANSLATION_SYSTEM_PROMPT = load_prompt("translation_system")
TRANSLATION_TASK_PROMPT = load_prompt("translation_task")

DEFINITION_SYSTEM_PROMPT = load_prompt("definition_system")
DEFINITION_TASK_PROMPT = load_prompt("definition_task")

LEARNING_SYSTEM_PROMPT = load_prompt("learning_system")
LEARNING_TASK_PROMPT = load_prompt("learning_task")
