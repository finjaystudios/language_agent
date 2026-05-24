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

[`app/application/agent_service.py`](C:\Projects\LocalTranslation\language_agent\app\application\agent_service.py)
imports:

- application and domain modules
- one infrastructure adapter for queue-backed composition convenience

The earlier API-layer dependency has been removed. The remaining concern is that
the service still instantiates concrete adapters via helper constructors, which
should eventually move fully into composition roots.

Impact:

- composition is not yet fully separated from the service class
- application constructors still know about concrete infrastructure

### 2. Queued LLM Adapter Depends on API Errors

[`app/infrastructure/redis/queued_gateway.py`](C:\Projects\LocalTranslation\language_agent\app\infrastructure\redis\queued_gateway.py)
now raises core errors instead of API-layer errors.

This dependency inversion has been corrected, but the adapter still lives close
to queue-specific data shapes and should later be formalized behind ports more
strictly.

Impact:

- queue-backed gateway should eventually depend only on formal ports and domain
  job models

### 3. API Dependency Wiring Lives in the Service Class

[`app/interfaces/api/dependencies.py`](C:\Projects\LocalTranslation\language_agent\app\interfaces\api\dependencies.py)
constructs the service by calling `AgentService.from_queue()`.

`AgentService.from_queue()` in turn instantiates `QueuedLLMService` directly.
That means the service class owns infrastructure selection instead of receiving
its dependencies from a composition root.

Impact:

- composition is spread across API dependency code and the service class
- application code knows too much about concrete adapters

### 4. Mode Handlers and Router Depend on Concrete LLM Type

[`app/application/intent_router.py`](C:\Projects\LocalTranslation\language_agent\app\application\intent_router.py),
[`app/application/modes/base.py`](C:\Projects\LocalTranslation\language_agent\app\application\modes\base.py),
and related handlers are typed around the concrete `LLMService` shape or queue
client shape instead of an explicit port.

Impact:

- local model and queued model access are not formalized behind one interface
- difficult to substitute fakes or future model-server adapters cleanly

### 5. Queue Module Mixes Too Many Concerns

[`app/infrastructure/redis/queue_service.py`](C:\Projects\LocalTranslation\language_agent\app\infrastructure\redis\queue_service.py)
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

[`app/cli/main.py`](C:\Projects\LocalTranslation\language_agent\app\cli\main.py) wires
`LLMService`, `ConversationMemory`, `IntentRouter`, and
`SessionOrchestrator`.

[`app/application/agent_service.py`](C:\Projects\LocalTranslation\language_agent\app\application\agent_service.py)
rebuilds a similar orchestration path for HTTP.

Impact:

- two composition styles for similar behavior
- drift risk between CLI and API feature behavior

### 7. Import-Time Config State Exists

[`app/infrastructure/llm/runtime_config.py`](C:\Projects\LocalTranslation\language_agent\app\infrastructure\llm\runtime_config.py)
reads env-derived values into module globals at import time.

Impact:

- configuration is less explicit than it should be
- future composition roots will have less control over runtime settings

### 8. API Package Re-Exports App Creation

Compatibility wrappers still exist under `app/api/`, `app/queue/`, and related
legacy paths so older imports continue to resolve during the transition.

Impact:

- dual-path imports still exist temporarily
- cleanup is still needed once the new package paths are fully adopted

## Things That Are Already Good

- FastAPI routes do not call the local model runtime directly
- worker code does not import FastAPI route modules
- Web UI code does not import backend internals
- the worker owns model loading and execution
- queue-backed execution is already separated from the HTTP process

## Entry Points and Composition Roots

Current practical composition roots:

- CLI root: [`app/cli/main.py`](C:\Projects\LocalTranslation\language_agent\app\cli\main.py)
- FastAPI root: [`app/interfaces/api/main.py`](C:\Projects\LocalTranslation\language_agent\app\interfaces\api\main.py)
- FastAPI dependency assembly: [`app/interfaces/api/dependencies.py`](C:\Projects\LocalTranslation\language_agent\app\interfaces\api\dependencies.py)
- worker root: [`app/worker/main.py`](C:\Projects\LocalTranslation\language_agent\app\worker\main.py)
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
