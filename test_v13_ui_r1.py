"""v1.3 UI-R1 — static asset cache-busting + Timeline CSS proof.

Requires the app running at http://localhost:8000.
Run: python3 test_v13_ui_r1.py
"""
import os
import re
import sys
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ROOT = Path(__file__).resolve().parent
ADMIN = os.environ.get("TEST_ADMIN_USERNAME", "admin")
ADMIN_PWD = os.environ.get("TEST_ADMIN_PASSWORD", "show me the money")
PASS, FAIL = [], []


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, reason):
    FAIL.append((name, reason))
    print(f"  ✗  {name}: {reason}")


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def login_session():
    s = requests.Session()
    r = s.post(
        f"{BASE}/auth/login",
        data={"username": ADMIN, "password": ADMIN_PWD},
        allow_redirects=False,
        timeout=8,
    )
    return s if r.status_code in (302, 303) else None


def main():
    print("\n── 1. Source-level cache-busting ──")
    base_template = read("app/templates/base.html")
    main_source = read("app/main.py")
    if "/static/css/styles.css?v={{ STATIC_ASSET_VERSION }}" in base_template:
        ok("base.html versions first-party CSS URL")
    else:
        fail("CSS asset URL", "missing STATIC_ASSET_VERSION query")
    if "/static/js/main.js?v={{ STATIC_ASSET_VERSION }}" in base_template:
        ok("base.html versions first-party JS URL")
    else:
        fail("JS asset URL", "missing STATIC_ASSET_VERSION query")
    if "_static_asset_version" in main_source and "os.path.getmtime" in main_source:
        ok("STATIC_ASSET_VERSION is derived from static file mtimes")
    else:
        fail("asset token helper", "missing mtime-derived helper")

    from app.main import _GLOBALS
    token = _GLOBALS.get("STATIC_ASSET_VERSION")
    if token and re.match(r"^1\.\d+\.\d+-\d{4}-\d{2}-\d{2}-\d+$", token):
        ok(f"STATIC_ASSET_VERSION global is populated ({token})")
    else:
        fail("STATIC_ASSET_VERSION global", token)

    print("\n── 2. Rendered HTML uses versioned URLs ──")
    session = login_session()
    if not session:
      fail("login", f"Could not log in to {BASE}")
    else:
        login_html = session.get(f"{BASE}/auth/login", timeout=8).text
        css_match = re.search(r'href="/static/css/styles\.css\?v=([^"]+)"', login_html)
        js_match = re.search(r'src="/static/js/main\.js\?v=([^"]+)"', login_html)
        if css_match:
            ok(f"Rendered HTML includes versioned CSS ({css_match.group(1)})")
        else:
            fail("rendered CSS URL", "no ?v= query in /auth/login HTML")
        if js_match:
            ok(f"Rendered HTML includes versioned JS ({js_match.group(1)})")
        else:
            fail("rendered JS URL", "no ?v= query in /auth/login HTML")
        if css_match and js_match and css_match.group(1) == js_match.group(1):
            ok("Rendered CSS and JS share the same asset token")
        elif css_match and js_match:
            fail("asset token mismatch", f"css={css_match.group(1)} js={js_match.group(1)}")

    print("\n── 3. Browser-computed Timeline CSS proof ──")
    if session:
        projects_html = session.get(f"{BASE}/projects", timeout=8).text
        project_ids = re.findall(r'href="/projects/(\d+)"', projects_html)
        if not project_ids:
            fail("project fixture", "no projects found to inspect")
        else:
            project_id = project_ids[0]
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)
                    page = browser.new_page(viewport={"width": 1440, "height": 950})
                    page.goto(f"{BASE}/auth/login")
                    if "/auth/login" in page.url:
                        page.fill("input[name='username']", ADMIN)
                        page.fill("input[name='password']", ADMIN_PWD)
                        page.click("form[action='/auth/login'] button[type='submit']")
                        page.wait_for_load_state("networkidle")
                    page.goto(f"{BASE}/projects/{project_id}#timeline")
                    page.wait_for_load_state("networkidle")
                    styles = page.evaluate("""
                    () => {
                      const q = s => document.querySelector(s);
                      const style = el => el ? getComputedStyle(el) : null;
                      const phase = q('.timeline-phase-strip');
                      const grid = q('.timeline-tiles-grid');
                      const chip = q('.timeline-history-chip');
                      return {
                        hasPhase: !!phase,
                        phaseDisplay: style(phase)?.display || null,
                        phaseDirection: style(phase)?.flexDirection || null,
                        gridDisplay: style(grid)?.display || null,
                        chipRadius: style(chip)?.borderRadius || null,
                        chipBorderStyle: style(chip)?.borderStyle || null,
                      };
                    }
                    """)
                    browser.close()
                if styles["hasPhase"] and styles["phaseDisplay"] == "flex" and styles["phaseDirection"] == "row":
                    ok("Timeline phase strip computes as horizontal flex row")
                else:
                    fail("phase strip computed style", styles)
                if styles["gridDisplay"] == "grid":
                    ok("Timeline summary tiles compute as CSS grid")
                else:
                    fail("timeline tiles computed style", styles)
                if styles["chipRadius"] not in (None, "", "0px") and styles["chipBorderStyle"] != "none":
                    ok("Timeline history chips compute as styled app controls")
                else:
                    fail("history chip computed style", styles)
            except Exception as exc:
                fail("Playwright Timeline CSS proof", repr(exc))

    print("\n── Summary ──")
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        print("\nFailures:")
        for name, reason in FAIL:
            print(f" - {name}: {reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
