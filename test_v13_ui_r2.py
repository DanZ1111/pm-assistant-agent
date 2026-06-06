"""v1.3 UI-R2 — Timeline Command Dashboard rescue.

Requires the app running at http://localhost:8000.
Run: python3 test_v13_ui_r2.py
"""
import json
import os
import re
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


def find_project_with_timeline(session):
    projects_html = session.get(f"{BASE}/projects", timeout=8).text
    for project_id in re.findall(r'href="/projects/(\d+)"', projects_html):
        page = session.get(f"{BASE}/projects/{project_id}", timeout=8).text
        if 'id="timeline-command-center"' in page and "timeline-phase-strip" in page:
            return project_id
    return None


def main():
    ARTIFACTS.mkdir(exist_ok=True)

    print("\n── 1. Source-level dashboard structure ──")
    template = read("app/templates/project_detail.html")
    css = read("app/static/css/styles.css")
    for marker, label in [
        ("timeline-command-card", "Command Center is wrapped in one dashboard card"),
        ("timeline-command-card-head", "Dashboard has a coherent header block"),
        ("timeline-command-support-grid", "Blocker and assistant areas share a support grid"),
        ("timeline-assistant-suggestion", "Assistant suggestion is an intentional panel"),
        ("timeline-map-section", "Detailed Timeline table is secondary section"),
    ]:
        if marker in template:
            ok(label)
        else:
            fail(label, f"missing marker {marker}")

    if "timeline-placeholder-badge" not in template and "timeline.placeholder_label" not in template:
        ok("User-facing placeholder badge copy removed from Timeline command dashboard")
    else:
        fail("placeholder copy removal", "template still renders placeholder badge/copy")
    if "'#timeline-command-center'" in template and "hash === '#timeline-command-center'" in template:
        ok("Timeline tab targets the command dashboard while preserving hash activation")
    else:
        fail("Timeline tab hash target", "Timeline workspace does not target #timeline-command-center")

    for selector, label in [
        (".timeline-command-card", "Dashboard card CSS exists"),
        (".timeline-command-card-head", "Dashboard header CSS exists"),
        (".timeline-command-support-grid", "Dashboard support grid CSS exists"),
        (".timeline-assistant-suggestion", "Assistant suggestion CSS exists"),
        (".timeline-map-section", "Secondary Timeline map CSS exists"),
    ]:
        if selector in css:
            ok(label)
        else:
            fail(label, f"missing selector {selector}")

    print("\n── 2. i18n parity + rescue labels ──")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    if set(en) == set(zh):
        ok(f"en/zh parity ({len(en)} keys)")
    else:
        fail("i18n parity", f"diff={sorted(set(en) ^ set(zh))[:12]}")

    required_keys = [
        "timeline.execution_workspace",
        "timeline.command_center",
        "timeline.command_center_subtitle",
        "timeline.ai_nudge_title",
        "timeline.ai_nudge_body",
        "timeline.map_title",
        "timeline.map_hint",
        "timeline.placeholder_label",
    ]
    missing = [k for k in required_keys if k not in en or k not in zh]
    if not missing:
        ok(f"All {len(required_keys)} UI-R2 i18n keys present")
    else:
        fail("UI-R2 i18n keys", missing)

    if en.get("timeline.ai_nudge_title") == "Assistant suggestions" and "Placeholder" not in en.get("timeline.ai_nudge_body", ""):
        ok("Assistant suggestion label is product-facing, not raw placeholder copy")
    else:
        fail("assistant label", en.get("timeline.ai_nudge_title"))

    print("\n── 3. Browser dashboard layout proof ──")
    session = login_session()
    if not session:
        fail("login", f"Could not log in to {BASE}")
    else:
        project_id = find_project_with_timeline(session)
        if not project_id:
            fail("project fixture", "no project with Timeline Command Center found")
        else:
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

                    page.goto(f"{BASE}/projects/{project_id}")
                    page.wait_for_load_state("networkidle")
                    page.evaluate("() => window.setProjectWorkspace && window.setProjectWorkspace('timeline', false)")
                    page.locator(".timeline-command-card").screenshot(
                        path=str(ARTIFACTS / "v13_ui_r2_timeline_desktop.png")
                    )
                    desktop = page.evaluate(
                        """
                        () => {
                          const q = s => document.querySelector(s);
                          const style = el => el ? getComputedStyle(el) : null;
                          const rect = el => el ? el.getBoundingClientRect() : null;
                          const card = q('.timeline-command-card');
                          const head = q('.timeline-command-card-head');
                          const phase = q('.timeline-phase-strip');
                          const tiles = q('.timeline-tiles-grid');
                          const support = q('.timeline-command-support-grid');
                          const actions = q('.timeline-action-row');
                          const map = q('.timeline-map-section');
                          const text = card ? card.innerText : '';
                          return {
                            hasCard: !!card,
                            cardDisplay: style(card)?.display || null,
                            cardRadius: style(card)?.borderRadius || null,
                            cardBorder: style(card)?.borderStyle || null,
                            headDisplay: style(head)?.display || null,
                            phaseDisplay: style(phase)?.display || null,
                            phaseDirection: style(phase)?.flexDirection || null,
                            tilesDisplay: style(tiles)?.display || null,
                            tilesColumns: style(tiles)?.gridTemplateColumns || null,
                            supportDisplay: style(support)?.display || null,
                            supportColumns: style(support)?.gridTemplateColumns || null,
                            cardRect: rect(card),
                            actionsRect: rect(actions),
                            mapRect: rect(map),
                            hasPlaceholderCopy: text.includes('AI Nudge Placeholder') || text.includes('Placeholder'),
                            actionText: actions ? actions.innerText : '',
                          };
                        }
                        """
                    )

                    page.set_viewport_size({"width": 390, "height": 844})
                    page.goto(f"{BASE}/projects/{project_id}")
                    page.wait_for_load_state("networkidle")
                    page.evaluate("() => window.setProjectWorkspace && window.setProjectWorkspace('timeline', false)")
                    page.locator(".timeline-command-card").screenshot(
                        path=str(ARTIFACTS / "v13_ui_r2_timeline_small.png")
                    )
                    small = page.evaluate(
                        """
                        () => {
                          const q = s => document.querySelector(s);
                          const style = el => el ? getComputedStyle(el) : null;
                          const card = q('.timeline-command-card');
                          const tiles = q('.timeline-tiles-grid');
                          const support = q('.timeline-command-support-grid');
                          return {
                            cardWidth: card ? card.getBoundingClientRect().width : null,
                            viewportWidth: window.innerWidth,
                            docScrollWidth: document.documentElement.scrollWidth,
                            tilesColumns: style(tiles)?.gridTemplateColumns || null,
                            supportColumns: style(support)?.gridTemplateColumns || null,
                          };
                        }
                        """
                    )
                    browser.close()

                if desktop["hasCard"] and desktop["cardDisplay"] == "block" and desktop["cardBorder"] != "none" and desktop["cardRadius"] != "0px":
                    ok("Timeline command dashboard computes as a bordered card")
                else:
                    fail("dashboard card computed style", desktop)
                if desktop["headDisplay"] == "flex":
                    ok("Dashboard header computes as horizontal flex layout")
                else:
                    fail("dashboard header layout", desktop)
                if desktop["phaseDisplay"] == "flex" and desktop["phaseDirection"] == "row":
                    ok("Phase strip computes as horizontal readable row")
                else:
                    fail("phase strip layout", desktop)
                if desktop["tilesDisplay"] == "grid" and len(desktop["tilesColumns"].split()) == 3:
                    ok("Current phase / next action / deadline tiles compute as 3-column grid")
                else:
                    fail("tile grid layout", desktop)
                if desktop["supportDisplay"] == "grid" and len(desktop["supportColumns"].split()) == 2:
                    ok("Blocker and assistant suggestion compute as 2-column dashboard support row")
                else:
                    fail("support grid layout", desktop)
                if desktop["actionsRect"] and desktop["cardRect"] and desktop["actionsRect"]["bottom"] <= desktop["cardRect"]["bottom"] + 1:
                    ok("Timeline action row belongs inside the dashboard card")
                else:
                    fail("action row placement", desktop)
                if desktop["mapRect"] and desktop["cardRect"] and desktop["mapRect"]["top"] > desktop["cardRect"]["bottom"]:
                    ok("Detailed Timeline map is visually secondary after command dashboard")
                else:
                    fail("timeline map placement", desktop)
                if not desktop["hasPlaceholderCopy"]:
                    ok("Dashboard first fold does not leak raw placeholder copy")
                else:
                    fail("placeholder copy leak", desktop)
                if "Finish Current Phase" in desktop["actionText"]:
                    ok("Existing Finish Current Phase action remains available")
                else:
                    fail("finish action visibility", desktop["actionText"])

                if small["docScrollWidth"] <= small["viewportWidth"] + 1 and small["cardWidth"] <= small["viewportWidth"]:
                    ok("Small viewport command dashboard fits without horizontal page overflow")
                else:
                    fail("small viewport overflow", small)
                if len(small["tilesColumns"].split()) == 1 and len(small["supportColumns"].split()) == 1:
                    ok("Small viewport stacks dashboard tiles/support sections")
                else:
                    fail("small viewport stacked layout", small)
            except Exception as exc:
                fail("Playwright dashboard proof", repr(exc))

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
