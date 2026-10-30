"""A browser per worker, a clean context per test, a screenshot and a trace in Allure on failure.

Own fixtures instead of pytest-playwright: its fixtures and options (browser, page, --headed) clash with these.
"""
import pytest
from playwright.sync_api import sync_playwright

from modules.allure_helper import attach_file, attach_png, attach_text


@pytest.fixture(scope="session")
def browser(pytestconfig, cfg):
    with sync_playwright() as p:
        p.selectors.set_test_id_attribute(cfg.get("ui_test_id_attribute", "data-testid"))
        browser_type = getattr(p, cfg.get("ui_browser", "chromium"))  # chromium / firefox / webkit
        browser = browser_type.launch(headless=not pytestconfig.getoption("headed"))
        yield browser
        browser.close()


@pytest.fixture
def page(browser, cfg, request, tmp_path):
    context = browser.new_context(ignore_https_errors=not cfg.get("verify_ssl", True),
                                  viewport={"width": 1440, "height": 900})
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    page.set_default_timeout(cfg.get("ui_timeout_ms", 15_000))
    yield page
    failed = any(getattr(getattr(request.node, f"rep_{when}", None), "failed", False) for when in ("setup", "call"))
    try:
        if failed:
            try:
                attach_png(page.screenshot(full_page=True), "Screenshot on failure")
            except Exception as error:  # noqa: BLE001 - the page may have crashed: still save the trace
                attach_text(repr(error), "No screenshot")
            context.tracing.stop(path=tmp_path / "trace.zip")
            attach_file(tmp_path / "trace.zip", "Playwright trace (playwright show-trace trace.zip)",
                        "application/zip", "zip")
        else:
            context.tracing.stop()
    finally:
        context.close()
