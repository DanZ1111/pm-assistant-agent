"""v1.3 Build 01 — Project Detail workspace shell tests.

Requires the app running at http://localhost:8000.
Run: python3 test_v13_build01.py
"""
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "test_artifacts"
PASS, FAIL = [], []

ADMIN, ADMIN_PWD = "admin", "show me the money"
PROJECT_NAME = "v13_build01_workspace_shell"


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, reason):
    FAIL.append((name, reason))
    print(f"  ✗  {name}: {reason}")


def login_session():
    s = requests.Session()
    r = s.post(
        f"{BASE}/auth/login",
        data={"username": ADMIN, "password": ADMIN_PWD},
        allow_redirects=False,
        timeout=5,
    )
    return s if r.status_code in (302, 303) else None


def login_page(page):
    page.goto(f"{BASE}/auth/login")
    if "/auth/login" not in page.url:
        return
    page.fill("input[name='username']", ADMIN)
    page.fill("input[name='password']", ADMIN_PWD)
    page.click("form[action='/auth/login'] button[type='submit']")
    page.wait_for_load_state("networkidle")


def db_exec(sql, params=()):
    conn = sqlite3.connect(ROOT / "pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def cleanup_project(name):
    conn = sqlite3.connect(ROOT / "pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE name = ?", (name,))
        ids = [row[0] for row in cur.fetchall()]
        for pid in ids:
            for table in (
                "phase_plan_changes",
                "project_journal_entries",
                "project_ideas",
                "project_variant_components",
                "project_variants",
                "project_changes",
                "project_phases",
                "project_files",
                "ai_messages",
                "project_creation_tokens",
            ):
                try:
                    cur.execute(f"DELETE FROM {table} WHERE project_id = ?", (pid,))
                except sqlite3.OperationalError:
                    pass
            cur.execute("DELETE FROM projects WHERE id = ?", (pid,))
        conn.commit()
    finally:
        conn.close()


def mint_token(session):
    r = session.get(f"{BASE}/projects/new", timeout=5)
    m = re.search(r'name="submission_token"\s+value="([a-f0-9]+)"', r.text)
    return m.group(1) if m else ""


def create_project(session):
    cleanup_project(PROJECT_NAME)
    token = mint_token(session)
    thesis = (
        "A workspace-shell test knife concept with enough thesis detail to keep "
        "Product Concept visible in Overview while Timeline remains a separate "
        "execution workspace for phases, dates, owners, and plan changes."
    )
    r = session.post(
        f"{BASE}/projects/new",
        data={
            "name": PROJECT_NAME,
            "brand": "Rblack",
            "product_manager": ADMIN,
            "engineer": "Test Engineer",
            "factory": "Test Factory",
            "target_factory_cost": "under 120 RMB",
            "target_msrp": "$70-100",
            "planned_launch_date": "2026-12-01",
            "project_thesis": thesis,
            "prototype_rounds": "single",
            "submission_token": token,
        },
        allow_redirects=False,
        timeout=5,
    )
    if r.status_code != 303:
        fail("create project", f"expected 303, got {r.status_code}: {r.text[:200]}")
        return None
    pid = r.headers.get("location", "").rstrip("/").split("/")[-1]
    return int(pid) if pid.isdigit() else None


def assert_i18n_parity():
    en = json.loads((ROOT / "app/i18n/en.json").read_text(encoding="utf-8"))
    zh = json.loads((ROOT / "app/i18n/zh.json").read_text(encoding="utf-8"))
    if set(en) == set(zh):
        ok(f"i18n parity preserved ({len(en)} keys)")
    else:
        fail(
            "i18n parity",
            f"missing_zh={sorted(set(en) - set(zh))[:8]} extra_zh={sorted(set(zh) - set(en))[:8]}",
        )


def main():
    print("\n── Setup ──")
    session = login_session()
    if not session:
        fail("admin login", "could not log in via requests")
        summary()
        return False
    ok("admin can log in via requests")

    pid = create_project(session)
    if not pid:
        summary()
        return False
    ok(f"fake project created ({pid})")

    print("\n── Static locks ──")
    template = (ROOT / "app/templates/project_detail.html").read_text(encoding="utf-8")
    if 'id="commercial-snapshot"' not in template and "project-snapshot-grid" not in template:
        ok("Commercial Snapshot section removed from project_detail.html")
    else:
        fail("Commercial Snapshot removal", "old snapshot id/grid still appears in template")

    if "workspaceTabOverview" in template and "workspaceTabTimeline" in template:
        ok("Overview/Timeline tab controls exist in template")
    else:
        fail("workspace tabs", "tab controls missing")

    assert_i18n_parity()

    print("\n── Browser workspace behavior ──")
    ARTIFACTS.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 950})
        login_page(page)

        page.goto(f"{BASE}/projects/{pid}")
        page.wait_for_load_state("networkidle")

        if page.locator("#workspaceTabOverview[aria-selected='true']").count() == 1:
            ok("Overview tab is active by default")
        else:
            fail("default overview tab", "Overview tab not active")

        if page.locator("#product-concept").is_visible() and not page.locator("#timeline").is_visible():
            ok("Overview shows Product Concept and hides Timeline by default")
        else:
            fail("default panel visibility", "expected product concept visible and timeline hidden")

        if page.locator("#commercial-snapshot").count() == 0:
            ok("Rendered page has no #commercial-snapshot")
        else:
            fail("rendered commercial snapshot", "#commercial-snapshot still rendered")

        if page.locator("#project-metadata").is_visible():
            meta_text = page.locator("#project-metadata").inner_text()
            if "$70-100" in meta_text and "under 120 RMB" in meta_text:
                ok("Created/updated and price estimates moved into quiet metadata area")
            else:
                fail("metadata price facts", meta_text[:300])
        else:
            fail("project metadata", "metadata section not visible in Overview")

        timeline_panel_text = page.locator("#workspacePanelTimeline").inner_text()
        if "Product Concept" not in timeline_panel_text:
            ok("Product Concept is not inside Timeline workspace")
        else:
            fail("timeline contents", "Product Concept leaked into Timeline panel")

        page.screenshot(path=str(ARTIFACTS / "v13_build01_desktop_overview.png"), full_page=True)
        ok("Desktop Overview screenshot captured")

        page.click("#workspaceTabTimeline")
        page.wait_for_function("document.getElementById('timeline') && !document.getElementById('timeline').hidden")
        if page.locator("#workspaceTabTimeline[aria-selected='true']").count() == 1 and page.locator("#timeline").is_visible():
            ok("Timeline tab click shows Timeline workspace")
        else:
            fail("timeline tab click", "Timeline did not become active/visible")

        if not page.locator("#product-concept").is_visible():
            ok("Overview content is hidden while Timeline is active")
        else:
            fail("overview hidden on timeline", "Product Concept stayed visible")

        edit_buttons = page.locator(".btn-phase-edit")
        if edit_buttons.count() >= 1:
            edit_buttons.first.click()
            page.wait_for_selector("#phaseModal.show", timeout=3000)
            ok("Existing phase edit modal still opens from Timeline")
            page.locator("#phaseModal .btn-close").click()
        else:
            fail("phase edit button", "no phase edit buttons visible in Timeline")

        page.goto(f"{BASE}/projects/{pid}#timeline")
        page.wait_for_load_state("networkidle")
        page.wait_for_function("document.querySelector('#workspaceTabTimeline[aria-selected=\"true\"]')")
        if page.locator("#timeline").is_visible():
            ok("/projects/{id}#timeline opens Timeline tab on load")
        else:
            fail("hash timeline", "Timeline not visible for #timeline")

        page.set_viewport_size({"width": 390, "height": 844})
        page.goto(f"{BASE}/projects/{pid}")
        page.wait_for_load_state("networkidle")
        page.screenshot(path=str(ARTIFACTS / "v13_build01_mobile_overview.png"), full_page=True)
        ok("Mobile Overview screenshot captured")

        browser.close()

    summary()
    return len(FAIL) == 0


def summary():
    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        for name, reason in FAIL:
            print(f"  ✗ {name}: {reason}")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
