# Docker Compose

Use Docker Compose to run Redis, FastAPI, the dedicated worker, a dedicated
`llama-server`, the Chainlit Web UI, and Caddy on one local network.

## Services

`compose.yml` defines:

- `redis`
- `llama-server`
- `fastapi`
- `llm-worker`
- `webui`
- `caddy`

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

For Compose, `LLM_MODEL_PATH` now belongs to `llama-server` and must point at
the in-container mount path under `/models`, for example:

```text
/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf
```

The default Compose flow now sets `LLM_BACKEND=llama_server`, so the worker
calls `http://llama-server:8080` over the internal Compose network.

GTX 1080 / Pascal note:

- the upstream `llama-server` image may still be incompatible with the host GPU
  if it was not built with `sm_61` support
- if that happens, build a local CUDA image with the right architecture and set
  `LLAMA_SERVER_IMAGE` in `.env`
- start conservatively with `LLM_CONTEXT_SIZE=1024` or `2048`,
  `LLM_N_GPU_LAYERS=20`, `LLAMA_SERVER_BATCH_SIZE=256`, and
  `LLAMA_SERVER_UBATCH_SIZE=128`

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
docker compose up -d redis llama-server llm-worker
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
