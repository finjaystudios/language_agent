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

The chat requests call the real local model through the FastAPI backend, so make
sure the model and GPU prerequisites used by the CLI are available before running
those requests. System health and metadata requests remain unauthenticated;
protected chat and error-case requests send `X-API-Key: {{apiKey}}`.
