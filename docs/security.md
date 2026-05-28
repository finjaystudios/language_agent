# Security

## Scope

This project currently documents service-to-service authentication between the
Chainlit Web UI and the FastAPI backend.

The current security model does not add:

- OAuth
- reverse-proxy TLS termination inside the app stack
- per-user authorization inside FastAPI

This change set enables Chainlit username/password login against the local
`users` table while preserving the separate service-to-service API key between
the Web UI server and FastAPI. It also enables Chainlit thread persistence in
the same internal PostgreSQL database.

## Boundary

Browser users interact with Chainlit only. Chainlit server-side Python then
calls FastAPI over HTTP.

The browser must not receive `FASTAPI_API_KEY`.

## Protected and Public Endpoints

FastAPI keeps these endpoints public:

- `GET /health`
- `GET /`

FastAPI protects model-backed and queue-inspection routes with `X-API-Key`:

- `POST /api/chat`
- `POST /api/chat/stream`
- `GET /api/queue/status`
- `GET /api/llm/jobs/{job_id}`
- `POST /api/llm/jobs/{job_id}/cancel`

## Authentication Mechanism

The current mechanism is a shared static service API key:

- header: `X-API-Key`
- FastAPI env var: `FASTAPI_API_KEY`
- Web UI env var: `FASTAPI_API_KEY`
- auth toggle: `AUTH_ENABLED`

This is service authentication, not user authentication.

## Stored User Credentials

Web UI users are stored in PostgreSQL with a password hash only:

- plaintext passwords must never be stored
- `PASSWORD_HASH_SCHEME` defaults to `argon2id`
- `bcrypt` remains available as a compatibility fallback
- inactive users can be retained in the database without being treated as valid
  sign-in candidates

Recommended handling:

- keep `DATABASE_HOST`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`,
  `POSTGRES_PASSWORD`, and
  `CHAINLIT_AUTH_SECRET` in local `.env` files or deployment secret stores
- keep `CHAINLIT_COOKIE_SAMESITE` at `lax` or `strict` for ordinary local and
  same-site deployments
- do not log password material or password hashes
- run `alembic upgrade head` before any code path that depends on the `users`
  table or Chainlit thread history tables
- use `scripts/create_user.py` or an equivalent admin path that hashes the
  password before storage; never insert plaintext passwords manually

## CORS

The browser does not call FastAPI directly in the normal Chainlit workflow, so
CORS is not required for ordinary Web UI chat.

If future browser-origin flows call FastAPI directly, configure explicit origins
through `CORS_ALLOWED_ORIGINS`, for example:

```powershell
$env:CORS_ALLOWED_ORIGINS = "http://localhost:8001,http://127.0.0.1:8001"
```

Wildcard origins with credentials are not used.

## Secret Handling Rules

- Do not commit real API keys.
- Do not commit real database credentials or session secrets.
- Keep `FASTAPI_API_KEY` in `.env`, shell environment, or deployment-specific
  secret management.
- Keep `DATABASE_HOST`, `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`,
  `POSTGRES_PASSWORD`, and
  `CHAINLIT_AUTH_SECRET` in `.env`, shell environment, or deployment-specific
  secret management.
- Keep PostgreSQL internal-only unless you have an explicit reason to publish it.
- Do not expose the API key in browser-visible content, logs, URLs, or public
  assets.
- Do not expose `DATABASE_PASSWORD`, `CHAINLIT_AUTH_SECRET`, or password hashes
  in Chainlit user metadata, messages, or browser-visible responses.
- Do not bake real secrets into Dockerfiles or images.

## Local and Docker Behavior

- Recommended examples keep `AUTH_ENABLED=true`.
- If `AUTH_ENABLED=true` and `FASTAPI_API_KEY` is missing or wrong, protected
  FastAPI routes should fail.
- If `AUTH_ENABLED=true` and `CHAINLIT_AUTH_SECRET` is missing, Chainlit login
  should not start successfully.
- The Web UI sends `X-API-Key` from server-side code only.
- Docker health checks stay on unauthenticated `GET /health`.

## Web UI Login Flow

- browser users authenticate to Chainlit with username and password
- Chainlit verifies credentials against the `users` table
- successful login creates a Chainlit session signed with `CHAINLIT_AUTH_SECRET`
- Chainlit persists thread history against its own internal tables keyed to the
  authenticated user's database-backed identifier
- the browser still does not receive `FASTAPI_API_KEY`
- FastAPI still authenticates only the Web UI server, not the browser user

## Chat History Boundaries

- Chainlit thread history is scoped to the authenticated Chainlit user.
- The Web UI stores safe profile fields such as `display_name`,
  `preferred_language`, and `ui_theme` in session/thread metadata for resume.
- Passwords, password hashes, `FASTAPI_API_KEY`, `DATABASE_PASSWORD`, and
  `CHAINLIT_AUTH_SECRET` must never appear in Chainlit user metadata or thread
  metadata.

## Current Limitations

- A shared API key authenticates the Web UI service, not individual users.
- FastAPI does not yet consume per-user identity from the Web UI.
- There are no user scopes, token expiry rules, or per-user audit trails.
- HTTP encryption is expected to be handled by deployment infrastructure such as
  Cloudflare Tunnel, not by this app-level auth mechanism.
