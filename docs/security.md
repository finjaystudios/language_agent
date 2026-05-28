# Security

## Scope

This project currently documents service-to-service authentication between the
Chainlit Web UI and the FastAPI backend.

The current security model does not add:

- browser user login
- OAuth
- reverse-proxy TLS termination inside the app stack
- per-user authorization

This change set adds the persistence and password-storage foundation for future
username/password login, but it does not enable Web UI sign-in yet.

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

Planned Web UI users are stored in PostgreSQL with a password hash only:

- plaintext passwords must never be stored
- `PASSWORD_HASH_SCHEME` defaults to `argon2id`
- `bcrypt` remains available as a compatibility fallback
- inactive users can be retained in the database without being treated as valid
  sign-in candidates

Recommended handling:

- keep `DATABASE_URL`, `POSTGRES_PASSWORD`, and `CHAINLIT_AUTH_SECRET` in local
  `.env` files or deployment secret stores
- do not log password material or password hashes
- run `alembic upgrade head` before any code path that depends on the `users`
  table

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
- Keep `DATABASE_URL`, `POSTGRES_PASSWORD`, and `CHAINLIT_AUTH_SECRET` in `.env`,
  shell environment, or deployment-specific secret management.
- Do not expose the API key in browser-visible content, logs, URLs, or public
  assets.
- Do not bake real secrets into Dockerfiles or images.

## Local and Docker Behavior

- Recommended examples keep `AUTH_ENABLED=true`.
- If `AUTH_ENABLED=true` and `FASTAPI_API_KEY` is missing or wrong, protected
  FastAPI routes should fail.
- The Web UI sends `X-API-Key` from server-side code only.
- Docker health checks stay on unauthenticated `GET /health`.

## Current Limitations

- A shared API key authenticates the Web UI service, not individual users.
- Username/password login is not wired into Chainlit yet.
- There are no user scopes, token expiry rules, or per-user audit trails.
- HTTP encryption is expected to be handled by deployment infrastructure such as
  Cloudflare Tunnel, not by this app-level auth mechanism.
