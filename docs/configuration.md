# Configuration

This document centralizes runtime configuration for host-local runs and Docker
Compose. Use [`.env.example`](../.env.example) for local host runs and
[`.env.compose.example`](../.env.compose.example) for Compose.

## FastAPI and Shared Runtime

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `APP_HOST` | `0.0.0.0` | FastAPI container | Uvicorn bind host |
| `APP_PORT` | `8000` | FastAPI container | Uvicorn bind port |
| `LOG_LEVEL` | `INFO` | FastAPI, worker, Web UI | Log verbosity |
| `AUTH_ENABLED` | `true` | FastAPI | Enables API key validation on protected routes |
| `FASTAPI_API_KEY` | None | FastAPI, Web UI | Shared service-to-service API key |
| `CORS_ALLOWED_ORIGINS` | empty in code, example values in env templates | FastAPI | Optional comma-separated origins for future direct browser access |

## Queue and Redis

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | FastAPI, worker | Redis connection URL |
| `LLM_BACKEND` | `llama_cpp_python` | FastAPI, worker | Runtime selector. Keep the current embedded runtime by default; use `llama_server` for the planned external HTTP backend |
| `LLM_QUEUE_NAME` | `llm` | FastAPI, worker | RQ queue name |
| `LLM_QUEUE_TIMEOUT_SECONDS` | `180` | FastAPI, worker | General queue operation timeout |
| `LLM_QUEUE_WAIT_TIMEOUT_SECONDS` | `300` | FastAPI, worker | Maximum wait time for queued non-streaming jobs |
| `LLM_GENERATION_TIMEOUT_SECONDS` | `180` | FastAPI, worker | Per-job generation timeout |
| `LLM_RESULT_TTL_SECONDS` | `300` | FastAPI, worker | Retention for completed job metadata and stream data |
| `LLM_MAX_QUEUE_SIZE` | `100` | FastAPI, worker | Backpressure threshold before `429` |
| `LLM_WORKER_CONCURRENCY` | `1` | worker | Worker concurrency; must remain `1` for the local GPU worker |
| `LLM_JOB_MAX_RETRIES` | `2` | FastAPI, worker | Retry count for transient worker failures |
| `LLM_STREAM_CHANNEL_PREFIX` | `llm-stream` | FastAPI, worker | Redis Stream prefix for streaming events |
| `LLM_STATUS_POLL_INTERVAL_SECONDS` | `0.05` | FastAPI, worker | Poll interval for queued job status checks |
| `LLM_STREAM_TIMEOUT_SECONDS` | `180` | FastAPI, worker | Maximum API wait time for stream events |

## Worker-Only LLM Runtime

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `LLM_MODEL_PATH` | `models/Qwen2.5-7B-Instruct-Q4_K_M.gguf` locally, `/models/model.gguf` style in Docker | CLI, worker | GGUF model path |
| `LLM_CONTEXT_SIZE` | `4096` | CLI, worker | Context window size |
| `LLM_N_GPU_LAYERS` | `-1` | CLI, worker | GPU layer offload override |
| `LLM_THREADS` | `4` | CLI, worker | CPU thread count |
| `LLM_RESERVED_VRAM_GB` | `1.5` | CLI, worker | VRAM headroom for automatic layer selection |

`llama-cpp-python` remains the active default runtime today. The migration
target is to keep FastAPI, Redis/RQ, and the worker unchanged at the queue
boundary while moving model ownership into an external `llama-server` process.

## Llama-Server Runtime

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `LLAMA_SERVER_URL` | `http://localhost:8080` locally, `http://llama-server:8080` in Compose | worker | Base URL for the external `llama-server` HTTP API |
| `LLAMA_SERVER_API_KEY` | empty | worker | Optional bearer or shared secret passed to `llama-server` |
| `LLAMA_SERVER_TIMEOUT_SECONDS` | `180` | worker | Non-streaming HTTP timeout for structured or full-text calls |
| `LLAMA_SERVER_STREAM_TIMEOUT_SECONDS` | `180` | worker | Streaming HTTP timeout for token/event reads |
| `LLAMA_SERVER_MODEL_NAME` | empty | worker | Optional request-level model name if the server exposes multiple models |
| `LLAMA_SERVER_HEALTH_PATH` | `/health` | worker, operations | Optional path used for future health checks or readiness probes |

When `LLM_BACKEND=llama_server`, the intended steady-state design is:

- `llama-server` owns GGUF model loading and GPU execution.
- The worker stays queue-backed and makes HTTP requests to `llama-server`.
- FastAPI endpoints and the Web UI remain unchanged.
- Redis/RQ still serializes all model-backed calls.

The code also accepts some legacy fallback names internally:

- `MODEL_PATH`
- `LLM_N_CTX`
- `LLM_GPU_LAYERS`
- `LLM_QUEUE_POLL_INTERVAL_SECONDS`

Prefer the `LLM_*` names shown in this document.

## Web UI

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `FASTAPI_BASE_URL` | `http://localhost:8000` locally, `http://fastapi:8000` in Compose | Web UI | Backend base URL for server-side Chainlit calls |
| `WEBUI_HOST` | `0.0.0.0` | Web UI container | Chainlit bind host |
| `WEBUI_PORT` | `8001` | Web UI container | Chainlit bind port |
| `WEBUI_REQUEST_TIMEOUT_SECONDS` | `120` | Web UI | Backend request timeout |
| `WEBUI_STREAMING_ENABLED` | `true` | Web UI | Enables streaming for Translation, Definition, and Learning modes |
| `DEBUG` | `false` in Compose examples | Web UI | Web UI debug toggle used in existing commands |

## Configuration Notes

- Keep `FASTAPI_API_KEY` out of browser-visible content.
- Keep real secrets out of committed files.
- For Compose, set `LLM_MODEL_PATH` to the in-container `/models/...` path, not
  a relative host path.
- For the future `llama_server` backend, point `LLAMA_SERVER_URL` at the
  reachable server address for that environment.
- The Web UI and FastAPI must share the same `FASTAPI_API_KEY` when auth is
  enabled.
- The worker should keep `LLM_WORKER_CONCURRENCY=1` so one long-lived process
  owns queued model execution, even after model loading moves to
  `llama-server`.
