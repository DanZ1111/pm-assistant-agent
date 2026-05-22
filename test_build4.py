"""
Build 4 — Change Log test suite
Run: python3 test_build4.py
"""

import sys
import io
import requests
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


def create_project(name, msrp="49.99"):
    r = requests.post(
        f"{BASE}/projects/new",
        data={"name": name, "prototype_rounds": "single", "target_msrp": msrp},
        allow_redirects=False,
    )
    pid = r.headers.get("location", "").rstrip("/").split("/")[-1]
    return int(pid) if pid.isdigit() else None


def update_project_http(project_id, name="Change Log Test", **fields):
    data = {"name": name, "status": "active"}
    data.update(fields)
    r = requests.post(
        f"{BASE}/projects/{project_id}/edit",
        data=data,
        allow_redirects=False,
    )
    return r.status_code in (302, 303)


def upload_file_http(project_id, filename, content, content_type, category="rendering"):
    r = requests.post(
        f"{BASE}/projects/{project_id}/files",
        files={"file": (filename, io.BytesIO(content), content_type)},
        data={"file_category": category, "source_note": ""},
        allow_redirects=False,
    )
    return r.status_code in (302, 303)


def archive_project_http(project_id):
    r = requests.post(f"{BASE}/projects/{project_id}/archive", allow_redirects=False)
    return r.status_code in (302, 303)


def make_png():
    return bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
        0x00, 0x00, 0x02, 0x00, 0x01, 0xE2, 0x21, 0xBC,
        0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
        0x44, 0xAE, 0x42, 0x60, 0x82,
    ])


def run_tests():
    pid = create_project("Change Log Test")
    assert pid, "Could not create test project"
    print(f"\nTest project ID: {pid}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # ----------------------------------------------------------------
        # 1. Project creation event logged
        # ----------------------------------------------------------------
        print("\n── Project Creation Log ──")
        page.goto(f"{BASE}/projects/{pid}")

        change_log = page.locator(".change-log")
        if change_log.is_visible():
            ok("Change log section visible after project creation")
        else:
            fail("Change log section", "not visible — check #changes section in template")

        entries = page.locator(".change-entry")
        entry_count = entries.count()
        if entry_count >= 1:
            ok(f"At least 1 change entry after creation (got {entry_count})")
        else:
            fail("Change entries after creation", f"expected ≥1, got {entry_count}")

        all_log_text = change_log.inner_text().lower() if change_log.is_visible() else ""
        if "created" in all_log_text:
            ok("Creation entry contains 'created'")
        else:
            fail("Creation entry text", f"'created' not in: '{all_log_text[:200]}'")

        # ----------------------------------------------------------------
        # 2. Field update (MSRP) logged with old → new
        # ----------------------------------------------------------------
        print("\n── Field Update Log (MSRP) ──")
        updated = update_project_http(pid, target_msrp="59.99")
        if updated:
            ok("Project MSRP update HTTP call returned redirect")
        else:
            fail("Project update HTTP call", "did not redirect")

        page.reload()
        log_text = page.locator(".change-log").inner_text().lower()

        field_entries = page.locator(".change-entry.change-field_update")
        if field_entries.count() >= 1:
            ok(f"field_update entries present ({field_entries.count()})")
        else:
            fail("field_update entries", "none found after MSRP edit")

        if "msrp" in log_text or "target" in log_text:
            ok("MSRP field_update entry found in change log")
        else:
            fail("MSRP field name in change log", f"not found. Log: '{log_text[:300]}'")

        if "59.99" in log_text:
            ok("New MSRP value 59.99 appears in change log")
        else:
            fail("New MSRP value in change log", f"'59.99' not found. Log: '{log_text[:300]}'")

        if "49.99" in log_text:
            ok("Old MSRP value 49.99 (strikethrough) appears in change log")
        else:
            fail("Old MSRP value in change log", f"'49.99' not found. Log: '{log_text[:300]}'")

        # ----------------------------------------------------------------
        # 3. Phase update logged
        # ----------------------------------------------------------------
        print("\n── Phase Update Log ──")
        phase_edit_btn = page.locator("[data-phase-id]").first
        phase_id = phase_edit_btn.get_attribute("data-phase-id") if phase_edit_btn.count() > 0 else None
        phase_name = phase_edit_btn.get_attribute("data-phase-name") if phase_id else "Design"

        if phase_id:
            ok(f"Got phase ID from DOM: {phase_id} ('{phase_name}')")
            r = requests.post(
                f"{BASE}/projects/{pid}/phases/{phase_id}/edit",
                data={
                    "phase_name": phase_name or "Design",
                    "phase_type": "design",
                    "status": "in_progress",
                    "planned_start_date": "",
                    "planned_end_date": "",
                    "actual_start_date": "",
                    "actual_end_date": "",
                    "owner": "",
                    "notes": "",
                },
                allow_redirects=False,
            )
            if r.status_code in (302, 303):
                ok("Phase status update HTTP call returned redirect")
            else:
                fail("Phase update HTTP call", f"status {r.status_code}")

            page.reload()
            phase_entries = page.locator(".change-entry.change-phase_update")
            if phase_entries.count() >= 1:
                ok(f"phase_update entry present ({phase_entries.count()})")
                phase_log_text = phase_entries.first.inner_text().lower()
                if phase_name and phase_name.lower() in phase_log_text:
                    ok(f"Phase name '{phase_name}' appears in phase_update entry")
                elif "updated" in phase_log_text or "phase" in phase_log_text:
                    ok("Phase update entry contains 'updated' or 'phase'")
                else:
                    fail("Phase update entry text", f"got: '{phase_log_text[:100]}'")
            else:
                fail("phase_update entry", "not found in change log")
        else:
            fail("Get phase ID", "no [data-phase-id] element found — check timeline section")

        # ----------------------------------------------------------------
        # 4. File upload logged
        # ----------------------------------------------------------------
        print("\n── File Upload Log ──")
        uploaded = upload_file_http(pid, "cl_test_render.png", make_png(), "image/png", "rendering")
        if uploaded:
            ok("File upload HTTP call returned redirect")
        else:
            fail("File upload HTTP call", "did not redirect")

        page.reload()
        upload_entries = page.locator(".change-entry.change-file_upload")
        if upload_entries.count() >= 1:
            ok(f"file_upload entry present ({upload_entries.count()})")
            upload_text = upload_entries.first.inner_text().lower()
            if "cl_test_render" in upload_text or "uploaded" in upload_text:
                ok("File upload entry mentions filename or 'uploaded'")
            else:
                fail("File upload entry text", f"got: '{upload_text[:100]}'")
        else:
            fail("file_upload entry", "not found in change log")

        # ----------------------------------------------------------------
        # 5. Change log count in section header
        # ----------------------------------------------------------------
        print("\n── Change Log Section Header ──")
        page.reload()
        header = page.locator("#changes .section-title")
        if header.count() > 0:
            header_text = header.first.inner_text()
            if "change log" in header_text.lower():
                ok(f"Change log section header found: '{header_text.strip()}'")
            else:
                fail("Change log header text", f"got: '{header_text.strip()}'")
            if "(" in header_text and ")" in header_text:
                ok(f"Change log count shown in header: '{header_text.strip()}'")
            else:
                fail("Change log count in header", f"no count found: '{header_text.strip()}'")
        else:
            fail("Change log section header", "#changes .section-title not found")

        # ----------------------------------------------------------------
        # 6. Archive event logged
        # ----------------------------------------------------------------
        print("\n── Archive Log ──")
        archived = archive_project_http(pid)
        if archived:
            ok("Archive HTTP call returned redirect")
        else:
            fail("Archive HTTP call", "did not redirect")

        # Project detail still accessible when archived
        resp = page.goto(f"{BASE}/projects/{pid}")
        if resp.status == 200:
            ok("Project detail accessible after archive")
        else:
            fail("Project detail after archive", f"status {resp.status}")

        archive_log = page.locator(".change-log").inner_text().lower()
        if "archived" in archive_log:
            ok("Archive event appears in change log")
        else:
            fail("Archive in change log", f"'archived' not found. Log: '{archive_log[:300]}'")

        # ----------------------------------------------------------------
        # 7. No server errors
        # ----------------------------------------------------------------
        print("\n── No Server Errors ──")
        body = page.locator("body").inner_text()
        if resp.status == 200 and "Internal Server Error" not in body and "Traceback" not in body:
            ok("Project detail renders without errors after all operations")
        else:
            fail("No server errors", f"status={resp.status}")

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
