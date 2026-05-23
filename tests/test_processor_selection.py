import importlib
import sys

import pytest


def reload_processor_selection(monkeypatch, **env):
    for key in (
        "LLM_MODEL_PATH",
        "MODEL_PATH",
        "LLM_CONTEXT_SIZE",
        "LLM_N_CTX",
        "LLM_THREADS",
        "LLM_RESERVED_VRAM_GB",
        "LLM_N_GPU_LAYERS",
        "LLM_GPU_LAYERS",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    sys.modules.pop("app.processor_selection", None)
    return importlib.import_module("app.processor_selection")


def test_model_path_comes_from_environment(monkeypatch):
    processor_selection = reload_processor_selection(
        monkeypatch, LLM_MODEL_PATH="models/custom.gguf"
    )

    assert processor_selection.MODEL_PATH == "models/custom.gguf"


def test_model_path_keeps_legacy_environment_fallback(monkeypatch):
    processor_selection = reload_processor_selection(
        monkeypatch, MODEL_PATH="models/legacy.gguf"
    )

    assert processor_selection.MODEL_PATH == "models/legacy.gguf"


def test_llm_model_path_takes_precedence(monkeypatch):
    processor_selection = reload_processor_selection(
        monkeypatch,
        LLM_MODEL_PATH="models/container.gguf",
        MODEL_PATH="models/legacy.gguf",
    )

    assert processor_selection.MODEL_PATH == "models/container.gguf"


def test_model_path_is_required(monkeypatch):
    processor_selection = reload_processor_selection(monkeypatch)

    with pytest.raises(RuntimeError) as error:
        processor_selection.require_model_path()

    assert "Set LLM_MODEL_PATH" in str(error.value)


def test_docker_model_path_resolves_to_local_model_when_running_from_repo(
    monkeypatch, tmp_path
):
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    model = models_dir / "model.gguf"
    model.write_bytes(b"model")
    monkeypatch.chdir(tmp_path)
    processor_selection = reload_processor_selection(
        monkeypatch, LLM_MODEL_PATH="/models/model.gguf"
    )

    assert processor_selection.require_model_path() == str(model)


def test_model_file_must_exist(monkeypatch):
    processor_selection = reload_processor_selection(monkeypatch)

    with pytest.raises(FileNotFoundError) as error:
        processor_selection.assert_model_file_exists("missing-model.gguf")

    assert "host-local run" in str(error.value)
    assert "For Docker" in str(error.value)


def test_model_file_exists_accepts_file(monkeypatch, tmp_path):
    model = tmp_path / "model.gguf"
    model.write_bytes(b"model")
    processor_selection = reload_processor_selection(monkeypatch)

    processor_selection.assert_model_file_exists(str(model))


def test_n_ctx_comes_from_environment(monkeypatch):
    processor_selection = reload_processor_selection(
        monkeypatch, LLM_CONTEXT_SIZE="8192"
    )

    assert processor_selection.N_CTX == 8192


def test_n_ctx_keeps_legacy_environment_fallback(monkeypatch):
    processor_selection = reload_processor_selection(monkeypatch, LLM_N_CTX="2048")

    assert processor_selection.N_CTX == 2048


def test_n_threads_comes_from_environment(monkeypatch):
    processor_selection = reload_processor_selection(monkeypatch, LLM_THREADS="8")

    assert processor_selection.N_THREADS == 8


def test_choose_gpu_layers_uses_environment_override(monkeypatch):
    processor_selection = reload_processor_selection(monkeypatch, LLM_N_GPU_LAYERS="12")

    assert processor_selection.choose_gpu_layers("missing-model.gguf") == 12


def test_choose_gpu_layers_keeps_legacy_environment_override(monkeypatch):
    processor_selection = reload_processor_selection(monkeypatch, LLM_GPU_LAYERS="10")

    assert processor_selection.choose_gpu_layers("missing-model.gguf") == 10


def test_model_size_raises_for_missing_model_file(monkeypatch):
    processor_selection = reload_processor_selection(monkeypatch)

    with pytest.raises(FileNotFoundError) as error:
        processor_selection._model_size_gb("missing-model.gguf")

    assert "Model file not found" in str(error.value)


def test_nvidia_smi_rejects_unsupported_query(monkeypatch):
    processor_selection = reload_processor_selection(monkeypatch)

    with pytest.raises(ValueError) as error:
        processor_selection._run_nvidia_smi("driver_version")

    assert "Unsupported nvidia-smi query" in str(error.value)
