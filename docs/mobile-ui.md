# Mobile UI

This document captures the current responsive behavior and validation approach
for the Chainlit Web UI.

## Current Direction

- Keep Chainlit as the UI shell
- Keep the existing custom JavaScript for landing-page status and accessibility
  behavior
- Use `public/style.css` as the active CSS entry point
- Preserve existing branding asset paths and metadata paths

## Implemented Responsive Work

- Responsive CSS breakpoints for phone, tablet, and desktop widths
- Reduced landing-page density on smaller screens
- Larger composer and tap targets
- Starter actions that wrap on phones and tablets
- Constrained chat width on tablet sizes
- No page-level horizontal scrolling
- Scrollable containers for code blocks and tables

## Current Coverage

Playwright coverage includes:

- `tests/e2e/test_chainlit_smoke.py`
- `tests/e2e/test_chainlit_mobile.py`

Device presets currently include:

- `Pixel 7`
- `iPhone 13`
- `iPad Mini`

## Manual Checklist

- Small phone: confirm no horizontal scrolling
- Small phone: confirm the composer and send button stay usable
- Phone and tablet: confirm starter actions wrap cleanly
- Tablet: confirm the chat column remains readable and not edge-to-edge
- Any size: confirm long content scrolls inside its own message container
- Desktop: confirm no visual regression in the landing page or active chat

## Useful Commands

Run the full E2E suite:

```powershell
pytest tests/e2e
```

Run the mobile-focused suite:

```powershell
pytest tests/e2e/test_chainlit_mobile.py
```

Run mobile Chrome emulation only:

```powershell
pytest tests/e2e/test_chainlit_mobile.py -k "mobile and not safari" --browser chromium
```

Run Safari emulation when WebKit is installed:

```powershell
pytest tests/e2e/test_chainlit_mobile.py -k safari --browser webkit
```

## Compose and Proxy Validation

When the full stack is running locally, validate through Caddy with:

- `http://localhost/`
- `http://localhost/public/theme.json`
- `http://localhost/public/style.css?v=languageagent-theme-v2`
- `http://localhost/public/landing-status.js`
- `http://localhost/logo?theme=dark`
- `http://localhost/favicon`

Physical phone or tablet checks over LAN and public-domain checks through
Cloudflare Tunnel are still manual validation tasks.
