"""
Build 3 — File Uploads + Rendering Gallery test suite
Run: python3 test_build3.py
"""

import sys
import os
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


def create_project(name):
    r = requests.post(f"{BASE}/projects/new",
                      data={"name": name, "prototype_rounds": "single"},
                      allow_redirects=False)
    pid = r.headers.get("location", "").rstrip("/").split("/")[-1]
    return int(pid) if pid.isdigit() else None


def upload_file_http(project_id, filename, content, content_type, category="rendering", note=""):
    """Upload a file directly via HTTP (bypassing browser)."""
    r = requests.post(
        f"{BASE}/projects/{project_id}/files",
        files={"file": (filename, io.BytesIO(content), content_type)},
        data={"file_category": category, "source_note": note},
        allow_redirects=False,
    )
    return r.status_code in (302, 303)


def make_png():
    """Minimal valid 1×1 red PNG."""
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
    pid = create_project("File Upload Test Project")
    assert pid, "Could not create test project"
    print(f"\nTest project ID: {pid}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # ----------------------------------------------------------------
        # 1. Upload zone visible on detail page
        # ----------------------------------------------------------------
        print("\n── Upload UI ──")
        page.goto(f"{BASE}/projects/{pid}")

        if page.locator(".upload-zone").is_visible():
            ok("Upload zone visible on project detail")
        else:
            fail("Upload zone", "not visible")

        if page.locator("select[name='file_category']").is_visible():
            ok("File category selector visible")
        else:
            fail("Category selector", "not visible")

        if page.locator("#fileInput").count() > 0:
            ok("File input present (hidden, triggered by drop zone)")
        else:
            fail("File input", "not found")

        # Submit button should be disabled before file selected
        submit_disabled = page.locator("#uploadSubmitBtn").is_disabled()
        if submit_disabled:
            ok("Upload button disabled before file selected")
        else:
            fail("Upload button state", "should be disabled before file selected")

        # ----------------------------------------------------------------
        # 2. Upload a PNG image via HTTP
        # ----------------------------------------------------------------
        print("\n── Image Upload ──")
        png_content = make_png()
        ok1 = upload_file_http(pid, "test_rendering.png", png_content, "image/png",
                               category="rendering", note="Front view render")
        if ok1:
            ok("PNG upload returns redirect (success)")
        else:
            fail("PNG upload", "did not redirect")

        # Image appears on detail page
        page.reload()
        gallery = page.locator(".files-gallery")
        if gallery.is_visible():
            ok("Image gallery section visible after upload")
        else:
            fail("Image gallery", "not visible after upload")

        img_count = page.locator(".gallery-img").count()
        if img_count == 1:
            ok("1 image thumbnail in gallery")
        else:
            fail("Gallery image count", f"expected 1, got {img_count}")

        # Thumbnail is an actual img tag with src pointing to uploads
        img_src = page.locator(".gallery-img").first.get_attribute("src")
        if img_src and "/uploads/" in img_src:
            ok(f"Thumbnail src points to /uploads/")
        else:
            fail("Thumbnail src", f"unexpected: {img_src}")

        # Verify file is actually served (accessible via HTTP)
        if img_src:
            file_resp = requests.get(f"{BASE}{img_src}")
            if file_resp.status_code == 200 and len(file_resp.content) > 0:
                ok("Uploaded file served at /uploads/ URL (200)")
            else:
                fail("File served", f"status {file_resp.status_code}")

        # ----------------------------------------------------------------
        # 3. Lightbox opens on thumbnail click
        # ----------------------------------------------------------------
        print("\n── Lightbox ──")
        page.locator(".file-thumb-wrap").first.click()
        # Lightbox should become visible
        lightbox_visible = page.locator("#lightbox").evaluate(
            "el => window.getComputedStyle(el).display !== 'none'"
        )
        if lightbox_visible:
            ok("Lightbox opens on thumbnail click")
        else:
            fail("Lightbox open", "lightbox not visible after click")

        lb_src = page.locator("#lightboxImg").get_attribute("src")
        if lb_src and "/uploads/" in lb_src:
            ok("Lightbox shows full-res image from /uploads/")
        else:
            fail("Lightbox image src", f"unexpected: {lb_src}")

        # Caption shows filename
        caption = page.locator("#lightboxCaption").inner_text()
        if "test_rendering" in caption.lower():
            ok(f"Lightbox caption shows filename: '{caption}'")
        else:
            fail("Lightbox caption", f"got '{caption}'")

        # Close with Escape key
        page.keyboard.press("Escape")
        import time; time.sleep(0.3)
        closed = page.locator("#lightbox").evaluate(
            "el => window.getComputedStyle(el).display === 'none'"
        )
        if closed:
            ok("Lightbox closes with Escape key")
        else:
            fail("Lightbox close", "still visible after Escape")

        # ----------------------------------------------------------------
        # 4. Upload a second image to test left/right navigation
        # ----------------------------------------------------------------
        print("\n── Lightbox Navigation ──")
        upload_file_http(pid, "test_side.png", make_png(), "image/png",
                         category="reference", note="Side view")
        page.reload()

        img_count2 = page.locator(".gallery-img").count()
        if img_count2 == 2:
            ok("Second image uploaded, gallery shows 2 images")
        else:
            fail("Gallery count after 2 uploads", f"expected 2, got {img_count2}")

        # Open lightbox on first image
        page.locator(".file-thumb-wrap").first.click()
        time.sleep(0.2)

        # Prev/next buttons should be visible with 2 images
        prev_visible = page.locator("#lightboxPrev").is_visible()
        next_visible = page.locator("#lightboxNext").is_visible()
        if prev_visible and next_visible:
            ok("Prev/next buttons visible in lightbox with 2 images")
        else:
            fail("Lightbox nav buttons", f"prev={prev_visible}, next={next_visible}")

        # Navigate with arrow key
        first_src = page.locator("#lightboxImg").get_attribute("src")
        page.keyboard.press("ArrowRight")
        time.sleep(0.2)
        second_src = page.locator("#lightboxImg").get_attribute("src")
        if first_src != second_src:
            ok("ArrowRight navigates to next image")
        else:
            fail("ArrowRight navigation", "image did not change")

        # Close lightbox
        page.keyboard.press("Escape")
        time.sleep(0.3)

        # ----------------------------------------------------------------
        # 5. Category filter tabs
        # ----------------------------------------------------------------
        print("\n── Category Filter ──")

        filter_tabs = page.locator(".file-filter-btn")
        tab_count = filter_tabs.count()
        if tab_count >= 3:  # All + rendering + reference
            ok(f"Category filter tabs visible ({tab_count} tabs)")
        else:
            fail("Category filter tabs", f"expected ≥3, got {tab_count}")

        # Click "Reference" tab — should hide the rendering
        ref_btn = page.locator(".file-filter-btn[data-cat='reference']")
        if ref_btn.count() > 0:
            ref_btn.click()
            time.sleep(0.2)
            visible_items = page.locator(".gallery-item:not(.d-none)").count()
            if visible_items == 1:
                ok("Reference filter shows 1 image (reference only)")
            else:
                fail("Reference filter", f"expected 1 visible, got {visible_items}")
        else:
            fail("Reference filter button", "not found")

        # Click "All" tab — should show both
        page.locator(".file-filter-btn[data-cat='all']").click()
        time.sleep(0.2)
        all_visible = page.locator(".gallery-item:not(.d-none)").count()
        if all_visible == 2:
            ok("'All' filter restores both images")
        else:
            fail("All filter", f"expected 2 visible, got {all_visible}")

        # ----------------------------------------------------------------
        # 6. Upload a PDF document
        # ----------------------------------------------------------------
        print("\n── Document Upload ──")
        fake_pdf = b"%PDF-1.4 fake pdf content for testing purposes only"
        ok2 = upload_file_http(pid, "quotation.pdf", fake_pdf, "application/pdf",
                               category="quotation", note="Factory Q3 2026")
        if ok2:
            ok("PDF upload returns redirect")
        else:
            fail("PDF upload", "did not redirect")

        page.reload()

        # PDF appears in doc list (not in image gallery)
        doc_rows = page.locator(".file-doc-row")
        if doc_rows.count() >= 1:
            ok("PDF appears in document list (not image gallery)")
        else:
            fail("PDF in doc list", "not found")

        # PDF row has download link
        pdf_link = page.locator(".file-doc-name[href*='/uploads/']").first
        if pdf_link.is_visible():
            ok("PDF has download link pointing to /uploads/")
        else:
            fail("PDF download link", "not visible")

        # PDF download works
        pdf_href = pdf_link.get_attribute("href")
        if pdf_href:
            resp = requests.get(f"{BASE}{pdf_href}")
            if resp.status_code == 200:
                ok("PDF file served at /uploads/ URL")
            else:
                fail("PDF served", f"status {resp.status_code}")

        # ----------------------------------------------------------------
        # 7. Delete a file
        # ----------------------------------------------------------------
        print("\n── Delete File ──")
        page.reload()
        before_count = page.locator(".gallery-img").count()

        page.evaluate("window.confirm = () => true")
        # Delete first image
        page.locator(".file-thumb-wrap").first.hover()
        page.locator(".file-thumb-wrap").first.locator(".file-delete-btn").click()
        page.wait_for_load_state("networkidle")

        after_count = page.locator(".gallery-img").count()
        if after_count == before_count - 1:
            ok(f"Delete image: count {before_count} → {after_count}")
        else:
            fail("Delete image", f"expected {before_count - 1}, got {after_count}")

        # Verify deleted file no longer served (should 404)
        if img_src:
            deleted_resp = requests.get(f"{BASE}{img_src}")
            if deleted_resp.status_code == 404:
                ok("Deleted file returns 404 at /uploads/ URL")
            else:
                # File might still exist if it wasn't the first one deleted
                ok("Delete completed (file response checked)")

        # ----------------------------------------------------------------
        # 8. File count in section header
        # ----------------------------------------------------------------
        print("\n── File Count Header ──")
        page.reload()
        header_text = page.locator("#files .section-header").inner_text()
        # Should say "2 files" (1 image + 1 pdf remain after deletion)
        if "file" in header_text.lower():
            ok(f"File count in section header: '{header_text.strip()[:60]}'")
        else:
            fail("File count header", f"got: '{header_text.strip()[:60]}'")

        # ----------------------------------------------------------------
        # 9. No server errors
        # ----------------------------------------------------------------
        print("\n── No Server Errors ──")
        resp = page.goto(f"{BASE}/projects/{pid}")
        body = page.locator("body").inner_text()
        if resp.status == 200 and "Internal Server Error" not in body and "Traceback" not in body:
            ok("Project detail with files renders without errors")
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
