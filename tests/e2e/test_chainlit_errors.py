import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_backend_unavailable_message_is_readable(
    page: Page,
    unavailable_backend_url: str,
    chainlit_process_factory,
    requires_managed_chainlit: None,
):
    url = chainlit_process_factory(
        unavailable_backend_url,
        name="chainlit-webui-offline",
    )
    page.goto(url)

    input_box = page.get_by_placeholder("Type your message here...")
    expect(input_box).to_be_enabled()
    input_box.fill("Hello")
    page.locator("#chat-submit:not([disabled])").click()

    expect(page.get_by_text("Service unavailable")).to_be_visible(timeout=15000)
    expect(
        page.get_by_text("The language service is not reachable right now.")
    ).to_be_visible()
    expect(page.get_by_text("FastAPI")).not_to_be_visible()
    expect(page.get_by_text("connection attempts")).not_to_be_visible()


def test_wrong_api_key_message_is_readable(
    page: Page,
    fake_backend: str,
    chainlit_process_factory,
    reset_fake_backend: None,
    backend_requests,
    requires_managed_chainlit: None,
):
    url = chainlit_process_factory(
        fake_backend,
        name="chainlit-webui-wrong-key",
        api_key="wrong-e2e-key",
    )
    page.goto(url)

    input_box = page.get_by_placeholder("Type your message here...")
    expect(input_box).to_be_enabled()
    input_box.fill("Define recursion")
    page.locator("#chat-submit:not([disabled])").click()

    expect(page.get_by_text("Backend authentication failed")).to_be_visible(
        timeout=15000
    )
    expect(
        page.get_by_text("The Web UI could not authenticate with the backend.")
    ).to_be_visible()
    expect(page.get_by_text("wrong-e2e-key")).not_to_be_visible()

    requests = backend_requests()
    assert requests[-1]["endpoint"] == "/api/chat"
    assert requests[-1]["api_key_present"] is True
    assert requests[-1]["api_key_valid"] is False


def test_missing_api_key_message_is_readable(
    page: Page,
    fake_backend: str,
    chainlit_process_factory,
    reset_fake_backend: None,
    backend_requests,
    requires_managed_chainlit: None,
):
    url = chainlit_process_factory(
        fake_backend,
        name="chainlit-webui-missing-key",
        api_key=None,
    )
    page.goto(url)

    input_box = page.get_by_placeholder("Type your message here...")
    expect(input_box).to_be_enabled()
    input_box.fill("Define recursion")
    page.locator("#chat-submit:not([disabled])").click()

    expect(page.get_by_text("Backend authentication is not configured")).to_be_visible(
        timeout=15000
    )
    expect(page.get_by_text("missing the backend API key")).to_be_visible()
    expect(page.get_by_text("e2e-test-secret")).not_to_be_visible()
    assert backend_requests() == []
