# LanguageAgent

LanguageAgent is a local-first language assistant with multiple runtime surfaces:

- CLI for direct local use
- FastAPI backend for HTTP access
- Chainlit Web UI for browser interaction
- Redis + RQ queue for serialized LLM work
- Dedicated GPU worker that brokers queued calls to `llama-server`

The current system separates the API, Web UI, queue, and worker so model-backed
requests can be queued and executed by one long-lived worker process instead of
loading the model in every service.

## Service Overview

```text
CLI -> legacy local llama-cpp-python runtime

Browser -> Chainlit Web UI -> FastAPI -> Redis + RQ -> GPU worker -> llama-server -> GPU model
                                  ^
                                  |
                                Caddy
```

- The CLI calls local services directly.
- The Web UI does not load the model and does not import backend internals.
- Every FastAPI LLM call goes through Redis + RQ.
- In the default runtime, `llama-server` is the only service allowed to load the GGUF model.

## Quick Start

For the full local stack with Caddy, Redis, FastAPI, the worker, and Chainlit:

```powershell
Copy-Item .env.compose.example .env
docker compose up --build
```

Open:

- Web UI: `http://localhost/`
- FastAPI health through Caddy: `http://localhost/api/health`

For a host-local development workflow without Docker, see
[`docs/local-development.md`](docs/local-development.md).

## Common Commands

Run the CLI:

```powershell
python -m app.cli.main
```

Run the FastAPI backend:

```powershell
python -m uvicorn app.interfaces.api.main:app --reload --host 127.0.0.1 --port 8000
```

Run the worker:

```powershell
python -m app.worker.main
```

Run the Web UI:

```powershell
Push-Location webui
chainlit run app.py --host 127.0.0.1 --port 8001
Pop-Location
```

Run the Playwright E2E suite:

```powershell
pytest tests/e2e
```

Run the Bruno collection:

```powershell
bru run bruno/local-language-agent-api --env Local
```

## Documentation

- [`docs/README.md`](docs/README.md): documentation index
- [`docs/architecture.md`](docs/architecture.md): service boundaries and dependency direction
- [`docs/local-development.md`](docs/local-development.md): host-local CLI, API, Redis, worker, and Web UI workflow
- [`docs/docker-compose.md`](docs/docker-compose.md): full containerized stack with Caddy
- [`docs/configuration.md`](docs/configuration.md): environment variables and where they apply
- [`docs/llama-server.md`](docs/llama-server.md): llama-server runtime, Compose workflow, and migration boundary
- [`docs/queue.md`](docs/queue.md): Redis + RQ design and job lifecycle
- [`docs/reverse-proxy.md`](docs/reverse-proxy.md): Caddy routing and Cloudflare Tunnel boundary
- [`docs/security.md`](docs/security.md): API key auth, CORS, and service boundaries
- [`docs/mobile-ui.md`](docs/mobile-ui.md): responsive Web UI behavior and validation
- [`docs/testing.md`](docs/testing.md): pytest, Playwright, Bruno, Compose, and audit workflows
- [`docs/troubleshooting.md`](docs/troubleshooting.md): common local failure modes
- [`webui/README.md`](webui/README.md): Chainlit-only usage
- [`bruno/README.md`](bruno/README.md): Bruno-only usage
- [`tests/e2e/README.md`](tests/e2e/README.md): Playwright-only usage

## Current Limitations

- The queue-backed chat flow depends on Redis and a separate `app.worker.main`
  process for all model-backed API requests.
- The current Docker setup expects NVIDIA GPU support for the `llama-server` container.
- The Web UI authenticates to FastAPI with a shared service API key, not
  per-user identity.
- Cloudflare Tunnel is documented as an external boundary and is not part of
  `compose.yml`.
