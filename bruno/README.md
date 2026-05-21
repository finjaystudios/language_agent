# Bruno API Client

This directory contains Git-tracked Bruno collections for local API testing.

Open `bruno/local-language-agent-api` in Bruno, select the `Local` environment,
set `apiKey` to the same value as `FASTAPI_API_KEY`, and run the FastAPI
backend:

```powershell
$env:AUTH_ENABLED = "true"
$env:FASTAPI_API_KEY = "local-dev-change-me"
python -m uvicorn app.api.main:app --reload
```

Run the collection with Bruno CLI:

```powershell
bru run bruno/local-language-agent-api --env Local
```

For the Docker Compose stack through Caddy, select the `Proxy` environment or
run:

```powershell
docker compose up --build
bru run bruno/local-language-agent-api --env Proxy
```

The `Proxy` environment uses `baseUrl: http://localhost`. API requests continue
to use `/api/...` paths, and protected endpoints still send
`X-API-Key: {{apiKey}}`. Use `System/Proxy Health` for the Caddy-routed backend
health check at `/api/health`.

The `Docker` environment remains available for direct backend checks against
`http://127.0.0.1:8000`, bypassing Caddy.

The chat requests call the real local model through the FastAPI backend, so make
sure the model and GPU prerequisites used by the CLI are available before running
those requests. System health and metadata requests remain unauthenticated;
protected chat and error-case requests send `X-API-Key: {{apiKey}}`.

To verify auth rejection manually, remove or change `apiKey` and run any Chat
request. The protected endpoint should return `401` without exposing the expected
key.

Bruno tests FastAPI API routes, either directly with `Docker` or through Caddy
with `Proxy`. Test the Chainlit Web UI through a browser or the Playwright
workflow, not through Bruno. The Web UI sends `X-API-Key` from its server-side
environment; that key should not appear in browser-visible output or service
logs.
