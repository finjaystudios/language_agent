## FastAPI backend

Run the backend locally:

```powershell
python -m uvicorn app.api.main:app --reload
```

The local model path must be configured before calling chat endpoints:

```powershell
$env:LLM_MODEL_PATH = "models/qwen2.5-7B-instruct-Q4_K_M.gguf"
```

Set logging verbosity with `LOG_LEVEL`:

```powershell
$env:LOG_LEVEL = "DEBUG"
python -m uvicorn app.api.main:app --reload
```

The application logs major stages such as model initialisation, intent routing,
mode selection, state updates, full-response generation, and streaming progress.
Logs intentionally include metadata such as mode, session id, message length, and
token counts rather than full user prompts.

OpenAPI docs are available at:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/openapi.json`

### Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Lightweight health check. Does not initialise the LLM. |
| `GET` | `/` | Service metadata. |
| `POST` | `/api/chat` | Full response chat endpoint. |
| `POST` | `/api/chat/stream` | Server-Sent Events streaming chat endpoint. |

### Full response request

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Define recursion in simple terms","mode":"definition"}'
```

Example response shape:

```json
{
  "mode": "definition",
  "response": "...",
  "intent": {
    "mode": "definition",
    "confidence": "high",
    "should_switch_mode": true,
    "reason": "Mode supplied by API request.",
    "clarification_question": ""
  },
  "data": {},
  "metadata": {
    "session_id": null
  }
}
```

### Streaming request

Stream a chat response with Server-Sent Events:

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message":"Translate this sentence to isiXhosa: Good morning","mode":"translation"}'
```

Streaming responses use `text/event-stream` events such as:

```text
data: {"mode": "translation", "token": "..."}

data: {"mode": "translation", "done": true}
```

### Error response shape

Errors use a stable JSON shape and do not include stack traces:

```json
{
  "error": "validation_error",
  "message": "Request validation failed.",
  "details": {
    "errors": []
  }
}
```

Expected status codes:

- `400`: invalid client input such as an unsupported streaming mode.
- `422`: request body schema validation failures such as a missing or empty message.
- `500`: LLM initialisation/runtime failures or unexpected internal errors.

### Known limitations

- The backend uses the same local GGUF model and GPU prerequisites as the CLI.
- Chat endpoints initialise the local model lazily on first use.
- Streaming is currently supported for modes configured as streaming in the existing agent (`translation` and `learning`).
- If an LLM failure occurs after an SSE response has started, the API emits a sanitized SSE error event instead of changing the HTTP status code.

## Docker

Build the FastAPI backend image:

```powershell
docker build -t local-language-agent-api .
```

The image does not include local GGUF/model files. Mount the model directory at
runtime and point `LLM_MODEL_PATH` at the file path inside the container:

```powershell
docker run --rm --gpus all -p 8000:8000 `
  --env-file .env.example `
  -e LLM_MODEL_PATH=/models/model.gguf `
  -v ${PWD}/models:/models `
  local-language-agent-api
```

GPU execution requires a host NVIDIA GPU, working NVIDIA drivers, Docker GPU
support such as NVIDIA Container Toolkit, and a CUDA-compatible
`llama-cpp-python` wheel. The Dockerfile installs `llama_cpp_python==0.3.4` from
the cu124 wheel index by default.

Container environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `APP_HOST` | `0.0.0.0` | Uvicorn bind host inside the container. |
| `APP_PORT` | `8000` | Uvicorn port inside the container. |
| `LOG_LEVEL` | `INFO` | Application logging level. |
| `LLM_MODEL_PATH` | `/models/model.gguf` | Mounted model file path inside the container. |
| `LLM_CONTEXT_SIZE` | `4096` | LLM context window size. |
| `LLM_N_GPU_LAYERS` | `-1` | GPU layer offload override; `-1` requests full offload. |
| `LLM_THREADS` | `4` | CPU thread count passed to llama-cpp. |
| `LLM_RESERVED_VRAM_GB` | `1.5` | VRAM headroom used when auto-selecting GPU layers. |

If `LLM_MODEL_PATH` is missing, or if the mounted file does not exist, the app
fails during LLM initialisation with a configuration error. It does not download
models or fall back to an unrelated local path.

## Bruno API client

Git-tracked Bruno collections live in `bruno/local-language-agent-api`.

Open that folder in Bruno and select the `Local` environment, or run it with the
Bruno CLI:

```powershell
bru run bruno/local-language-agent-api --env Local
```
