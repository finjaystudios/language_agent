## FastAPI backend

Run the API locally:

```powershell
python -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

Chat endpoints now enqueue each individual LLM call into Redis + RQ. Start Redis
and the dedicated LLM worker before calling `/api/chat` or `/api/chat/stream`:

```powershell
docker run --rm -p 6379:6379 redis:7-alpine
```

```powershell
$env:LLM_MODEL_PATH = "models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
python -m app.queue.worker
```

The API process itself does not load the local model. Configure queue access for
the API, and model settings for the worker:

```powershell
$env:AUTH_ENABLED = "true"
$env:FASTAPI_API_KEY = "local-dev-change-me"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:LLM_STREAM_CHANNEL_PREFIX = "llm-stream"
```

Set logging verbosity with `LOG_LEVEL`:

```powershell
$env:LOG_LEVEL = "DEBUG"
python -m uvicorn app.api.main:app --reload
```

The application logs major stages such as model initialisation, intent routing,
mode selection, state updates, full-response generation, and streaming progress.
Logs intentionally include metadata such as mode, session id, message length, and
token counts rather than full user prompts. API keys are not logged.

OpenAPI docs are available at:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/openapi.json`

### Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | Lightweight health check. Does not initialise the LLM or worker model. |
| `GET` | `/` | Service metadata. |
| `POST` | `/api/chat` | Full response chat endpoint. |
| `POST` | `/api/chat/stream` | Server-Sent Events streaming chat endpoint. |
| `GET` | `/api/queue/status` | Protected Redis/RQ queue status, depth, worker heartbeat, and failed-job counts. |

Protected chat endpoints require service-to-service API key authentication with
`X-API-Key`. `GET /health` and `GET /` remain public for health checks and local
tooling.

### Queue architecture

Each individual LLM call is the queued unit, not the top-level HTTP request.
That matters because one API request can trigger multiple model calls for intent
routing, state updates, and final generation. Putting the queue at the LLM call
boundary guarantees that only one GPU-backed model call runs at a time even
when multiple API requests overlap.

Current flow:

- FastAPI validates input, applies auth, and calls the queued LLM gateway.
- The queued gateway enqueues one RQ job per LLM call.
- Redis stores queue state, stream events, lightweight metrics, and RQ registries.
- The dedicated worker owns the local model and is the only process allowed to
  call it directly.
- Streaming jobs publish token chunks and status events through Redis Streams;
  FastAPI forwards those events as SSE to the Web UI or other clients.

### Full response request

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: local-dev-change-me" \
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
  -H "X-API-Key: local-dev-change-me" \
  -d '{"message":"Translate this sentence to isiXhosa: Good morning","mode":"translation"}'
```

Streaming responses use `text/event-stream` events such as:

```text
data: {"mode": "translation", "token": "..."}

data: {"mode": "translation", "done": true}
```

Streaming calls are also queued. The worker publishes token and status events
through Redis Streams, and the FastAPI streaming endpoint forwards them as SSE.
Additional SSE status events may include `job_id`, `status`, `queue_position`,
`elapsed_seconds`, and `cancel_requested`; the existing `token` and `done`
events remain compatible with the current Web UI.

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
- `401`: missing or invalid API key on protected endpoints.
- `429`: queue backpressure rejected the request; check `Retry-After`.
- `422`: request body schema validation failures such as a missing or empty message.
- `500`: LLM initialisation/runtime failures or unexpected internal errors.
- `504`: queue wait, generation, or streaming timeout.

### CORS

The browser does not call FastAPI directly in the current architecture. The
Chainlit browser app calls Chainlit routes, and Chainlit server-side Python calls
FastAPI with `X-API-Key`, so CORS is not required for normal Web UI chat.

If a future browser-origin flow calls FastAPI directly, configure explicit
origins with `CORS_ALLOWED_ORIGINS`, for example:

```powershell
$env:CORS_ALLOWED_ORIGINS = "http://localhost:8001,http://127.0.0.1:8001"
```

Wildcard origins with credentials are not used.

### Known limitations

- The API depends on Redis plus a separate `app.queue.worker` process for all model-backed requests.
- The worker uses the same local GGUF model and GPU prerequisites as the CLI.
- Retry behavior is limited to transient worker failures and defaults to `LLM_JOB_MAX_RETRIES=2`.
- Cancellation is cooperative. Queued jobs cancel immediately. Running streaming jobs stop between generated chunks when possible. Running non-streaming jobs cannot be interrupted mid-call by the current local model runtime and may finish before cancellation is applied.
- If an LLM failure occurs after an SSE response has started, the API emits a sanitized SSE error event instead of changing the HTTP status code.
- Future scaling options such as a dedicated `llama.cpp` server or continuous batching are intentionally out of scope for this implementation.

## Chainlit Web UI

The Web UI lives in `webui/` as a separate Chainlit application. It is designed
to be deployed independently from the FastAPI backend and must communicate with
the backend only over HTTP. The Web UI does not import backend internals, call
the LLM directly, or load the local GGUF model.

See `webui/README.md` for the full Web UI setup, validation, Docker-backend
workflow, Bruno workflow, and known limitations.

Install the Web UI dependencies:

```powershell
pip install -r webui/requirements.txt
```

Run the Chainlit app locally:

```powershell
$env:FASTAPI_BASE_URL = "http://127.0.0.1:8000"
$env:FASTAPI_API_KEY = "local-dev-change-me"
$env:WEBUI_REQUEST_TIMEOUT_SECONDS = "120"
$env:WEBUI_STREAMING_ENABLED = "true"
Push-Location webui
chainlit run app.py --host 127.0.0.1 --port 8001
Pop-Location
```

Open the Web UI at:

- `http://127.0.0.1:8001`

The LanguageAgent UI shows a branded landing page, checks backend health, offers
starter prompts, and sends chat requests over HTTP from the Chainlit server to
the FastAPI backend. Translation and Learning modes use the backend streaming
endpoint when
`WEBUI_STREAMING_ENABLED=true`; Auto, Definition, and General use the full
response endpoint. The browser never receives `FASTAPI_API_KEY`; the key is read
only by the Chainlit server process and sent only on protected FastAPI requests.

The personalised UI assets live under `webui/public/`: theme variables in
`theme.json`, scoped CSS in `style.css`, landing-page behavior in
`landing-status.js`, and runtime logos/favicons in the same directory. The chat
interface includes starter prompts, response mode settings, stop/retry controls
where Chainlit exposes them, response feedback actions, visible focus states,
and polite live-region updates for streamed responses.

### Run Backend and Web UI Together

Terminal 1:

```powershell
$env:AUTH_ENABLED = "true"
$env:FASTAPI_API_KEY = "local-dev-change-me"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:LLM_STREAM_CHANNEL_PREFIX = "llm-stream"
python -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
docker run --rm -p 6379:6379 redis:7-alpine
```

Terminal 3:

```powershell
$env:LLM_MODEL_PATH = "models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
$env:LLM_STREAM_CHANNEL_PREFIX = "llm-stream"
python -m app.queue.worker
```

Terminal 4:

```powershell
$env:FASTAPI_BASE_URL = "http://127.0.0.1:8000"
$env:FASTAPI_API_KEY = "local-dev-change-me"
$env:WEBUI_REQUEST_TIMEOUT_SECONDS = "120"
$env:WEBUI_STREAMING_ENABLED = "true"
Push-Location webui
chainlit run app.py --host 127.0.0.1 --port 8001
Pop-Location
```

The backend and Web UI intentionally use different ports because they are
separate applications and will later be deployed as separate containers.

### Web UI Browser Tests

Local Playwright tests for the Chainlit Web UI live in `tests/e2e/`. They start
a deterministic fake backend and do not require Docker or the GGUF model:

```powershell
pip install -r tests/e2e/requirements.txt
python -m playwright install chromium
pytest tests/e2e
```

The browser suite checks the LanguageAgent title and static assets, landing-page
backend status, quick actions, response mode overrides, streaming/full-response
requests, retry and feedback buttons, and readable error states.

Run additional Playwright browsers when installed:

```powershell
pytest tests/e2e --browser chromium
pytest tests/e2e --browser firefox
pytest tests/e2e --browser webkit
```

To target a Web UI that is already running, set `E2E_BASE_URL`. This is useful
for Docker Compose validation and does not change the default deterministic test
path:

```powershell
$env:E2E_BASE_URL = "http://localhost"
pytest tests/e2e/test_chainlit_smoke.py
```

When `E2E_BASE_URL` points at the Compose proxy, the test is a local integration
check against Caddy, the real Web UI, the real FastAPI backend, and the mounted
model. Keep using plain `pytest tests/e2e` for fake-backend browser coverage,
including readable auth failures and checks that API keys are not displayed in
the browser.

## Docker

### Prerequisites

- Docker with BuildKit enabled.
- For FastAPI only: NVIDIA GPU, working host NVIDIA drivers, and Docker GPU
  support such as NVIDIA Container Toolkit.
- For FastAPI only: a local GGUF model file stored outside the image, for
  example in `models/`.
- Environment values based on `.env.example` or `.env.compose.example`,
  especially `FASTAPI_API_KEY` and `LLM_MODEL_PATH`.

Dockerfiles:

- FastAPI backend: `Dockerfile`
- Chainlit Web UI: `Dockerfile.webui`

Build the FastAPI backend image:

```powershell
docker build -t local-language-agent-api .
```

Build the Chainlit Web UI image:

```powershell
docker build -f Dockerfile.webui -t local-language-agent-webui .
```

The Dockerfile includes a container health check that calls `GET /health`.
That endpoint is intentionally lightweight and does not initialise, load, or
query the local LLM model. The API container only enqueues jobs; the worker
container owns the model.

The image does not include local GGUF/model files. Mount the model directory at
runtime and point `LLM_MODEL_PATH` at the file path inside the container:

```powershell
docker run --rm --gpus all -p 8000:8000 `
  --env-file .env.example `
  -e FASTAPI_API_KEY=local-dev-change-me `
  -e LLM_MODEL_PATH=/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf `
  -v ${PWD}/models:/models `
  local-language-agent-api
```

Use `.env.example` as the template for host-local FastAPI settings. For Docker,
override `LLM_MODEL_PATH` with the in-container `/models/...` path as shown
above, and set `APP_HOST=0.0.0.0` so the published port is reachable from the
host.

GPU execution requires a host NVIDIA GPU, working NVIDIA drivers, Docker GPU
support such as NVIDIA Container Toolkit, and a CUDA-compatible
`llama-cpp-python` wheel. The Dockerfile installs `llama_cpp_python==0.3.4` from
the cu124 wheel index by default.

The Web UI image does not need GPU access and must not mount `./models`. It only
needs network access to FastAPI and the same `FASTAPI_API_KEY` value.

FastAPI API container environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `APP_HOST` | `0.0.0.0` | Uvicorn bind host inside the container. |
| `APP_PORT` | `8000` | Uvicorn port inside the container. |
| `LOG_LEVEL` | `INFO` | Application logging level. |
| `AUTH_ENABLED` | `true` | Enables API key validation on protected API routes. |
| `FASTAPI_API_KEY` | None | Shared service API key. Set this at runtime; do not bake real secrets into images. |
| `CORS_ALLOWED_ORIGINS` | Empty | Optional comma-separated browser origins allowed to call FastAPI directly. |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection used by the queued gateway. |
| `LLM_QUEUE_NAME` | `llm` | RQ queue name for model-call jobs. |
| `LLM_QUEUE_TIMEOUT_SECONDS` | `180` | General queue operation timeout. |
| `LLM_QUEUE_WAIT_TIMEOUT_SECONDS` | `300` | Maximum time the API waits for a queued non-streaming job, including cold-start model initialization. |
| `LLM_GENERATION_TIMEOUT_SECONDS` | `180` | Per-job generation timeout enforced by RQ. |
| `LLM_RESULT_TTL_SECONDS` | `300` | How long completed job metadata and stream data are retained. |
| `LLM_MAX_QUEUE_SIZE` | `100` | Maximum queued job depth before backpressure returns `429`. |
| `LLM_JOB_MAX_RETRIES` | `2` | Retries for transient worker failures. |
| `LLM_STREAM_CHANNEL_PREFIX` | `llm-stream` | Redis Stream prefix for queued streaming events. |
| `LLM_STATUS_POLL_INTERVAL_SECONDS` | `0.05` | Poll interval for non-streaming job status checks. |
| `LLM_STREAM_TIMEOUT_SECONDS` | `180` | Maximum time the API waits for streaming events. |

Worker-only environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `LLM_MODEL_PATH` | `/models/model.gguf` | Mounted model file path inside the worker container. |
| `LLM_CONTEXT_SIZE` | `4096` | LLM context window size. |
| `LLM_N_GPU_LAYERS` | `-1` | GPU layer offload override; `-1` requests full offload. |
| `LLM_THREADS` | `4` | CPU thread count passed to llama-cpp. |
| `LLM_RESERVED_VRAM_GB` | `1.5` | VRAM headroom used when auto-selecting GPU layers. |

If `LLM_MODEL_PATH` is missing, or if the mounted file does not exist, the
worker fails during LLM initialisation with a configuration error. It does not
download models or fall back to an unrelated local path.

Web UI container environment variables:

| Variable | Default | Description |
| --- | --- | --- |
| `FASTAPI_BASE_URL` | `http://fastapi:8000` | FastAPI URL called by server-side Chainlit code. |
| `FASTAPI_API_KEY` | None | Shared backend API key. Must match FastAPI. |
| `WEBUI_HOST` | `0.0.0.0` | Chainlit bind host inside the container. |
| `WEBUI_PORT` | `8001` | Chainlit port inside the container. |
| `WEBUI_REQUEST_TIMEOUT_SECONDS` | `120` | Backend request timeout. |
| `WEBUI_STREAMING_ENABLED` | `true` | Enables streaming for supported modes. |
| `LOG_LEVEL` | `INFO` | Web UI server logging level. |

### Container validation

From another terminal, verify the exposed API:

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/
```

Protected endpoints should reject unauthenticated requests:

```powershell
curl -X POST http://127.0.0.1:8000/api/chat `
  -H "Content-Type: application/json" `
  -d '{"message":"Define recursion in simple terms"}'
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
  -Headers @{"X-API-Key" = "local-dev-change-me"} `
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
  -Headers @{"X-API-Key" = "local-dev-change-me"} `
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

### Docker Compose local development

Use Compose to run Redis, the FastAPI API, the dedicated LLM worker, and the
Chainlit Web UI as separate containers on one local Docker network, with Caddy
as the preferred local entry point. Only the worker mounts `./models` and
requests GPU access. The Web UI does not mount the model directory and calls
FastAPI over the internal Compose URL `http://fastapi:8000`, not through Caddy.

Create a local Compose env file from the template and set the model filename and
shared API key for your machine:

```powershell
Copy-Item .env.compose.example .env
```

For Compose, `LLM_MODEL_PATH` must use the in-container mount path, for example
`/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf`. A relative host path such as
`models/Qwen2.5-7B-Instruct-Q4_K_M.gguf` will be resolved inside the container
as `/app/models/...` and the backend will fail to load the model.

Build both images:

```powershell
docker compose build
```

Start the stack:

```powershell
docker compose up
```

Or rebuild and start in one command:

```powershell
docker compose up --build
```

VSCode task equivalents:

- `compose-config: language-agent`
- `compose-up: language-agent`
- `compose-down: language-agent`

Open through Caddy:

- Chainlit Web UI: `http://localhost/`
- FastAPI health through the proxy: `http://localhost/api/health`
- FastAPI protected API through the proxy: `http://localhost/api/chat`

From another device on the same home network, replace `localhost` with the host
machine's LAN IP address:

- Web UI: `http://<host-lan-ip>/`
- FastAPI health: `http://<host-lan-ip>/api/health`
- FastAPI API: `http://<host-lan-ip>/api/chat`

If your router DNS, local hosts files, or mDNS setup maps `agent.local` to the
Docker host, you can use friendlier LAN URLs:

- Web UI: `http://agent.local/`
- FastAPI health: `http://agent.local/api/health`
- FastAPI full response: `http://agent.local/api/chat`
- FastAPI streaming alias: `http://agent.local/api/stream`

Caddy does not create the `agent.local` name by itself; LAN devices must resolve
that name to the host running Docker.

Inside Compose, the Web UI still reaches FastAPI at `http://fastapi:8000`.
Direct host ports remain published for development fallbacks:

- FastAPI direct: `http://127.0.0.1:8000`
- Chainlit direct: `http://127.0.0.1:8001`

Later deployments can remove direct host exposure for FastAPI and Web UI if
Caddy is the only required local origin.

Useful log commands:

```powershell
docker compose logs -f caddy
docker compose logs -f webui
docker compose logs -f fastapi
docker compose logs -f llm-worker
docker compose logs -f redis
```

Manual streaming and cancellation checks:

```powershell
$streamBody = @{
  message = "Translate this sentence to French: Good morning and welcome."
  mode = "translation"
  stream = $true
} | ConvertTo-Json -Compress
Invoke-WebRequest `
  -UseBasicParsing `
  -Uri http://127.0.0.1:8000/api/chat/stream `
  -Method Post `
  -ContentType "application/json" `
  -Headers @{"X-API-Key" = "local-dev-change-me"} `
  -Body $streamBody
```

The first SSE status event includes the queued `job_id`. Cancel it with:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/llm/jobs/<job-id>/cancel `
  -Method Post `
  -Headers @{"X-API-Key" = "local-dev-change-me"}
```

Inspect queue status details with:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/llm/jobs/<job-id> `
  -Headers @{"X-API-Key" = "local-dev-change-me"}
```

Queue monitoring check:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/queue/status `
  -Headers @{"X-API-Key" = "local-dev-change-me"}
```

Expected fields include Redis connectivity, queue depth, active job count,
failed job count, worker count, worker heartbeat age, average wait time, and
estimated wait time.

Stop and remove the local containers:

```powershell
docker compose down
```

Validate the Compose network path through the Web UI server:

```powershell
Invoke-RestMethod http://localhost/webui/backend-status
```

Protected FastAPI endpoints should still reject missing API keys:

```powershell
Invoke-WebRequest `
  -UseBasicParsing `
  -Uri http://localhost/api/chat `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"Define recursion in simple terms"}'
```

Then send the same request with the configured API key. Chat requests initialise
the local model lazily, so the first authenticated request can take longer than
the proxy health check:

```powershell
$body = @{
  message = "Define recursion in simple terms"
  mode = "definition"
} | ConvertTo-Json -Compress
Invoke-RestMethod `
  -Uri http://localhost/api/chat `
  -Method Post `
  -ContentType "application/json" `
  -Headers @{"X-API-Key" = $env:FASTAPI_API_KEY} `
  -Body $body
```

Streaming through Caddy uses the same `/api` path:

```powershell
$streamBody = @{
  message = "Translate this sentence to isiXhosa: Good morning"
  mode = "translation"
} | ConvertTo-Json -Compress
Invoke-WebRequest `
  -UseBasicParsing `
  -Uri http://localhost/api/chat/stream `
  -Method Post `
  -ContentType "application/json" `
  -Headers @{"X-API-Key" = $env:FASTAPI_API_KEY} `
  -Body $streamBody
```

Caddy access logs are written to stdout and can be followed with
`docker compose logs -f caddy`. Request headers are removed from the Caddy
access log so API key headers are not logged.

Cloudflare Tunnel is not part of this Compose file. For future domain routing,
run Cloudflare Tunnel outside Compose and point it at the host Caddy port, for
example `http://localhost:80`. Cloudflare will handle public HTTPS for the
domain; Caddy remains the local HTTP origin.

### Docker implementation summary

- Both images use `python:3.11-slim`.
- The backend image installs only backend runtime dependencies.
- The Web UI image installs only `webui/requirements.txt` dependencies and
  copies only Web UI Python files, Chainlit config, `chainlit.md`, and public
  assets including the LanguageAgent logos, favicon, theme, CSS, and custom JS.
- BuildKit cache mounts are used for apt and pip downloads to speed up rebuilds.
- The backend CUDA `llama_cpp_python==0.3.4` wheel is installed from the cu124
  index.
- Local models, virtual environments, caches, tests, Bruno files, and editor
  settings are excluded from the Docker build context.
- The backend container exposes port `8000` and runs
  `uvicorn app.api.main:app` without reload.
- The Web UI container exposes port `8001` and runs Chainlit headlessly.
- Docker health checks call FastAPI `/health` and the Chainlit root route.
- Caddy exposes port `80`, routes `/` to Chainlit, routes `/api/*` to FastAPI,
  and provides `/api/health` as a proxy alias for FastAPI `/health`.

### Docker known limitations

- CPU-only execution is not supported by this Docker setup.
- The worker container expects compatible NVIDIA GPU runtime support on the host.
- The LLM model is not included in either image and must be mounted only into
  the worker container at runtime.
- The Web UI container does not include or load the LLM.
- The Web UI requires FastAPI to be reachable and requires a matching
  `FASTAPI_API_KEY`.
- The FastAPI app fails LLM initialisation if `LLM_MODEL_PATH` is missing or
  points to a file that is not mounted inside the container.
- Chat endpoints enqueue work immediately, but the first worker job can still be
  slower because the worker loads the model lazily on first use.
- The API key authenticates the calling service, not individual browser users.
- Cloudflare Tunnel config, public domain routing, and user login are
  intentionally outside this local Docker setup.
- Public HTTPS is expected to be handled by Cloudflare Tunnel later; Caddy runs
  HTTP locally for now.
- Load balancing is not configured because the Compose stack runs one FastAPI
  container and one Web UI container.

## Bruno API client

Git-tracked Bruno collections live in `bruno/local-language-agent-api`.

Open that folder in Bruno and select either the `Local` or `Docker`
environment. For the Compose reverse proxy workflow, set the Docker
environment `baseUrl` to `http://localhost` and keep API request paths under
`/api/...`. Protected API requests still require `X-API-Key`.

The public FastAPI health endpoint is direct at `/health`, while the Caddy
proxy exposes it as `/api/health`. Use `http://localhost/api/health` for proxy
health checks, or the direct FastAPI port `http://127.0.0.1:8000/health` when
testing the backend without Caddy.

The `Local` and `Docker` Bruno environments include an `apiKey` placeholder.
Set it to the same value as `FASTAPI_API_KEY`; protected chat requests send it
as `X-API-Key`, while public system health requests remain unauthenticated.

Run the collection against the Dockerized API with:

```powershell
bru run bruno/local-language-agent-api --env Docker
```
