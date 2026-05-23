## Chainlit Web UI

The Web UI lives in `webui/` as a separate Chainlit application. It communicates
with the FastAPI backend only over HTTP and is deployed separately from the
backend in its own Docker image.

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

The Web UI Dockerfile is `Dockerfile.webui`. The backend Dockerfile remains the
root `Dockerfile`.

### Run FastAPI and Chainlit With Compose

From the repository root, copy the Compose env template and set a local shared
API key and mounted model filename:

```powershell
Copy-Item .env.compose.example .env
```

Build and run both separate containers:

```powershell
docker compose up --build
```

Open `http://127.0.0.1:8001`. The Web UI service uses
`FASTAPI_BASE_URL=http://fastapi:8000` inside the Compose network. Only the
FastAPI service mounts `./models:/models:ro`; the Web UI service never mounts or
loads model files.

Keep `LLM_MODEL_PATH` in `.env` pointed at the container path under `/models`,
not a relative host path such as `models/...`.

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

To smoke-test a Web UI that is already running, including the Docker Compose Web
UI, set `E2E_BASE_URL` and run the smoke test:

```powershell
$env:E2E_BASE_URL = "http://127.0.0.1:8001"
pytest tests/e2e/test_chainlit_smoke.py
```

The full fake-backend browser suite remains the default because it is
deterministic and does not require the real LLM. Compose-based browser checks
use the real backend and mounted model, so treat them as local integration
tests.

### Branding Assets

LanguageAgent branding is configured through `.chainlit/config.toml` and static
files in `public/`.

- Replace `public/logo_dark.png` and `public/logo_light.png` to update the
  header logo. Keep transparent PNGs sized around `640x160` so Chainlit can
  scale them cleanly in the header.
- Replace `public/favicon` to update the browser tab icon. The file is a PNG
  without an extension because Chainlit looks up that exact public path.
- Keep editable source designs outside the Docker image path, such as
  `../design/languageagent-logo.svg` and `../design/languageagent-icon.svg`.
  The Web UI Dockerfile only copies `webui/public`, so design sources are not
  included in the runtime image.
- Update `.chainlit/config.toml` for future brand text changes: `name`,
  `description`, `custom_meta_url`, `custom_meta_image_url`, and
  `[[UI.header_links]]`. Keep `logo_file_url` empty when both dark and light
  logo variants are present so Chainlit can switch between them by theme.
- Clear the browser cache or hard refresh after replacing logos or favicons;
  browsers often cache these assets aggressively.

### Implementation Summary

- `app.py` owns Chainlit callbacks, mode controls, starters, and UI messages.
- `client.py` owns async HTTP calls to `/health`, `/api/chat`, and
  `/api/chat/stream`. It sends `X-API-Key` only on protected chat requests,
  using the server-side `FASTAPI_API_KEY` environment variable.
- `renderer.py` formats structured backend payloads for Translation, Definition,
  and Learning responses.
- `.chainlit/config.toml` sets the LanguageAgent metadata, logo URL, theme,
  sidebar settings, custom CSS, and custom JS.
- `public/theme.json` contains the Chainlit theme variables, `public/style.css`
  contains scoped UI polish, and `public/logo_dark.png`,
  `public/logo_light.png`, and `public/favicon` contain the runtime brand
  assets.

### Known Limitations

- The Web UI does not load the LLM directly.
- The Web UI requires the FastAPI backend to be running for model-backed chat.
- The Web UI requires `FASTAPI_API_KEY` to match the FastAPI backend key.
- The FastAPI backend requires the local model to be mounted/configured.
- The FastAPI Docker setup requires GPU access for the current model runtime.
- The Web UI and FastAPI backend are separate applications and separate
  processes.
- Reverse proxy, HTTPS/TLS termination, domain deployment, and user login are
  separate future features.
- Browser-based CORS changes are not needed yet because Chainlit server-side
  code calls FastAPI directly. FastAPI supports explicit `CORS_ALLOWED_ORIGINS`
  for future browser-origin API access.
