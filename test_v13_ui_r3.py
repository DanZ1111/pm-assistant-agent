"""v1.3 UI-R3 — AI composer overlap + dock collapse control.

Requires the app running at http://localhost:8000.
Run: python3 test_v13_ui_r3.py
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
        if 'id="timeline-command-center"' in page and "timeline-action-row" in page:
            return project_id
    return None


def main():
    ARTIFACTS.mkdir(exist_ok=True)

    print("\n── 1. Source-level dock controls ──")
    component = read("app/templates/components/bottom_chat.html")
    js = read("app/static/js/main.js")
    css = read("app/static/css/styles.css")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))

    for marker, label in [
        ("bottomChatCollapseBtn", "bottom dock has a collapse button"),
        ("bottomChatRestoreBtn", "bottom dock has a compact restore button"),
        ("chat.collapse_dock", "collapse control is translated"),
        ("chat.expand_dock", "restore control is translated"),
    ]:
        if marker in component:
            ok(label)
        else:
            fail(label, f"missing marker {marker}")

    for marker, label in [
        ("function setDockCollapsed", "shared dock collapse state function exists"),
        ("assistant-dock-collapsed", "body state class is toggled"),
        ("dockInput.focus", "re-expand returns focus to the composer"),
    ]:
        if marker in js:
            ok(label)
        else:
            fail(label, f"missing JS marker {marker}")

    for marker, label in [
        (".bottom-chat-bar.is-collapsed .bottom-chat-form", "collapsed form moves out of the workspace"),
        (".bottom-chat-restore", "restore affordance is styled"),
        ("body.has-bottom-chat.assistant-dock-collapsed .main-content", "collapsed state reduces reserved padding"),
        ("scroll-margin-bottom: 168px", "Timeline action row reserves dock clearance"),
    ]:
        if marker in css:
            ok(label)
        else:
            fail(label, f"missing CSS marker {marker}")

    if set(en) == set(zh):
        ok(f"en/zh parity ({len(en)} keys)")
    else:
        fail("i18n parity", f"diff={sorted(set(en) ^ set(zh))[:12]}")
    for key in ["chat.collapse_dock", "chat.expand_dock"]:
        if key in en and key in zh:
            ok(f"{key} present in both bundles")
        else:
            fail(f"{key} parity", "missing")

    print("\n── 2. Browser overlap + collapse proof ──")
    session = login_session()
    if not session:
        fail("login", f"Could not log in to {BASE}")
    else:
        project_id = find_project_with_timeline(session)
        if not project_id:
            fail("project fixture", "no project with Timeline action row found")
        else:
            try:
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(headless=True)

                    def run_viewport(width, height, label):
                        page = browser.new_page(viewport={"width": width, "height": height})
                        page.goto(f"{BASE}/auth/login")
                        if "/auth/login" in page.url:
                            page.fill("input[name='username']", ADMIN)
                            page.fill("input[name='password']", ADMIN_PWD)
                            page.click("form[action='/auth/login'] button[type='submit']")
                            page.wait_for_load_state("networkidle")
                        page.goto(f"{BASE}/projects/{project_id}#timeline-command-center")
                        page.wait_for_load_state("networkidle")
                        page.evaluate("() => window.setProjectWorkspace && window.setProjectWorkspace('timeline', false)")
                        page.evaluate("""
                        () => {
                          const row = document.querySelector('.timeline-action-row');
                          if (row) row.scrollIntoView({block: 'end', inline: 'nearest'});
                        }
                        """)
                        page.wait_for_timeout(120)

                        expanded = page.evaluate("""
                        () => {
                          const rect = el => el ? el.getBoundingClientRect() : null;
                          const visible = el => {
                            if (!el) return false;
                            const s = getComputedStyle(el);
                            return s.display !== 'none' && s.visibility !== 'hidden' &&
                              Number(s.opacity || 1) > 0.05 && s.pointerEvents !== 'none';
                          };
                          const intersects = (a, b) => !!(a && b &&
                            a.left < b.right && a.right > b.left &&
                            a.top < b.bottom && a.bottom > b.top);
                          const row = document.querySelector('.timeline-action-row');
                          const form = document.querySelector('.bottom-chat-form');
                          const restore = document.querySelector('.bottom-chat-restore');
                          const finish = document.querySelector('.timeline-action-row [data-action="finish"]');
                          return {
                            bodyCollapsed: document.body.classList.contains('assistant-dock-collapsed'),
                            barCollapsed: document.querySelector('#bottomChatBar')?.classList.contains('is-collapsed') || false,
                            formVisible: visible(form),
                            restoreVisible: visible(restore),
                            rowRect: rect(row),
                            formRect: rect(form),
                            restoreRect: rect(restore),
                            overlapsForm: visible(form) && intersects(rect(row), rect(form)),
                            overlapsRestore: visible(restore) && intersects(rect(row), rect(restore)),
                            finishVisible: visible(finish),
                            finishText: finish ? finish.textContent.trim() : '',
                          };
                        }
                        """)
                        if not expanded["bodyCollapsed"] and expanded["formVisible"] and not expanded["restoreVisible"]:
                            ok(f"{label}: bottom dock is expanded by default")
                        else:
                            fail(f"{label}: default expanded state", expanded)
                        if not expanded["overlapsForm"] and expanded["finishVisible"]:
                            ok(f"{label}: expanded composer does not overlap Timeline actions")
                        else:
                            fail(f"{label}: expanded composer overlap", expanded)

                        page.click(".timeline-action-row [data-action='finish']")
                        if page.locator("#cc-action-form").is_visible():
                            ok(f"{label}: Finish Current Phase remains clickable with composer expanded")
                        else:
                            fail(f"{label}: finish action click", "inline form did not open")
                        page.locator("[data-cc-cancel]").first.click()

                        page.fill("#chatInputTextarea", f"draft preserved {label}")
                        page.click("#bottomChatCollapseBtn")
                        page.wait_for_timeout(160)
                        collapsed_path = ARTIFACTS / f"v13_ui_r3_{label}_collapsed.png"
                        page.screenshot(path=str(collapsed_path), full_page=False)
                        collapsed = page.evaluate("""
                        () => {
                          const rect = el => el ? el.getBoundingClientRect() : null;
                          const visible = el => {
                            if (!el) return false;
                            const s = getComputedStyle(el);
                            return s.display !== 'none' && s.visibility !== 'hidden' &&
                              Number(s.opacity || 1) > 0.05 && s.pointerEvents !== 'none';
                          };
                          const intersects = (a, b) => !!(a && b &&
                            a.left < b.right && a.right > b.left &&
                            a.top < b.bottom && a.bottom > b.top);
                          const row = document.querySelector('.timeline-action-row');
                          const form = document.querySelector('.bottom-chat-form');
                          const restore = document.querySelector('.bottom-chat-restore');
                          const input = document.querySelector('#chatInputTextarea');
                          return {
                            bodyCollapsed: document.body.classList.contains('assistant-dock-collapsed'),
                            barCollapsed: document.querySelector('#bottomChatBar')?.classList.contains('is-collapsed') || false,
                            formVisible: visible(form),
                            restoreVisible: visible(restore),
                            inputValue: input ? input.value : '',
                            rowRect: rect(row),
                            formRect: rect(form),
                            restoreRect: rect(restore),
                            overlapsForm: visible(form) && intersects(rect(row), rect(form)),
                            overlapsRestore: visible(restore) && intersects(rect(row), rect(restore)),
                          };
                        }
                        """)
                        if collapsed["bodyCollapsed"] and collapsed["barCollapsed"] and not collapsed["formVisible"] and collapsed["restoreVisible"]:
                            ok(f"{label}: dock collapses to compact restore button")
                        else:
                            fail(f"{label}: collapsed state", collapsed)
                        if not collapsed["overlapsForm"] and not collapsed["overlapsRestore"]:
                            ok(f"{label}: collapsed dock does not overlap Timeline actions")
                        else:
                            fail(f"{label}: collapsed overlap", collapsed)
                        if collapsed["inputValue"] == f"draft preserved {label}":
                            ok(f"{label}: collapse preserves composer draft")
                        else:
                            fail(f"{label}: draft preservation on collapse", collapsed)

                        page.click("#bottomChatRestoreBtn")
                        page.wait_for_timeout(160)
                        expanded_path = ARTIFACTS / f"v13_ui_r3_{label}_expanded.png"
                        page.screenshot(path=str(expanded_path), full_page=False)
                        restored = page.evaluate("""
                        () => {
                          const input = document.querySelector('#chatInputTextarea');
                          const form = document.querySelector('.bottom-chat-form');
                          const restore = document.querySelector('.bottom-chat-restore');
                          const s = form ? getComputedStyle(form) : null;
                          const rs = restore ? getComputedStyle(restore) : null;
                          return {
                            bodyCollapsed: document.body.classList.contains('assistant-dock-collapsed'),
                            formVisible: !!(s && s.display !== 'none' && Number(s.opacity || 1) > 0.05 && s.pointerEvents !== 'none'),
                            restoreVisible: !!(rs && rs.display !== 'none' && rs.visibility !== 'hidden' && !restore.hidden),
                            inputValue: input ? input.value : '',
                            activeMode: document.querySelector('[data-chat-mode].active')?.dataset.chatMode || '',
                            activeScope: document.querySelector('[data-chat-scope].active')?.dataset.chatScope || '',
                          };
                        }
                        """)
                        if not restored["bodyCollapsed"] and restored["formVisible"] and not restored["restoreVisible"]:
                            ok(f"{label}: restore expands the dock")
                        else:
                            fail(f"{label}: restore state", restored)
                        if restored["inputValue"] == f"draft preserved {label}" and restored["activeMode"] and restored["activeScope"]:
                            ok(f"{label}: restore preserves draft, mode, and scope")
                        else:
                            fail(f"{label}: preservation after restore", restored)
                        page.close()

                    run_viewport(1440, 950, "desktop")
                    run_viewport(390, 844, "small")
                    browser.close()
            except Exception as exc:
                fail("Playwright UI-R3 proof", repr(exc))

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
