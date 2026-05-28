# Troubleshooting

## Import Errors After Refactor

Symptoms:

- startup fails with `ModuleNotFoundError`
- local scripts still refer to removed compatibility paths from older branches
- worker or API startup fails after switching branches

Checks:

- prefer the current entry points:
  - `python -m uvicorn app.interfaces.api.main:app --reload`
  - `python -m app.worker.main`
- confirm your shell is running from the repository root
- update local scripts or IDE launch profiles to the canonical paths under
  `app/interfaces`, `app/infrastructure`, `app/application`, or `app/worker`

## Worker Cannot Import App Modules

Symptoms:

- `python -m app.worker.main` fails before connecting to Redis
- errors mention missing `app.*` modules from the worker process

Checks:

- start the worker from the repository root, not from inside `app/worker`
- confirm the active Python environment has the project dependencies installed
- avoid invoking worker internals as loose files; use `python -m app.worker.main`
- if you use Docker, confirm the image copied the full `app/` package

## Model Loading Location

Symptoms:

- FastAPI or the worker appears to try loading the GGUF model directly
- multiple processes consume GPU memory
- the wrong service owns the model path or GPU settings

Checks:

- in the default Compose path, only `llama-server` should load the GGUF model
- FastAPI should enqueue through Redis + RQ, not import model runtime code
- the worker should call `llama-server` over HTTP, not load GGUF files itself
- the Web UI should call FastAPI over HTTP only
- for Compose, confirm only `llama-server` mounts `./models`

## Model Not Found

Symptoms:

- `llama-server` fails to start
- health checks fail before requests complete
- errors mention a missing GGUF file or bad model path

Checks:

- confirm `LLAMA_SERVER_MODEL_PATH` points at a real file inside the container
- for host-local runs, pass a real path to the `llama-server --model ...` command
- for Compose, use the in-container `/models/...` path for `llama-server`
- confirm `./models` is mounted into the `llama-server` container

## GPU Unavailable

Symptoms:

- `llama-server` fails to start or crashes on first request
- model initialization fails before requests complete

Checks:

- confirm the host has an NVIDIA GPU and working drivers
- confirm Docker GPU support is installed for container runs
- confirm the `llama-server` container, not FastAPI or Web UI, owns model execution
- for GTX 1080 / Pascal, confirm the `llama-server` binary or image was built
  with `sm_61` support
- reduce `LLAMA_SERVER_CONTEXT_SIZE`, `LLAMA_SERVER_N_GPU_LAYERS`,
  `LLAMA_SERVER_BATCH_SIZE`, and `LLAMA_SERVER_UBATCH_SIZE` if the server fails
  during model load
- if you see `CUDA error: no kernel image is available for execution on the device`,
  treat that as a GPU-architecture build mismatch and rebuild or replace the
  `llama-server` binary/image with `sm_61` support

## Redis Unavailable

Symptoms:

- FastAPI chat requests fail before queueing
- queue status fails
- worker cannot start or cannot consume jobs

Checks:

- for host-local runs, confirm Redis is running on `127.0.0.1:6379`
- for Compose, confirm the `redis` service is healthy
- confirm `REDIS_URL` matches the current environment

## PostgreSQL Unavailable

Symptoms:

- `alembic upgrade head` fails before applying migrations
- `scripts/create_user.py` fails to connect
- Web UI or future auth work fails when opening database-backed features

Checks:

- for Compose, confirm the `postgres` service is healthy
- confirm `DATABASE_URL` points at `postgres:5432` inside Compose and
  `127.0.0.1:5432` for host-local backend and Chainlit history runs
- confirm `WEBUI_DATABASE_URL` points at the same database for Web UI login and
  persistence unless you intentionally override it
- confirm `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` match the
  credentials embedded in `DATABASE_URL`
- run `docker compose logs -f postgres`
- validate readiness with `docker compose exec postgres pg_isready -U language_agent -d language_agent`

## Migration Failure

Symptoms:

- `alembic upgrade head` exits with import or connection errors
- the `users` table or Chainlit history tables are missing after startup

Checks:

- confirm the active Python environment has `alembic`, `SQLAlchemy`, and
  `asyncpg` installed
- confirm you are running commands from the repository root
- for Compose, run either `docker compose run --rm fastapi alembic upgrade head`
  or `docker compose --profile tools run --rm db-migrate`
- do not assume migrations run automatically; this stack applies them only when
  you invoke the command
- if login works but chat history does not appear, confirm the Chainlit tables
  were created by the current Alembic revision

## Queue Stuck

Symptoms:

- queue depth rises and does not fall
- jobs remain `queued`
- streaming never begins

Checks:

- confirm `app.worker.main` is running
- confirm `llama-server` is healthy
- inspect `GET /api/queue/status`
- inspect `GET /api/llm/jobs/{job_id}`
- follow `docker compose logs -f llm-worker` and `docker compose logs -f llama-server`

## Worker Not Running

Symptoms:

- FastAPI health works but chat does not
- jobs queue successfully but never complete

Checks:

- start the worker with `python -m app.worker.main`
- confirm it shares the same `REDIS_URL` and queue settings as FastAPI
- confirm `LLM_WORKER_CONCURRENCY` remains `1`
- if `LLM_BACKEND=llama_server`, confirm `LLAMA_SERVER_URL` resolves and the
  `llama-server` health endpoint responds

## Llama-Server Unavailable

Symptoms:

- worker logs say `The external llama-server is unavailable.`
- streaming jobs fail quickly after dequeuing
- `docker compose ps` shows the worker as unhealthy while Redis is healthy

Checks:

- confirm `docker compose logs -f llama-server`
- confirm `curl http://127.0.0.1:8080/health`
- confirm `LLAMA_SERVER_URL=http://llama-server:8080` inside the worker
- confirm the selected image is compatible with the host GPU architecture

## Web UI Auth Failure

Symptoms:

- login is rejected
- Web UI can load but chat requests fail with auth-related errors
- previous threads do not appear after login or refresh

Checks:

- confirm the user exists in the `users` table
- confirm the stored user is active
- confirm the login password matches the stored hash
- confirm `AUTH_ENABLED=true` and `CHAINLIT_AUTH_SECRET` are set for the Web UI
- confirm `WEBUI_DATABASE_URL` is reachable from the Web UI process or container
- confirm `DATABASE_URL` is present for the Web UI process when chat history is
  expected
- confirm FastAPI and Web UI use the same `FASTAPI_API_KEY`
- confirm `AUTH_ENABLED=true` is expected for the current run
- confirm the browser is talking to Chainlit and Chainlit is calling FastAPI
  server-side
- confirm `alembic upgrade head` ran after pulling changes that added Chainlit
  persistence tables

If login unexpectedly succeeds without a prompt, confirm that the Web UI did not
start with `AUTH_ENABLED=false`.

## Caddy Routing Failure

Symptoms:

- `http://localhost/` does not reach the Web UI
- `http://localhost/api/health` does not reach FastAPI

Checks:

- confirm `docker compose up --build` started `caddy`, `webui`, and `fastapi`
- follow `docker compose logs -f caddy`
- confirm the upstream services are healthy before Caddy starts routing

## Cloudflare Tunnel Origin Failure

Symptoms:

- public domain requests fail while the local stack works

Checks:

- confirm the local origin behind the tunnel is the host Caddy port
- confirm the local stack works at `http://localhost/` first
- remember Cloudflare Tunnel is outside `compose.yml`; inspect tunnel config
  separately from local app services
