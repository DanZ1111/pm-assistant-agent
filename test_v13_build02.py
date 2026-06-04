"""v1.3 Build 02 — Project Pulse v1 (rules-based) tests.

Requires the app running at http://localhost:8000, or set BASE_URL.
Run: python3 test_v13_build02.py
"""
import json
import os
import re
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ROOT = Path(__file__).resolve().parent
PASS, FAIL = [], []

ADMIN, ADMIN_PWD = "admin", "show me the money"
VIEWER_USER, VIEWER_PWD = "testviewer_b8", "viewerpass8!"
PREFIX = "v13_build02_"


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, reason):
    FAIL.append((name, reason))
    print(f"  ✗  {name}: {reason}")


def login_session(username, password):
    s = requests.Session()
    r = s.post(
        f"{BASE}/auth/login",
        data={"username": username, "password": password},
        allow_redirects=False,
        timeout=5,
    )
    return s if r.status_code in (302, 303) else None


def login_page(page, username=ADMIN, password=ADMIN_PWD):
    page.goto(f"{BASE}/auth/login")
    if "/auth/login" not in page.url:
        return
    page.fill("input[name='username']", username)
    page.fill("input[name='password']", password)
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


def cleanup():
    conn = sqlite3.connect(ROOT / "pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE name LIKE ?", (PREFIX + "%",))
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


def create_project(session, name, complete=True):
    data = {
        "name": name,
        "prototype_rounds": "single",
        "submission_token": mint_token(session),
    }
    if complete:
        data.update({
            "brand": "Rblack",
            "product_manager": ADMIN,
            "engineer": "Sensitive Engineer",
            "factory": "Sensitive Factory",
            "target_factory_cost": "under 120 RMB",
            "target_msrp": "$70-100",
            "planned_launch_date": "2026-12-01",
            "project_thesis": (
                "A rules-based pulse test project with enough product thesis detail "
                "to pass health checks while the Overview can summarize status, "
                "owners, launch target, and recommended next action."
            ),
        })
    r = session.post(f"{BASE}/projects/new", data=data, allow_redirects=False, timeout=5)
    if r.status_code != 303:
        fail(f"create {name}", f"expected 303, got {r.status_code}: {r.text[:200]}")
        return None
    pid = r.headers.get("location", "").rstrip("/").split("/")[-1]
    return int(pid) if pid.isdigit() else None


def make_delayed(pid):
    overdue = (date.today() - timedelta(days=4)).isoformat()
    db_exec(
        "UPDATE project_phases SET status = 'in_progress', planned_end_date = ? "
        "WHERE project_id = ? AND phase_order = 1",
        (overdue, pid),
    )
    db_exec(
        "UPDATE projects SET current_stage = 'Design', estimated_launch_date = ? WHERE id = ?",
        ((date.today() + timedelta(days=4)).isoformat(), pid),
    )


def mark_all_phases_done(pid):
    today = date.today().isoformat()
    db_exec(
        "UPDATE project_phases SET status = 'done', actual_start_date = ?, actual_end_date = ? "
        "WHERE project_id = ?",
        (today, today, pid),
    )
    db_exec("UPDATE projects SET current_stage = 'Launch' WHERE id = ?", (pid,))


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
    cleanup()
    admin_s = login_session(ADMIN, ADMIN_PWD)
    viewer_s = login_session(VIEWER_USER, VIEWER_PWD)
    if not admin_s:
        fail("admin login", "could not log in")
        summary()
        return False
    ok("admin can log in")
    if not viewer_s:
        fail("viewer login", "could not log in")
        summary()
        return False
    ok("viewer can log in")

    delayed_id = create_project(admin_s, PREFIX + "delayed")
    missing_id = create_project(admin_s, PREFIX + "missing")
    healthy_id = create_project(admin_s, PREFIX + "healthy")
    viewer_id = create_project(admin_s, PREFIX + "viewer_sensitive")
    if not all([delayed_id, missing_id, healthy_id, viewer_id]):
        summary()
        return False
    make_delayed(delayed_id)
    db_exec("UPDATE projects SET brand = NULL WHERE id = ?", (missing_id,))
    mark_all_phases_done(healthy_id)
    ok("test projects prepared")

    print("\n── Static locks ──")
    template = (ROOT / "app/templates/project_detail.html").read_text(encoding="utf-8")
    if template.find('id="project-pulse"') < template.find('id="thesis"'):
        ok("Project Pulse appears before Product Thesis in template")
    else:
        fail("Project Pulse order", "Pulse does not precede Thesis")
    if 'data-pulse-version="rules-v1"' in template and "pulse.rules_based_v1" in template:
        ok("Project Pulse explicitly identifies rules-based v1")
    else:
        fail("Pulse v1 label", "rules-based v1 marker missing")
    assert_i18n_parity()

    print("\n── Browser behavior ──")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 950})
        login_page(page)

        page.goto(f"{BASE}/projects/{delayed_id}")
        page.wait_for_load_state("networkidle")
        pulse = page.locator("#project-pulse")
        if pulse.is_visible() and pulse.bounding_box()["y"] < page.locator("#thesis").bounding_box()["y"]:
            ok("Project Pulse renders before Product Thesis")
        else:
            fail("Pulse visual order", "Pulse not visible before Thesis")
        delayed_text = pulse.inner_text()
        if "Timeline needs attention" in delayed_text and "Open Timeline" in delayed_text:
            ok("Delayed project shows Timeline action")
        else:
            fail("Delayed Pulse action", delayed_text[:300])

        page.goto(f"{BASE}/projects/{missing_id}")
        page.wait_for_load_state("networkidle")
        missing_text = page.locator("#project-pulse").inner_text()
        if "Critical information missing" in missing_text and "brand" in missing_text.lower():
            ok("Missing-critical project shows highest-priority missing-field action")
        else:
            fail("Missing-field Pulse action", missing_text[:300])

        page.goto(f"{BASE}/projects/{healthy_id}")
        page.wait_for_load_state("networkidle")
        healthy_text = page.locator("#project-pulse").inner_text()
        if "No urgent action" in healthy_text:
            ok("Healthy project shows no urgent action")
        else:
            fail("Healthy Pulse action", healthy_text[:300])

        viewer_page = browser.new_page(viewport={"width": 1280, "height": 900})
        login_page(viewer_page, VIEWER_USER, VIEWER_PWD)
        viewer_page.goto(f"{BASE}/projects/{viewer_id}")
        viewer_page.wait_for_load_state("networkidle")
        viewer_text = viewer_page.locator("#project-pulse").inner_text()
        forbidden = ["Sensitive Engineer", "Sensitive Factory", "under 120 RMB"]
        leaked = [value for value in forbidden if value in viewer_text]
        if not leaked:
            ok("Viewer Pulse hides engineer/factory/cost-sensitive details")
        else:
            fail("Viewer sensitive leak", f"leaked: {leaked}")

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
