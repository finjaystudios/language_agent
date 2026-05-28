## Playwright E2E

These tests exercise the Chainlit Web UI from a browser using Playwright for
Python.

The default workflow starts:

- a deterministic fake backend
- the local Chainlit app from `webui/`
- a temporary migrated SQLite database seeded with a deterministic login user

The default E2E path does not require Docker or the real GGUF model.

### Install

```powershell
pip install -r tests/e2e/requirements.txt
python -m playwright install chromium
```

Install additional browsers when needed:

```powershell
python -m playwright install firefox webkit
```

### Run

```powershell
pytest tests/e2e
pytest tests/e2e/test_chainlit_login.py
pytest tests/e2e --headed
pytest tests/e2e --browser chromium
pytest tests/e2e --browser firefox
pytest tests/e2e --browser webkit
pytest tests/e2e/test_chainlit_chat.py
pytest tests/e2e/test_chainlit_mobile.py
pytest tests/e2e/test_chainlit_chat.py::test_definition_starter_sets_mode_and_renders_response
```

Useful mobile-specific variants:

```powershell
pytest tests/e2e/test_chainlit_mobile.py --headed
pytest tests/e2e/test_chainlit_mobile.py -k "mobile and not safari" --browser chromium
pytest tests/e2e/test_chainlit_mobile.py -k safari --browser webkit
```

### Run Against an Existing Web UI

```powershell
$env:E2E_BASE_URL = "http://localhost"
pytest tests/e2e/test_chainlit_smoke.py
```

When `E2E_BASE_URL` is set, tests that depend on the deterministic fake backend
are skipped.

### Scope

- covers Chainlit browser behavior
- covers the username/password login flow with a seeded test user
- covers the self-service sign-up flow on the custom `/login` page, including
  client-side password confirmation and a follow-up login
- covers starter actions, mode controls, streaming/full-response UX, and error
  states
- includes mobile and tablet coverage
- does not replace Bruno for direct FastAPI API checks

Because the managed E2E database is SQLite, it runs with
`CHAINLIT_HISTORY_ENABLED=false`. Persisted Chainlit history still requires the
real PostgreSQL-backed app workflow.

Managed E2E login credentials:

- username: `e2e-user`
- password: `correct horse battery staple`

Managed E2E sign-up defaults:

- sign-up is enabled
- minimum password length is `12`
- newly signed-up users are active immediately
