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


def select_response_mode(page: Page, label: str) -> None:
    page.locator("#chat-settings-header-button").click()
    page.locator("#selected_mode").click()
    page.get_by_role("option", name=label).click()
    page.get_by_role("button", name="Confirm").click()
    expect(page.get_by_text(f"Response mode set to {label}.")).to_be_visible()


def expect_response_actions(page: Page) -> None:
    expect(page.get_by_role("button", name="Retry")).to_be_visible()
    expect(page.get_by_role("button", name="Helpful")).to_be_visible()
    expect(page.get_by_role("button", name="Needs improvement")).to_be_visible()


def test_definition_starter_sets_mode_and_renders_response(
    requires_fake_backend: None,
    page: Page,
    chainlit_url: str,
    reset_fake_backend: None,
    backend_requests,
):
    page.goto(chainlit_url)

    expect(
        page.get_by_placeholder("Ask your local language assistant...")
    ).to_be_enabled()
    page.get_by_role("button", name=re.compile(r"Define")).click()

    expect(page.get_by_text("Define recursion in simple terms.")).to_be_visible()
    expect(page.get_by_text("Definition from fake stream.")).to_be_visible(
        timeout=15000
    )
    expect(page.locator("#lla-backend-status")).to_be_hidden()
    expect_response_actions(page)

    requests = backend_requests()
    assert requests[-1]["endpoint"] == "/api/chat/stream"
    assert requests[-1]["payload"]["mode"] == "definition"
    assert requests[-1]["payload"]["stream"] is True
    assert requests[-1]["api_key_present"] is True
    assert requests[-1]["api_key_valid"] is True


def test_user_can_send_full_response_message(
    requires_fake_backend: None,
    page: Page,
    chainlit_url: str,
    reset_fake_backend: None,
    backend_requests,
):
    page.goto(chainlit_url)

    submit_chat_message(page, "Workshop")

    expect(page.get_by_text("Workshop")).to_be_visible()
    expect(
        page.get_by_text(re.compile(r"E2E full response from fake backend"))
    ).to_be_visible(timeout=15000)
    expect_response_actions(page)

    requests = backend_requests()
    assert requests[-1]["endpoint"] == "/api/chat"
    assert "mode" not in requests[-1]["payload"]
    assert requests[-1]["api_key_present"] is True
    assert requests[-1]["api_key_valid"] is True


def test_settings_response_mode_overrides_next_message(
    requires_fake_backend: None,
    page: Page,
    chainlit_url: str,
    reset_fake_backend: None,
    backend_requests,
):
    page.goto(chainlit_url)

    select_response_mode(page, "Definition")
    submit_chat_message(page, "Workshop")

    expect(page.get_by_text("Definition from fake stream.")).to_be_visible(
        timeout=15000
    )

    requests = backend_requests()
    assert requests[-1]["endpoint"] == "/api/chat/stream"
    assert requests[-1]["payload"]["mode"] == "definition"
    assert requests[-1]["payload"]["stream"] is True


def test_streaming_starter_renders_streamed_response(
    requires_fake_backend: None,
    page: Page,
    chainlit_url: str,
    reset_fake_backend: None,
    backend_requests,
):
    page.goto(chainlit_url)

    expect(
        page.get_by_placeholder("Ask your local language assistant...")
    ).to_be_enabled()
    page.get_by_role("button", name=re.compile(r"Translate")).click()

    expect(page.get_by_text("Bonjour from fake stream.")).to_be_visible(timeout=15000)
    expect_response_actions(page)

    requests = backend_requests()
    assert requests[-1]["endpoint"] == "/api/chat/stream"
    assert requests[-1]["payload"]["mode"] == "translation"
    assert requests[-1]["payload"]["stream"] is True
    assert requests[-1]["api_key_present"] is True
    assert requests[-1]["api_key_valid"] is True
