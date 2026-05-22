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
    expect(page.get_by_placeholder("Type your message here...")).to_be_visible()
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
