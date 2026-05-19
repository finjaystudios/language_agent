"""Load prompt templates from YAML files."""

from pathlib import Path


PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(prompt_name: str) -> str:
    """Load a prompt by name from the prompts directory."""
    path = PROMPTS_DIR / f"{prompt_name}.yaml"

    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")

    return _load_prompt_yaml(path)


def _load_prompt_yaml(path: Path) -> str:
    """Load the single `prompt` block from a simple YAML prompt file."""
    lines = path.read_text(encoding="utf-8").splitlines()

    if not lines or lines[0].strip() != "prompt: |":
        raise ValueError(f"Prompt file must start with 'prompt: |': {path}")

    prompt_lines = []
    for line in lines[1:]:
        if line.startswith("  "):
            prompt_lines.append(line[2:])
        elif not line:
            prompt_lines.append("")
        else:
            raise ValueError(f"Unexpected YAML content in prompt file: {path}")

    return "\n".join(prompt_lines).strip() + "\n"
