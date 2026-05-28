# Review scope

Use this guide for the Chainlit Web UI.

The Web UI owns:

- user-facing chat interface
- Chainlit configuration
- branding/theme/mobile CSS
- username/password login UX
- chat history UX was enabled
- server-side FastAPI client
- Playwright UI behaviour


## Web UI boundaries

The Web UI must communicate with FastAPI over HTTP.

Do not import backend internals.

Do not call llama-server directly.

Do not expose the FastAPI API key to the browser.

Keep the FastAPI API key server-side only.

## Auth rules

If username/password login is enabled:

- require login before chat access
- use safe generic login errors
- do not log passwords
- do not expose password hashes
- do not store plaintext passwords
- keep session/config secrets out of the repo

## FastAPI client rules

The Web UI FastAPI client should own:

- base URL
- API key header
- request timeouts
- queue/status/result calls
- streaming handling
- safe error mapping

Avoid raw HTTP calls scattered through Chainlit handlers.

## UI review

Check:

- mobile responsiveness
- touch-friendly controls
- no horizontal overflow
- readable queue/status/error states
- streaming still works
- chat history/resume works where enabled
- branding/theme assets load through Caddy
- no secrets in rendered HTML, metadata, or client-side JS

## Tests

For Web UI changes, prefer Playwright tests or targeted client tests.

Tests should not require:

- real llama-server
- real model
- Cloudflare domain
- public internet

Use fake backend/test users where possible.
