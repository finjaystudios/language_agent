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
    expect(page.locator('#lla-login-form input[name="username"]')).to_be_visible()
    expect(page.locator('#lla-login-form input[name="password"]')).to_be_visible()
    expect(
        page.locator("#lla-login-form").get_by_role("button", name="Sign In")
    ).to_be_visible()
    expect(page.get_by_role("button", name="Create account")).to_be_visible()


def test_invalid_login_is_rejected(
    requires_managed_chainlit: None,
    page: Page,
    chainlit_url: str,
    login_to_chainlit,
    e2e_credentials,
    chat_input,
):
    page.goto(chainlit_url)
    login_to_chainlit(
        page,
        e2e_credentials["username"],
        "wrong-password",
    )

    expect(page.locator('#lla-login-form input[name="password"]')).to_be_visible(
        timeout=15000
    )
    expect(
        page.get_by_text(
            "Sign-in failed. Check your username and password, then try again."
        )
    ).to_be_visible(
        timeout=15000,
    )
    expect(chat_input(page)).not_to_be_visible()


def test_valid_login_reaches_chat_ui(
    requires_managed_chainlit: None,
    page: Page,
    chainlit_url: str,
    login_to_chainlit,
    e2e_credentials,
    chat_input,
):
    page.goto(chainlit_url)
    login_to_chainlit(
        page,
        e2e_credentials["username"],
        e2e_credentials["password"],
    )

    expect(chat_input(page)).to_be_visible(timeout=15000)
    expect(page.get_by_text("Translate")).to_be_visible()


def test_logout_returns_to_login_page(
    requires_managed_chainlit: None,
    page: Page,
    chainlit_url: str,
    login_to_chainlit,
    e2e_credentials,
    chat_input,
):
    page.goto(chainlit_url)
    login_to_chainlit(
        page,
        e2e_credentials["username"],
        e2e_credentials["password"],
    )
    expect(chat_input(page)).to_be_visible(timeout=15000)

    response = page.request.post(f"{chainlit_url}/logout")
    assert response.ok

    page.reload()
    expect(page.locator('#lla-login-form input[name="username"]')).to_be_visible(
        timeout=15000
    )
    expect(page.locator('#lla-login-form input[name="password"]')).to_be_visible()


def test_signup_mismatch_and_success_then_login(
    requires_managed_chainlit: None,
    page: Page,
    chainlit_url: str,
    chat_input,
):
    page.goto(chainlit_url)
    page.locator("#lla-signup-form input[name='username']").fill("new-e2e-user")
    page.locator("#lla-signup-form input[name='password']").fill(
        "correct horse battery staple"
    )
    page.locator("#lla-signup-form input[name='confirm_password']").fill(
        "different password"
    )
    page.get_by_role("button", name="Create account").click()

    expect(
        page.get_by_text("Passwords do not match yet. Re-enter them and try again.")
    ).to_be_visible(timeout=15000)

    page.locator("#lla-signup-form input[name='confirm_password']").fill(
        "correct horse battery staple"
    )
    page.get_by_role("button", name="Create account").click()

    expect(page.get_by_text("Account created. Please sign in.")).to_be_visible(
        timeout=15000
    )

    page.locator('#lla-login-form input[name="username"]').fill("new-e2e-user")
    page.locator('#lla-login-form input[name="password"]').fill(
        "correct horse battery staple"
    )
    page.locator("#lla-login-form").get_by_role("button", name="Sign In").click()

    expect(chat_input(page)).to_be_visible(timeout=15000)
