import re

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_login_page_loads(
    requires_managed_chainlit: None,
    page: Page,
    chainlit_url: str,
):
    page.goto(chainlit_url)

    expect(page).to_have_title(re.compile(r"LanguageAgent"))
    expect(page.get_by_text("Login to access the app")).to_be_visible()
    expect(page.get_by_role("textbox", name="Email address")).to_be_visible()
    expect(page.get_by_role("textbox", name="Password")).to_be_visible()
    expect(page.get_by_role("button", name="Sign In")).to_be_visible()


def test_invalid_login_is_rejected(
    requires_managed_chainlit: None,
    page: Page,
    chainlit_url: str,
    login_to_chainlit,
    e2e_credentials,
):
    page.goto(chainlit_url)
    login_to_chainlit(
        page,
        e2e_credentials["username"],
        "wrong-password",
    )

    expect(page.get_by_role("textbox", name="Password")).to_be_visible(timeout=15000)
    expect(
        page.get_by_placeholder("Ask your local language assistant...")
    ).not_to_be_visible()


def test_valid_login_reaches_chat_ui(
    requires_managed_chainlit: None,
    page: Page,
    chainlit_url: str,
    login_to_chainlit,
    e2e_credentials,
):
    page.goto(chainlit_url)
    login_to_chainlit(
        page,
        e2e_credentials["username"],
        e2e_credentials["password"],
    )

    expect(
        page.get_by_placeholder("Ask your local language assistant...")
    ).to_be_visible(timeout=15000)
    expect(page.get_by_text("Translate")).to_be_visible()


def test_logout_returns_to_login_page(
    requires_managed_chainlit: None,
    page: Page,
    chainlit_url: str,
    login_to_chainlit,
    e2e_credentials,
):
    page.goto(chainlit_url)
    login_to_chainlit(
        page,
        e2e_credentials["username"],
        e2e_credentials["password"],
    )
    expect(
        page.get_by_placeholder("Ask your local language assistant...")
    ).to_be_visible(timeout=15000)

    response = page.request.post(f"{chainlit_url}/logout")
    assert response.ok

    page.reload()
    expect(page.get_by_role("textbox", name="Email address")).to_be_visible(
        timeout=15000
    )
    expect(page.get_by_role("textbox", name="Password")).to_be_visible()
