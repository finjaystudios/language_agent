# Architecture

## Purpose

This document captures:

- the current runtime and package shape
- the target Ports and Adapters direction
- the dependency audit results
- the composition roots for each entry point

The detailed migration sequence lives in
[`refactor-plan.md`](refactor-plan.md).

## Runtime Shape

LanguageAgent currently has multiple entry points:

- CLI: `python -m app.cli.main`
- FastAPI: `python -m uvicorn app.interfaces.api.main:app ...`
- Chainlit Web UI: `chainlit run webui/app.py ...`
- RQ worker: `python -m app.worker.main`
- tests: `pytest ...`

Current runtime flow:

```text
CLI -> legacy local llama-cpp-python runtime

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
  cli/
  worker/
```

Current role summary:

- `app/core/`: shared errors and logging setup
- `app/domain/`: framework-independent models for intent, responses, session
  state, and queue job state
- `app/application/`: application services, memory, routers, and mode handlers
- `app/ports/`: gateway interfaces
- `app/infrastructure/llm/`: local model runtime plus prompt/schema assets
- `app/infrastructure/redis/`: Redis + RQ queue adapters
- `app/interfaces/api/`: FastAPI app, routes, schemas, auth, and dependency
  wiring
- `app/cli/`: CLI entry point
- `app/worker/`: worker entry point and job execution functions

## Target Structure Summary

Recommended target package shape:

```text
src/language_agent/
  core/
  domain/
  application/
  ports/
  infrastructure/
  interfaces/api/
  cli/
  worker/
```

Recommended responsibilities:

- `core/`: cross-cutting config, logging, shared errors, small utility helpers
- `domain/`: domain models, mode/state concepts, pure domain rules
- `application/`: use cases, `AgentService`, intent coordination, prompt
  coordination, queue-aware orchestration contracts
- `ports/`: abstract interfaces such as LLM gateway and job/status store
- `infrastructure/`: Redis/RQ adapter, llama-server and legacy local-model adapters, prompt/schema file
  loaders, environment-backed config
- `interfaces/api/`: FastAPI app, routes, API schemas, auth, exception mapping
- `cli/`: CLI composition root and CLI-only presentation
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
- FastAPI routes -> local model runtime directly
- CLI -> FastAPI route modules

## Ports and Adapters

The backend now follows a lightweight Ports and Adapters split:

- `application/` depends on ports such as `LLMGateway`, `JobStore`, and
  `QueueClient`
- `infrastructure/llm/` implements the default llama-server adapter and the
  legacy local-model adapter
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

## What Not to Import

Keep these boundaries explicit during future work:

- `app/domain/` must not import `fastapi`, `chainlit`, `redis`, or `rq`
- `app/application/` must not import FastAPI route modules or Chainlit modules
- `app/interfaces/api/` must not import worker job modules
- `app/worker/` must not import FastAPI route handlers or API schemas
- `webui/` must not import anything from `app/`
- FastAPI routes and dependencies must not call
  `app.infrastructure.llm.local_model` directly
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
still exposes convenience constructors for local-model and queue-backed startup.
The earlier API-layer dependency has been removed, but those constructors still
select concrete adapters inside the service layer.

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

### 3. Compatibility Wrappers Still Exist

Compatibility wrappers still exist under `app/api/`, `app/queue/`, `app/llm/`,
and related legacy paths so older imports continue to resolve during the
transition.

Impact:

- dual-path imports still exist temporarily
- full cleanup is blocked until downstream callers stop using legacy paths

### 4. Import-Time Runtime Configuration Still Exists

[`app/infrastructure/llm/runtime_config.py`](C:\Projects\LocalTranslation\language_agent\app\infrastructure\llm\runtime_config.py)
still reads env-derived values into module globals at import time.

Impact:

- configuration remains less explicit than it should be
- later composition-root cleanup should move more runtime choices behind
  `AppSettings` or worker-local config

### 5. Tests and Tooling Still Use Some Legacy Import Paths

Some tests and wrappers still import through compatibility paths such as
`app.api.*` and `app.llm.queued`.

Impact:

- the runtime boundaries are cleaner than the import graph seen by every caller
- wrapper removal should be a separate, low-risk cleanup once all callers migrate

## Things That Are Already Good

- FastAPI routes do not call the local model runtime directly
- worker code does not import FastAPI route modules
- Web UI code does not import backend internals
- the queue boundary already isolates HTTP handling from model execution
- queue-backed execution is already separated from the HTTP process

## Entry Points and Composition Roots

Current practical composition roots:

- CLI root: [`app/cli/main.py`](C:\Projects\LocalTranslation\language_agent\app\cli\main.py)
- FastAPI root: [`app/interfaces/api/main.py`](C:\Projects\LocalTranslation\language_agent\app\interfaces\api\main.py)
- FastAPI dependency assembly: [`app/interfaces/api/dependencies.py`](C:\Projects\LocalTranslation\language_agent\app\interfaces\api\dependencies.py)
- worker root: [`app/worker/main.py`](C:\Projects\LocalTranslation\language_agent\app\worker\main.py)
- Web UI root: [`webui/app.py`](C:\Projects\LocalTranslation\language_agent\webui\app.py)

Current dependency-injection responsibilities:

- `get_settings()`: environment-backed shared settings
- `get_queue_client()`: Redis/RQ queue adapter
- `get_job_store()`: Redis-backed job/result store adapter
- `get_llm_gateway()`: queue-backed LLM gateway
- `get_agent_service()`: application facade for API requests

Target composition roots:

- `cli/main.py`: assemble local-model adapter and CLI presentation
- `interfaces/api/dependencies.py`: assemble application services with queue
  adapters
- `worker/main.py`: assemble the selected runtime adapter and queue job executor
- `webui/app.py`: keep separate and HTTP-only

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
| legacy local model adapter | `infrastructure/llm/local_model.py` | wraps llama.cpp runtime |
| worker entry point | `worker/main.py` | composition root only |
| CLI entry point | `cli/main.py` | composition root only |

## Migration Principle

Do not start by moving files. Start by removing bad edges while files stay where
they are. Once the dependency direction is corrected, physical file moves become
mostly mechanical.

See [`refactor-plan.md`](refactor-plan.md) for the concrete module-by-module
migration order.
