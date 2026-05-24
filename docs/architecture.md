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

- CLI: `python -m app.main`
- FastAPI: `python -m uvicorn app.api.main:app ...`
- Chainlit Web UI: `chainlit run webui/app.py ...`
- RQ worker: `python -m app.queue.worker`
- tests: `pytest ...`

Current runtime flow:

```text
CLI -> local model runtime

Browser -> Chainlit Web UI -> FastAPI -> Redis + RQ -> GPU worker -> local model
                                  ^
                                  |
                                Caddy
```

## Current Structure Summary

Current backend package shape:

```text
app/
  api/
  data_models/
  llm/
  memory/
  orchestration/
  queue/
  services/
  errors.py
  logging_config.py
  main.py
  processor_selection.py
```

Current role summary:

- `app/api/`: FastAPI routes, request/response schemas, auth, exception handlers,
  and dependency wiring
- `app/data_models/`: core Pydantic models for intent, responses, and session
  state
- `app/llm/`: local llama.cpp integration, prompt/schema loading, queued LLM
  client
- `app/memory/`: conversation memory
- `app/orchestration/`: mode handlers, routing, session orchestration
- `app/queue/`: Redis + RQ models, errors, status, stream handling, and worker
- `app/services/agent_service.py`: application facade for FastAPI chat flows

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
- `infrastructure/`: Redis/RQ adapter, local model adapter, prompt/schema file
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
- worker -> FastAPI route modules
- webui -> backend internals
- FastAPI routes -> local model runtime directly

## Audit Result

Static scan result:

- no hard Python import cycle was detected in `app/`
- the main problem is dependency direction, not an existing import loop

That means the code is still importable, but several modules already depend
downward on interface-layer concepts and would become cycle-prone during a file
move unless those edges are removed first.

## Current Dependency Risks

### 1. Service Layer Depends on API Layer

[`app/services/agent_service.py`](C:\Projects\LocalTranslation\language_agent\app\services\agent_service.py)
imports:

- `app.api.errors`
- `app.api.models`

This is the strongest architectural violation in the current codebase.
`AgentService` is acting as an application service, but it currently returns API
DTOs and raises API-layer errors.

Impact:

- blocks a clean `application/` package move
- couples application logic to FastAPI request/response types
- makes future interface changes ripple into core behavior

### 2. Queued LLM Adapter Depends on API Errors

[`app/llm/queued.py`](C:\Projects\LocalTranslation\language_agent\app\llm\queued.py)
imports `app.api.errors.LLMServiceError`.

This is another downward dependency inversion. Queue-backed LLM access is an
infrastructure concern and should raise core/application errors, not API
exceptions.

Impact:

- infrastructure depends on interface semantics
- queue adapter cannot be reused cleanly by non-API entry points

### 3. API Dependency Wiring Lives in the Service Class

[`app/api/dependencies.py`](C:\Projects\LocalTranslation\language_agent\app\api\dependencies.py)
constructs the service by calling `AgentService.from_queue()`.

`AgentService.from_queue()` in turn instantiates `QueuedLLMService` directly.
That means the service class owns infrastructure selection instead of receiving
its dependencies from a composition root.

Impact:

- composition is spread across API dependency code and the service class
- application code knows too much about concrete adapters

### 4. Mode Handlers and Router Depend on Concrete LLM Type

[`app/orchestration/router.py`](C:\Projects\LocalTranslation\language_agent\app\orchestration\router.py),
[`app/orchestration/modes/base.py`](C:\Projects\LocalTranslation\language_agent\app\orchestration\modes\base.py),
and related handlers are typed around the concrete `LLMService` shape or queue
client shape instead of an explicit port.

Impact:

- local model and queued model access are not formalized behind one interface
- difficult to substitute fakes or future model-server adapters cleanly

### 5. Queue Module Mixes Too Many Concerns

[`app/queue/service.py`](C:\Projects\LocalTranslation\language_agent\app\queue\service.py)
currently combines:

- Redis connection creation
- RQ queue access
- enqueue logic
- status polling
- stream transport
- queue metrics
- cancellation
- health/status snapshots

Impact:

- high change surface
- hard to separate ports from adapters
- likely hotspot for future cyclic risk once files start moving

### 6. CLI and API Orchestration Are Duplicated

[`app/main.py`](C:\Projects\LocalTranslation\language_agent\app\main.py) wires
`LLMService`, `ConversationMemory`, `IntentRouter`, and
`SessionOrchestrator`.

[`app/services/agent_service.py`](C:\Projects\LocalTranslation\language_agent\app\services\agent_service.py)
rebuilds a similar orchestration path for HTTP.

Impact:

- two composition styles for similar behavior
- drift risk between CLI and API feature behavior

### 7. Import-Time Config State Exists

[`app/processor_selection.py`](C:\Projects\LocalTranslation\language_agent\app\processor_selection.py)
reads env-derived values into module globals at import time.

Impact:

- configuration is less explicit than it should be
- future composition roots will have less control over runtime settings

### 8. API Package Re-Exports App Creation

[`app/api/__init__.py`](C:\Projects\LocalTranslation\language_agent\app\api\__init__.py)
imports `app.api.main` at package import time.

Impact:

- importing `app.api` triggers app construction side effects
- makes `app.api` an awkward package boundary for refactoring

## Things That Are Already Good

- FastAPI routes do not call the local model runtime directly
- worker code does not import FastAPI route modules
- Web UI code does not import backend internals
- the worker owns model loading and execution
- queue-backed execution is already separated from the HTTP process

## Entry Points and Composition Roots

Current practical composition roots:

- CLI root: [`app/main.py`](C:\Projects\LocalTranslation\language_agent\app\main.py)
- FastAPI root: [`app/api/main.py`](C:\Projects\LocalTranslation\language_agent\app\api\main.py)
- FastAPI dependency assembly: [`app/api/dependencies.py`](C:\Projects\LocalTranslation\language_agent\app\api\dependencies.py)
- worker root: [`app/queue/worker.py`](C:\Projects\LocalTranslation\language_agent\app\queue\worker.py)
- Web UI root: [`webui/app.py`](C:\Projects\LocalTranslation\language_agent\webui\app.py)

Target composition roots:

- `cli/main.py`: assemble local-model adapter and CLI presentation
- `interfaces/api/dependencies.py`: assemble application services with queue
  adapters
- `worker/main.py`: assemble the local-model adapter and queue job executor
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
| local model adapter | `infrastructure/llm/local_model.py` | wraps llama.cpp runtime |
| worker entry point | `worker/main.py` | composition root only |
| CLI entry point | `cli/main.py` | composition root only |

## Migration Principle

Do not start by moving files. Start by removing bad edges while files stay where
they are. Once the dependency direction is corrected, physical file moves become
mostly mechanical.

See [`refactor-plan.md`](refactor-plan.md) for the concrete module-by-module
migration order.
