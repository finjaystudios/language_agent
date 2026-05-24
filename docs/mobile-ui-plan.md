# Mobile UI Plan

## Final Decisions

- Keep Chainlit as the UI shell.
- Keep `default_theme = "dark"` and `alert_style = "modern"`.
- Switch Chainlit layout from `wide` to `default`.
- Start the sidebar `closed` on first load.
- Keep the existing custom JS because it already owns the landing-page status card and accessibility patching.
- Keep branding assets and metadata paths unchanged.
- Use `custom_css = "/public/style.css?v=languageagent-theme-v2"` as the single active CSS entrypoint.

## Implemented UI Changes

- Added responsive CSS breakpoints for:
  - `max-width: 480px`
  - `max-width: 768px`
  - `min-width: 769px and max-width: 1024px`
- Reduced landing-page hero density on smaller screens.
- Enlarged composer and tap targets to mobile-safe sizes.
- Made starter actions wrap into usable rows on phones and tablets.
- Constrained chat width on tablet sizes so the layout does not feel stretched.
- Prevented page-level horizontal scrolling.
- Forced code blocks and tables to scroll inside their own container.
- Tuned theme tokens for slightly stronger contrast and softer card/border balance.
- Removed the stale `webui/public/custom.css` file.

## Test Coverage

Playwright coverage now includes:

- Desktop smoke coverage in `tests/e2e/test_chainlit_smoke.py`
- Mobile/tablet emulation in `tests/e2e/test_chainlit_mobile.py`
- Device presets in `tests/e2e/conftest.py`:
  - `Pixel 7`
  - `iPhone 13`
  - `iPad Mini`

Current mobile/tablet checks cover:

- Landing page load at emulated mobile/tablet widths
- No horizontal page overflow
- Visible composer and reachable send button
- Starter actions wrapping cleanly
- Successful message submit and visible assistant response
- Readable offline error state
- Tablet layout staying within viewport width

## Validation Completed

- `pytest tests/e2e/test_chainlit_mobile.py` passed on May 24, 2026.
- `pytest tests/e2e/test_chainlit_smoke.py` passed on May 24, 2026.
- `docker compose config` completed on May 24, 2026.
- `docker compose build webui` completed on May 24, 2026.
- The rebuilt Web UI image was checked to contain:
  - `public/style.css`
  - `public/theme.json`
  - `public/landing-status.js`
  - logos and favicon assets
  - `.chainlit/config.toml`
- A temporary local Caddy-to-WebUI Docker check returned `200` for:
  - `/`
  - `/public/theme.json`
  - `/public/style.css?v=languageagent-theme-v2`
  - `/public/landing-status.js`
  - `/logo?theme=dark`
  - `/favicon`

## Manual Mobile Checklist

- Small phone: `320px` to `375px`
  - Confirm no horizontal scrolling.
  - Confirm the logo and status card do not bury the composer.
  - Confirm starter actions are easy to tap.
- Large phone: `425px`
  - Confirm quick actions wrap cleanly.
  - Confirm the send button remains visible and comfortable.
- Tablet portrait: `768px`
  - Confirm the chat column does not feel edge-to-edge.
  - Confirm settings and composer remain usable.
- Tablet landscape: `1024px`
  - Confirm the layout stays centered and readable.
- Desktop:
  - Confirm no visual regression in landing layout, composer, or action buttons.

## Browser Device Mode

Use browser device emulation for quick manual checks:

1. Open the Web UI in Chromium/Brave.
2. Open DevTools.
3. Toggle device toolbar.
4. Test at least:
   - `iPhone SE`
   - `iPhone 12 Pro`
   - `Pixel 7`
   - `iPad Mini`
   - `iPad Air`
5. Verify both portrait and landscape on tablet sizes.

## Playwright Commands

```powershell
pytest tests/e2e
pytest tests/e2e/test_chainlit_mobile.py
pytest tests/e2e/test_chainlit_mobile.py --headed
pytest tests/e2e/test_chainlit_mobile.py -k "mobile and not safari" --browser chromium
pytest tests/e2e/test_chainlit_mobile.py -k safari --browser webkit
pytest tests/e2e/test_chainlit_smoke.py
```

## Remaining Manual Checks

Not completed in this environment:

- Physical phone or tablet testing over LAN
- Manual public-domain testing through the Cloudflare Tunnel

Those flows should be checked on the deployed host without changing Cloudflare configuration unless a real routing issue is found.
