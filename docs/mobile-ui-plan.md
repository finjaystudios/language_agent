# Mobile UI Plan

## Scope

Audit target: the Chainlit Web UI in `webui/` only.

Out of scope:

- Replacing Chainlit
- Backend queue or streaming changes
- Auth changes
- Caddy or routing changes

## Current Web UI Structure

- Entry point: `webui/app.py`
- Landing copy: `webui/chainlit.md`
- Chainlit config: `webui/.chainlit/config.toml`
- Theme tokens: `webui/public/theme.json`
- Active custom CSS: `webui/public/style.css`
- Unused legacy CSS file present: `webui/public/custom.css`
- Active custom JS: `webui/public/landing-status.js`
- Branding assets: `webui/public/logo_dark.png`, `webui/public/logo_light.png`, `webui/public/favicon`, `webui/public/languageagent-icon-32.png`, `webui/public/languageagent-icon-64.png`
- Playwright coverage: `tests/e2e/test_chainlit_smoke.py`, `tests/e2e/test_chainlit_chat.py`, `tests/e2e/test_chainlit_errors.py`

## Current Chainlit Customisation Usage

- `layout = "wide"`
- `default_theme = "dark"`
- `custom_css = "/public/style.css?v=languageagent-theme-v1"`
- `custom_js = "/public/landing-status.js"`
- `alert_style = "modern"`
- `logo_file_url = ""`
  Chainlit falls back to theme-aware `/logo`.
- `default_avatar_file_url = ""`
  No custom avatar configured.
- `custom_meta_url` is set to the GitHub repo.
- `custom_meta_image_url` is set to `/public/logo_dark.png`.
- `translation` files are present under `webui/.chainlit/translations/`, but no forced UI language is configured.
- `default_sidebar_state = "open"`
- `chat_settings_location = "sidebar"`
- `default_chat_settings_open = false`

## Audit Findings

The current UI is branded and functional, but it is still tuned like a desktop-first Chainlit shell:

- `layout = "wide"` increases horizontal spread on tablet and landscape widths.
- The landing logo is intentionally oversized with `width: clamp(560px, 32vw, 640px)`, which is too large for first-screen mobile density.
- The status card and landing copy add vertical weight above the composer.
- Settings live in the sidebar, which is acceptable on desktop but costly on smaller widths.
- CSS currently improves colors, bubbles, and focus states, but it does not include breakpoint-specific layout rules for the composer, header, actions, tables, or code blocks.
- JS improves placeholder text and accessibility, but it does not address mobile viewport, virtual keyboard, or sidebar behavior.

## Breakpoint Audit

| Viewport | Likely issues | Proposed Chainlit-first fix |
| --- | --- | --- |
| `320px` | Landing logo dominates first screen, starter/actions wrap poorly, composer feels cramped, status card is dense, code/tables likely overflow | Add `@media (max-width: 360px)` rules to shrink logo, reduce landing spacing, stack/wrap action groups, tighten message padding, force code/table horizontal scrolling |
| `375px` | Better than `320px`, but header + logo + status card still consume too much height; sidebar/settings interactions remain awkward | Reduce top spacing, cap logo closer to phone width, move emphasis from hero area to composer area, keep settings panel collapsed by default |
| `425px` | Quick actions and feedback buttons may wrap inconsistently; wide message rows still feel desktop-like | Normalize action button min/max width, use flex-wrap with controlled gaps, cap message content width and padding for handheld widths |
| `768px` | Tablet portrait can end up between mobile and desktop patterns: wide layout, sidebar pressure, oversized empty margins | Add tablet-specific max widths for chat column, consider `layout = "default"` if Chainlit wide mode remains too spread out, tune sidebar width/overlay behavior with CSS |
| `1024px` | Small desktop / landscape tablet can feel over-wide with current `wide` layout and large hero logo | Keep desktop polish, but constrain landing content and chat width so the interface does not look sparse |

## Issue List

| Issue | Affected sizes | Proposed CSS/config fix | Test coverage needed |
| --- | --- | --- | --- |
| Horizontal overflow risk from code blocks and tables | `320px`, `375px`, `425px`, `768px` | Add `overflow-x: auto` and `max-width: 100%` for `pre`, `code`, `table`, and rich message containers | Add a mobile e2e case that renders a long code block or wide table and asserts no page-level horizontal scroll regression where practical |
| Header/logo takes too much space before first message | `320px`, `375px`, `425px`, `768px` | Reduce logo width and vertical margins at mobile/tablet breakpoints; trim landing markdown spacing | Add smoke assertions for visible composer and starters within the initial viewport on mobile sizes |
| Chat input feels cramped with mobile keyboard competition | `320px`, `375px`, `425px` | Increase composer hit area, reduce surrounding chrome, add bottom safe-area padding, keep submit/stop controls at touch size | Add Playwright mobile viewport checks for visible textarea and enabled submit button after focus |
| Sidebar/settings behavior is desktop-first | `320px`, `375px`, `425px`, `768px` | Keep chat settings collapsed by default; add CSS rules so sidebar behaves as overlay rather than consuming chat width on small screens; verify if `default_sidebar_state = "closed"` is better than `open` | Add viewport tests that open settings and assert the chat column remains usable |
| Starter buttons and feedback actions wrap badly | `320px`, `375px`, `425px` | Add explicit wrapping, full-width or two-up layouts at phone widths, and larger tap targets | Add visual interaction tests that click wrapped starter/action buttons on phone widths |
| Message bubbles read too wide on tablet and too tight on phones | `320px` to `1024px` | Add breakpoint-specific `max-width`, padding, and gap rules for user/assistant messages | Add screenshot or DOM-based width assertions across at least phone and tablet sizes |
| Status/streaming messages are clear textually but weak spatially on mobile | `320px`, `375px`, `425px` | Improve spacing and emphasis for temporary status messages; ensure stop button and stream state remain obvious | Add one streaming mobile test validating queued/processing/streaming text visibility and stop button accessibility |
| Tablet layout wastes space | `768px`, `1024px` | Constrain main chat column width and reduce reliance on `wide` layout | Add tablet smoke coverage for landing and one active conversation state |

## Recommended Implementation Order

1. Keep the current Chainlit architecture and work through config/CSS/JS only.
2. Add responsive CSS breakpoints for `360px`, `480px`, `768px`, and `1024px`.
3. Shrink the landing hero first: logo, landing copy spacing, status card spacing.
4. Fix composer and button touch targets next.
5. Add overflow handling for `pre`, `table`, and long inline content.
6. Re-evaluate `layout = "wide"` after CSS changes.
   If the chat column still feels too desktop-like on tablet, switch to `layout = "default"` and re-test.
7. Only add small custom JS if CSS cannot solve keyboard visibility or sidebar state friction.

## Suggested Changes By File

- `webui/public/style.css`
  Add the responsive rules. This should carry most of the work.
- `webui/.chainlit/config.toml`
  Re-evaluate `layout` and possibly `default_sidebar_state` after the CSS pass.
- `webui/chainlit.md`
  Trim landing copy if the hero remains too tall on phones.
- `webui/public/landing-status.js`
  Only touch if the composer/status card placement needs mobile-specific behavior that CSS cannot handle.

## Test Coverage Plan

Add a small mobile-focused e2e file, for example `tests/e2e/test_chainlit_mobile.py`, with viewport coverage for:

- `320x568`
- `375x667`
- `425x800`
- `768x1024`
- `1024x768`

Recommended assertions:

- Landing page loads with no obvious horizontal overflow.
- Composer is visible and focusable at each viewport.
- Starter buttons remain visible and clickable.
- Settings panel can open without trapping or collapsing the main chat unusably.
- A sent message and returned response remain readable at phone and tablet widths.
- Streaming state text and stop control remain visible during a stream.

## Manual Test Checklist

- Load the landing page at all five target widths.
- Confirm no page-level horizontal scrolling on landing and in an active chat.
- Confirm the logo, status card, and landing copy do not push the composer too far below the fold on phones.
- Confirm starter prompts are easy to tap and wrap cleanly.
- Focus the composer on a phone-sized viewport and verify it is not obscured by the virtual keyboard area.
- Send one normal message and one streaming message.
- Open chat settings/sidebar on phone and tablet widths and verify returning to chat is obvious.
- Check a response containing long text, fenced code, and structured content.
- Check portrait and landscape on a tablet-sized viewport.

## Validation Notes

- Existing practical validation: `pytest tests/e2e/test_chainlit_smoke.py` passed on May 24, 2026.
- There is currently no mobile-specific Playwright coverage.
- `webui/public/custom.css` appears to be a stale duplicate and should not be used for new work unless the active config is changed intentionally.
