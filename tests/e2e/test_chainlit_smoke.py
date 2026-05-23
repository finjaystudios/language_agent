import re

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_chainlit_landing_page_loads(
    page: Page,
    chainlit_url: str,
    external_chainlit_url: str | None,
):
    page.goto(chainlit_url)

    expect(page).to_have_title(re.compile(r"LanguageAgent"))
    expect(page.get_by_alt_text("logo")).to_be_visible()
    expect(
        page.get_by_placeholder("Ask your local language assistant...")
    ).to_be_visible()
    expect(page.get_by_text("Translate")).to_be_visible()
    expect(page.get_by_text("Define")).to_be_visible()
    expect(page.get_by_text("Learn")).to_be_visible()
    expect(page.get_by_text("Language service online")).to_be_visible(timeout=15000)
    backend_target_pattern = (
        r"Backend target: http://fastapi:8000"
        if external_chainlit_url
        else r"Backend target: http://127\.0\.0\.1:\d+"
    )
    expect(page.get_by_text(re.compile(backend_target_pattern))).to_be_visible(
        timeout=15000
    )
    expect(
        page.get_by_role("button", name="Refresh language service status")
    ).to_be_visible()
    expect(page.get_by_text("Service unavailable")).not_to_be_visible()

    for asset_path in (
        "/public/theme.json",
        "/public/style.css?v=languageagent-theme-v1",
        "/public/landing-status.js",
        "/logo?theme=dark",
        "/favicon",
    ):
        response = page.request.get(f"{chainlit_url}{asset_path}")
        assert response.ok, f"{asset_path} was not served by Chainlit"
