## Chainlit Web UI

The Web UI lives in `webui/` as a separate Chainlit application. It communicates
with the FastAPI backend only over HTTP and is intended to be deployed separately
from the backend in a later Web UI Docker feature.

### Install Dependencies

From the repository root:

```powershell
pip install -r webui/requirements.txt
```

### Environment

Example local values:

```powershell
$env:FASTAPI_BASE_URL = "http://127.0.0.1:8000"
$env:FASTAPI_API_KEY = "local-dev-change-me"
$env:WEBUI_REQUEST_TIMEOUT_SECONDS = "120"
$env:WEBUI_STREAMING_ENABLED = "true"
```

The Web UI also reads `.env` when launched through the VSCode configuration.
Use `.env.example` as the shared template.
Do not set `FASTAPI_API_KEY` in browser-visible content; it belongs only in the
server process environment.

### Run FastAPI Locally

Terminal 1:

```powershell
$env:LLM_MODEL_PATH = "models/Qwen2.5-7B-Instruct-Q4_K_M.gguf"
$env:AUTH_ENABLED = "true"
$env:FASTAPI_API_KEY = "local-dev-change-me"
python -m uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

Confirm the backend is reachable:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

### Run FastAPI Through Docker

Build the backend image:

```powershell
docker build -t local-language-agent-api .
```

Run it with the local model directory mounted:

```powershell
docker run --rm --gpus all -p 8000:8000 `
  --env-file .env.example `
  -e APP_HOST=0.0.0.0 `
  -e FASTAPI_API_KEY=local-dev-change-me `
  -e LLM_MODEL_PATH=/models/Qwen2.5-7B-Instruct-Q4_K_M.gguf `
  -v ${PWD}/models:/models `
  local-language-agent-api
```

The Web UI uses the same `FASTAPI_BASE_URL` for a local uvicorn backend and for a
Dockerized backend published to `127.0.0.1:8000`.
Use the same `FASTAPI_API_KEY` value for the backend and Web UI process.

### Run Chainlit Locally

Terminal 2:

```powershell
$env:FASTAPI_BASE_URL = "http://127.0.0.1:8000"
$env:FASTAPI_API_KEY = "local-dev-change-me"
$env:WEBUI_REQUEST_TIMEOUT_SECONDS = "120"
$env:WEBUI_STREAMING_ENABLED = "true"
$env:DEBUG = "false"
Push-Location webui
chainlit run app.py --host 127.0.0.1 --port 8001
Pop-Location
```

Open `http://127.0.0.1:8001`.

### Run Chainlit Through Docker

Build the Web UI image from the repository root:

```powershell
docker build -f Dockerfile.webui -t local-language-agent-webui .
```

Run it against a FastAPI backend reachable from the container:

```powershell
docker run --rm -p 8001:8001 `
  -e FASTAPI_BASE_URL=http://host.docker.internal:8000 `
  -e FASTAPI_API_KEY=local-dev-change-me `
  -e WEBUI_HOST=0.0.0.0 `
  -e WEBUI_PORT=8001 `
  -e DEBUG=false `
  -e LOG_LEVEL=INFO `
  local-language-agent-webui
```

When running Web UI and FastAPI containers on the same Docker network, set
`FASTAPI_BASE_URL=http://fastapi:8000`. The Web UI image does not include or
mount model files; it only calls the FastAPI backend over HTTP.

### Testing With Bruno and the Web UI

Use Bruno to confirm the backend independently:

```powershell
bru run bruno/local-language-agent-api --env Local
```

Then use the Web UI against the same backend URL:

1. Open `http://127.0.0.1:8001`.
2. Confirm the welcome message reports backend health as connected.
3. Select `Definition - full response` and ask for a definition.
4. Select `Translation - stream` or `Learning - stream` to test streaming.
5. Change the Web UI key to a wrong value and send a message; the UI should show
   a backend authentication failure without printing the key.
6. Unset the Web UI key and send a message; the UI should show a missing backend
   API key configuration message.
7. Stop the backend and send another message; the UI should show a clear backend
   unavailable message.

### Local Browser Tests

The local Playwright tests live in `tests/e2e/`. They start a fake backend and
the Chainlit Web UI locally, so they do not require Docker or a GGUF model.

Install test dependencies and browser binaries:

```powershell
pip install -r tests/e2e/requirements.txt
python -m playwright install chromium
```

Run the browser tests:

```powershell
pytest tests/e2e
```

Run them headed:

```powershell
pytest tests/e2e --headed
```

See `tests/e2e/README.md` for single-file and single-test commands.

### Implementation Summary

- `app.py` owns Chainlit callbacks, mode controls, starters, and UI messages.
- `client.py` owns async HTTP calls to `/health`, `/api/chat`, and
  `/api/chat/stream`. It sends `X-API-Key` only on protected chat requests,
  using the server-side `FASTAPI_API_KEY` environment variable.
- `renderer.py` formats structured backend payloads for Translation, Definition,
  and Learning responses.
- `.chainlit/config.toml` sets the Chainlit theme, sidebar settings, and custom
  CSS.
- `public/custom.css` contains the lightweight Web UI styling.

### Known Limitations

- The Web UI does not load the LLM directly.
- The Web UI requires the FastAPI backend to be running for model-backed chat.
- The FastAPI backend requires the local model to be mounted/configured.
- The Web UI and FastAPI backend are separate applications and separate
  processes.
- Web UI Dockerization is handled by the later `Docker Container: Web UI`
  feature.
- Browser-based CORS changes are not needed yet because Chainlit server-side
  code calls FastAPI directly. FastAPI supports explicit `CORS_ALLOWED_ORIGINS`
  for future browser-origin API access.
