## FastAPI backend

Run the backend locally:

```powershell
python -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
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

## Chainlit Web UI

The Web UI lives in `webui/` as a separate Chainlit application. It is designed
to be deployed independently from the FastAPI backend and must communicate with
the backend only over HTTP. The Web UI does not import backend internals, call
the LLM directly, or load the local GGUF model.

Install the Web UI dependencies:

```powershell
pip install -r webui/requirements.txt
```

Run the Chainlit app locally:

```powershell
$env:FASTAPI_BASE_URL = "http://127.0.0.1:8000"
Push-Location webui
chainlit run app.py --host 127.0.0.1 --port 8001
Pop-Location
```

Open the Web UI at:

- `http://127.0.0.1:8001`

The initial UI shows a welcome message and a placeholder response. Backend chat
integration will be added over HTTP in a later step.

### Run Backend and Web UI Together

Terminal 1:

```powershell
$env:LLM_MODEL_PATH = "models/qwen2.5-7B-instruct-Q4_K_M.gguf"
python -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
$env:FASTAPI_BASE_URL = "http://127.0.0.1:8000"
Push-Location webui
chainlit run app.py --host 127.0.0.1 --port 8001
Pop-Location
```

The backend and Web UI intentionally use different ports because they are
separate applications and will later be deployed as separate containers.

## Docker

### Prerequisites

- Docker with BuildKit enabled.
- NVIDIA GPU, working host NVIDIA drivers, and Docker GPU support such as
  NVIDIA Container Toolkit.
- A local GGUF model file stored outside the image, for example in `models/`.
- Environment values based on `.env.example`, especially `LLM_MODEL_PATH`.

Build the FastAPI backend image:

```powershell
docker build -t local-language-agent-api .
```

The Dockerfile includes a container health check that calls `GET /health`.
That endpoint is intentionally lightweight and does not initialise, load, or
query the local LLM model. Chat endpoints initialise the model lazily on first
use, so a healthy container only means the HTTP API process is reachable.

The image does not include local GGUF/model files. Mount the model directory at
runtime and point `LLM_MODEL_PATH` at the file path inside the container:

```powershell
docker run --rm --gpus all -p 8000:8000 `
  --env-file .env.example `
  -e LLM_MODEL_PATH=/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf `
  -v ${PWD}/models:/models `
  local-language-agent-api
```

Use `.env.example` as the template for local container settings. If you use a
VSCode-oriented `.env` with `APP_HOST=127.0.0.1`, override it with
`-e APP_HOST=0.0.0.0` for Docker so the published port is reachable from the
host.

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

### Container validation

From another terminal, verify the exposed API:

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/
```

Then test the model-backed endpoints after confirming GPU access and the mounted
model path:

```powershell
$fullBody = @{
  message = "Define recursion in simple terms"
  mode = "definition"
} | ConvertTo-Json -Compress
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/chat `
  -Method Post `
  -ContentType "application/json" `
  -Body $fullBody

$streamBody = @{
  message = "Translate this sentence to isiXhosa: Good morning"
  mode = "translation"
} | ConvertTo-Json -Compress
Invoke-WebRequest `
  -UseBasicParsing `
  -Uri http://127.0.0.1:8000/api/chat/stream `
  -Method Post `
  -ContentType "application/json" `
  -Body $streamBody
```

Docker health status can be inspected with:

```powershell
docker ps
docker inspect --format='{{json .State.Health}}' <container-id>
```

Application logs are written to stdout/stderr and can be viewed with:

```powershell
docker logs <container-id>
```

### Docker implementation summary

- The image uses `python:3.11-slim` and installs only backend runtime
  dependencies.
- BuildKit cache mounts are used for apt and pip downloads to speed up rebuilds.
- The CUDA `llama_cpp_python==0.3.4` wheel is installed from the cu124 index.
- Local models, virtual environments, caches, tests, Bruno files, and editor
  settings are excluded from the Docker build context.
- The container exposes port `8000` and runs `uvicorn app.api.main:app` without
  reload.
- Docker `HEALTHCHECK` calls `GET /health`, which does not load the LLM.

### Docker known limitations

- CPU-only execution is not supported by this Docker setup.
- The container expects compatible NVIDIA GPU runtime support on the host.
- The LLM model is not included in the image and must be mounted at runtime.
- The app fails LLM initialisation if `LLM_MODEL_PATH` is missing or points to a
  file that is not mounted inside the container.
- Chat endpoints load the model lazily on first use, so the first model-backed
  request can take significantly longer than `/health`.

## Bruno API client

Git-tracked Bruno collections live in `bruno/local-language-agent-api`.

Open that folder in Bruno and select either the `Local` or `Docker`
environment. Both target `http://127.0.0.1:8000`, so the same requests validate
the local uvicorn app and the Dockerized app as long as the container publishes
port `8000`.

Run the collection against the Dockerized API with:

```powershell
bru run bruno/local-language-agent-api --env Docker
```
