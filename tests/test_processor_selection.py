import importlib
import sys

import pytest


def reload_processor_selection(monkeypatch, **env):
    for key in ("MODEL_PATH", "LLM_N_CTX", "LLM_RESERVED_VRAM_GB", "LLM_GPU_LAYERS"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    sys.modules.pop("processor_selection", None)
    return importlib.import_module("processor_selection")


def test_model_path_comes_from_environment(monkeypatch):
    processor_selection = reload_processor_selection(monkeypatch, MODEL_PATH="models/custom.gguf")

    assert processor_selection.MODEL_PATH == "models/custom.gguf"


def test_n_ctx_comes_from_environment(monkeypatch):
    processor_selection = reload_processor_selection(monkeypatch, LLM_N_CTX="8192")

    assert processor_selection.N_CTX == 8192


def test_choose_gpu_layers_uses_environment_override(monkeypatch):
    processor_selection = reload_processor_selection(monkeypatch, LLM_GPU_LAYERS="12")

    assert processor_selection.choose_gpu_layers("missing-model.gguf") == 12


def test_model_size_raises_for_missing_model_file(monkeypatch):
    processor_selection = reload_processor_selection(monkeypatch)

    with pytest.raises(FileNotFoundError) as error:
        processor_selection._model_size_gb("missing-model.gguf")

    assert "Model file not found" in str(error.value)
