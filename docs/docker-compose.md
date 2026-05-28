# Docker Compose

Use Docker Compose to run PostgreSQL, Redis, FastAPI, the dedicated worker, a
dedicated `llama-server`, the Chainlit Web UI, and Caddy on one local network.

## Services

`compose.yml` defines:

- `postgres`
- `redis`
- `llama-server`
- `fastapi`
- `llm-worker`
- `webui`
- `caddy`

`postgres` is internal-only by default and does not publish a host port, which
keeps the user-profile database off the public interface unless you opt in
separately.

Only `llama-server` mounts `./models` and requests GPU access. The worker does
not mount the model directory in the default Compose path. The Web UI does not
mount the model directory and does not load the model.

## Prerequisites

- Docker with BuildKit enabled
- NVIDIA GPU support for the `llama-server` container
- Local GGUF model file under `models/`

Use [`.env.compose.example`](../.env.compose.example) as the template for
Compose-specific environment values.

## Setup

Create a local `.env` file:

```powershell
Copy-Item .env.compose.example .env
```

Set database secrets in that local `.env`, especially:

```text
POSTGRES_PASSWORD=replace-me
DATABASE_URL=postgresql+psycopg://language_agent:replace-me@postgres:5432/language_agent
CHAINLIT_AUTH_SECRET=replace-with-random-secret
```

For Compose, `LLAMA_SERVER_MODEL_PATH` now belongs to `llama-server` and must point at
the in-container mount path under `/models`, for example:

```text
/models/Qwen3-4B-Q4_K_M.gguf
```

The default Compose flow sets `LLM_BACKEND=llama_server`, so the worker
calls `http://llama-server:8080` over the internal Compose network.
The worker also reads `MODEL_PROFILES_PATH=config/model_profiles.yml`, and the
backend image now copies that YAML file into `/app/config/`.

GTX 1080 / Pascal note:

- the upstream `llama-server` image may still be incompatible with the host GPU
  if it was not built with `sm_61` support
- if that happens, build a local CUDA image with the right architecture and set
  `LLAMA_SERVER_IMAGE` in `.env`
- start conservatively with `LLAMA_SERVER_CONTEXT_SIZE=1024` or `2048`,
  `LLAMA_SERVER_N_GPU_LAYERS=20`, `LLAMA_SERVER_BATCH_SIZE=256`, and
  `LLAMA_SERVER_UBATCH_SIZE=128`

Apply migrations after PostgreSQL becomes healthy:

```powershell
docker compose run --rm fastapi alembic upgrade head
```

Build and start the stack:

```powershell
docker compose up --build
```

Or build first:

```powershell
docker compose build
docker compose up
```

Start only the queue path and model server while debugging:

```powershell
docker compose up -d postgres redis llama-server llm-worker
```

## URLs

Preferred local entry points through Caddy:

- Web UI: `http://localhost/`
- FastAPI health: `http://localhost/api/health`
- FastAPI full response: `http://localhost/api/chat`
- FastAPI streaming: `http://localhost/api/chat/stream`
- Streaming alias: `http://localhost/api/stream`

Direct host ports remain available for development:

- FastAPI direct: `http://127.0.0.1:8000`
- Chainlit direct: `http://127.0.0.1:8001`
- llama-server direct debug port: `http://127.0.0.1:8080`

LAN devices can replace `localhost` with the host machine IP address. If local
name resolution maps `agent.local` to the Docker host, the same routes can be
used there as well.

## Health and Logs

Validate the exposed API:

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/
```

Validate `llama-server` directly without bypassing the app in normal use:

```powershell
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/v1/models
```

Follow service logs:

```powershell
docker compose logs -f caddy
docker compose logs -f webui
docker compose logs -f fastapi
docker compose logs -f llm-worker
docker compose logs -f llama-server
docker compose logs -f redis
```

Inspect health:

```powershell
docker ps
docker inspect --format='{{json .State.Health}}' <container-id>
```

Render the fully resolved stack:

```powershell
docker compose config
```

Stop the stack:

```powershell
docker compose down
```

## Compose-Native Checks

Manual validation checklist:

1. `docker compose up -d redis llama-server llm-worker`
2. `docker compose run --rm fastapi alembic upgrade head`
3. `curl http://127.0.0.1:8080/health`
4. `docker compose up -d fastapi webui caddy`
5. Submit an authenticated `/api/chat` request
6. Submit an authenticated `/api/chat/stream` request
7. Confirm `docker compose logs -f llm-worker` shows worker activity
8. Confirm `docker compose logs -f llama-server` shows model-server requests
9. Confirm Web UI works at `http://localhost/`
10. Confirm Caddy still proxies `http://localhost/api/health`

Backend status route through the Web UI server:

```powershell
Invoke-RestMethod http://localhost/webui/backend-status
```

Protected FastAPI endpoints should reject missing API keys:

```powershell
Invoke-WebRequest `
  -UseBasicParsing `
  -Uri http://localhost/api/chat `
  -Method Post `
  -ContentType "application/json" `
  -Body '{"message":"Define recursion in simple terms"}'
```

Authenticated full response:

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

Authenticated streaming request:

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

## Related Docs

- [`llama-server.md`](llama-server.md)
- [`reverse-proxy.md`](reverse-proxy.md)
- [`queue.md`](queue.md)
- [`security.md`](security.md)
- [`testing.md`](testing.md)
