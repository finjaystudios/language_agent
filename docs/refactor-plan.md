# Refactor Plan

## Goal

Refactor the backend toward Ports and Adapters without changing behavior and
without taking on a high-risk file move first.

## Summary

The codebase does not currently have a hard import cycle, but it does have
wrong-way dependencies that will create refactor pain if files are moved too
early.

The safest sequence is:

1. introduce core/application/port abstractions in place
2. migrate dependencies to those abstractions
3. move files only after imports point the right way

## Current-to-Target Mapping

| Current area | Target area | Notes |
| --- | --- | --- |
| `app/errors.py` | `core/errors.py` | base service errors only |
| `app/logging_config.py` | `core/logging.py` | shared logging setup |
| `app/processor_selection.py` | `infrastructure/llm/runtime_config.py` or `core/config.py` | split env config from GPU/runtime probing |
| `app/data_models/*` | `domain/*` | keep pure models here |
| `app/orchestration/router.py` | `application/intent_service.py` or `application/mode_router.py` | depends on `LLMGateway` port |
| `app/orchestration/modes/*` | `application/` and possibly `domain/` helpers | keep use-case logic above domain |
| `app/memory/short_term.py` | `application/` or `domain/` | likely application state helper |
| `app/services/agent_service.py` | `application/agent_service.py` | should stop importing API DTOs first |
| `app/llm/service.py` | `infrastructure/llm/local_model.py` | local llama.cpp adapter |
| `app/llm/queued.py` | `infrastructure/redis/queued_gateway.py` | queue-backed gateway adapter |
| `app/llm/prompts.py` and loaders | `infrastructure/llm/` | prompt/schema assets stay infra-side |
| `app/queue/models.py` | split between `domain/jobs.py`, `ports/`, and `infrastructure/redis/` DTOs | current file mixes several levels |
| `app/queue/service.py` | `infrastructure/redis/` modules | split queue access, job store, stream transport, monitoring |
| `app/queue/worker.py` | `worker/main.py` and `worker/jobs.py` | keep entry point separate from job executor |
| `app/api/*` | `interfaces/api/*` | keep FastAPI-specific concerns here |

## Required Interface Cuts Before Moving Files

### Cut 1: Stop Returning API DTOs from AgentService

Current problem:

- `AgentService` accepts `ChatRequest`
- returns `ChatResponse`
- builds `ResponseMetadata`
- uses `ApiMode`

Target:

- define application commands and results in `application/`
- let FastAPI route modules map API schemas to application commands/results

Safe first step:

- add application-level request/result models
- add mappers in the API layer
- keep behavior identical

### Cut 2: Stop Raising API Errors from Application and Infrastructure

Current problem:

- `AgentService` raises `app.api.errors.LLMServiceError`
- `QueuedLLMService` raises `app.api.errors.LLMServiceError`

Target:

- define service/runtime errors in `core/errors.py`
- map those errors to HTTP responses only in `interfaces/api/errors.py`

Safe first step:

- add neutral error classes in `app/errors.py`
- update API handlers to translate them
- then remove `app.api.errors` imports from non-API modules

### Cut 3: Introduce an LLM Gateway Port

Current problem:

- router, handlers, CLI, and service code all assume concrete LLM behavior

Target:

- `ports/llm_gateway.py` defines `ask_llm`, `stream_llm`, and `cancel_job`
- local model adapter and queue-backed adapter both implement that contract

Safe first step:

- define a protocol or abstract base
- type router, handlers, and `AgentService` to the port instead of concrete
  adapters

### Cut 4: Move Composition Out of AgentService Classmethods

Current problem:

- `AgentService.from_queue()` and `AgentService.from_local_model()` choose
  infrastructure directly

Target:

- composition roots choose adapters
- `AgentService` only accepts injected dependencies

Safe first step:

- keep current classmethods temporarily
- introduce standalone builder functions in API, CLI, and worker layers
- then delete classmethods

### Cut 5: Split Queue Module by Responsibility

Current problem:

- `app/queue/service.py` is both queue adapter and monitoring/job-store logic

Target:

- queue client adapter
- job state adapter
- stream transport adapter
- queue metrics/monitoring adapter

Safe first step:

- separate functions into new modules while preserving public wrappers
- update imports incrementally

## Planned Module Moves

### Phase 1: In-Place Architectural Cleanup

No file moves yet.

- add application DTOs and results
- add a neutral LLM gateway interface
- move non-HTTP exceptions to core
- remove `app.api.*` imports from `app/services/agent_service.py`
- remove `app.api.*` imports from `app/llm/queued.py`

### Phase 2: Composition Root Cleanup

- move API assembly logic into dedicated dependency builders
- keep CLI assembly in one CLI root
- move worker assembly into one worker root
- stop using `AgentService` classmethods for concrete adapter selection

### Phase 3: Queue Adapter Split

- separate Redis/RQ connection code
- separate enqueue/status/cancel functions
- separate stream transport
- separate queue monitoring snapshot logic

### Phase 4: Physical Package Move

Once imports already follow the desired direction:

- create `core/`, `domain/`, `application/`, `ports/`, `infrastructure/`,
  `interfaces/api/`, `cli/`, `worker/`
- move modules in small batches
- keep temporary re-export shims only if needed

## Risks

### API Contract Drift

Risk:

- moving too fast from API DTOs to application DTOs can change response shape

Mitigation:

- keep API schemas stable
- add explicit mapping functions at the boundary

### Queue Behavior Regression

Risk:

- splitting `app/queue/service.py` too early may break retries, stream events, or
  queue status reporting

Mitigation:

- split by wrapper-preserving extraction
- keep existing tests around queue and API status behavior green

### CLI/API Drift

Risk:

- separate orchestration paths may diverge during refactor

Mitigation:

- converge on one application service/facade used by both CLI and API where
  practical

### Import Breakage During File Moves

Risk:

- early package moves create churn and hidden import fallout

Mitigation:

- do not move files until bad edges are already removed

## Suggested Migration Order

1. Introduce neutral core errors and use them outside the API layer.
2. Introduce an `LLMGateway` port and type the router/handlers/service to it.
3. Introduce application commands/results and API mappers.
4. Remove `AgentService.from_queue()` and `from_local_model()` usage from core
   logic in favor of composition roots.
5. Split queue code into smaller adapters while preserving behavior.
6. Move files into the target package layout in small batches.
7. Update docs and imports after each batch, not only at the end.

## Keep vs Move

Keep as-is for now:

- Web UI HTTP-only separation
- worker ownership of the local model
- queue-backed FastAPI execution model
- Caddy and deployment boundaries

Move later after dependency cleanup:

- `app/services/agent_service.py`
- `app/orchestration/*`
- `app/llm/queued.py`
- `app/queue/service.py`
- `app/processor_selection.py`
