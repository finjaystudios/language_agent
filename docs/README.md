# Documentation

Use this directory as the durable system manual. The root
[`README.md`](../README.md) is the landing page; detailed operational and
architectural material lives here.

## Core Docs

- [`architecture.md`](architecture.md): system shape, service boundaries,
  dependency direction, entry points, and deployment model
- [`refactor-plan.md`](refactor-plan.md): staged backend migration plan for the
  package and dependency cleanup
- [`local-development.md`](local-development.md): run the CLI, FastAPI, Redis,
  worker, and Chainlit locally without Docker Compose
- [`docker-compose.md`](docker-compose.md): run the full local container stack
  with Redis, FastAPI, the worker, Chainlit, and Caddy
- [`configuration.md`](configuration.md): centralized environment variable
  reference
- [`llama-server.md`](llama-server.md): planned external llama-server runtime,
  migration boundary, and environment variables
- [`queue.md`](queue.md): Redis + RQ design, worker lifecycle, queue status,
  streaming, retries, and cancellation
- [`reverse-proxy.md`](reverse-proxy.md): Caddy routing, LAN access, and
  Cloudflare Tunnel boundary
- [`security.md`](security.md): service-to-service API key auth, CORS, secret
  handling, and public/private endpoints
- [`mobile-ui.md`](mobile-ui.md): responsive Web UI behavior, manual checks, and
  mobile-focused Playwright coverage
- [`testing.md`](testing.md): pytest, Playwright, Bruno, Compose validation, and
  dependency audit commands
- [`troubleshooting.md`](troubleshooting.md): common local setup and runtime
  failures

## Component Docs

- [`../webui/README.md`](../webui/README.md): Chainlit Web UI usage only
- [`../bruno/README.md`](../bruno/README.md): Bruno collection usage only
- [`../tests/e2e/README.md`](../tests/e2e/README.md): Playwright E2E usage only

## Renamed Topics

- [`mobile-ui.md`](mobile-ui.md) replaces `mobile-ui-plan.md`
- [`reverse-proxy.md`](reverse-proxy.md) replaces `reverse_proxy.md`
- [`security.md`](security.md) replaces `security_webui_fastapi.md`
