"""
Build 1 — Playwright test suite
Run: python3 test_build1.py
"""

import sys
import time
from playwright.sync_api import sync_playwright, expect

BASE = "http://localhost:8000"
PASS = []
FAIL = []


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, reason):
    FAIL.append((name, reason))
    print(f"  ✗  {name}: {reason}")


def run_tests():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        # ----------------------------------------------------------------
        # 1. Navigation — root redirects to /projects
        # ----------------------------------------------------------------
        print("\n── Navigation ──")
        page.goto(BASE)
        page.wait_for_url("**/projects**")
        if "/projects" in page.url:
            ok("Root redirects to /projects")
        else:
            fail("Root redirect", f"landed on {page.url}")

        # Nav links visible
        for label in ["Projects", "Admin"]:
            link = page.locator(f"text={label}").first
            if link.is_visible():
                ok(f"Nav link '{label}' visible")
            else:
                fail(f"Nav link '{label}'", "not visible")

        # ----------------------------------------------------------------
        # 2. Empty state
        # ----------------------------------------------------------------
        print("\n── Empty state ──")
        page.goto(f"{BASE}/projects")
        # May or may not be empty depending on existing data — just check no 500
        if page.title():
            ok("Projects list loads (no 500)")
        else:
            fail("Projects list", "blank title")

        # ----------------------------------------------------------------
        # 3. Create project — name only (Needs Info badge expected)
        # ----------------------------------------------------------------
        print("\n── Create: name-only project ──")
        page.goto(f"{BASE}/projects/new")
        expect(page.locator("h1")).to_contain_text("New Project")
        ok("New Project form loads")

        page.fill("input[name='name']", "Test Minimal Project")
        page.click("button[type='submit']")
        page.wait_for_url("**/projects/**")

        # Should be on detail page
        if "/projects/" in page.url and page.url.rstrip("/").split("/")[-1].isdigit():
            ok("Name-only create → redirected to detail page")
        else:
            fail("Name-only create redirect", f"url={page.url}")

        # Needs Info banner must appear
        if page.locator(".alert-needs-info").is_visible():
            ok("Needs Info banner visible on detail (name-only project)")
        else:
            fail("Needs Info banner", "not visible on name-only project")

        # Product Thesis section must exist and show empty state
        thesis_section = page.locator(".thesis-empty")
        if thesis_section.is_visible():
            ok("Product Thesis empty-state message visible")
        else:
            fail("Product Thesis empty state", "not visible")

        minimal_id = page.url.rstrip("/").split("/")[-1]

        # Check badge on list page
        page.goto(f"{BASE}/projects")
        badge = page.locator(f"a[href='/projects/{minimal_id}'] .badge-needs-info, "
                             f"a[href='/projects/{minimal_id}'] .badge-delayed").first
        if badge.count() > 0 or page.locator(".badge-needs-info").count() > 0:
            ok("Needs Info badge visible on project list")
        else:
            fail("Needs Info badge on list", "not found")

        # ----------------------------------------------------------------
        # 4. Create project — all critical fields (no Needs Info badge)
        # ----------------------------------------------------------------
        print("\n── Create: fully complete project ──")
        page.goto(f"{BASE}/projects/new")

        page.fill("input[name='name']", "Damascus Chef Knife")
        page.fill("input[name='brand']", "Rblack")
        page.fill("input[name='sku']", "RB-CHEF-001")
        page.fill("input[name='product_type']", "fixed blade")
        page.fill("input[name='product_manager']", "Alice Chen")
        page.fill("input[name='engineer']", "Bob Wei")
        page.fill("input[name='factory']", "Guangzhou Factory A")
        page.fill("input[name='target_factory_cost']", "28.50")
        page.fill("input[name='target_msrp']", "129.99")
        page.fill("input[name='planned_launch_date']", "2025-12-01")
        thesis = (
            "Damascus Chef Knife targets professional home cooks and gift-buyers who want "
            "genuine Damascus steel at an accessible price. The product differentiates through "
            "authentic pattern-welded steel and premium fit and finish at under $130 MSRP. "
            "Rblack brand DNA fits this premium positioning. Main risk: Damascus supply chain costs."
        )
        page.fill("textarea[name='project_thesis']", thesis)
        # Select double prototype
        page.click("input[value='double']")
        page.click("button[type='submit']")
        page.wait_for_url("**/projects/**")

        full_id = page.url.rstrip("/").split("/")[-1]
        ok("Full project created → redirected to detail")

        # No Needs Info banner
        if not page.locator(".alert-needs-info").is_visible():
            ok("No Needs Info banner on complete project")
        else:
            fail("Needs Info banner", "incorrectly shown on complete project")

        # Product Thesis displayed prominently (thesis-box, not thesis-empty)
        if page.locator(".thesis-box").is_visible():
            ok("Product Thesis box shown (not empty state)")
        else:
            fail("Product Thesis box", "not visible on complete project")

        # Thesis text present
        if "Damascus" in page.locator(".thesis-text").inner_text():
            ok("Product Thesis text content correct")
        else:
            fail("Product Thesis text", "content missing or wrong")

        # Timeline section — 10 phases for double prototype
        rows = page.locator(".timeline-table tbody tr").count()
        if rows == 10:
            ok(f"Timeline: 10 phases generated for double-prototype project")
        else:
            fail("Timeline phases", f"expected 10, got {rows}")

        # ----------------------------------------------------------------
        # 5. Edit project
        # ----------------------------------------------------------------
        print("\n── Edit project ──")
        page.goto(f"{BASE}/projects/{full_id}/edit")
        expect(page.locator("h1")).to_contain_text("Edit Project")
        ok("Edit form loads")

        # Check field is pre-filled
        factory_val = page.input_value("input[name='factory']")
        if factory_val == "Guangzhou Factory A":
            ok("Edit form pre-fills existing field values")
        else:
            fail("Edit form prefill", f"factory='{factory_val}'")

        # Change target MSRP
        page.fill("input[name='target_msrp']", "139.99")
        page.click("button[type='submit']")
        page.wait_for_url(f"**/projects/{full_id}")

        # Verify updated value in sidebar
        page_text = page.locator(".detail-sidebar").inner_text()
        if "139.99" in page_text:
            ok("Edit saved — updated MSRP visible in sidebar")
        else:
            fail("Edit save", f"new MSRP not found; sidebar text: {page_text[:200]}")

        # Change log should record the edit
        change_log = page.locator(".change-log")
        if change_log.is_visible() and "139.99" in change_log.inner_text():
            ok("Change log records the MSRP edit")
        else:
            # Change log might not show yet if entry not there
            log_text = change_log.inner_text() if change_log.is_visible() else "(not visible)"
            fail("Change log MSRP entry", f"log text: {log_text[:300]}")

        # ----------------------------------------------------------------
        # 6. Filters on list page
        # ----------------------------------------------------------------
        print("\n── Filters ──")
        page.goto(f"{BASE}/projects")

        for filter_status, label in [
            ("all", "All"),
            ("active", "Active"),
            ("completed", "Completed"),
            ("archived", "Archived"),
        ]:
            resp = page.goto(f"{BASE}/projects?status={filter_status}")
            if resp.status == 200:
                ok(f"Filter '{label}' returns 200")
            else:
                fail(f"Filter '{label}'", f"status {resp.status}")

        # Brand filter dropdown
        page.goto(f"{BASE}/projects")
        brand_sel = page.locator("select[name='brand']")
        if brand_sel.is_visible():
            ok("Brand filter dropdown visible")
        else:
            fail("Brand filter dropdown", "not visible")

        # Search
        page.fill("input[name='search']", "Damascus")
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        if "Damascus" in page.content():
            ok("Search for 'Damascus' returns matching project")
        else:
            fail("Search", "no result found for 'Damascus'")

        # ----------------------------------------------------------------
        # 7. Card / Table view toggle
        # ----------------------------------------------------------------
        print("\n── View toggle ──")
        page.goto(f"{BASE}/projects")

        card_view = page.locator("#cardView")
        table_view = page.locator("#tableView")

        card_visible = not card_view.is_hidden()
        table_hidden = table_view.is_hidden()
        if card_visible and table_hidden:
            ok("Default view is card (table hidden)")
        else:
            fail("Default card view", f"card_visible={card_visible}, table_hidden={table_hidden}")

        page.click("#tableViewBtn")
        page.wait_for_function("document.getElementById('tableView') && !document.getElementById('tableView').classList.contains('d-none')", timeout=3000)
        card_hidden_now = card_view.is_hidden()
        table_visible_now = not table_view.is_hidden()
        if card_hidden_now and table_visible_now:
            ok("Table view toggle works (card hidden, table shown)")
        else:
            fail("Table view toggle", f"card_hidden={card_hidden_now}, table_visible={table_visible_now}")

        page.click("#cardViewBtn")
        page.wait_for_function("document.getElementById('cardView') && !document.getElementById('cardView').classList.contains('d-none')", timeout=3000)
        if not card_view.is_hidden():
            ok("Card view toggle back works")
        else:
            fail("Card view toggle back", "card still hidden")

        # ----------------------------------------------------------------
        # 8. Archive project
        # ----------------------------------------------------------------
        print("\n── Archive project ──")
        page.goto(f"{BASE}/projects/{minimal_id}")

        # Click archive button — use evaluate to bypass the confirm() dialog
        page.evaluate("window.confirm = () => true")
        page.locator(f"form[action='/projects/{minimal_id}/archive'] button").click()
        page.wait_for_url("**/projects")
        ok("Archive → redirected to /projects")

        # Should not appear in active filter
        page.goto(f"{BASE}/projects?status=active")
        if f"/projects/{minimal_id}" not in page.content():
            ok("Archived project not in Active filter")
        else:
            fail("Archive filter", "project still in Active filter")

        # Should appear in archived filter
        page.goto(f"{BASE}/projects?status=archived")
        if f"/projects/{minimal_id}" in page.content():
            ok("Archived project appears in Archived filter")
        else:
            fail("Archived filter", "project not found in Archived filter")

        # ----------------------------------------------------------------
        # 9. Database Inspector
        # ----------------------------------------------------------------
        print("\n── Database Inspector ──")
        page.goto(f"{BASE}/admin/database")
        if page.title():
            ok("Database Inspector loads (no 500)")
        else:
            fail("Database Inspector", "blank title")

        # Table stats visible
        if page.locator(".admin-stat-card").count() > 0:
            ok("Table stat cards visible")
        else:
            fail("Table stat cards", "none found")

        # Field usage table
        if page.locator(".admin-table").count() > 0:
            ok("Field usage table visible")
        else:
            fail("Field usage table", "not found")

        # ----------------------------------------------------------------
        # 10. 404 handling
        # ----------------------------------------------------------------
        print("\n── Error handling ──")
        resp = page.goto(f"{BASE}/projects/99999")
        if resp.status == 404:
            ok("Non-existent project returns 404")
        else:
            fail("404 handling", f"got status {resp.status}")

        # ----------------------------------------------------------------
        # 11. Project form — cancel button
        # ----------------------------------------------------------------
        print("\n── Form UX ──")
        page.goto(f"{BASE}/projects/new")
        cancel = page.locator("a", has_text="Cancel")
        if cancel.is_visible():
            ok("Cancel button visible on create form")
        else:
            fail("Cancel button", "not visible")

        # Submit empty name → should show error, NOT redirect
        page.goto(f"{BASE}/projects/new")
        # Clear name and submit
        page.fill("input[name='name']", "")
        page.click("button[type='submit']")
        time.sleep(0.5)
        if "/projects/new" in page.url or "required" in page.content().lower() or "alert" in page.content().lower():
            ok("Empty name submission handled (validation)")
        else:
            fail("Empty name validation", f"unexpectedly redirected to {page.url}")

        # ----------------------------------------------------------------
        # Report
        # ----------------------------------------------------------------
        browser.close()

        print("\n" + "="*60)
        print(f"PASSED: {len(PASS)}")
        print(f"FAILED: {len(FAIL)}")
        if FAIL:
            print("\nFailed tests:")
            for name, reason in FAIL:
                print(f"  ✗ {name}: {reason}")
        print("="*60)

        return len(FAIL) == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
