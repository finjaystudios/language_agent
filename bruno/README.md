# Bruno API Client

This directory contains Git-tracked Bruno collections for local API testing.

Open `bruno/local-language-agent-api` in Bruno, select the `Local` environment,
and run the FastAPI backend:

```powershell
python -m uvicorn app.api.main:app --reload
```

Run the collection with Bruno CLI:

```powershell
bru run bruno/local-language-agent-api --env Local
```

The chat requests call the real local model through the FastAPI backend, so make
sure the model and GPU prerequisites used by the CLI are available before running
those requests.
