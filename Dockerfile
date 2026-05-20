FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LLM_MODEL_PATH=/models/model.gguf \
    LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cuda_runtime/lib:/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib

WORKDIR /app

COPY requirements.txt .

ARG LLAMA_CPP_PYTHON_INDEX_URL="https://abetlen.github.io/llama-cpp-python/whl/cu124"
ARG NVIDIA_CUDA_RUNTIME_VERSION="12.4.127"
ARG NVIDIA_CUBLAS_VERSION="12.4.5.8"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 \
    && python -m pip install --upgrade pip \
    && grep -v '^llama_cpp_python==' requirements.txt > /tmp/requirements-api.txt \
    && python -m pip install --no-cache-dir -r /tmp/requirements-api.txt \
    && python -m pip install --no-cache-dir \
        "nvidia-cuda-runtime-cu12==$NVIDIA_CUDA_RUNTIME_VERSION" \
        "nvidia-cublas-cu12==$NVIDIA_CUBLAS_VERSION" \
    && python -m pip install --no-cache-dir --no-deps --index-url "$LLAMA_CPP_PYTHON_INDEX_URL" llama_cpp_python==0.3.4 \
    && rm -rf /tmp/requirements-api.txt /var/lib/apt/lists/*

COPY app ./app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
