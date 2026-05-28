# Reverse Proxy

Caddy is the selected reverse proxy for local and LAN routing.

## Purpose

- Route `/` to the Chainlit Web UI
- Route `/api/*` to FastAPI
- Preserve service separation between Web UI and backend
- Provide one host-local entry point for browser users

## Current Services

| Service | Internal URL | Purpose |
| --- | --- | --- |
| `fastapi` | `http://fastapi:8000` | FastAPI backend |
| `webui` | `http://webui:8001` | Chainlit Web UI |

The Web UI still calls FastAPI directly over the internal Docker network using
`FASTAPI_BASE_URL=http://fastapi:8000`.

## Public Routes

| Public route | Upstream | Result |
| --- | --- | --- |
| `http://localhost/` | `http://webui:8001` | Chainlit Web UI |
| `http://localhost/api/health` | `http://fastapi:8000/health` | FastAPI health |
| `http://localhost/api/*` | `http://fastapi:8000` | FastAPI API |
| `http://localhost/api/stream` | `http://fastapi:8000/api/chat/stream` | Friendly streaming alias |

The same routes can be used with the host LAN IP address. If `agent.local`
resolves to the Docker host on the local network, those URLs also work there.

## Current Caddyfile Shape

The repository `Caddyfile` uses this routing pattern:

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
		reverse_proxy fastapi:8000 {
			header_up Host {host}
		}
	}

	handle /api/stream {
		rewrite * /api/chat/stream
		reverse_proxy fastapi:8000 {
			header_up Host {host}
		}
	}

	handle /api/* {
		reverse_proxy fastapi:8000 {
			header_up Host {host}
		}
	}

	handle {
		reverse_proxy webui:8001 {
			header_up Host {host}
		}
	}
}
```

## Traffic Flow

Browser to Web UI:

```text
browser -> host port 80 -> Caddy -> webui:8001
```

Browser or API client to FastAPI:

```text
client -> host port 80 -> Caddy /api/* -> fastapi:8000
```

Web UI server-side backend call:

```text
webui container -> Docker network -> fastapi:8000
```

## Logging and Headers

Caddy logs to stdout. Request headers are removed from logs so `X-API-Key` is
not exposed in access logging.

Use:

```powershell
docker compose logs -f caddy
```

## Cloudflare Tunnel Boundary

Cloudflare Tunnel is intentionally outside `compose.yml`. The documented future
shape is:

```text
Cloudflare Tunnel -> host Caddy port -> Caddy -> webui or fastapi
```

This repo does not currently define Cloudflare services, public domain routing,
or tunnel configuration inside Compose.

When exposing the stack over a LAN hostname or public domain:

- browser users must pass the Web UI username/password login before chat access
- FastAPI remains separately protected by `FASTAPI_API_KEY`
- `llama-server` should remain internal-only
- PostgreSQL should remain internal-only and must not be published through
  Caddy or Cloudflare

## Related Docs

- [`docker-compose.md`](docker-compose.md)
- [`security.md`](security.md)
- [`troubleshooting.md`](troubleshooting.md)
