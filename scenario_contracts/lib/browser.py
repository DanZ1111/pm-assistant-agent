"""Playwright session/page lifecycle for UI-tagged scenarios.

Locked decisions (QA-03 plan):
- Dev server is external; runner does not start it.
- Headless by default; QA_BROWSER_HEADED=1 switches to headed.
- Failure screenshots only; QA_BROWSER_TRACE=1 also records a trace zip.
- Defaults: BASE_URL=http://localhost:8000, TEST_ADMIN_USERNAME=admin,
  TEST_ADMIN_PASSWORD="show me the money" (matches test_v13_ui_r*.py).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
SCREENSHOTS_DIR = REPORTS_DIR / "screenshots"
TRACES_DIR = REPORTS_DIR / "traces"


def base_url():
    return os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")


def admin_credentials():
    return (
        os.environ.get("TEST_ADMIN_USERNAME", "admin"),
        os.environ.get("TEST_ADMIN_PASSWORD", "show me the money"),
    )


def is_playwright_available():
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except Exception:
        return False


def is_dev_server_reachable(url=None):
    url = url or base_url()
    try:
        import urllib.request
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=3) as response:
            return 200 <= response.status < 500
    except Exception:
        # Some servers don't support HEAD; try GET.
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=3) as response:
                return 200 <= response.status < 500
        except Exception:
            return False


@contextmanager
def BrowserContext(role="admin"):
    """Yield a logged-in Playwright Page.

    On exit, closes the browser even if the scenario raised. Failure
    artifacts (screenshot, optional trace) are captured by the runner,
    not here — this context manager is only responsible for setup +
    teardown of the browser lifecycle.
    """
    if role != "admin":
        raise ValueError(
            f"QA-03 only ships admin login; got role={role!r}. "
            "PM/viewer logins land in QA-03b."
        )

    from playwright.sync_api import sync_playwright

    headed = os.environ.get("QA_BROWSER_HEADED") == "1"
    trace_enabled = os.environ.get("QA_BROWSER_TRACE") == "1"

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=not headed)
    context = browser.new_context(viewport={"width": 1440, "height": 950})
    if trace_enabled:
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()

    try:
        # Login as admin.
        username, password = admin_credentials()
        page.goto(f"{base_url()}/auth/login", wait_until="domcontentloaded")
        if "/auth/login" in page.url:
            page.fill("input[name='username']", username)
            page.fill("input[name='password']", password)
            page.click("form[action='/auth/login'] button[type='submit']")
            page.wait_for_load_state("domcontentloaded")
        yield page
    finally:
        try:
            if trace_enabled:
                ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
                TRACES_DIR.mkdir(parents=True, exist_ok=True)
                context.tracing.stop(path=str(TRACES_DIR / f"trace_{ts}.zip"))
        finally:
            try:
                context.close()
            finally:
                browser.close()
                pw.stop()


def capture_failure_artifacts(page, scenario_id):
    """Save a screenshot for the failing scenario; return the path."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    path = SCREENSHOTS_DIR / f"{scenario_id}_{ts}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception as exc:
        return f"screenshot_failed: {exc!r}"
