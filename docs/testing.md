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
pytest tests/e2e/test_chainlit_login.py
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

The managed E2E path now starts Chainlit with:

- password auth enabled
- a seeded deterministic test user
- a temporary SQLite database migrated with Alembic
- the fake backend instead of the real FastAPI + worker + llama-server path

For that managed no-Docker E2E path, `CHAINLIT_HISTORY_ENABLED=false` is used
because the official Chainlit data layer requires PostgreSQL/`asyncpg` rather
than SQLite. Postgres-backed history and resume behavior remain part of the real
app workflow and unit/integration coverage.

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

## Manual Integration Checklist

1. Run `alembic upgrade head`.
2. Create a user with `python scripts/create_user.py --username ...`.
3. Start the stack with `docker compose up --build`.
4. Open `http://localhost/` through Caddy.
5. Confirm the login form appears before chat access.
6. Confirm invalid credentials are rejected.
7. Confirm valid credentials open the chat UI.
8. Confirm chat requests still work and FastAPI API key protection remains in place.
9. Refresh or reopen the Web UI and confirm chat history resumes if persistence is enabled.
10. Confirm auth logs do not contain plaintext passwords, hashes, or secrets.

## Dependency Audit

The repository documentation already references `pip-audit`:

```powershell
pip-audit
```
