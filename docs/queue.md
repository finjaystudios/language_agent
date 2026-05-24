# Queue

## Overview

FastAPI does not call the model directly. Every model-backed LLM call goes
through Redis + RQ and is executed by a separate worker process.

```text
FastAPI -> enqueue LLM call in Redis + RQ -> worker -> local model
```

This queue boundary is intentionally at the LLM-call level, not the top-level
HTTP request level. A single API request may trigger multiple LLM calls for
intent routing, state updates, and final generation.

## Why the Queue Exists

- Serialize GPU-backed model execution by default
- Keep the model loaded in one long-lived worker process
- Isolate API request handling from model execution latency
- Expose queue status, retries, and cancellation
- Support streaming over Redis-backed event transport

## Components

- Redis stores queue state, job metadata, streaming events, and failed-job
  registries.
- RQ provides queued job execution.
- FastAPI produces jobs.
- `app.queue.worker` consumes jobs.
- The worker owns the GGUF model lifecycle.

## Request Flow

Non-streaming:

```text
client -> FastAPI /api/chat -> enqueue one or more LLM jobs -> worker -> result stored in Redis -> FastAPI returns response
```

Streaming:

```text
client -> FastAPI /api/chat/stream -> enqueue streaming job -> worker publishes stream events -> FastAPI forwards SSE
```

## Single Worker Ownership

The worker uses `SimpleWorker` and requires `LLM_WORKER_CONCURRENCY=1`. That is
intentional: one long-lived worker process keeps one loaded model instance
instead of spawning multiple independent model owners.

## API Endpoints

Protected queue-related endpoints:

- `GET /api/queue/status`
- `GET /api/llm/jobs/{job_id}`
- `POST /api/llm/jobs/{job_id}/cancel`

Chat endpoints are also queue-backed:

- `POST /api/chat`
- `POST /api/chat/stream`

## Status and Result Handling

Queue status reports are available through `GET /api/queue/status`. The returned
payload includes queue depth and worker/Redis health information.

Job-specific status is available through `GET /api/llm/jobs/{job_id}`. Fields
include:

- `job_id`
- `call_type`
- `mode`
- `status`
- `queue_position`
- `elapsed_seconds`
- `retry_count`
- `cancel_requested`
- `last_error`

## Streaming Event Handling

Streaming jobs publish status and token events into Redis Streams using
`LLM_STREAM_CHANNEL_PREFIX`. FastAPI reads those events and forwards them as
`text/event-stream`.

Event shapes include:

```text
data: {"mode": "translation", "token": "..."}

data: {"mode": "translation", "done": true}
```

Additional status events may include `job_id`, `status`, `queue_position`,
`elapsed_seconds`, and `cancel_requested`.

## Backpressure and Timeouts

The queue layer enforces limits using configuration such as:

- `LLM_MAX_QUEUE_SIZE`
- `LLM_QUEUE_WAIT_TIMEOUT_SECONDS`
- `LLM_GENERATION_TIMEOUT_SECONDS`
- `LLM_STREAM_TIMEOUT_SECONDS`

When the queue is saturated, FastAPI returns `429` with `Retry-After`.

## Retries and Failures

- Transient worker failures retry up to `LLM_JOB_MAX_RETRIES`
- Non-retryable invalid structured output errors fail immediately
- Failed jobs move through normal RQ failure handling or Redis-backed error
  state

Sanitized failure messages are returned; stack traces are not exposed through
the public API.

## Cancellation

Queued jobs can be cancelled immediately. Streaming jobs check for cancellation
during generation and stop between generated chunks when possible. Non-streaming
jobs cannot always be interrupted mid-call by the current local runtime.

Example cancellation flow:

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:8000/api/llm/jobs/<job-id>/cancel `
  -Method Post `
  -Headers @{"X-API-Key" = "local-dev-change-me"}
```
