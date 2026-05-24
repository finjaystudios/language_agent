# Bruno API Client

This directory contains the Git-tracked Bruno collection for FastAPI API
testing.

Open `bruno/local-language-agent-api` in Bruno and choose one of the existing
environments:

- `Local`: host-local backend checks
- `Docker`: direct FastAPI checks on `http://127.0.0.1:8000`
- `Proxy`: Caddy-routed checks on `http://localhost`

Set `apiKey` to the same value as `FASTAPI_API_KEY` for protected requests.

## Run

Local backend:

```powershell
$env:AUTH_ENABLED = "true"
$env:FASTAPI_API_KEY = "local-dev-change-me"
python -m uvicorn app.api.main:app --reload
bru run bruno/local-language-agent-api --env Local
```

Compose proxy:

```powershell
docker compose up --build
bru run bruno/local-language-agent-api --env Proxy
```

## Scope

- Bruno tests FastAPI routes only
- public health and metadata requests stay unauthenticated
- protected chat and queue-related requests use `X-API-Key`
- Chainlit Web UI behavior is out of scope for Bruno

See [`../docs/testing.md`](../docs/testing.md) for the broader test matrix.
