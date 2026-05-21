# Reverse Proxy Architecture

## Decision

Caddy is the selected reverse proxy for this project.

The project is a good fit for Caddy because:

- Caddy uses a small, readable `Caddyfile`.
- It fits naturally as a third Docker Compose service.
- Reverse proxy support is built in and does not require extra modules.
- The configuration is simpler than nginx for this local path-based routing
  setup.

## Current Services

FastAPI and the Chainlit Web UI remain separate applications and separate
containers. The reverse proxy does not merge them.

| Compose service | Container port | Current internal URL | Purpose |
| --- | ---: | --- | --- |
| `fastapi` | `8000` | `http://fastapi:8000` | FastAPI backend API |
| `webui` | `8001` | `http://webui:8001` | Chainlit browser UI |

The Web UI is already configured with `FASTAPI_BASE_URL=http://fastapi:8000`,
so server-side Web UI calls to FastAPI continue to use the internal Docker
network directly. The shared API key authentication between Web UI and FastAPI
must remain in place.

## FastAPI Routes

The FastAPI application currently exposes:

| Method | Path | Auth | Notes |
| --- | --- | --- | --- |
| `GET` | `/health` | Public | Container health check and local service probe. |
| `GET` | `/` | Public | Basic service metadata. |
| `POST` | `/api/chat` | `X-API-Key` | Full language-agent response. |
| `POST` | `/api/chat/stream` | `X-API-Key` | Server-Sent Events streaming response. |

The chat router already uses the `/api` prefix. Caddy should preserve the
incoming `/api/*` path when proxying to FastAPI. It should not strip `/api` and
then re-add it, because that would risk double-prefixing or routing to the
wrong backend path.

## Intended Local Routing

Path-based routing will be used.

| Public local route | Caddy upstream | Result |
| --- | --- | --- |
| `http://localhost/` | `http://webui:8001` | Chainlit Web UI |
| `http://<host-lan-ip>/` | `http://webui:8001` | Chainlit Web UI from another LAN device |
| `http://localhost/api/health` | `http://fastapi:8000/health` | Proxied FastAPI health check |
| `http://localhost/api/*` | `http://fastapi:8000` | FastAPI API endpoint |
| `http://<host-lan-ip>/api/health` | `http://fastapi:8000/health` | Proxied FastAPI health check from another LAN device |
| `http://<host-lan-ip>/api/*` | `http://fastapi:8000` | FastAPI API endpoint from another LAN device |

The intended Caddy routing shape is:

```caddyfile
{
    log {
        output stdout
        format filter {
            wrap console
            fields {
                request>headers delete
            }
        }
    }
}

:80 {
    encode zstd gzip

    log {
        output stdout
        format filter {
            wrap console
            fields {
                request>headers delete
            }
        }
    }

    handle /api/health {
        rewrite * /health
        reverse_proxy fastapi:8000
    }

    handle /api/* {
        reverse_proxy fastapi:8000
    }

    handle {
        reverse_proxy webui:8001
    }
}
```

This preserves FastAPI paths such as `/api/chat` and `/api/chat/stream`.
`/api/health` is the only proxy-specific alias; it rewrites to FastAPI
`/health` so local and LAN clients can validate the backend through Caddy while
the Web UI continues to own `/`.
Caddy's `reverse_proxy` transport supports streaming and WebSocket-style
upgrades by default. It also forwards standard proxy headers such as
`X-Forwarded-For` and `X-Forwarded-Proto`; the project Caddyfile explicitly
preserves the incoming `Host` header for both upstreams.

## Logging

Caddy access logs are written to stdout with console formatting, so they are
visible through Docker Compose:

```powershell
docker compose logs -f caddy
```

Proxy logs record request metadata such as method, path, status, and latency.
Request headers are removed from both access logs and Caddy error logs, so the
`X-API-Key` header used by protected FastAPI endpoints is not exposed in proxy
logs. Do not pass API keys in query strings, because URLs can appear in ordinary
access logs.

## Health Checks

Compose health checks are configured for all three services:

| Service | Health check | Purpose |
| --- | --- | --- |
| `fastapi` | `GET http://127.0.0.1:8000/health` inside the container | Confirms the backend process is reachable without initializing the LLM. |
| `webui` | `GET http://127.0.0.1:8001/` inside the container | Confirms the Chainlit server is serving the UI. |
| `caddy` | `GET http://127.0.0.1/` inside the container | Confirms the proxy can serve the local root route through the Web UI upstream. |

Caddy depends on both upstream services with `condition: service_healthy`, so
the proxy starts only after FastAPI and Web UI have passed their health checks.

## Traffic Flow

LAN browser to Web UI:

```text
Browser on local network -> host port exposed by Caddy -> Caddy -> webui:8001
```

LAN client to FastAPI API:

```text
Browser or API client on local network -> host port exposed by Caddy -> Caddy /api/* -> fastapi:8000
```

Web UI server-side backend calls:

```text
webui container -> Docker Compose network -> fastapi:8000
```

Future public access:

```text
Cloudflare Tunnel outside Docker Compose -> host port exposed by Caddy -> Caddy -> webui or fastapi
```

Cloudflare Tunnel is intentionally outside this Compose stack. This feature
does not add Cloudflare services, tunnel configuration, domain routing, or
public deployment settings to `compose.yml`.

## TLS Boundary

The local Docker Compose deployment can run plain HTTP for now. Caddy local TLS
is optional and is not required for this feature unless a later local
development requirement explicitly adds it.

Public HTTPS will be handled by Cloudflare Tunnel when domain routing is
configured outside Docker Compose. In that future shape, Cloudflare terminates
public HTTPS and forwards traffic through the tunnel to the host port exposed by
Caddy.

## Compose Direction

Caddy is implemented as a third service in Docker Compose. Its configuration is
stored at `Caddyfile` and mounted read-only into the container at
`/etc/caddy/Caddyfile`. The existing internal service addresses remain valid:

- FastAPI inside Compose: `http://fastapi:8000`
- Web UI inside Compose: `http://webui:8001`

Caddy exposes host port `80` for local HTTP routing, so LAN devices can use
`http://<host-lan-ip>/`. Cloudflare Tunnel will later target that same
host-side Caddy port. FastAPI and Web UI may keep their existing direct host
port mappings for development; later deployments can expose only Caddy if
direct host access is no longer needed.

## Local Workflow

Start the full local stack with Caddy:

```powershell
docker compose up --build
```

Use these local URLs:

| URL | Expected result |
| --- | --- |
| `http://localhost/` | Chainlit Web UI |
| `http://localhost/api/health` | FastAPI health response through Caddy |
| `http://localhost/api/chat` | Protected FastAPI chat endpoint through Caddy |
| `http://localhost/api/chat/stream` | Protected FastAPI streaming endpoint through Caddy |

Use the host machine's LAN IP from another home-network device:

| URL | Expected result |
| --- | --- |
| `http://<host-lan-ip>/` | Chainlit Web UI |
| `http://<host-lan-ip>/api/health` | FastAPI health response through Caddy |
| `http://<host-lan-ip>/api/chat` | Protected FastAPI chat endpoint through Caddy |

Inspect proxy logs:

```powershell
docker compose logs -f caddy
```

Stop the stack:

```powershell
docker compose down
```

Bruno can exercise the proxied API by using the `Proxy` environment with
`baseUrl: http://localhost`. API requests should keep `/api/...` paths, and
protected endpoints still require the `X-API-Key` header. Use `System/Proxy
Health` for the proxied health check.

Playwright can smoke-test the Web UI through Caddy by setting:

```powershell
$env:E2E_BASE_URL = "http://localhost"
pytest tests/e2e/test_chainlit_smoke.py
```

This is an integration workflow against the running Compose stack. The default
`pytest tests/e2e` workflow still uses the deterministic fake backend.

## Load Balancing

No load balancing is needed for the current local deployment. There is one
FastAPI container and one Web UI container on a single host, so adding multiple
upstreams would not improve availability or throughput for this feature.

Caddy can support load balancing later by listing multiple upstreams in a
`reverse_proxy` block if the services are scaled or split across hosts, for
example:

```caddyfile
handle /api/* {
    reverse_proxy fastapi-1:8000 fastapi-2:8000
}
```

This feature intentionally does not add replicas or extra upstream containers.

## Limitations

- No Cloudflare Tunnel service is added to Docker Compose.
- No domain deployment or Cloudflare routing is implemented here.
- No user login is added.
- Existing FastAPI API key authentication is retained.
- No secrets should be written into the Caddyfile, Compose file, or docs.
- No load balancing is needed for the current single FastAPI container and
  single Web UI container.
- `/api/*` is the public FastAPI API route through Caddy. Other backend paths,
  such as `/health`, remain backend service endpoints unless a future task
  deliberately exposes them through the proxy.

## Validation

Before adding a Caddy service, `docker compose config` was run against the
current Compose file and completed successfully. `docker compose ps` showed no
currently running Compose containers, so no running stack was changed while
preparing this architecture plan.
