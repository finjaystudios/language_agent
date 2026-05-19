import os
import re
import shutil
import subprocess  # nosec B404
from pathlib import Path

MODEL_PATH = os.getenv("MODEL_PATH", "models/qwen2.5-7B-instruct-Q4_K_M.gguf")
N_CTX = int(os.getenv("LLM_N_CTX", "4096"))
RESERVED_VRAM_GB = float(os.getenv("LLM_RESERVED_VRAM_GB", "1.5"))

QWEN_LAYER_COUNTS = {
    "0.5b": 24,
    "1.5b": 28,
    "3b": 36,
    "7b": 28,
    "14b": 48,
    "32b": 64,
}
NVIDIA_SMI_QUERIES = {
    "memory.free",
    "name,memory.total,memory.free",
}
"""
Fallback layer counts for common Qwen2.5 models. Used only when full offload is unlikely to fit and we need a partial-offload estimate.
"""


def _nvidia_smi_path() -> str:
    nvidia_smi_path = shutil.which("nvidia-smi")
    if nvidia_smi_path is None:
        raise RuntimeError(
            "CUDA enforcement failed: 'nvidia-smi' was not found. "
            "Install/repair the NVIDIA driver, then confirm `nvidia-smi` works."
        )
    return nvidia_smi_path


def _run_nvidia_smi(query: str) -> str:
    if query not in NVIDIA_SMI_QUERIES:
        raise ValueError(f"Unsupported nvidia-smi query: {query}")

    result = subprocess.run(
        [
            _nvidia_smi_path(),
            f"--query-gpu={query}",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        check=False,
    )  # nosec B603
    if result.returncode != 0:
        raise RuntimeError(
            "CUDA enforcement failed: NVIDIA GPU is not visible.\n"
            f"nvidia-smi error:\n{result.stderr.strip()}"
        )
    return result.stdout.strip().splitlines()[0]


def _gpu_free_vram_gb() -> float:
    # nvidia-smi reports MiB when using nounits.
    free_mib = float(_run_nvidia_smi("memory.free").split(",")[0].strip())
    return free_mib / 1024


def _model_size_gb(model_path: str) -> float:
    path = Path(model_path)
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path.resolve()}")
    return path.stat().st_size / (1024**3)


def _guess_qwen_layers(model_path: str) -> int:
    name = Path(model_path).name.lower()
    for size, layers in QWEN_LAYER_COUNTS.items():
        if re.search(rf"(^|[-_]){re.escape(size)}([-_]|$)", name):
            return layers
    # Conservative fallback. If this is wrong, set LLM_GPU_LAYERS manually.
    return 28


def assert_nvidia_gpu_visible() -> None:
    gpu_info = _run_nvidia_smi("name,memory.total,memory.free")
    print(f"CUDA GPU detected: {gpu_info}")


def assert_llama_cpp_gpu_offload_supported() -> None:
    try:
        from llama_cpp import llama_supports_gpu_offload
    except ImportError:
        print(
            "Warning: this llama-cpp-python version does not expose "
            "llama_supports_gpu_offload(). Relying on verbose load logs."
        )
        return

    if not llama_supports_gpu_offload():
        raise RuntimeError(
            """
            CUDA enforcement failed: llama-cpp-python was installed without GPU offload support.\n
            Install a CUDA wheel, for example:\n
              pip uninstall -y llama-cpp-python\n
              pip cache purge\n
              pip install llama-cpp-python --index-url
            https://abetlen.github.io/llama-cpp-python/whl/cu124
            """
        )


def choose_gpu_layers(model_path: str) -> int:
    """
    Choose n_gpu_layers based on free VRAM and model file size.

    - Returns -1 when full offload should fit.
    - Otherwise estimates a partial layer count.
    - Override with LLM_GPU_LAYERS, e.g. PowerShell:
        $env:LLM_GPU_LAYERS="20"
    """
    override = os.getenv("LLM_GPU_LAYERS")
    if override is not None:
        return int(override)

    free_gb = _gpu_free_vram_gb()
    model_gb = _model_size_gb(model_path)

    # KV cache, CUDA buffers, and Windows display usage need headroom.
    budget_gb = max(0.0, free_gb - RESERVED_VRAM_GB)

    if model_gb <= budget_gb:
        print(
            f"""
            VRAM tuner: full GPU offload selected
            (model={model_gb:.2f}GB, free={free_gb:.2f}GB, reserve={RESERVED_VRAM_GB:.2f}GB)."""
        )
        return -1

    total_layers = _guess_qwen_layers(model_path)
    # Estimate only the weight portion; leave reserve untouched.
    fraction = max(0.0, min(1.0, budget_gb / model_gb))
    layers = max(0, int(total_layers * fraction) - 1)

    print(
        f"VRAM tuner: partial GPU offload selected "
        f"(n_gpu_layers={layers}/{total_layers}, model={model_gb:.2f}GB, "
        f"free={free_gb:.2f}GB, reserve={RESERVED_VRAM_GB:.2f}GB). "
        "For more speed, close GPU-heavy apps or lower LLM_RESERVED_VRAM_GB."
    )
    return layers
