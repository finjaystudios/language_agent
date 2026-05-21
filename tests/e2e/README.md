## Local Chainlit Web UI E2E Tests

These tests use Playwright for Python to exercise the Chainlit Web UI from a
browser. They start a deterministic fake backend and the local Chainlit app as
subprocesses. They do not require Docker, GitHub Actions, or the real GGUF model.

### Install

From the repository root:

```powershell
pip install -r tests/e2e/requirements.txt
python -m playwright install chromium
```

### Run

Run all local browser tests:

```powershell
pytest tests/e2e
```

Run headed:

```powershell
pytest tests/e2e --headed
```

Run one file:

```powershell
pytest tests/e2e/test_chainlit_chat.py
```

Run one test:

```powershell
pytest tests/e2e/test_chainlit_chat.py::test_definition_starter_sets_mode_and_renders_response
```

Use Playwright debugging options locally as needed, for example:

```powershell
pytest tests/e2e --headed --slowmo 250
```

### Run Against an Existing Web UI

Set `E2E_BASE_URL` to point the smoke test at a Web UI that is already running.
This is useful for validating the Dockerized Web UI without making Docker the
default test path:

```powershell
$env:E2E_BASE_URL = "http://127.0.0.1:8001"
pytest tests/e2e/test_chainlit_smoke.py
```

When `E2E_BASE_URL` is set, tests that require the deterministic fake backend
are skipped because they assert exact fake responses and inspect fake backend
request records.

### Docker Compose Web UI Check

The Compose stack runs the real FastAPI backend and real model, so treat this as
a local integration test. It requires the mounted GGUF model and GPU runtime
used by the backend container.

```powershell
docker compose up --build
```

Wait until both services are healthy, then run the Playwright smoke test against
the published Web UI:

```powershell
$env:E2E_BASE_URL = "http://127.0.0.1:8001"
pytest tests/e2e/test_chainlit_smoke.py
```

Useful logs while debugging:

```powershell
docker compose logs -f webui
docker compose logs -f fastapi
```

Stop the stack when finished:

```powershell
docker compose down
```

### What Starts

- Fake backend: exposes `GET /health`, `POST /api/chat`, and
  `POST /api/chat/stream`.
- Chainlit Web UI: started from `webui/` with `FASTAPI_BASE_URL` pointed at the
  fake backend.

The tests assert landing-page status, starters, chat input, full responses,
streamed responses, selected mode behavior, and readable offline errors.

The fake-backend tests confirm that the Web UI sends the backend API key from
server-side environment variables, that wrong keys produce a readable UI error,
and that API key values are not rendered in the browser.
