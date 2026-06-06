"""v1.3 UI-R4 — Timeline History event feed polish.

Requires the app running at http://localhost:8000.
Run: python3 test_v13_ui_r4.py
"""
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "test_artifacts"
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


def table_exists(cur, table):
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def cleanup(prefix):
    conn = sqlite3.connect(ROOT / "pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE name LIKE ?", (prefix + "%",))
        project_ids = [row[0] for row in cur.fetchall()]
        for pid in project_ids:
            if table_exists(cur, "planning_sandboxes"):
                cur.execute("SELECT id FROM planning_sandboxes WHERE project_id = ?", (pid,))
                sandbox_ids = [row[0] for row in cur.fetchall()]
                for sid in sandbox_ids:
                    cur.execute("DELETE FROM planning_sandbox_edges WHERE sandbox_id = ?", (sid,))
                    cur.execute("DELETE FROM planning_sandbox_nodes WHERE sandbox_id = ?", (sid,))
                cur.execute("DELETE FROM planning_sandboxes WHERE project_id = ?", (pid,))
            for table in [
                "project_blockers",
                "project_variant_components",
                "project_variants",
                "project_changes",
                "project_files",
                "project_journal_entries",
                "ai_messages",
                "project_creation_tokens",
            ]:
                if table_exists(cur, table):
                    cur.execute(f"DELETE FROM {table} WHERE project_id = ?", (pid,))
            if table_exists(cur, "phase_plan_changes"):
                cur.execute(
                    "DELETE FROM phase_plan_changes WHERE phase_id IN "
                    "(SELECT id FROM project_phases WHERE project_id = ?)",
                    (pid,),
                )
            cur.execute("DELETE FROM project_phases WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM projects WHERE id = ?", (pid,))
        conn.commit()
    finally:
        conn.close()


def make_history_fixture():
    from app import crud
    from app.database import SessionLocal
    from app.models import ProjectPhase, User

    cleanup("uir4_test")
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == ADMIN).first()
        project = crud.create_project(
            db,
            {
                "name": "uir4_test_history_feed",
                "product_manager": ADMIN,
            },
            prototype_rounds="single",
        )
        phase = (
            db.query(ProjectPhase)
            .filter(ProjectPhase.project_id == project.id)
            .order_by(ProjectPhase.phase_order)
            .first()
        )
        crud.create_journal_entry(
            db,
            project.id,
            "Decision: keep the first prototype direction and request a cleaner handle sample.",
            "decision",
            author_user_id=admin.id if admin else None,
        )
        crud.create_blocker(
            db,
            project.id,
            "Factory sample photos are late",
            description="Need photos before engineering review can move.",
            severity="high",
            phase_id=phase.id if phase else None,
            created_by_user_id=admin.id if admin else None,
        )
        return project.id
    finally:
        db.close()


def main():
    ARTIFACTS.mkdir(exist_ok=True)

    print("\n── 1. Source-level feed polish markers ──")
    template = read("app/templates/project_detail.html")
    css = read("app/static/css/styles.css")
    js = read("app/static/js/main.js")

    for marker, label in [
        ("timeline-history-card", "History rows render as event cards"),
        ("timeline-history-type-icon", "Each event has a type icon affordance"),
        ('role="tab"', "Filter controls expose tab semantics"),
        ('aria-selected="{% if chip', "Initial active filter has aria-selected state"),
        ("timeline-history-content", "Event card content is grouped"),
    ]:
        if marker in template:
            ok(label)
        else:
            fail(label, f"missing marker {marker}")

    for marker, label in [
        (".timeline-history-filters", "Segmented filter shell CSS exists"),
        (".timeline-history-chip.timeline-history-chip-active", "Active filter chip CSS exists"),
        (".timeline-history-card", "Event card CSS exists"),
        (".timeline-history-type-icon", "Type icon CSS exists"),
        (".timeline-history-empty", "Intentional empty state CSS exists"),
    ]:
        if marker in css:
            ok(label)
        else:
            fail(label, f"missing selector {marker}")

    if "aria-selected" in js and "timeline-history-chip-active" in js:
        ok("Filter script updates visual and ARIA selected state together")
    else:
        fail("filter selected-state JS", "missing aria-selected update")

    print("\n── 2. i18n parity preserved ──")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    if set(en) == set(zh):
        ok(f"en/zh parity ({len(en)} keys)")
    else:
        fail("i18n parity", f"diff={sorted(set(en) ^ set(zh))[:12]}")

    print("\n── 3. Browser event feed layout proof ──")
    session = login_session()
    if not session:
        fail("login", f"Could not log in to {BASE}")
    else:
        project_id = make_history_fixture()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 950})
                page = context.new_page()
                page.goto(f"{BASE}/auth/login")
                if "/auth/login" in page.url:
                    page.fill("input[name='username']", ADMIN)
                    page.fill("input[name='password']", ADMIN_PWD)
                    page.click("form[action='/auth/login'] button[type='submit']")
                    page.wait_for_load_state("networkidle")

                page.goto(f"{BASE}/projects/{project_id}#timeline-history")
                page.wait_for_load_state("networkidle")
                page.evaluate("() => window.setProjectWorkspace && window.setProjectWorkspace('timeline', false)")
                page.locator("#timeline-history").screenshot(
                    path=str(ARTIFACTS / "v13_ui_r4_history_desktop.png")
                )
                desktop = page.evaluate(
                    """
                    () => {
                      const q = s => document.querySelector(s);
                      const qa = s => Array.from(document.querySelectorAll(s));
                      const style = el => el ? getComputedStyle(el) : null;
                      const rect = el => el ? el.getBoundingClientRect() : null;
                      const section = q('#timeline-history');
                      const filters = q('.timeline-history-filters');
                      const active = q('.timeline-history-chip-active');
                      const card = q('.timeline-history-card');
                      const icon = q('.timeline-history-type-icon');
                      const title = q('.timeline-history-title');
                      const body = q('.timeline-history-body');
                      const meta = q('.timeline-history-meta');
                      const rowTypes = qa('.timeline-history-row').map(r => r.dataset.eventType);
                      return {
                        sectionText: section ? section.innerText : '',
                        filterDisplay: style(filters)?.display || null,
                        filterRadius: style(filters)?.borderRadius || null,
                        activeAria: active ? active.getAttribute('aria-selected') : null,
                        activeBg: style(active)?.backgroundColor || null,
                        cardDisplay: style(card)?.display || null,
                        cardColumns: style(card)?.gridTemplateColumns || null,
                        cardBorder: style(card)?.borderStyle || null,
                        cardRadius: style(card)?.borderRadius || null,
                        iconWidth: rect(icon)?.width || null,
                        titleText: title ? title.textContent.trim() : '',
                        bodyText: body ? body.textContent.trim() : '',
                        metaText: meta ? meta.textContent.trim() : '',
                        rowTypes,
                        docScrollWidth: document.documentElement.scrollWidth,
                        viewportWidth: window.innerWidth,
                      };
                    }
                    """
                )

                page.click('.timeline-history-chip[data-filter="blockers"]')
                filtered = page.evaluate(
                    """
                    () => {
                      const visibleRows = Array.from(document.querySelectorAll('.timeline-history-row'))
                        .filter(row => getComputedStyle(row).display !== 'none')
                        .map(row => row.dataset.eventType);
                      const active = document.querySelector('.timeline-history-chip-active');
                      const emptyFilter = document.querySelector('[data-empty-state="filter"]');
                      return {
                        activeFilter: active ? active.dataset.filter : null,
                        activeAria: active ? active.getAttribute('aria-selected') : null,
                        visibleRows,
                        emptyHidden: emptyFilter ? emptyFilter.hidden : null,
                      };
                    }
                    """
                )

                page.click('.timeline-history-chip[data-filter="files"]')
                empty_filter = page.evaluate(
                    """
                    () => {
                      const active = document.querySelector('.timeline-history-chip-active');
                      const emptyFilter = document.querySelector('[data-empty-state="filter"]');
                      return {
                        activeFilter: active ? active.dataset.filter : null,
                        activeAria: active ? active.getAttribute('aria-selected') : null,
                        emptyVisible: emptyFilter ? !emptyFilter.hidden : false,
                        emptyText: emptyFilter ? emptyFilter.textContent.trim() : '',
                      };
                    }
                    """
                )

                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(f"{BASE}/projects/{project_id}#timeline-history")
                page.wait_for_load_state("networkidle")
                page.evaluate("() => window.setProjectWorkspace && window.setProjectWorkspace('timeline', false)")
                page.click('.timeline-history-chip[data-filter="all"]')
                if page.locator("#bottomChatCollapseBtn").is_visible():
                    page.click("#bottomChatCollapseBtn")
                    page.wait_for_timeout(120)
                page.locator("#timeline-history").screenshot(
                    path=str(ARTIFACTS / "v13_ui_r4_history_small.png")
                )
                small = page.evaluate(
                    """
                    () => {
                      const card = document.querySelector('.timeline-history-card');
                      const filters = document.querySelector('.timeline-history-filters');
                      const style = el => el ? getComputedStyle(el) : null;
                      return {
                        cardColumns: style(card)?.gridTemplateColumns || null,
                        filterWidth: filters ? filters.getBoundingClientRect().width : null,
                        docScrollWidth: document.documentElement.scrollWidth,
                        viewportWidth: window.innerWidth,
                      };
                    }
                    """
                )
                browser.close()

            if desktop["filterDisplay"] == "flex" and desktop["filterRadius"] != "0px" and desktop["activeAria"] == "true":
                ok("History filters compute as app-native segmented chips")
            else:
                fail("history filter computed style", desktop)

            if desktop["cardDisplay"] == "grid" and desktop["cardBorder"] != "none" and desktop["cardRadius"] != "0px":
                ok("History events compute as bordered feed cards")
            else:
                fail("history card computed style", desktop)

            if desktop["iconWidth"] and desktop["iconWidth"] >= 30:
                ok("History events include a visible type icon")
            else:
                fail("history type icon", desktop)

            if desktop["titleText"] and desktop["metaText"] and desktop["rowTypes"]:
                ok("History card exposes summary, meta, and event type")
            else:
                fail("history card content", desktop)

            if "blockers" in desktop["rowTypes"] and "decisions" in desktop["rowTypes"]:
                ok("Fixture renders multiple event buckets for filter proof")
            else:
                fail("fixture event buckets", desktop["rowTypes"])

            if (
                filtered["activeFilter"] == "blockers"
                and filtered["activeAria"] == "true"
                and filtered["visibleRows"]
                and all(t == "blockers" for t in filtered["visibleRows"])
                and filtered["emptyHidden"] is True
            ):
                ok("Blocker filter keeps existing behavior while using polished controls")
            else:
                fail("blocker filter behavior", filtered)

            if (
                empty_filter["activeFilter"] == "files"
                and empty_filter["activeAria"] == "true"
                and empty_filter["emptyVisible"]
                and "No events match" in empty_filter["emptyText"]
            ):
                ok("No-match filter empty state is visible and intentional")
            else:
                fail("filter empty state", empty_filter)

            mobile_card_columns = (small["cardColumns"] or "").split()
            if small["docScrollWidth"] <= small["viewportWidth"] + 1 and len(mobile_card_columns) == 1:
                ok("Mobile history feed has no horizontal overflow and stacks cards")
            else:
                fail("mobile history layout", small)
        except Exception as exc:
            fail("browser proof", repr(exc))

    cleanup("uir4_test")

    print(f"\nPassed: {len(PASS)} / {len(PASS) + len(FAIL)}")
    if FAIL:
        print("Failures:")
        for name, reason in FAIL:
            print(f" - {name}: {reason}")
        return False
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
