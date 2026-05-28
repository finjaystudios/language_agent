import re

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def submit_chat_message(page: Page, text: str) -> None:
    input_box = page.get_by_placeholder("Ask your local language assistant...")
    expect(input_box).to_be_enabled()
    input_box.fill(text)
    page.locator("#chat-submit:not([disabled])").click()


def assert_no_horizontal_overflow(page: Page) -> None:
    overflow = page.evaluate(
        """() => ({
            viewport: window.innerWidth,
            pageWidth: document.documentElement.scrollWidth,
        })"""
    )
    assert overflow["pageWidth"] <= overflow["viewport"], overflow


@pytest.mark.parametrize("emulated_page", ["pixel"], indirect=True)
def test_mobile_layout_is_touch_friendly_and_submits_message(
    requires_fake_backend: None,
    emulated_page: Page,
    chainlit_url: str,
    login_to_chainlit,
    e2e_credentials,
    reset_fake_backend: None,
    backend_requests,
):
    page = emulated_page
    page.goto(chainlit_url)
    login_to_chainlit(
        page,
        e2e_credentials["username"],
        e2e_credentials["password"],
    )

    expect(page).to_have_title(re.compile(r"LanguageAgent"))
    expect(
        page.get_by_placeholder("Ask your local language assistant...")
    ).to_be_visible()
    expect(page.locator("#chat-submit")).to_be_visible()
    expect(page.get_by_role("button", name="Translate")).to_be_visible()
    expect(page.get_by_role("button", name="Define")).to_be_visible()
    expect(page.get_by_role("button", name="Learn")).to_be_visible()

    assert_no_horizontal_overflow(page)

    button_metrics = page.evaluate(
        """() => ({
            submit: document.querySelector("#chat-submit")?.getBoundingClientRect(),
            starters: Array.from(document.querySelectorAll("#starters > button")).map(
                (button) => button.getBoundingClientRect()
            ),
        })"""
    )
    assert button_metrics["submit"]["height"] >= 44
    assert button_metrics["submit"]["width"] >= 44
    starter_rows = {round(rect["top"], 1) for rect in button_metrics["starters"]}
    assert len(starter_rows) >= 2

    submit_chat_message(
        page,
        "SupercalifragilisticexpialidociousSupercalifragilisticexpialidocious",
    )

    expect(
        page.get_by_text("E2E full response from fake backend for general.")
    ).to_be_visible(timeout=15000)
    expect(page.get_by_role("button", name="Retry")).to_be_visible()
    expect(page.get_by_role("button", name="Helpful")).to_be_visible()
    expect(page.get_by_role("button", name="Needs improvement")).to_be_visible()

    assert_no_horizontal_overflow(page)

    requests = backend_requests()
    assert requests[-1]["endpoint"] == "/api/chat"
    assert requests[-1]["api_key_valid"] is True


@pytest.mark.parametrize("emulated_page", ["pixel"], indirect=True)
def test_mobile_error_state_is_readable(
    emulated_page: Page,
    unavailable_backend_url: str,
    chainlit_process_factory,
    login_to_chainlit,
    e2e_credentials,
    requires_managed_chainlit: None,
):
    page = emulated_page
    url = chainlit_process_factory(
        unavailable_backend_url,
        name="chainlit-webui-mobile-offline",
    )
    page.goto(url)
    login_to_chainlit(
        page,
        e2e_credentials["username"],
        e2e_credentials["password"],
    )

    submit_chat_message(page, "Hello")

    expect(page.get_by_text("Service unavailable")).to_be_visible(timeout=15000)
    expect(
        page.get_by_text("The language service is not reachable right now.")
    ).to_be_visible()
    assert_no_horizontal_overflow(page)


@pytest.mark.parametrize("emulated_page", ["tablet"], indirect=True)
def test_tablet_layout_remains_readable_without_horizontal_overflow(
    requires_fake_backend: None,
    emulated_page: Page,
    chainlit_url: str,
    login_to_chainlit,
    e2e_credentials,
    reset_fake_backend: None,
):
    page = emulated_page
    page.goto(chainlit_url)
    login_to_chainlit(
        page,
        e2e_credentials["username"],
        e2e_credentials["password"],
    )

    expect(
        page.get_by_placeholder("Ask your local language assistant...")
    ).to_be_visible()
    expect(page.locator("#chat-submit")).to_be_visible()
    assert_no_horizontal_overflow(page)

    layout_metrics = page.evaluate(
        """() => ({
            viewport: window.innerWidth,
            composer: document.querySelector("#message-composer")?.getBoundingClientRect(),
            status: document.querySelector("#lla-backend-status")?.getBoundingClientRect(),
        })"""
    )
    assert layout_metrics["composer"]["width"] < layout_metrics["viewport"]
    assert layout_metrics["status"]["width"] < layout_metrics["viewport"]

    submit_chat_message(page, "Workshop")

    expect(
        page.get_by_text("E2E full response from fake backend for general.")
    ).to_be_visible(timeout=15000)
    assert_no_horizontal_overflow(page)


@pytest.mark.parametrize("emulated_page", ["iphone"], indirect=True)
def test_mobile_safari_layout_smoke_if_webkit_available(
    browser_name: str,
    emulated_page: Page,
    chainlit_url: str,
    login_to_chainlit,
    e2e_credentials,
):
    if browser_name != "webkit":
        pytest.skip("Run with --browser webkit to validate iPhone Safari emulation.")

    page = emulated_page
    page.goto(chainlit_url)
    login_to_chainlit(
        page,
        e2e_credentials["username"],
        e2e_credentials["password"],
    )

    expect(
        page.get_by_placeholder("Ask your local language assistant...")
    ).to_be_visible()
    expect(page.get_by_role("button", name="Translate")).to_be_visible()
    assert_no_horizontal_overflow(page)
