# Llama-Server Migration Boundary

## Goal

Move GGUF model ownership out of the Python worker process and into an external
`llama-server` process without changing the FastAPI API surface, Chainlit Web
UI flow, or the Redis/RQ queue boundary.

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

## Migration Plan

1. Keep the queue contract intact and add `llama-server` configuration first.
2. Introduce a worker-side HTTP adapter that matches the existing
   ask/stream/cancel expectations where feasible.
3. Switch worker job execution from `create_local_llm_service()` to the
   `llama-server` adapter when `LLM_BACKEND=llama_server`.
4. Preserve Redis stream publishing semantics so FastAPI streaming stays
   compatible with the current SSE path.
5. Remove direct `llama-cpp-python` ownership only after the HTTP path matches
   the existing queue and streaming behavior.

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

## Local Manual Command Placeholder

Replace the placeholder values with the actual model path and flags required by
your `llama-server` build:

```powershell
llama-server --model <path-to-model.gguf> --host 0.0.0.0 --port 8080
```

## Docker Compose Goal

The intended Compose end state is:

- a dedicated `llama-server` service
- FastAPI and the worker configured with `LLAMA_SERVER_URL=http://llama-server:8080`
- the worker still consuming Redis/RQ jobs instead of bypassing the queue

This document does not implement those Compose changes yet.

## Known Limitation

`llama-server` still has to be built for the target GPU architecture. On older
GPUs such as a GTX 1080, CUDA build compatibility must be verified separately
from the Python application because the queue/worker change does not remove that
runtime requirement.
