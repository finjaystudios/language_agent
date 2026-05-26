from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


class ModelProfileConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class ModelMetadata:
    active_model_id: str
    active_model_name: str
    backend: str


@dataclass(frozen=True)
class ModelProfile:
    name: str
    model: str
    reasoning: str
    prompt_control: str
    temperature: float
    top_p: float
    top_k: int
    min_p: float
    max_tokens: int
    stream: bool

    def generation_parameters(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "min_p": self.min_p,
            "max_tokens": self.max_tokens,
        }


@dataclass(frozen=True)
class ModelProfiles:
    model: ModelMetadata
    profiles: dict[str, ModelProfile]

    def select(self, mode: str | None) -> ModelProfile:
        if mode == "general" and "general" in self.profiles:
            return self.profiles["general"]
        if mode and mode in self.profiles:
            return self.profiles[mode]
        return self.profiles["default"]


def _normalize_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return Path.cwd() / candidate


def _require_mapping(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ModelProfileConfigurationError(f"{label} must be a mapping.")
    return value


def _require_string(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelProfileConfigurationError(f"{label} must be a non-empty string.")
    return value.strip()


def _require_float(value: Any, *, label: str) -> float:
    if not isinstance(value, (int, float)):
        raise ModelProfileConfigurationError(f"{label} must be a number.")
    return float(value)


def _require_int(value: Any, *, label: str) -> int:
    if not isinstance(value, int):
        raise ModelProfileConfigurationError(f"{label} must be an integer.")
    return value


def _require_bool(value: Any, *, label: str) -> bool:
    if not isinstance(value, bool):
        raise ModelProfileConfigurationError(f"{label} must be a boolean.")
    return value


def _parse_profile(name: str, data: Any) -> ModelProfile:
    mapping = _require_mapping(data, label=f"profiles.{name}")
    reasoning = _require_string(
        mapping.get("reasoning"), label=f"profiles.{name}.reasoning"
    )
    if reasoning not in {"on", "off"}:
        raise ModelProfileConfigurationError(
            f"profiles.{name}.reasoning must be 'on' or 'off'."
        )
    prompt_control = _require_string(
        mapping.get("prompt_control"),
        label=f"profiles.{name}.prompt_control",
    )
    if prompt_control not in {"/think", "/no_think"}:
        raise ModelProfileConfigurationError(
            f"profiles.{name}.prompt_control must be '/think' or '/no_think'."
        )
    return ModelProfile(
        name=name,
        model=_require_string(mapping.get("model"), label=f"profiles.{name}.model"),
        reasoning=reasoning,
        prompt_control=prompt_control,
        temperature=_require_float(
            mapping.get("temperature"), label=f"profiles.{name}.temperature"
        ),
        top_p=_require_float(mapping.get("top_p"), label=f"profiles.{name}.top_p"),
        top_k=_require_int(mapping.get("top_k"), label=f"profiles.{name}.top_k"),
        min_p=_require_float(mapping.get("min_p"), label=f"profiles.{name}.min_p"),
        max_tokens=_require_int(
            mapping.get("max_tokens"), label=f"profiles.{name}.max_tokens"
        ),
        stream=_require_bool(mapping.get("stream"), label=f"profiles.{name}.stream"),
    )


def load_model_profiles(path: str) -> ModelProfiles:
    resolved_path = _normalize_path(path)
    if not resolved_path.exists():
        raise ModelProfileConfigurationError(
            f"Model profiles file not found: {resolved_path}"
        )

    with resolved_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    root = _require_mapping(raw, label="model_profiles")
    model_mapping = _require_mapping(root.get("model"), label="model")
    profiles_mapping = _require_mapping(root.get("profiles"), label="profiles")
    if "default" not in profiles_mapping:
        raise ModelProfileConfigurationError(
            "Model profiles must define a default profile."
        )

    model = ModelMetadata(
        active_model_id=_require_string(
            model_mapping.get("active_model_id"), label="model.active_model_id"
        ),
        active_model_name=_require_string(
            model_mapping.get("active_model_name"), label="model.active_model_name"
        ),
        backend=_require_string(model_mapping.get("backend"), label="model.backend"),
    )
    profiles = {
        name: _parse_profile(name, profile_data)
        for name, profile_data in profiles_mapping.items()
    }
    return ModelProfiles(model=model, profiles=profiles)


@lru_cache(maxsize=8)
def get_model_profiles(path: str) -> ModelProfiles:
    return load_model_profiles(path)


def clear_model_profiles_cache() -> None:
    get_model_profiles.cache_clear()
