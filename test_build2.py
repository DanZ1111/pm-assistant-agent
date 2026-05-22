"""
Build 2 — Timeline + Delay test suite
Run: python3 test_build2.py
"""

import sys
import time
import requests
from datetime import date, timedelta
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
PASS = []
FAIL = []


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, reason):
    FAIL.append((name, reason))
    print(f"  ✗  {name}: {reason}")


def create_project(name, prototype_rounds="single", **kwargs):
    data = {"name": name, "prototype_rounds": prototype_rounds, **kwargs}
    r = requests.post(f"{BASE}/projects/new", data=data, allow_redirects=False)
    location = r.headers.get("location", "")
    pid = location.rstrip("/").split("/")[-1]
    return int(pid) if pid.isdigit() else None


def run_tests():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # ----------------------------------------------------------------
        # 1. Phase templates — single vs double
        # ----------------------------------------------------------------
        print("\n── Phase Templates ──")

        p1 = create_project("Single Prototype Knife", prototype_rounds="single")
        p2 = create_project("Double Prototype Knife", prototype_rounds="double")

        page.goto(f"{BASE}/projects/{p1}")
        rows = page.locator(".timeline-table tbody tr").count()
        if rows == 8:
            ok("Single prototype → 8 phases created")
        else:
            fail("Single prototype phase count", f"expected 8, got {rows}")

        page.goto(f"{BASE}/projects/{p2}")
        rows = page.locator(".timeline-table tbody tr").count()
        if rows == 10:
            ok("Double prototype → 10 phases created")
        else:
            fail("Double prototype phase count", f"expected 10, got {rows}")

        # ----------------------------------------------------------------
        # 2. Phase edit modal
        # ----------------------------------------------------------------
        print("\n── Phase Edit Modal ──")

        page.goto(f"{BASE}/projects/{p1}")

        # Edit button visible on first phase row
        edit_btns = page.locator(".btn-phase-edit")
        if edit_btns.count() == 8:
            ok("Edit button on every phase row (8 total)")
        else:
            fail("Edit buttons count", f"expected 8, got {edit_btns.count()}")

        # Open modal by clicking first edit button
        edit_btns.first.click()
        page.wait_for_selector("#phaseModal.show", timeout=3000)
        if page.locator("#phaseModal").is_visible():
            ok("Phase edit modal opens")
        else:
            fail("Phase edit modal", "did not open")

        # Check modal pre-fills phase name
        phase_name_val = page.input_value("#modalPhaseName")
        if phase_name_val == "Design":
            ok("Modal pre-fills phase name ('Design')")
        else:
            fail("Modal prefill phase name", f"got '{phase_name_val}'")

        # Change status to in_progress and set planned end date to yesterday (trigger delay)
        yesterday = (date.today() - timedelta(days=3)).isoformat()
        page.select_option("#modalStatus", "in_progress")
        page.fill("#modalPlannedEnd", yesterday)
        page.fill("#modalOwner", "Alice")
        page.fill("#modalNotes", "Design phase started, working on initial sketches.")
        page.click("#phaseEditForm button[type='submit']")

        page.wait_for_load_state("networkidle")
        if "/projects/" in page.url:
            ok("Phase edit saves and stays on project page")
        else:
            fail("Phase edit redirect", f"unexpected url: {page.url}")

        # ----------------------------------------------------------------
        # 3. Delay detection
        # ----------------------------------------------------------------
        print("\n── Delay Detection ──")

        page.goto(f"{BASE}/projects/{p1}")

        # Delay banner on detail page
        if page.locator(".alert-delayed").is_visible():
            ok("Delay banner visible on project detail after overdue phase")
        else:
            fail("Delay banner", "not visible")

        # Delay summary inside timeline section
        if page.locator(".delay-summary").is_visible():
            ok("Delay summary visible in timeline section")
        else:
            fail("Delay summary", "not visible inside timeline")

        # Days late shown
        delay_text = page.locator(".alert-delayed").inner_text()
        if "day" in delay_text.lower() and ("late" in delay_text.lower() or "overdue" in delay_text.lower()):
            ok(f"Delay banner shows days: '{delay_text.strip()[:80]}'")
        else:
            fail("Delay banner text", f"unexpected: '{delay_text.strip()[:80]}'")

        # Delay badge on project list
        page.goto(f"{BASE}/projects")
        delayed_badges = page.locator(".badge-delayed")
        if delayed_badges.count() > 0:
            ok("Delay badge visible on project list card")
        else:
            fail("Delay badge on list", "not found")

        # Needs Attention section shows delayed project
        attention = page.locator(".attention-section")
        if attention.is_visible() and "Single Prototype Knife" in attention.inner_text():
            ok("Needs Attention section shows delayed project")
        else:
            fail("Needs Attention delayed", "project not in section")

        # ----------------------------------------------------------------
        # 4. current_stage update
        # ----------------------------------------------------------------
        print("\n── Current Stage Derivation ──")

        page.goto(f"{BASE}/projects/{p2}")

        # Stage should be "Design" (first phase not done)
        sidebar_text = page.locator(".detail-sidebar").inner_text()
        if "Design" in sidebar_text:
            ok("current_stage is 'Design' on fresh double-prototype project")
        else:
            fail("current_stage initial", f"sidebar: {sidebar_text[:200]}")

        # Mark Design as done — open modal, set status=done, set actual end
        today_str = date.today().isoformat()
        edit_btns2 = page.locator(".btn-phase-edit")
        edit_btns2.first.click()
        page.wait_for_selector("#phaseModal.show", timeout=3000)
        page.select_option("#modalStatus", "done")
        page.fill("#modalActualEnd", today_str)
        page.click("#phaseEditForm button[type='submit']")
        page.wait_for_load_state("networkidle")

        # current_stage should now be "Engineering Review"
        sidebar_text2 = page.locator(".detail-sidebar").inner_text()
        if "Engineering Review" in sidebar_text2:
            ok("current_stage advances to 'Engineering Review' after Design is done")
        else:
            fail("current_stage after done", f"sidebar: {sidebar_text2[:200]}")

        # ----------------------------------------------------------------
        # 5. Add phase
        # ----------------------------------------------------------------
        print("\n── Add Phase ──")

        page.goto(f"{BASE}/projects/{p1}")
        initial_count = page.locator(".timeline-table tbody tr").count()

        # Toggle add phase form
        page.click("#addPhaseToggle")
        page.wait_for_selector("#addPhaseForm:not(.d-none)", timeout=2000)
        if not page.locator("#addPhaseForm").is_hidden():
            ok("Add Phase form appears after toggle")
        else:
            fail("Add Phase toggle", "form still hidden")

        # Fill and submit
        page.fill("input[name='phase_name']", "Factory Feedback Round")
        page.select_option("select[name='phase_type']", "review")
        page.click("#addPhaseForm button[type='submit']")
        page.wait_for_load_state("networkidle")

        new_count = page.locator(".timeline-table tbody tr").count()
        if new_count == initial_count + 1:
            ok(f"Add phase: count went {initial_count} → {new_count}")
        else:
            fail("Add phase count", f"expected {initial_count + 1}, got {new_count}")

        # New phase appears in table
        if "Factory Feedback Round" in page.locator(".timeline-table").inner_text():
            ok("New phase name visible in timeline table")
        else:
            fail("New phase in table", "'Factory Feedback Round' not found")

        # ----------------------------------------------------------------
        # 6. Delete phase
        # ----------------------------------------------------------------
        print("\n── Delete Phase ──")

        count_before_delete = page.locator(".timeline-table tbody tr").count()
        page.evaluate("window.confirm = () => true")
        # Click delete on last phase (the one we just added)
        delete_btns = page.locator(".btn-phase-delete")
        delete_btns.last.click()
        page.wait_for_load_state("networkidle")

        count_after_delete = page.locator(".timeline-table tbody tr").count()
        if count_after_delete == count_before_delete - 1:
            ok(f"Delete phase: count went {count_before_delete} → {count_after_delete}")
        else:
            fail("Delete phase count", f"expected {count_before_delete - 1}, got {count_after_delete}")

        # ----------------------------------------------------------------
        # 7. Phases due this week (Needs Attention)
        # ----------------------------------------------------------------
        print("\n── Phases Due This Week ──")

        # Set a phase planned_end_date to tomorrow on p2
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        page.goto(f"{BASE}/projects/{p2}")
        # Open modal for second phase (Engineering Review — first is done)
        edit_btns3 = page.locator(".btn-phase-edit")
        edit_btns3.nth(1).click()
        page.wait_for_selector("#phaseModal.show", timeout=3000)
        page.select_option("#modalStatus", "in_progress")
        page.fill("#modalPlannedEnd", tomorrow)
        page.click("#phaseEditForm button[type='submit']")
        page.wait_for_load_state("networkidle")

        page.goto(f"{BASE}/projects")
        attention_text = page.locator(".attention-section").inner_text()
        if "due" in attention_text.lower():
            ok("'Phases due this week' entry appears in Needs Attention")
        else:
            fail("Phases due this week", f"not found in attention section: {attention_text[:200]}")

        # ----------------------------------------------------------------
        # 8. Estimated launch date in sidebar
        # ----------------------------------------------------------------
        print("\n── Estimated Launch Date ──")

        # Create a project WITH a planned launch date, then mark a phase overdue
        p3 = create_project(
            "Delayed Launch Test",
            prototype_rounds="single",
            planned_launch_date="2026-09-01",
        )
        page.goto(f"{BASE}/projects/{p3}")

        # Set first phase to overdue
        overdue = (date.today() - timedelta(days=5)).isoformat()
        page.locator(".btn-phase-edit").first.click()
        page.wait_for_selector("#phaseModal.show", timeout=3000)
        page.select_option("#modalStatus", "in_progress")
        page.fill("#modalPlannedEnd", overdue)
        page.click("#phaseEditForm button[type='submit']")
        page.wait_for_load_state("networkidle")

        sidebar = page.locator(".detail-sidebar").inner_text().lower()
        if "est. launch" in sidebar or "estimated" in sidebar or "delayed" in sidebar:
            ok("Estimated launch date appears in sidebar when delayed")
        else:
            fail("Est. launch in sidebar", f"not found; sidebar: {sidebar[:300]}")

        # ----------------------------------------------------------------
        # 9. Modal cancel / close
        # ----------------------------------------------------------------
        print("\n── Modal UX ──")

        page.goto(f"{BASE}/projects/{p1}")
        page.locator(".btn-phase-edit").first.click()
        page.wait_for_selector("#phaseModal.show", timeout=3000)

        page.click("#phaseModal .btn-close")
        # Wait for Bootstrap fade animation to finish (modal gets display:none after transition)
        page.wait_for_function(
            "window.getComputedStyle(document.getElementById('phaseModal')).display === 'none'",
            timeout=3000,
        )
        ok("Modal closes with X button")

        # ----------------------------------------------------------------
        # 10. No 500 errors on all phase-related pages
        # ----------------------------------------------------------------
        print("\n── No Server Errors ──")

        for pid in [p1, p2, p3]:
            resp = page.goto(f"{BASE}/projects/{pid}")
            body = page.locator("body").inner_text()
            if resp.status == 200 and "Internal Server Error" not in body:
                ok(f"Project {pid} detail renders without errors")
            else:
                fail(f"Project {pid} detail", f"status={resp.status}")

        # ----------------------------------------------------------------
        # Report
        # ----------------------------------------------------------------
        browser.close()

    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        print("\nFailed tests:")
        for name, reason in FAIL:
            print(f"  ✗ {name}: {reason}")
    print("=" * 60)

    return len(FAIL) == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
