# Testing

This project currently uses pytest, Playwright, Bruno, Docker Compose checks,
and `pip-audit`.

## Backend and Unit Tests

Run the repository pytest suite:

```powershell
pytest
```

Examples of targeted test runs already used in the repo:

```powershell
pytest tests/test_api_routes.py
pytest tests/test_llm_queue.py
pytest tests/test_webui_app.py
```

## Playwright E2E

Install the E2E dependencies:

```powershell
pip install -r tests/e2e/requirements.txt
python -m playwright install chromium
```

Run the E2E suite:

```powershell
pytest tests/e2e
```

Useful variants:

```powershell
pytest tests/e2e --headed
pytest tests/e2e --browser chromium
pytest tests/e2e --browser firefox
pytest tests/e2e --browser webkit
pytest tests/e2e/test_chainlit_mobile.py
pytest tests/e2e/test_chainlit_chat.py
pytest tests/e2e/test_chainlit_chat.py::test_definition_starter_sets_mode_and_renders_response
```

Run against an already running Web UI:

```powershell
$env:E2E_BASE_URL = "http://localhost"
pytest tests/e2e/test_chainlit_smoke.py
```

See [`../tests/e2e/README.md`](../tests/e2e/README.md) for Playwright-only
usage details.

## Bruno

Run the Bruno collection:

```powershell
bru run bruno/local-language-agent-api --env Local
bru run bruno/local-language-agent-api --env Proxy
```

See [`../bruno/README.md`](../bruno/README.md) for Bruno-only usage details.

## Docker and Compose Validation

Build images:

```powershell
docker build -t local-language-agent-api .
docker build -f Dockerfile.webui -t local-language-agent-webui .
```

Validate and run Compose:

```powershell
docker compose config
docker compose build
docker compose up --build
```

Useful service logs:

```powershell
docker compose logs -f caddy
docker compose logs -f webui
docker compose logs -f fastapi
docker compose logs -f llm-worker
docker compose logs -f redis
```

## Dependency Audit

The repository documentation already references `pip-audit`:

```powershell
pip-audit
```
