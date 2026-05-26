import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.model_profiles import (  # noqa: E402
    ModelProfileConfigurationError,
    clear_model_profiles_cache,
    get_model_profiles,
    load_model_profiles,
)


def test_loads_yaml_profiles():
    profiles = load_model_profiles("config/model_profiles.yml")

    assert profiles.model.active_model_name == "Qwen3-4B-Q4_K_M"
    assert profiles.select("translation").temperature == 0.3
    assert profiles.select("learning").prompt_control == "/think"


def test_default_profile_is_required(tmp_path):
    path = tmp_path / "profiles.yml"
    path.write_text(
        """
model:
  active_model_id: qwen
  active_model_name: Qwen
  backend: llama_server
profiles:
  intent:
    model: qwen
    reasoning: off
    prompt_control: /no_think
    temperature: 0.1
    top_p: 0.8
    top_k: 20
    min_p: 0
    max_tokens: 128
    stream: false
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ModelProfileConfigurationError) as error:
        load_model_profiles(str(path))

    assert "default profile" in str(error.value).lower()


def test_profile_selection_by_mode_and_unknown_fallback():
    profiles = load_model_profiles("config/model_profiles.yml")

    assert profiles.select("intent").name == "intent"
    assert profiles.select("general").name == "general"
    assert profiles.select("unknown").name == "default"
    assert profiles.select(None).name == "default"


def test_profile_cache_can_be_cleared():
    clear_model_profiles_cache()

    first = get_model_profiles("config/model_profiles.yml")
    second = get_model_profiles("config/model_profiles.yml")

    assert first is second
