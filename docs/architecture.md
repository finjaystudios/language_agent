# Architecture

## Runtime Shape

LanguageAgent currently has multiple entry points:

- CLI: `python -m app.main`
- FastAPI: `python -m uvicorn app.api.main:app ...`
- Chainlit Web UI: `chainlit run webui/app.py ...`
- RQ worker: `python -m app.queue.worker`
- tests: `pytest ...`

The system is deployed as separate processes and can also run as separate
containers:

```text
CLI -> local model runtime

Browser -> Chainlit Web UI -> FastAPI -> Redis + RQ -> GPU worker -> local model
                                  ^
                                  |
                                Caddy
```

## Service Boundaries

- The CLI runs local orchestration directly and is separate from the HTTP stack.
- FastAPI exposes health, metadata, chat, streaming, queue status, and job
  management endpoints.
- Redis + RQ provide queued execution, status tracking, retries, and streaming
  event transport.
- The worker owns the GGUF model lifecycle and is the only process that should
  call the local model runtime.
- The Web UI calls FastAPI over HTTP from server-side Chainlit code and must
  not load the model or import backend internals.
- Caddy is a reverse proxy in front of FastAPI and Chainlit for local/LAN
  routing.
- Cloudflare Tunnel, when used, sits outside Docker Compose and points at the
  host Caddy port.

## Dependency Direction

The target architecture rules for the backend are:

```text
interfaces -> application -> domain
infrastructure implements ports
composition roots wire concrete dependencies
```

The current codebase is still organized under `app/` by accumulated backend
areas such as `api`, `llm`, `orchestration`, `memory`, `queue`, and `services`.
Documentation should therefore describe the intended boundaries clearly even
before the codebase is fully rearranged into a layered package structure.

## Architectural Rules

- Use a Ports and Adapters / Hexagonal direction for new backend structure.
- Keep route handlers thin; orchestration belongs in services.
- Treat Redis, RQ, the local model runtime, and future external services as
  adapters.
- Keep dependency injection lightweight at entry points instead of adding a
  large DI framework.
- Use DTOs or schemas at API and queue boundaries where needed.
- Keep logging structured and avoid logging secrets or prompt content by
  default.

## Queue-Centric Model Execution

Every model-backed FastAPI request is decomposed into one or more queued LLM
calls. The queue boundary is the LLM call, not the top-level HTTP request. This
ensures only one GPU-backed model call runs at a time even when multiple API
requests overlap.

## Current Backend Package Shape

```text
app/
  api/
  data_models/
  llm/
  memory/
  orchestration/
  queue/
  services/
```

This shape reflects feature-driven growth. The documentation refactor is meant
to prepare for a later code-structure refactor toward clearer domain,
application, interface, and infrastructure boundaries.

## Deployment Modes

- Host-local development: CLI, FastAPI, Redis, worker, and Chainlit started
  manually
- Docker image workflows: FastAPI image and Web UI image built separately
- Docker Compose: Redis, FastAPI, worker, Web UI, and Caddy on one local
  network

See [`local-development.md`](local-development.md) and
[`docker-compose.md`](docker-compose.md) for exact operational workflows.
