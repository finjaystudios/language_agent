# Architecture

## Purpose

This document captures:

- the current runtime and package shape
- the composition roots for each entry point
- the dependency and cleanup audit results

The detailed migration sequence lives in
[`refactor-plan.md`](refactor-plan.md).

## Runtime Shape

LanguageAgent currently has these runtime entry points:

- FastAPI: `python -m uvicorn app.interfaces.api.main:app ...`
- Chainlit Web UI: `chainlit run webui/chainlit_app.py ...`
- RQ worker: `python -m app.worker.main`
- tests: `pytest ...`

Current runtime flow:

```text
Browser -> Chainlit Web UI -> FastAPI -> Redis + RQ -> GPU worker -> llama-server -> GPU model
                                  ^
                                  |
                                Caddy
```

## Current Structure Summary

Current backend package shape:

```text
app/
  core/
  domain/
  application/
  ports/
  infrastructure/
  interfaces/api/
  worker/
```

Current role summary:

- `app/core/`: shared errors and logging setup
- `app/domain/`: framework-independent models for intent, responses, session
  state, and queue job state
- `app/application/`: application services, memory, routers, and mode handlers
- `app/ports/`: gateway interfaces
- `app/infrastructure/llm/`: llama-server adapter plus prompt/schema assets
- `app/infrastructure/redis/`: Redis + RQ queue adapters
- `app/interfaces/api/`: FastAPI app, routes, schemas, auth, and dependency
  wiring
- `app/worker/`: worker entry point and job execution functions

## Target Structure Summary

Current responsibilities:

- `core/`: cross-cutting config, logging, shared errors, small utility helpers
- `domain/`: domain models, mode/state concepts, pure domain rules
- `application/`: use cases, `AgentService`, intent coordination, prompt
  coordination, queue-aware orchestration contracts
- `ports/`: abstract interfaces such as LLM gateway and job/status store
- `infrastructure/`: Redis/RQ adapter, llama-server adapter, prompt/schema file
  loaders, environment-backed config
- `interfaces/api/`: FastAPI app, routes, API schemas, auth, exception mapping
- `worker/`: worker composition root and worker job execution entry point

## Dependency Direction Rules

Target dependency direction:

```text
interfaces -> application -> domain
infrastructure -> ports/application/domain
composition roots wire concrete dependencies
```

Forbidden dependency directions:

- domain -> FastAPI
- domain -> Chainlit
- domain -> Redis/RQ
- application -> FastAPI route modules
- application -> Chainlit modules
- worker -> FastAPI route modules
- webui -> backend internals
- FastAPI routes -> llama-server directly

## Ports and Adapters

The backend now follows a lightweight Ports and Adapters split:

- `application/` depends on ports such as `LLMGateway`, `JobStore`, and
  `QueueClient`
- `infrastructure/llm/` implements the llama-server adapter
- `infrastructure/redis/` implements Redis/RQ queue, job-state, and streaming
  adapters
- `interfaces/api/` wires concrete implementations into FastAPI dependencies
- `worker/` wires the selected runtime into the RQ job executor

Operationally, that means:

- FastAPI enqueues work through queue-backed adapters
- `llama-server` is the default runtime that loads and executes the GGUF model
- the worker is the only backend process that calls the model runtime on behalf
  of queued jobs
- the Web UI remains an HTTP client of FastAPI only

## Cleanup Summary

- `llama-server` is the only supported model runtime.
- Embedded `llama-cpp-python` inference was removed from active code, tests,
  and docs.
- The worker is now strictly a queue consumer, policy layer, and streaming
  publisher that talks to `llama-server` over HTTP.
- Redis/RQ remains responsible for backpressure, status tracking, cancellation,
  retries, and stream delivery.

## What Not to Import

Keep these boundaries explicit during future work:

- `app/domain/` must not import `fastapi`, `chainlit`, `redis`, or `rq`
- `app/application/` must not import FastAPI route modules or Chainlit modules
- `app/interfaces/api/` must not import worker job modules
- `app/worker/` must not import FastAPI route handlers or API schemas
- `webui/` must not import anything from `app/`
- FastAPI routes and dependencies must not call `llama-server` directly

## Audit Result

Static scan result:

- no hard Python import cycle was detected in `app/`
- the main problem is dependency direction, not an existing import loop

That means the code is still importable, but several modules already depend
downward on interface-layer concepts and would become cycle-prone during a file
move unless those edges are removed first.

## Current Dependency Risks

### 1. Composition Still Exists in More Than One Place

[`app/application/agent_service.py`](C:\Projects\LocalTranslation\language_agent\app\application\agent_service.py)
still exposes a queue-backed convenience constructor.

Impact:

- application-level convenience constructors still know about infrastructure
- future entry points could drift if composition logic is duplicated

### 2. Queue Coordination Still Has a Broad Surface

[`app/infrastructure/redis/queue_service.py`](C:\Projects\LocalTranslation\language_agent\app\infrastructure\redis\queue_service.py)
has been split behind ports, but it still owns several responsibilities:

- enqueue logic
- status polling
- cancellation
- queue health and metrics
- stream/result compatibility helpers

Impact:

- it remains the highest-change adapter surface
- future queue changes should be kept inside `infrastructure/redis/`

### 3. Refactor-Planning Docs Still Reference Removed Paths

Some planning documents still mention removed compatibility paths from the
transition period.

Impact:

- active runtime code now uses canonical modules only
- follow-up doc cleanup should stay limited to planning/history material

## Things That Are Already Good

- FastAPI routes do not call the model runtime directly
- worker code does not import FastAPI route modules
- Web UI code does not import backend internals
- the queue boundary already isolates HTTP handling from model execution
- queue-backed execution is already separated from the HTTP process

## Entry Points and Composition Roots

Current practical composition roots:

- FastAPI root: [`app/interfaces/api/main.py`](C:\Projects\LocalTranslation\language_agent\app\interfaces\api\main.py)
- FastAPI dependency assembly: [`app/interfaces/api/dependencies.py`](C:\Projects\LocalTranslation\language_agent\app\interfaces\api\dependencies.py)
- worker root: [`app/worker/main.py`](C:\Projects\LocalTranslation\language_agent\app\worker\main.py)
- Web UI root: [`webui/ui_app.py`](C:\Projects\LocalTranslation\language_agent\webui\ui_app.py)

Current dependency-injection responsibilities:

- `get_settings()`: environment-backed shared settings
- `get_queue_client()`: Redis/RQ queue adapter
- `get_job_store()`: Redis-backed job/result store adapter
- `get_llm_gateway()`: queue-backed LLM gateway
- `get_agent_service()`: application facade for API requests

Target composition roots:

- `interfaces/api/dependencies.py`: assemble application services with queue
  adapters
- `worker/main.py`: assemble the selected runtime adapter and queue job executor
- `webui/ui_app.py`: keep separate and HTTP-only

## Recommended Home for Key Concepts

| Concept | Target home | Notes |
| --- | --- | --- |
| config | `core/config.py` and infrastructure-specific config modules | move env parsing out of scattered modules |
| logging | `core/logging.py` | keep shared structured logging setup here |
| domain models | `domain/` | move `data_models` and session-state concepts here, excluding API DTOs |
| API schemas | `interfaces/api/schemas/` | `ChatRequest`, `ChatResponse`, error payloads, queue status response DTOs |
| agent service | `application/agent_service.py` | facade over router, handlers, and LLM gateway port |
| LLM gateway port | `ports/llm_gateway.py` | contract for ask/stream/cancel behavior |
| Redis/RQ adapter | `infrastructure/redis/` | queue adapter, job state adapter, stream adapter |
| default runtime adapter | `infrastructure/llm/llama_server_gateway.py` | wraps the OpenAI-compatible llama-server HTTP API |
| worker entry point | `worker/main.py` | composition root only |

## Migration Principle

Do not start by moving files. Start by removing bad edges while files stay where
they are. Once the dependency direction is corrected, physical file moves become
mostly mechanical.

See [`refactor-plan.md`](refactor-plan.md) for the concrete module-by-module
migration order.
