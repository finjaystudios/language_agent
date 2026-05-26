# Llama-Server Runtime

## Goal

Move GGUF model ownership out of the Python worker process and into an external
`llama-server` process without changing the FastAPI API surface, Chainlit Web
UI flow, or the Redis/RQ queue boundary.

`llama-server` is now the default runtime for production-style local inference.
The embedded `llama-cpp-python` path remains legacy-only.

## Target Architecture

Current runtime:

```text
FastAPI -> Redis/RQ -> worker -> embedded llama-cpp-python -> GPU model
```

Target runtime:

```text
FastAPI -> Redis/RQ -> worker -> HTTP llama-server -> GPU model
```

## Boundaries That Stay Fixed

- FastAPI endpoints remain unchanged.
- Chainlit continues calling FastAPI, not the model runtime directly.
- Redis + RQ continues serializing every LLM-backed call.
- The worker remains the only component that performs model execution work on
  behalf of queued jobs.
- Queue job payloads stay centered on `LLMCallJob` message lists, schemas,
  modes, and generation parameters.

## Current Code Surfaces

- `app/ports/llm_gateway.py`: application-facing LLM contract
- `app/infrastructure/llm/local_model.py`: current embedded
  `llama-cpp-python` adapter
- `app/infrastructure/llm/queued_gateway.py`: queue-backed LLM gateway used by
  FastAPI/application code
- `app/worker/jobs.py`: worker job execution path and current direct model load
- `app/domain/jobs.py`: queue job schema
- `app/core/config.py`: shared environment-backed settings

No FastAPI route or application service imports `llama_cpp`. The queue-backed
worker/runtime boundary remains the only model-execution integration point.

## Compose Service

The default local Compose stack now includes a dedicated `llama-server`
container:

```text
redis -> llm-worker -> http://llama-server:8080
```

Operational boundaries:

- `llama-server` is the only default Compose service that mounts `./models`
- `llama-server` is the only default Compose service that requests GPU access
- `llm-worker` stays queue-backed and calls `llama-server` over HTTP
- FastAPI and Chainlit still do not talk to `llama-server` directly

## Environment Variables

| Variable | Example | Purpose |
| --- | --- | --- |
| `LLM_BACKEND` | `llama_server` | Select the external HTTP runtime once implemented |
| `LLAMA_SERVER_URL` | `http://localhost:8080` or `http://llama-server:8080` | Base URL for `llama-server` |
| `LLAMA_SERVER_API_KEY` | empty by default | Optional auth secret for the server |
| `LLAMA_SERVER_TIMEOUT_SECONDS` | `180` | Non-streaming worker HTTP timeout |
| `LLAMA_SERVER_STREAM_TIMEOUT_SECONDS` | `180` | Streaming worker HTTP timeout |
| `LLAMA_SERVER_MODEL_NAME` | `qwen2.5-7b-instruct` | Optional model name passed to the server |
| `LLAMA_SERVER_HEALTH_PATH` | `/health` | Optional future readiness path |
| `MODEL_PROFILES_PATH` | `config/model_profiles.yml` | YAML file for per-mode generation settings |

Common Compose-local runtime knobs for the `llama-server` container:

| Variable | Example | Purpose |
| --- | --- | --- |
| `LLAMA_SERVER_IMAGE` | `ghcr.io/ggml-org/llama.cpp:server-cuda` | Upstream image to run |
| `LLAMA_SERVER_PORT` | `8080` | Internal service port |
| `LLAMA_SERVER_HOST_PORT` | `8080` | Optional direct host debug port |
| `LLAMA_SERVER_BATCH_SIZE` | `256` | Conservative GTX 1080-friendly batch size |
| `LLAMA_SERVER_UBATCH_SIZE` | `128` | Conservative GTX 1080-friendly micro-batch size |

## Local Manual Command

```powershell
llama-server `
  --model <path-to-model.gguf> `
  --host 0.0.0.0 `
  --port 8080 `
  --ctx-size 2048 `
  --n-gpu-layers 20 `
  --batch-size 256 `
  --ubatch-size 128 `
  --parallel 1
```

## Docker Compose

Start only the model server, Redis, and worker while debugging:

```powershell
docker compose up -d redis llama-server llm-worker
```

Start the full local stack:

```powershell
docker compose up --build
```

Inspect the rendered configuration:

```powershell
docker compose config
```

Test `llama-server` directly:

```powershell
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/v1/models
```

The direct port exists for local debugging only. Caddy does not route to
`llama-server`, and this stack does not expose it through Cloudflare.

## Model Profiles

The worker now loads one YAML model-profile file at startup and uses it to tune
per-mode llama-server requests while keeping a single loaded model:
`Qwen3-4B-Q4_K_M`.

Current built-in profiles:

- `default`
- `intent`
- `translation`
- `definition`
- `learning`
- `general`

This is not multi-model routing. The selected profile changes generation
controls such as `temperature`, `top_p`, `top_k`, `min_p`, `max_tokens`, and
Qwen3 reasoning hints via `/think` or `/no_think`, but all requests still hit
the same llama-server instance and the same loaded GGUF model.

## Worker Behaviour

With `LLM_BACKEND=llama_server`:

- the worker no longer needs the model mount in Compose
- the worker no longer needs local GPU execution settings in Compose
- the worker healthcheck can fail even when the Python process is up, if
  `llama-server` is unreachable

Legacy fallback remains available by setting `LLM_BACKEND=llama_cpp_python`, but
that is now a compatibility path rather than the default runtime. It also
requires the optional dependency in
[`../requirements-legacy-llama-cpp.txt`](../requirements-legacy-llama-cpp.txt).

## Manual Validation Checklist

1. Start `llama-server`.
2. Check `llama-server` health with `curl http://127.0.0.1:8080/health`.
3. Start Redis.
4. Start the worker.
5. Start FastAPI.
6. Submit a queued request to `/api/chat`.
7. Confirm worker logs show calls to `llama-server`.
8. Open the Web UI and confirm a normal chat response works.
9. Confirm `/api/chat/stream` and Web UI streaming both work.
10. Confirm Caddy still serves `http://localhost/` and `http://localhost/api/health`.

## Known Limitation

`llama-server` still has to be built for the target GPU architecture. On older
GPUs such as a GTX 1080, CUDA build compatibility must be verified separately
from the Python application because the queue/worker change does not remove that
runtime requirement.

For Pascal / GTX 1080 specifically:

- the upstream CUDA image may not work if it was not built with `sm_61` support
- if that happens, build a local `llama.cpp` CUDA image with the appropriate
  architecture flags and set `LLAMA_SERVER_IMAGE` to that local image name
- the upstream llama.cpp Docker docs note that local CUDA image builds may need
  different settings depending on the GPU architecture
- the older `CUDA error: no kernel image is available for execution on the device`
  issue is usually a sign that the binary or image was not built for `sm_61`
