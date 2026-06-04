"""v1.3 Build 03 — Overview Product Concept tests.

Requires the app running at http://localhost:8000, or set BASE_URL.
Run: python3 test_v13_build03.py
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
PASS, FAIL = [], []

ADMIN, ADMIN_PWD = "admin", "show me the money"
VIEWER_USER, VIEWER_PWD = "testviewer_b8", "viewerpass8!"
PROJECT_NAME = "v13_build03_product_concept"
IDEA_NAME = "v13_build03_reference_idea"


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


def cleanup():
    conn = sqlite3.connect(ROOT / "pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM ideas WHERE name LIKE ?", ("v13_build03_%",))
        idea_ids = [row[0] for row in cur.fetchall()]
        for idea_id in idea_ids:
            cur.execute("DELETE FROM project_ideas WHERE idea_id = ?", (idea_id,))
            cur.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))

        cur.execute("SELECT id FROM projects WHERE name = ?", (PROJECT_NAME,))
        project_ids = [row[0] for row in cur.fetchall()]
        for pid in project_ids:
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
    thesis = (
        "This compact marine folding knife exists for coastal EDC users who need "
        "a corrosion-resistant utility blade that still feels refined enough for "
        "daily carry. The concept balances saltwater durability, one-hand use, "
        "simple maintenance, and a premium-but-accessible price story."
    )
    r = session.post(
        f"{BASE}/projects/new",
        data={
            "name": PROJECT_NAME,
            "brand": "Rblack",
            "product_manager": ADMIN,
            "engineer": "Concept Engineer",
            "factory": "Concept Factory",
            "target_factory_cost": "under 120 RMB",
            "target_msrp": "$70-100",
            "planned_launch_date": "2026-12-01",
            "project_thesis": thesis,
            "prototype_rounds": "single",
            "submission_token": mint_token(session),
        },
        allow_redirects=False,
        timeout=5,
    )
    if r.status_code != 303:
        fail("create project", f"expected 303, got {r.status_code}: {r.text[:200]}")
        return None
    pid = r.headers.get("location", "").rstrip("/").split("/")[-1]
    return int(pid) if pid.isdigit() else None


def assert_i18n_parity_and_labels():
    en = json.loads((ROOT / "app/i18n/en.json").read_text(encoding="utf-8"))
    zh = json.loads((ROOT / "app/i18n/zh.json").read_text(encoding="utf-8"))
    if set(en) == set(zh):
        ok(f"i18n parity preserved ({len(en)} keys)")
    else:
        fail(
            "i18n parity",
            f"missing_zh={sorted(set(en) - set(zh))[:8]} extra_zh={sorted(set(zh) - set(en))[:8]}",
        )

    expected = {
        "section.product_concept": ("Product Concept", "产品理念"),
        "concept.thesis_label": ("What is this product, and why?", "这款产品是什么？为什么存在？"),
        "concept.references": ("Concept references", "灵感来源"),
        "concept.no_references": ("No concept references linked yet.", "暂无关联的灵感记录。"),
        "concept.add_reference": ("Add reference", "添加灵感"),
        "pulse.thesis_needed_title": ("Product Concept needs work", "产品理念需要完善"),
    }
    mismatches = [
        key for key, (en_val, zh_val) in expected.items()
        if en.get(key) != en_val or zh.get(key) != zh_val
    ]
    if not mismatches:
        ok("Build 03 exact EN/ZH labels are locked")
    else:
        fail("Build 03 i18n labels", f"mismatches: {mismatches}")


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

    pid = create_project(admin_s)
    if not pid:
        summary()
        return False
    ok(f"fake project created ({pid})")

    print("\n── Static locks ──")
    template = (ROOT / "app/templates/project_detail.html").read_text(encoding="utf-8")
    if 'id="product-concept"' in template and 'id="thesis"' in template:
        ok("Product Concept primary id plus #thesis compatibility anchor exist")
    else:
        fail("concept anchors", "missing product-concept or thesis anchor")
    if "<section" in template and 'section class="detail-section" id="inspired-by"' not in template:
        ok("Inspired By is no longer a standalone peer section")
    else:
        fail("standalone Inspired By", "old standalone section still appears")
    assert_i18n_parity_and_labels()

    print("\n── Browser behavior ──")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 950})
        login_page(page)
        page.goto(f"{BASE}/projects/{pid}")
        page.wait_for_load_state("networkidle")

        if page.locator("#project-pulse").bounding_box()["y"] < page.locator("#product-concept").bounding_box()["y"]:
            ok("Product Concept appears after Project Pulse")
        else:
            fail("Product Concept order", "not after Pulse")
        if page.locator("#product-concept").bounding_box()["y"] < page.locator("#files").bounding_box()["y"]:
            ok("Product Concept appears before Files/Renderings")
        else:
            fail("Product Concept before files", "files appear first")

        concept_text = page.locator("#product-concept").inner_text()
        if "Product Concept" in concept_text and "What is this product, and why?" in concept_text:
            ok("Product Concept header and concept label render")
        else:
            fail("Product Concept text", concept_text[:300])

        anchor_inside = page.evaluate("""
            () => {
              const concept = document.querySelector('#product-concept');
              const thesis = document.querySelector('#thesis');
              return Boolean(concept && thesis && concept.contains(thesis));
            }
        """)
        if anchor_inside:
            ok("#thesis compatibility anchor is inside Product Concept")
        else:
            fail("thesis compatibility anchor", "not inside Product Concept")

        page.goto(f"{BASE}/projects/{pid}#thesis")
        page.wait_for_load_state("networkidle")
        if page.locator("#product-concept").is_visible():
            ok("Old #thesis deep link lands in Overview Product Concept")
        else:
            fail("#thesis deep link", "Product Concept not visible")

        page.click("#product-concept button:has-text('Edit')")
        if page.locator("#thesisEditForm").is_visible():
            ok("Inline concept/prose edit form still opens")
        else:
            fail("inline edit open", "form not visible")
        updated = (
            "Updated Build 03 concept prose. This marine folder concept exists "
            "to prove the old thesis edit route still saves the product concept "
            "without any schema or route change."
        )
        page.fill("#thesisEditForm textarea[name='project_thesis']", updated)
        page.click("#thesisEditForm button[type='submit']")
        page.wait_for_load_state("networkidle")
        if updated[:40] in page.locator("#product-concept").inner_text():
            ok("Inline edit still saves through /thesis/inline-edit")
        else:
            fail("inline edit save", page.locator("#product-concept").inner_text()[:300])

        page.click("#product-concept button:has-text('Extract')")
        if page.locator("#thesisExtractForm").is_visible():
            ok("Business-plan re-extract form still appears for admin")
        else:
            fail("re-extract form", "not visible after click")

        page.click("#product-concept button:has-text('Add reference')")
        page.wait_for_selector("#createLinkIdeaModal.show", timeout=3000)
        if page.locator("#createLinkIdeaModal").is_visible():
            ok("Create & Link Idea modal still opens from Product Concept")
        else:
            fail("create-link modal", "not visible")
        page.fill("#createLinkIdeaModal input[name='name']", IDEA_NAME)
        page.select_option("#createLinkIdeaModal select[name='idea_type']", "material")
        page.select_option("#createLinkIdeaModal select[name='source']", "factory")
        page.fill("#createLinkIdeaModal textarea[name='description']", "Factory-sourced corrosion material inspiration.")
        page.fill("#createLinkIdeaModal input[name='link_note']", "Use as the concept reference.")
        page.click("#createLinkIdeaModal button[type='submit']")
        page.wait_for_load_state("networkidle")

        refs = page.locator("#product-concept #inspired-by")
        refs_text = refs.inner_text()
        if refs.is_visible() and IDEA_NAME in refs_text and refs.locator(".concept-reference-chip").count() >= 1:
            ok("Linked idea renders as internal concept-reference chip")
        else:
            fail("concept reference chip", refs_text[:300])
        if page.locator("section#inspired-by").count() == 0:
            ok("No standalone section#inspired-by remains")
        else:
            fail("standalone inspired-by section", "section#inspired-by still exists")

        viewer_page = browser.new_page(viewport={"width": 1280, "height": 900})
        login_page(viewer_page, VIEWER_USER, VIEWER_PWD)
        viewer_page.goto(f"{BASE}/projects/{pid}")
        viewer_page.wait_for_load_state("networkidle")
        viewer_refs_text = viewer_page.locator("#product-concept #inspired-by").inner_text()
        if IDEA_NAME in viewer_refs_text:
            ok("Viewer sees concept references")
        else:
            fail("viewer references", viewer_refs_text[:300])
        viewer_controls = viewer_page.locator(
            "#product-concept #inspired-by button, "
            "#product-concept #inspired-by form, "
            "#product-concept button:has-text('Edit'), "
            "#product-concept button:has-text('Add reference')"
        )
        if viewer_controls.count() == 0:
            ok("Viewer sees no concept mutation controls")
        else:
            fail("viewer mutation controls", f"count={viewer_controls.count()}")

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
