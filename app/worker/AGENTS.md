# Review scope

Use this guide for the LLM worker.

The worker owns:

- consuming Redis/RQ jobs
- applying model profiles
- calling llama-server through an LLM gateway adapter
- publishing streaming chunks
- updating job status/results
- handling cancellation
- handling retries/timeouts/failures

## Worker boundaries

The worker must not import FastAPI route modules.

The worker must not load GGUF models directly.

The worker must not import `llama_cpp` or use `llama-cpp-python`.

The worker should call llama-server through the configured gateway abstraction.

## Queue rules

Every LLM call is processed as a queued job.

The worker should preserve:

- queued
- processing
- streaming
- completed
- failed
- cancelled

Do not remove queue status updates to simplify code.

Do not bypass cancellation checks.

Do not remove retry/failure handling unless explicitly requested.

## llama-server rules

llama-server is the model runtime.

The worker may call llama-server over HTTP using the gateway.

Do not expose llama-server URLs or API keys in logs.

Do not send raw prompt content to logs by default.

## Model profiles

The worker should select the correct profile per mode/task.

Profiles may control:

- prompt control, such as `/think` or `/no_think`
- temperature
- top_p
- top_k
- min_p
- max_tokens
- stream behaviour

Do not implement multi-model routing unless explicitly requested.

## Tests

Worker tests should mock the LLM gateway.

Normal tests should not require:

- real Redis unless marked integration
- real llama-server
- real GPU
- real model

Review for tests covering job success, job failure, cancellation, timeout, streaming chunks, and profile application.
