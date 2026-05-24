# Troubleshooting

## Model Not Found

Symptoms:

- worker startup fails
- CLI startup fails
- errors mention `LLM_MODEL_PATH` or a missing GGUF file

Checks:

- confirm `LLM_MODEL_PATH` points at a real file
- for host-local runs, use a repo path such as `models/...`
- for Compose, use the in-container `/models/...` path
- confirm `./models` is mounted into the worker container

## GPU Unavailable

Symptoms:

- CLI or worker fails during GPU checks
- containerized worker cannot use `--gpus all`
- model initialization fails before requests complete

Checks:

- confirm the host has an NVIDIA GPU and working drivers
- confirm Docker GPU support is installed for container runs
- confirm the worker container, not FastAPI or Web UI, owns model execution

## Redis Unavailable

Symptoms:

- FastAPI chat requests fail before queueing
- queue status fails
- worker cannot start or cannot consume jobs

Checks:

- for host-local runs, confirm Redis is running on `127.0.0.1:6379`
- for Compose, confirm the `redis` service is healthy
- confirm `REDIS_URL` matches the current environment

## Queue Stuck

Symptoms:

- queue depth rises and does not fall
- jobs remain `queued`
- streaming never begins

Checks:

- confirm `app.worker.main` is running
- inspect `GET /api/queue/status`
- inspect `GET /api/llm/jobs/{job_id}`
- follow `docker compose logs -f llm-worker` or local worker logs

## Worker Not Running

Symptoms:

- FastAPI health works but chat does not
- jobs queue successfully but never complete

Checks:

- start the worker with `python -m app.worker.main`
- confirm it shares the same `REDIS_URL` and queue settings as FastAPI
- confirm `LLM_WORKER_CONCURRENCY` remains `1`

## Web UI Auth Failure

Symptoms:

- Web UI can load but chat requests fail with auth-related errors

Checks:

- confirm FastAPI and Web UI use the same `FASTAPI_API_KEY`
- confirm `AUTH_ENABLED=true` is expected for the current run
- confirm the browser is talking to Chainlit and Chainlit is calling FastAPI
  server-side

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
