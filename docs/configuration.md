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
| `CHAINLIT_AUTH_SECRET` | unset | Web UI | Reserved session/auth secret for future username/password login wiring |
| `PASSWORD_HASH_SCHEME` | `argon2id` | backend auth utilities | Password hashing algorithm for stored user credentials |
| `CORS_ALLOWED_ORIGINS` | empty in code, example values in env templates | FastAPI | Optional comma-separated origins for future direct browser access |

## Database

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://language_agent:change-me@127.0.0.1:5432/language_agent` locally, `postgresql+psycopg://language_agent:change-me@postgres:5432/language_agent` in Compose examples | FastAPI, worker, Alembic | SQLAlchemy and Alembic database connection string |
| `DATABASE_POOL_SIZE` | `5` | FastAPI, worker | SQLAlchemy connection pool size for non-SQLite backends |
| `DATABASE_ECHO` | `false` | FastAPI, worker | Enables SQLAlchemy SQL logging when debugging |
| `POSTGRES_DB` | `language_agent` | Compose `postgres` service | Internal database name for the bundled PostgreSQL container |
| `POSTGRES_USER` | `language_agent` | Compose `postgres` service | Internal PostgreSQL username |
| `POSTGRES_PASSWORD` | placeholder in env examples | Compose `postgres` service | Internal PostgreSQL password; keep in local `.env` only |

Migration commands:

```powershell
alembic upgrade head
alembic current
alembic history
```

## Queue and Redis

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `REDIS_URL` | `redis://127.0.0.1:6379/0` | FastAPI, worker | Redis connection URL |
| `LLM_BACKEND` | `llama_server` | FastAPI, worker | Runtime selector. `llama_server` is now the default runtime for host-local and Compose flows |
| `LLM_QUEUE_NAME` | `llm` | FastAPI, worker | RQ queue name |
| `LLM_QUEUE_TIMEOUT_SECONDS` | `180` | FastAPI, worker | General queue operation timeout |
| `LLM_QUEUE_WAIT_TIMEOUT_SECONDS` | `300` | FastAPI, worker | Maximum wait time for queued non-streaming jobs |
| `LLM_GENERATION_TIMEOUT_SECONDS` | `180` | FastAPI, worker | Per-job generation timeout |
| `LLM_RESULT_TTL_SECONDS` | `300` | FastAPI, worker | Retention for completed job metadata and stream data |
| `LLM_MAX_QUEUE_SIZE` | `100` | FastAPI, worker | Backpressure threshold before `429` |
| `LLM_WORKER_CONCURRENCY` | `1` | worker | Worker concurrency; must remain `1` for the queue-backed worker |
| `LLM_JOB_MAX_RETRIES` | `2` | FastAPI, worker | Retry count for transient worker failures |
| `LLM_STREAM_CHANNEL_PREFIX` | `llm-stream` | FastAPI, worker | Redis Stream prefix for streaming events |
| `LLM_STATUS_POLL_INTERVAL_SECONDS` | `0.05` | FastAPI, worker | Poll interval for queued job status checks |
| `LLM_STREAM_TIMEOUT_SECONDS` | `180` | FastAPI, worker | Maximum API wait time for stream events |

## Llama-Server Runtime

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `LLAMA_SERVER_URL` | `http://localhost:8080` locally, `http://llama-server:8080` in Compose | worker | Base URL for the external `llama-server` HTTP API |
| `LLAMA_SERVER_API_KEY` | empty | worker | Optional bearer or shared secret passed to `llama-server` |
| `LLAMA_SERVER_TIMEOUT_SECONDS` | `180` | worker | Non-streaming HTTP timeout for structured or full-text calls |
| `LLAMA_SERVER_STREAM_TIMEOUT_SECONDS` | `180` | worker | Streaming HTTP timeout for token/event reads |
| `LLAMA_SERVER_MODEL_NAME` | empty | worker | Optional request-level model name if the server exposes multiple models |
| `LLAMA_SERVER_HEALTH_PATH` | `/health` | worker, operations | Optional path used for future health checks or readiness probes |
| `MODEL_PROFILES_PATH` | `config/model_profiles.yml` | worker, local runtime tests | YAML file containing task-specific llama-server generation profiles |

Compose-local `llama-server` defaults also use:

| Variable | Default | Used by | Purpose |
| --- | --- | --- | --- |
| `LLAMA_SERVER_IMAGE` | `ghcr.io/ggml-org/llama.cpp:server-cuda` | Compose | Official upstream container image |
| `LLAMA_SERVER_PORT` | `8080` | Compose | Internal llama-server listen port |
| `LLAMA_SERVER_HOST_PORT` | `8080` | Compose | Optional host port for direct debugging |
| `LLAMA_SERVER_MODEL_PATH` | `/models/Qwen3-4B-Q4_K_M.gguf` | Compose llama-server service | In-container GGUF model path |
| `LLAMA_SERVER_CONTEXT_SIZE` | `2048` | Compose llama-server service | Conservative context size for Pascal-class GPUs |
| `LLAMA_SERVER_N_GPU_LAYERS` | `20` | Compose llama-server service | Conservative GPU offload setting for Pascal-class GPUs |
| `LLAMA_SERVER_BATCH_SIZE` | `256` | llama-server | Conservative prompt batch size for GTX 1080-class GPUs |
| `LLAMA_SERVER_UBATCH_SIZE` | `128` | llama-server | Conservative micro-batch size for GTX 1080-class GPUs |
| `LLAMA_SERVER_THREADS` | `4` | Compose llama-server service | CPU thread count for llama-server |

When `LLM_BACKEND=llama_server`, the intended steady-state design is:

- `llama-server` owns GGUF model loading and GPU execution.
- The worker stays queue-backed and makes HTTP requests to `llama-server`.
- FastAPI endpoints and the Web UI remain unchanged.
- Redis/RQ still serializes all model-backed calls.

## Model Profiles

`MODEL_PROFILES_PATH` points at a YAML file that maps task modes such as
`intent`, `translation`, `definition`, `learning`, and `general` to
generation settings for the single active llama-server model.

Each profile can tune:

- `temperature`
- `top_p`
- `top_k`
- `min_p`
- `max_tokens`
- `prompt_control` via `/think` or `/no_think`

This is not multi-model routing yet. All current profiles target the same
loaded Qwen3 profile model, `Qwen3-4B-Q4_K_M`, and the worker still sends every
request through the Redis/RQ queue before reaching `llama-server`.

The embedded `llama-cpp-python` runtime was removed from the active code path.
`LLM_BACKEND` remains as a guardrail setting and must stay `llama_server`.

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
- Keep `CHAINLIT_AUTH_SECRET`, `POSTGRES_PASSWORD`, and `DATABASE_URL` credentials
  out of committed files.
- Keep real secrets out of committed files.
- For Compose, `LLAMA_SERVER_MODEL_PATH` belongs to the `llama-server` service
  and should point at the in-container `/models/...` path.
- The bundled PostgreSQL service is internal-only in `compose.yml`; no host port
  is published by default.
- For Compose-local Pascal GPUs such as a GTX 1080, start with
  `LLAMA_SERVER_CONTEXT_SIZE=1024` or `2048`, modest
  `LLAMA_SERVER_N_GPU_LAYERS`, and conservative `LLAMA_SERVER_BATCH_SIZE` /
  `LLAMA_SERVER_UBATCH_SIZE`.
- Point `LLAMA_SERVER_URL` at the reachable server address for that environment.
- Keep `MODEL_PROFILES_PATH` in sync with the file copied into the runtime
  image or available on the host.
- The Web UI and FastAPI must share the same `FASTAPI_API_KEY` when auth is
  enabled.
- The worker should keep `LLM_WORKER_CONCURRENCY=1` so one long-lived process
  owns queued model execution, even after model loading moves to
  `llama-server`.
