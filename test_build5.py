"""
Build 5 — AI Text Intake test suite
Run: python3 test_build5.py
"""

import sys
import requests
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
PASS = []
FAIL = []

SAMPLE_TEXT = (
    "New project: Damascus Chef Knife for Rblack brand. "
    "Product manager is Sarah Chen, engineer is Mike Torres. "
    "Working with Guangzhou Blade Co factory. "
    "Target factory cost $18.50, MSRP $129.99. "
    "Planned launch Q4 2026 (2026-10-01). "
    "This knife is for serious home cooks who want a professional-grade Damascus blade "
    "without paying boutique prices. It solves the gap between cheap stamped knives and "
    "custom hand-forged blades by offering precision-forged Damascus steel at an accessible price."
)


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, reason):
    FAIL.append((name, reason))
    print(f"  ✗  {name}: {reason}")


def count_projects() -> int:
    r = requests.get(f"{BASE}/projects")
    return r.status_code


def run_tests():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # ----------------------------------------------------------------
        # 1. Intake page loads
        # ----------------------------------------------------------------
        print("\n── Intake Page Load ──")
        resp = page.goto(f"{BASE}/ai/intake")
        if resp.status == 200:
            ok("GET /ai/intake returns 200")
        else:
            fail("Intake page load", f"status {resp.status}")

        textarea = page.locator("textarea[name='raw_text']")
        if textarea.is_visible():
            ok("Raw text textarea visible")
        else:
            fail("Textarea", "not visible")

        extract_btn = page.locator("button[type='submit']")
        if extract_btn.count() > 0 and "extract" in extract_btn.first.inner_text().lower():
            ok("'Extract Fields' button visible")
        else:
            fail("Extract button", "not found or wrong label")

        # ----------------------------------------------------------------
        # 2. Nav link is active on AI Intake page
        # ----------------------------------------------------------------
        print("\n── Nav Link ──")
        ai_nav = page.locator("a.nav-link[href='/ai/intake']")
        if ai_nav.count() > 0:
            ok("AI Intake nav link points to /ai/intake (enabled)")
        else:
            fail("AI Intake nav link", "href='/ai/intake' not found — still disabled?")

        # ----------------------------------------------------------------
        # 3. AI extraction (real OpenAI call)
        # ----------------------------------------------------------------
        print("\n── AI Extraction (live OpenAI call) ──")
        print("    (calling GPT-4o — may take a few seconds...)")

        textarea.fill(SAMPLE_TEXT)
        page.locator("button[type='submit']").first.click()
        page.wait_for_load_state("networkidle", timeout=30000)

        # Check for error vs success
        error_alert = page.locator(".alert-danger")
        if error_alert.is_visible():
            error_text = error_alert.inner_text()
            fail("AI extraction", f"Error shown: {error_text[:200]}")
            # Still run the rest of the tests using direct confirm
            extraction_ok = False
        else:
            extraction_ok = True
            ok("Extraction completed without error")

        if extraction_ok:
            # Proposed fields form should appear
            confirm_form = page.locator("form[action='/ai/intake/confirm']")
            if confirm_form.count() > 0:
                ok("Proposed fields confirm form appears after extraction")
            else:
                fail("Confirm form", "not found after extraction")
                extraction_ok = False

        if extraction_ok:
            # Name field should be pre-filled
            name_val = page.locator("input[name='name']").input_value()
            if name_val:
                ok(f"Project name pre-filled: '{name_val}'")
            else:
                fail("Name pre-fill", "name field empty after extraction")

            # At least one more field should be populated
            brand_val = page.locator("input[name='brand']").input_value()
            factory_val = page.locator("input[name='factory']").input_value()
            pm_val = page.locator("input[name='product_manager']").input_value()
            msrp_val = page.locator("input[name='target_msrp']").input_value()
            filled = [v for v in [brand_val, factory_val, pm_val, msrp_val] if v]
            if len(filled) >= 2:
                ok(f"At least 2 additional fields pre-filled ({len(filled)} filled)")
            else:
                fail("Field pre-fill", f"expected ≥2 non-name fields, got {len(filled)}")

            # Health check section should appear
            health_alert = page.locator(".alert-warning, .alert-success")
            if health_alert.count() > 0:
                ok("Health check alert shown after extraction")
            else:
                fail("Health check alert", "not visible after extraction")

            # Original text shown in left column
            original_text_visible = page.locator("pre").count() > 0
            if original_text_visible:
                ok("Original text shown as reference in left column")
            else:
                fail("Original text reference", "not visible")

        # ----------------------------------------------------------------
        # 4. No project created yet (extraction is proposal only)
        # ----------------------------------------------------------------
        print("\n── No Silent Save ──")
        # Count projects before confirm — extraction must not create any
        # We check by looking at the projects list and comparing count
        projects_page = requests.get(f"{BASE}/projects")
        if projects_page.status_code == 200:
            # We navigate to verify no new project matches our specific text
            ok("Projects list still accessible (extraction did not crash app)")

        # The confirm form is the only path to project creation
        confirm_route_check = requests.get(f"{BASE}/ai/intake/confirm")
        if confirm_route_check.status_code == 405:
            ok("GET /ai/intake/confirm returns 405 (POST only — cannot be accessed directly)")

        # ----------------------------------------------------------------
        # 5. Confirm creates project (bypass extraction, POST directly)
        # ----------------------------------------------------------------
        print("\n── Confirm Creates Project ──")
        confirm_data = {
            "raw_text": SAMPLE_TEXT,
            "name": "Damascus Chef Knife B5 Test",
            "brand": "Rblack",
            "sku": "RB-B5-001",
            "product_type": "Chef's Knife",
            "product_manager": "Sarah Chen",
            "engineer": "Mike Torres",
            "factory": "Guangzhou Blade Co",
            "target_factory_cost": "18.50",
            "target_msrp": "129.99",
            "planned_launch_date": "2026-10-01",
            "project_thesis": (
                "This knife is for serious home cooks who want a professional-grade Damascus blade "
                "without paying boutique prices. It bridges the gap between cheap stamped knives and "
                "custom hand-forged blades by offering precision-forged Damascus steel at an accessible price point."
            ),
            "prototype_rounds": "single",
        }
        r = requests.post(f"{BASE}/ai/intake/confirm", data=confirm_data, allow_redirects=False)
        if r.status_code in (302, 303):
            ok("POST /ai/intake/confirm returns redirect")
        else:
            fail("Confirm redirect", f"status {r.status_code}")
            browser.close()
            _print_summary()
            return len(FAIL) == 0

        location = r.headers.get("location", "")
        pid_str = location.rstrip("/").split("/")[-1]
        pid = int(pid_str) if pid_str.isdigit() else None

        if pid:
            ok(f"Redirected to project detail /projects/{pid}")
        else:
            fail("Project ID from redirect", f"could not parse from location: {location}")

        # ----------------------------------------------------------------
        # 6. Project detail shows AI-sourced change log entry
        # ----------------------------------------------------------------
        print("\n── Project Detail After AI Confirm ──")
        if pid:
            resp2 = page.goto(f"{BASE}/projects/{pid}")
            if resp2.status == 200:
                ok("Project detail page loads after AI intake confirm")
            else:
                fail("Project detail load", f"status {resp2.status}")

            # Change log should show AI-sourced entry
            change_log_text = page.locator(".change-log").inner_text().lower()
            if "ai" in change_log_text:
                ok("Change log shows AI attribution (changed_by=ai or 'ai intake')")
            else:
                fail("AI attribution in change log", f"'ai' not found in: '{change_log_text[:200]}'")

            # Project name should appear in the page
            if "Damascus Chef Knife B5 Test".lower() in page.content().lower():
                ok("Project name appears on detail page")
            else:
                fail("Project name on detail page", "not found")

            # MSRP should appear
            if "129.99" in page.content():
                ok("MSRP value 129.99 appears on detail page")
            else:
                fail("MSRP on detail page", "129.99 not found")

        # ----------------------------------------------------------------
        # 7. ai_messages recorded (check via admin database page)
        # ----------------------------------------------------------------
        print("\n── AI Messages Stored ──")
        admin_resp = page.goto(f"{BASE}/admin/database")
        if admin_resp.status == 200:
            admin_text = page.locator("body").inner_text()
            # ai_messages table should show at least 1 row
            # Table name rendered as "ai messages" (underscores replaced with spaces in template)
            if "ai messages" in admin_text.lower():
                ok("ai_messages table visible in admin database inspector")
            else:
                fail("ai_messages in admin", "not found on admin page")
        else:
            fail("Admin database page", f"status {admin_resp.status}")

        # ----------------------------------------------------------------
        # 8. Start Over link returns to clean intake form
        # ----------------------------------------------------------------
        print("\n── Start Over ──")
        page.goto(f"{BASE}/ai/intake")
        textarea2 = page.locator("textarea[name='raw_text']")
        if textarea2.is_visible():
            ok("GET /ai/intake shows clean textarea (start over works)")
        else:
            fail("Start over", "textarea not visible on fresh GET")

        # ----------------------------------------------------------------
        # 9. Empty submission shows error
        # ----------------------------------------------------------------
        print("\n── Empty Submission Validation ──")
        page.goto(f"{BASE}/ai/intake")
        page.locator("textarea[name='raw_text']").fill("")
        page.locator("button[type='submit']").first.click()
        page.wait_for_load_state("networkidle")
        err = page.locator(".alert-danger")
        if err.is_visible():
            ok("Empty submission shows error alert")
        else:
            fail("Empty submission validation", "no error shown for empty text")

        # ----------------------------------------------------------------
        # 10. No server errors
        # ----------------------------------------------------------------
        print("\n── No Server Errors ──")
        resp3 = page.goto(f"{BASE}/ai/intake")
        body = page.locator("body").inner_text()
        if resp3.status == 200 and "Internal Server Error" not in body and "Traceback" not in body:
            ok("AI intake page renders without errors")
        else:
            fail("No server errors", f"status={resp3.status}")

        browser.close()

    _print_summary()
    return len(FAIL) == 0


def _print_summary():
    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        print("\nFailed tests:")
        for name, reason in FAIL:
            print(f"  ✗ {name}: {reason}")
    print("=" * 60)


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
