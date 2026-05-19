"""Load response schemas from YAML files."""

from pathlib import Path

import yaml

SCHEMAS_DIR = Path(__file__).parent / "schemas"


def load_schema(schema_name: str) -> dict:
    """Load a response schema by name from the schemas directory."""
    path = SCHEMAS_DIR / f"{schema_name}.yaml"

    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")

    schema = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        raise ValueError(f"Schema file must contain a YAML mapping: {path}")

    return schema
