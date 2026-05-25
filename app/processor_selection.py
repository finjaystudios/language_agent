from importlib import reload

import app.infrastructure.llm.runtime_config as _runtime_config

_runtime_config = reload(_runtime_config)

MODEL_PATH = _runtime_config.MODEL_PATH
N_CTX = _runtime_config.N_CTX
N_THREADS = _runtime_config.N_THREADS
RESERVED_VRAM_GB = _runtime_config.RESERVED_VRAM_GB
QWEN_LAYER_COUNTS = _runtime_config.QWEN_LAYER_COUNTS
NVIDIA_SMI_QUERIES = _runtime_config.NVIDIA_SMI_QUERIES


def _run_nvidia_smi(query: str) -> str:
    return _runtime_config._run_nvidia_smi(query)


def _model_size_gb(model_path: str) -> float:
    return _runtime_config._model_size_gb(model_path)


def require_model_path() -> str:
    return _runtime_config.require_model_path()


def resolve_model_path(model_path: str) -> str:
    return _runtime_config.resolve_model_path(model_path)


def assert_model_file_exists(model_path: str) -> None:
    _runtime_config.assert_model_file_exists(model_path)


def assert_nvidia_gpu_visible() -> None:
    _runtime_config.assert_nvidia_gpu_visible()


def assert_llama_cpp_gpu_offload_supported() -> None:
    _runtime_config.assert_llama_cpp_gpu_offload_supported()


def choose_gpu_layers(model_path: str) -> int:
    return _runtime_config.choose_gpu_layers(model_path)
