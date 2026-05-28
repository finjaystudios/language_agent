import re

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_chainlit_landing_page_loads(
    requires_managed_chainlit: None,
    page: Page,
    chainlit_url: str,
    login_to_chainlit,
    e2e_credentials,
):
    page.goto(chainlit_url)

    expect(page).to_have_title(re.compile(r"LanguageAgent"))
    expect(page.get_by_role("textbox", name="Email address")).to_be_visible()
    expect(page.get_by_role("textbox", name="Password")).to_be_visible()
    expect(page.get_by_role("button", name="Sign In")).to_be_visible()

    login_to_chainlit(
        page,
        e2e_credentials["username"],
        e2e_credentials["password"],
    )

    expect(page.get_by_alt_text("logo")).to_be_visible(timeout=15000)
    expect(
        page.get_by_placeholder("Ask your local language assistant...")
    ).to_be_visible()
    expect(page.get_by_text("Translate")).to_be_visible()
    expect(page.get_by_text("Define")).to_be_visible()
    expect(page.get_by_text("Learn")).to_be_visible()

    status_response = page.request.get(f"{chainlit_url}/webui/backend-status")
    assert status_response.ok
    payload = status_response.json()
    assert payload["status"] == "online"
    assert re.match(r"http://127\.0\.0\.1:\d+", payload["target"])

    for asset_path in (
        "/public/theme.json",
        "/public/style.css?v=languageagent-theme-v2",
        "/public/landing-status.js",
        "/logo?theme=dark",
        "/favicon",
    ):
        response = page.request.get(f"{chainlit_url}{asset_path}")
        assert response.ok, f"{asset_path} was not served by Chainlit"
