## Chainlit Web UI

The Web UI lives in `webui/` as a separate Chainlit application. It communicates
with FastAPI over HTTP and is deployable separately from the backend.

## Install

```powershell
pip install -r webui/requirements.txt
```

## Environment

Example local values:

```powershell
$env:FASTAPI_BASE_URL = "http://127.0.0.1:8000"
$env:AUTH_ENABLED = "true"
$env:FASTAPI_API_KEY = "local-dev-change-me"
$env:WEBUI_DATABASE_URL = "postgresql+psycopg://language_agent:change-me@127.0.0.1:5432/language_agent"
$env:CHAINLIT_AUTH_SECRET = "replace-with-random-secret"
$env:CHAINLIT_COOKIE_SAMESITE = "lax"
$env:WEBUI_REQUEST_TIMEOUT_SECONDS = "120"
$env:WEBUI_STREAMING_ENABLED = "true"
```

Keep `FASTAPI_API_KEY`, `WEBUI_DATABASE_URL`, and `CHAINLIT_AUTH_SECRET` in the
server-side Web UI environment only.

## Run Locally

Run FastAPI separately, then start Chainlit:

```powershell
$env:FASTAPI_BASE_URL = "http://127.0.0.1:8000"
$env:AUTH_ENABLED = "true"
$env:FASTAPI_API_KEY = "local-dev-change-me"
$env:WEBUI_DATABASE_URL = "postgresql+psycopg://language_agent:change-me@127.0.0.1:5432/language_agent"
$env:CHAINLIT_AUTH_SECRET = "replace-with-random-secret"
$env:CHAINLIT_COOKIE_SAMESITE = "lax"
$env:WEBUI_REQUEST_TIMEOUT_SECONDS = "120"
$env:WEBUI_STREAMING_ENABLED = "true"
$env:DEBUG = "false"
Push-Location webui
chainlit run chainlit_app.py --host 127.0.0.1 --port 8001
Pop-Location
```

Open `http://127.0.0.1:8001`.

## Run in Docker

Build:

```powershell
docker build -f Dockerfile.webui -t local-language-agent-webui .
```

Run:

```powershell
docker run --rm -p 8001:8001 `
  -e FASTAPI_BASE_URL=http://host.docker.internal:8000 `
  -e AUTH_ENABLED=true `
  -e FASTAPI_API_KEY=local-dev-change-me `
  -e WEBUI_DATABASE_URL=postgresql+psycopg://language_agent:change-me@host.docker.internal:5432/language_agent `
  -e CHAINLIT_AUTH_SECRET=replace-with-random-secret `
  -e CHAINLIT_COOKIE_SAMESITE=lax `
  -e WEBUI_HOST=0.0.0.0 `
  -e WEBUI_PORT=8001 `
  -e DEBUG=false `
  -e LOG_LEVEL=INFO `
  local-language-agent-webui
```

When the Web UI runs beside FastAPI on the same Docker network, set
`FASTAPI_BASE_URL=http://fastapi:8000`.

## Compose

```powershell
Copy-Item .env.compose.example .env
docker compose up --build
```

Preferred Web UI URL through Caddy:

- `http://localhost/`

Direct host port:

- `http://127.0.0.1:8001`

## Scope and Behavior

- the Web UI requires username/password login when `AUTH_ENABLED=true`
- Chainlit validates credentials against the local `users` table
- `WEBUI_DATABASE_URL` is kept separate from Chainlit's optional own data-layer
  `DATABASE_URL` so login can work without enabling chat-history persistence yet
- the Web UI does not load the GGUF model
- the Web UI sends `X-API-Key` only from server-side code
- Translation, Definition, and Learning can stream when
  `WEBUI_STREAMING_ENABLED=true`
- the browser never receives `FASTAPI_API_KEY`
- the browser never receives database credentials or password hashes

## Assets and Customization

Runtime assets live under `webui/public/` and Chainlit configuration lives under
`webui/.chainlit/` plus `chainlit.md`.

Relevant files:

- `public/theme.json`
- `public/style.css`
- `public/landing-status.js`
- `public/logo_dark.png`
- `public/logo_light.png`
- `public/favicon`

## Testing

Run the Playwright suite from the repository root:

```powershell
pytest tests/e2e
```

See [`../tests/e2e/README.md`](../tests/e2e/README.md) for Playwright-only
usage and [`../docs/mobile-ui.md`](../docs/mobile-ui.md) for responsive
validation notes.
