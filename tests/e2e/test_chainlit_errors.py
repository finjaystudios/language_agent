import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_backend_unavailable_message_is_readable(
    page: Page,
    unavailable_backend_url: str,
    chainlit_process_factory,
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
