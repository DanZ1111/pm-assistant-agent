"""
Build 6 — AI File/Image Intake test suite
Run: python3 test_build6.py
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


import struct
import zlib


def make_png(width=64, height=64):
    """Create a valid width×height solid-brown PNG (large enough for vision API)."""
    def png_chunk(tag, data):
        crc = zlib.crc32(tag + data) & 0xffffffff
        return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', crc)

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    # Solid brown scanlines: filter byte 0 + RGB per pixel
    row = b'\x00' + bytes([139, 90, 43]) * width
    raw = row * height
    idat = zlib.compress(raw)

    return (
        b'\x89PNG\r\n\x1a\n' +
        png_chunk(b'IHDR', ihdr) +
        png_chunk(b'IDAT', idat) +
        png_chunk(b'IEND', b'')
    )


def make_pdf():
    """Create a valid single-page PDF with extractable text (correct xref offsets)."""
    text = (b"BT /F1 12 Tf 50 750 Td "
            b"(Damascus Chef Knife for Rblack. PM: Sarah Chen. "
            b"Factory: Guangzhou Blade Co. MSRP $129.99.) Tj ET")

    objs = {}
    buf = bytearray(b"%PDF-1.4\n")

    def add_obj(n, content):
        objs[n] = len(buf)
        buf.extend(content)

    add_obj(1, b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    add_obj(2, b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    add_obj(3, (b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"))
    stream = b"4 0 obj\n<< /Length %d >>\nstream\n%s\nendstream\nendobj\n" % (len(text), text)
    add_obj(4, stream)
    add_obj(5, b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")

    xref_pos = len(buf)
    xref = b"xref\n0 6\n0000000000 65535 f \n"
    for i in range(1, 6):
        xref += b"%010d 00000 n \n" % objs[i]
    buf.extend(xref)
    buf.extend(b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref_pos)
    return bytes(buf)


def run_tests():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # ----------------------------------------------------------------
        # 1. File upload input visible on intake page
        # ----------------------------------------------------------------
        print("\n── File Upload UI ──")
        resp = page.goto(f"{BASE}/ai/intake")
        if resp.status == 200:
            ok("GET /ai/intake returns 200")
        else:
            fail("Intake page load", f"status {resp.status}")

        file_input = page.locator("input[type='file'][name='file']")
        if file_input.count() > 0:
            ok("File input present on intake page")
        else:
            fail("File input", "not found on intake page")

        file_submit = page.locator("#intakeFileSubmit")
        if file_submit.count() > 0 and file_submit.is_disabled():
            ok("File upload button disabled before file selected")
        else:
            fail("File upload button state", "should be disabled before file selected")

        category_select = page.locator("select[name='file_category']")
        if category_select.count() > 0:
            ok("File category selector present")
        else:
            fail("File category selector", "not found")

        or_divider = page.locator("text=OR")
        if or_divider.count() > 0:
            ok("OR divider between text and file options visible")
        else:
            fail("OR divider", "not found — layout may be off")

        # ----------------------------------------------------------------
        # 2. PDF upload → fields proposed (live AI call)
        # ----------------------------------------------------------------
        print("\n── PDF Upload (live AI call) ──")
        print("    (calling GPT-5.4 for PDF extraction — may take a few seconds...)")

        pdf_content = make_pdf()
        r = requests.post(
            f"{BASE}/ai/intake/extract-file",
            files={"file": ("spec_sheet.pdf", io.BytesIO(pdf_content), "application/pdf")},
            data={"file_category": "reference"},
            allow_redirects=True,
        )
        if r.status_code == 200:
            ok("POST /ai/intake/extract-file (PDF) returns 200")
        else:
            fail("PDF extract-file HTTP", f"status {r.status_code}")

        html = r.text.lower()
        if "confirm" in html and "proposed" not in html.split("proposed")[0][-5:]:
            # Check confirm form appeared
            if 'action="/ai/intake/confirm"' in r.text:
                ok("State 2 (confirm form) appears after PDF upload")
            else:
                fail("State 2 after PDF", "confirm form not found in response HTML")
        elif 'action="/ai/intake/confirm"' in r.text:
            ok("State 2 (confirm form) appears after PDF upload")
        else:
            # Check for error
            if "error" in html or "alert-danger" in html:
                # Extract error text for diagnosis
                import re
                err = re.search(r'alert-danger[^>]*>(.*?)</div', r.text, re.DOTALL)
                err_text = err.group(1).strip()[:200] if err else "unknown"
                fail("PDF extraction", f"Error shown: {err_text}")
            else:
                fail("PDF extraction", "neither confirm form nor error found in response")

        # Check for uploaded_filename hidden field (file was saved to disk)
        if 'name="uploaded_filename"' in r.text:
            ok("uploaded_filename hidden field present after PDF upload")
        else:
            fail("uploaded_filename hidden field", "not found in State 2 HTML")

        # ----------------------------------------------------------------
        # 3. Image upload → ai_summary generated (live AI call)
        # ----------------------------------------------------------------
        print("\n── Image Upload (live AI call) ──")
        print("    (calling GPT-5.4 vision — may take a few seconds...)")

        png_content = make_png()
        r2 = requests.post(
            f"{BASE}/ai/intake/extract-file",
            files={"file": ("product_render.png", io.BytesIO(png_content), "image/png")},
            data={"file_category": "rendering"},
            allow_redirects=True,
        )
        if r2.status_code == 200:
            ok("POST /ai/intake/extract-file (image) returns 200")
        else:
            fail("Image extract-file HTTP", f"status {r2.status_code}")

        if 'action="/ai/intake/confirm"' in r2.text:
            ok("State 2 (confirm form) appears after image upload")
            # ai_summary should be in the response (shown in left panel)
            if 'name="uploaded_ai_summary"' in r2.text:
                ok("uploaded_ai_summary hidden field present in State 2")
            else:
                fail("uploaded_ai_summary hidden field", "not found after image upload")
        else:
            import re
            err = re.search(r'alert-danger[^>]*>(.*?)</div', r2.text, re.DOTALL)
            err_text = err.group(1).strip()[:200] if err else "unknown"
            fail("Image extraction", f"confirm form not found. Error: {err_text}")

        # ----------------------------------------------------------------
        # 4. Unsupported file type returns error
        # ----------------------------------------------------------------
        print("\n── Unsupported File Type ──")
        r3 = requests.post(
            f"{BASE}/ai/intake/extract-file",
            files={"file": ("data.xlsx", io.BytesIO(b"fake xlsx"), "application/vnd.ms-excel")},
            data={"file_category": "other"},
            allow_redirects=True,
        )
        if r3.status_code == 200 and "alert-danger" in r3.text:
            ok("Unsupported file type returns error on intake page")
        else:
            fail("Unsupported file type handling", f"status {r3.status_code}, no error shown")

        # ----------------------------------------------------------------
        # 5. Confirm with uploaded_filename attaches file to project
        # ----------------------------------------------------------------
        print("\n── Confirm Attaches File to Project ──")

        # Use a known uploaded file by first doing an extract-file call,
        # then parsing the uploaded_filename from the response HTML
        png2 = make_png()
        r4 = requests.post(
            f"{BASE}/ai/intake/extract-file",
            files={"file": ("b6_render.png", io.BytesIO(png2), "image/png")},
            data={"file_category": "rendering"},
            allow_redirects=True,
        )

        # Parse uploaded_filename from hidden field in response
        import re
        match = re.search(r'name="uploaded_filename"\s+value="([^"]+)"', r4.text)
        uploaded_filename = match.group(1) if match else ""

        match_summary = re.search(r'name="uploaded_ai_summary"\s+value="([^"]*)"', r4.text)
        uploaded_ai_summary = match_summary.group(1) if match_summary else ""

        if uploaded_filename:
            ok(f"Parsed uploaded_filename from response: {uploaded_filename[:20]}...")
        else:
            fail("Parse uploaded_filename", "not found in response HTML — skipping attach test")

        if uploaded_filename:
            confirm_data = {
                "raw_text": "",
                "name": "Damascus Chef Knife B6 Test",
                "brand": "Rblack",
                "sku": "",
                "product_type": "Chef's Knife",
                "product_manager": "",
                "engineer": "",
                "factory": "",
                "target_factory_cost": "",
                "target_msrp": "129.99",
                "planned_launch_date": "",
                "project_thesis": (
                    "This knife is designed for serious home cooks who want professional-grade "
                    "Damascus steel at an accessible price point. It bridges the gap between "
                    "cheap stamped knives and expensive custom blades with precision forging."
                ),
                "prototype_rounds": "single",
                "uploaded_filename": uploaded_filename,
                "uploaded_original_filename": "b6_render.png",
                "uploaded_file_type": "image",
                "uploaded_file_category": "rendering",
                "uploaded_ai_summary": uploaded_ai_summary,
            }
            r5 = requests.post(f"{BASE}/ai/intake/confirm", data=confirm_data, allow_redirects=False)
            if r5.status_code in (302, 303):
                ok("POST /ai/intake/confirm with file returns redirect")
            else:
                fail("Confirm with file", f"status {r5.status_code}")
                browser.close()
                _print_summary()
                return len(FAIL) == 0

            location = r5.headers.get("location", "")
            pid_str = location.rstrip("/").split("/")[-1]
            pid = int(pid_str) if pid_str.isdigit() else None

            if pid:
                ok(f"Redirected to project /projects/{pid}")
            else:
                fail("Project ID from redirect", f"could not parse: {location}")
                browser.close()
                _print_summary()
                return len(FAIL) == 0

            # Visit project detail and check file is attached
            resp2 = page.goto(f"{BASE}/projects/{pid}")
            if resp2.status == 200:
                ok("Project detail loads after AI file intake")
            else:
                fail("Project detail", f"status {resp2.status}")

            # Gallery should show the uploaded image
            gallery_imgs = page.locator(".gallery-img")
            if gallery_imgs.count() >= 1:
                ok(f"Uploaded image appears in project gallery ({gallery_imgs.count()} image(s))")
            else:
                fail("Image in project gallery", "no .gallery-img found after file intake confirm")

            # Verify project_files row exists with ai_summary via DB (check project detail HTML)
            # The file should appear in the files section
            files_section = page.locator("#files")
            if files_section.count() > 0:
                files_text = files_section.inner_text()
                if "b6_render" in files_text.lower() or gallery_imgs.count() >= 1:
                    ok("File attached to project (appears in files section)")
                else:
                    fail("File attached check", "b6_render not found in files section")
            else:
                fail("Files section", "#files not found on project detail")

        # ----------------------------------------------------------------
        # 6. No server errors
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
