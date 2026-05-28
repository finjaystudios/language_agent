# Review scope

This is the root review guide for LanguageAgent. Use it for general pull request review across the whole repository.
LanguageAgent is a local-first LLM application with:

- FastAPI backend
- Chainlit Web UI
- Redis/RQ queue
- LLM worker
- llama-server for GGUF model inference
- PostgreSQL for user profiles and chat history was enabled
- Caddy reverse proxy
- Docker Compose
- Bruno API collections
- Playwright E2E tests

Current runtime path:
Web UI → FastAPI → Redis/RQ → LLM worker → llama-server → GPU model

## General review priorities

Check:

1. What changed?
2. Whether the change fits the existing architecture.
3. Whether the change introduces security, correctness, or operational risks.
4. Whether tests and docs are updated where needed.

## Architecture rules

Follow Ports and Adapters / Hexagonal Architecture.

Expected dependency direction:
interfaces → application → domain
infrastructure implements ports
composition roots wire concrete dependencies

Do not allow:

- Web UI importing backend internals.
- FastAPI routes bypassing Redis/RQ for LLM calls.
- FastAPI routes calling llama-server directly.
- Worker importing FastAPI route modules.
- Domain/application code depending directly on Chainlit, FastAPI, Redis, RQ, SQLAlchemy, or llama-server HTTP details.
- llama-server, Redis, PostgreSQL, or worker services exposed publicly.

## Service boundaries

FastAPI owns API contracts, auth, validation, enqueueing, status/result endpoints, and health checks.

Web UI owns Chainlit UI, login UX, chat UX, and server-side FastAPI calls.

Worker owns queued job execution, model profile selection, llama-server HTTP calls, streaming forwarding, retries, cancellation, and job status updates.

llama-server owns model loading and GPU inference.

PostgreSQL owns persistent user/chat data where enabled.

Redis/RQ owns queueing, job state, and backpressure.

## Security review

Block PRs that:

- Commit secrets.
- Log API keys, passwords, password hashes, database credentials, session secrets, or raw prompt content by default.
- Store plaintext passwords.
- Weaken Web UI sign-in.
- Weaken Web UI → FastAPI API key auth.
- Expose the llama-server, Redis, PostgreSQL, or the worker through Caddy/Cloudflare.
- Return sensitive internal errors to users.

## Testing expectations

Prefer targeted tests.

Normal automated tests should not require:

- real GPU
- real GGUF model
- real llama-server
- Cloudflare Tunnel
- public domain access

Useful checks:

- pytest
- pytest --cov
- pip-audit
- docker compose config
- pytest tests/e2e

Only require expensive/manual validation when the PR changes Docker, model serving, queue behaviour, auth, or Web UI flows.

## Documentation expectations

If a PR changes commands, environment variables, service names, routes, auth behaviour, queue behaviour, model profiles, or Docker services, update the relevant docs.

Common docs:

README.md
docs/configuration.md
docs/docker-compose.md
docs/queue.md
docs/llama-server.md
docs/security.md
docs/testing.md
docs/troubleshooting.md

## Review output format

Use this structure:

Summary:

- What changed?
- Whether the change fits the architecture.

Blocking issues:

- Security, correctness, broken startup, broken tests, data loss, queue bypass, and auth bypass.

Non-blocking suggestions:

- Maintainability, naming, cleanup, and docs.

Tests/docs to add:

- Missing targeted tests.
- Missing docs for changed behaviour.

Final assessment:

- Ready to merge / needs changes / needs manual validation.
