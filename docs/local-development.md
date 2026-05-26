# Local Development

This workflow runs the services directly from the repository without Docker
Compose.

## Prerequisites

- Python environment with project dependencies installed
- Local GGUF model file under `models/` or another reachable path
- NVIDIA GPU support for model-backed flows
- Redis available locally for FastAPI queue-backed requests

Use [`.env.example`](../.env.example) as the host-local configuration template.

## Redis

Start Redis locally:

```powershell
docker run --rm -p 6379:6379 redis:7-alpine
```

## Worker

The worker must be running for FastAPI chat requests. In the preferred local
workflow, the worker calls an external `llama-server` process over HTTP.

```powershell
$env:LLM_BACKEND = "llama_server"
$env:LLAMA_SERVER_URL = "http://127.0.0.1:8080"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:LLM_STREAM_CHANNEL_PREFIX = "llm-stream"
python -m app.worker.main
```

## Llama-Server

Start `llama-server` locally before the worker:

```powershell
llama-server `
  --model models/Qwen3-4B-Q4_K_M.gguf `
  --host 127.0.0.1 `
  --port 8080 `
  --ctx-size 2048 `
  --n-gpu-layers 20 `
  --batch-size 256 `
  --ubatch-size 128 `
  --parallel 1
```

Validate it directly:

```powershell
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/v1/models
```

## FastAPI

The API enqueues LLM work into Redis + RQ and does not load the model itself.

```powershell
$env:AUTH_ENABLED = "true"
$env:FASTAPI_API_KEY = "local-dev-change-me"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:LLM_STREAM_CHANNEL_PREFIX = "llm-stream"
python -m uvicorn app.interfaces.api.main:app --reload --host 127.0.0.1 --port 8000
```

Useful endpoints:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/openapi.json`

Set log verbosity when needed:

```powershell
$env:LOG_LEVEL = "DEBUG"
python -m uvicorn app.interfaces.api.main:app --reload
```

## Chainlit Web UI

Run the Web UI as a separate local process:

```powershell
$env:FASTAPI_BASE_URL = "http://127.0.0.1:8000"
$env:FASTAPI_API_KEY = "local-dev-change-me"
$env:WEBUI_REQUEST_TIMEOUT_SECONDS = "120"
$env:WEBUI_STREAMING_ENABLED = "true"
Push-Location webui
chainlit run app.py --host 127.0.0.1 --port 8001
Pop-Location
```

Open `http://127.0.0.1:8001`.

## Typical Host-Local Workflow

1. Start Redis.
2. Start `llama-server`.
3. Start the worker.
4. Start FastAPI.
5. Start Chainlit.

At that point:

- Browser users go to `http://127.0.0.1:8001`
- FastAPI health is `http://127.0.0.1:8000/health`
- Protected chat calls require `X-API-Key: local-dev-change-me`

## Manual API Checks

Full response:

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-dev-change-me" \
  -d '{"message":"Define recursion in simple terms","mode":"definition"}'
```

Streaming response:

```bash
curl -N -X POST http://127.0.0.1:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-dev-change-me" \
  -d '{"message":"Translate this sentence to isiXhosa: Good morning","mode":"translation"}'
```

Queue status:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/queue/status `
  -Headers @{"X-API-Key" = "local-dev-change-me"}
```
