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

### What Starts

- Fake backend: exposes `GET /health`, `POST /api/chat`, and
  `POST /api/chat/stream`.
- Chainlit Web UI: started from `webui/` with `FASTAPI_BASE_URL` pointed at the
  fake backend.

The tests assert landing-page status, starters, chat input, full responses,
streamed responses, selected mode behavior, and readable offline errors.
