"""Load prompt templates from YAML files."""

from pathlib import Path

import yaml


PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(prompt_name: str) -> str:
    """Load a prompt by name from the prompts directory."""
    path = PROMPTS_DIR / f"{prompt_name}.yaml"

    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    prompt_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(prompt_data, dict):
        raise ValueError(f"Prompt file must contain a YAML mapping: {path}")

    prompt = prompt_data.get("prompt")
    if not isinstance(prompt, str):
        raise ValueError(f"Prompt file must contain a string `prompt` value: {path}")

    return prompt
