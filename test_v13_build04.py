"""v1.3 Build 04 — Overview Renderings Section tests.

Requires the app running at http://localhost:8000, or set BASE_URL.
Run: python3 test_v13_build04.py
"""
import base64
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ROOT = Path(__file__).resolve().parent
UPLOAD_DIR = ROOT / "app/uploads"
ARTIFACT_DIR = ROOT / "test_artifacts"
PASS, FAIL = [], []

ADMIN, ADMIN_PWD = "admin", "show me the money"
VIEWER_USER, VIEWER_PWD = "testviewer_b8", "viewerpass8!"
PREFIX = "v13_build04_"
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


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
    filenames = set()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE name LIKE ?", (PREFIX + "%",))
        project_ids = [row[0] for row in cur.fetchall()]
        for pid in project_ids:
            try:
                cur.execute("SELECT filename FROM project_files WHERE project_id = ?", (pid,))
                filenames.update(row[0] for row in cur.fetchall() if row[0])
            except sqlite3.OperationalError:
                pass
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

    for path in UPLOAD_DIR.glob(PREFIX + "*"):
        path.unlink(missing_ok=True)
    for name in filenames:
        (UPLOAD_DIR / name).unlink(missing_ok=True)


def mint_token(session):
    r = session.get(f"{BASE}/projects/new", timeout=5)
    m = re.search(r'name="submission_token"\s+value="([a-f0-9]+)"', r.text)
    return m.group(1) if m else ""


def create_project(session, name):
    r = session.post(
        f"{BASE}/projects/new",
        data={
            "name": name,
            "brand": "Rblack",
            "product_manager": ADMIN,
            "engineer": "Rendering Engineer",
            "factory": "Rendering Factory",
            "target_factory_cost": "under 120 RMB",
            "target_msrp": "$70-100",
            "planned_launch_date": "2026-12-01",
            "project_thesis": (
                "Build 04 rendering overview project with enough product concept "
                "detail to pass health checks while visuals can be tested in the "
                "new standalone renderings section."
            ),
            "prototype_rounds": "single",
            "submission_token": mint_token(session),
        },
        allow_redirects=False,
        timeout=5,
    )
    if r.status_code != 303:
        fail(f"create {name}", f"expected 303, got {r.status_code}: {r.text[:200]}")
        return None
    pid = r.headers.get("location", "").rstrip("/").split("/")[-1]
    return int(pid) if pid.isdigit() else None


def db_insert_file(project_id, filename, original, file_type, category, uploaded_at, note="", size=None):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / filename
    if file_type == "image":
        path.write_bytes(PNG_BYTES)
    else:
        path.write_bytes(b"Build 04 non-image visual fallback")
    file_size = size if size is not None else path.stat().st_size
    conn = sqlite3.connect(ROOT / "pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO project_files
                (project_id, filename, original_filename, file_path, file_type,
                 file_category, file_size, source_note, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                filename,
                original,
                f"uploads/{filename}",
                file_type,
                category,
                file_size,
                note or None,
                uploaded_at.strftime("%Y-%m-%d %H:%M:%S.%f"),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def upload_rendering(session, project_id):
    files = {"file": (PREFIX + "route_upload.png", PNG_BYTES, "image/png")}
    r = session.post(
        f"{BASE}/projects/{project_id}/files",
        data={"file_category": "rendering", "source_note": "Uploaded through existing Files form."},
        files=files,
        allow_redirects=False,
        timeout=5,
    )
    return r


def assert_i18n_labels():
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
        "section.renderings_overview": ("Renderings", "渲染图"),
        "renderings.latest_visual": ("Latest visual", "最新视觉稿"),
        "renderings.open_history": ("Open rendering history", "查看渲染图历史"),
        "renderings.open_prototype_photos": ("Open prototype photos", "查看样品照片"),
        "renderings.open_file": ("Open file", "打开文件"),
        "renderings.no_visual_title": ("No rendering or prototype photo yet", "暂无渲染图或样品照片"),
        "renderings.designer_portal": ("Designer Portal", "设计师入口"),
    }
    mismatches = [
        key for key, (en_val, zh_val) in expected.items()
        if en.get(key) != en_val or zh.get(key) != zh_val
    ]
    if not mismatches:
        ok("Build 04 exact EN/ZH labels are locked")
    else:
        fail("Build 04 i18n labels", f"mismatches: {mismatches}")


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

    empty_id = create_project(admin_s, PREFIX + "empty")
    mixed_id = create_project(admin_s, PREFIX + "mixed")
    proto_id = create_project(admin_s, PREFIX + "prototype_only")
    doc_id = create_project(admin_s, PREFIX + "doc_fallback")
    upload_id = create_project(admin_s, PREFIX + "upload")
    if not all([empty_id, mixed_id, proto_id, doc_id, upload_id]):
        summary()
        return False
    ok("test projects created")

    now = datetime(2026, 6, 4, 9, 0, 0)
    db_insert_file(mixed_id, PREFIX + "render_old.png", "old-rendering.png", "image", "rendering", now)
    db_insert_file(
        mixed_id,
        PREFIX + "render_new.png",
        "newest-rendering.png",
        "image",
        "rendering",
        now + timedelta(hours=1),
        "Current blade-side rendering.",
    )
    for idx in range(3):
        db_insert_file(
            mixed_id,
            f"{PREFIX}proto_{idx}.png",
            f"prototype-photo-{idx}.png",
            "image",
            "prototype_photo",
            now + timedelta(hours=2 + idx),
        )
    db_insert_file(proto_id, PREFIX + "prototype_only.png", "prototype-only.png", "image", "prototype_photo", now)
    db_insert_file(
        doc_id,
        PREFIX + "rendering_doc.pdf",
        "factory-rendering-brief.pdf",
        "pdf",
        "rendering",
        now,
        "Rendering packet from supplier.",
        size=24576,
    )
    ok("file fixtures prepared")

    print("\n── Static locks ──")
    template = (ROOT / "app/templates/project_detail.html").read_text(encoding="utf-8")
    css = (ROOT / "app/static/css/styles.css").read_text(encoding="utf-8")
    if (
        template.find('id="product-concept"')
        < template.find('id="renderings-overview"')
        < template.find('components/variants_section.html')
    ):
        ok("Renderings overview is after Product Concept and before Variants")
    else:
        fail("Renderings overview order", "template order is wrong")
    required_sources = (
        'id="renderings-overview"',
        '{% set media_anchor = "renderings" %}',
        '{% set media_anchor = "prototype-photos" %}',
        'id="files"',
    )
    for anchor in required_sources:
        if anchor not in template:
            fail("required anchors", f"missing {anchor}")
            break
    else:
        ok("Renderings, history, prototype, and files anchors exist")
    if "max-height: 360px" in css and "object-fit: contain" in css:
        ok("Rendering preview image has safe size constraints")
    else:
        fail("rendering preview CSS", "missing max-height/object-fit constraints")
    assert_i18n_labels()

    print("\n── Browser behavior ──")
    ARTIFACT_DIR.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 950})
        login_page(page)

        page.goto(f"{BASE}/projects/{empty_id}")
        page.wait_for_load_state("networkidle")
        empty_text = page.locator("#renderings-overview").inner_text()
        if "No rendering or prototype photo yet" in empty_text and "Upload (Files section" in empty_text:
            ok("Empty state appears with upload link for editor")
        else:
            fail("empty state", empty_text[:400])
        if "Designer Portal" in empty_text and "Not active yet" in empty_text:
            ok("Designer Portal renders as disabled future placeholder")
        else:
            fail("designer placeholder", empty_text[:400])
        page.screenshot(path=str(ARTIFACT_DIR / "v13-build04-empty-desktop.png"), full_page=True)

        page.goto(f"{BASE}/projects/{mixed_id}")
        page.wait_for_load_state("networkidle")
        section = page.locator("#renderings-overview")
        text = section.inner_text()
        img_src = section.locator("img").first.get_attribute("src")
        if "newest-rendering.png" in text and "prototype-photo" not in text and img_src and "render_new" in img_src:
            ok("Newest rendering image wins by uploaded_at")
        else:
            fail("rendering cascade", f"text={text[:300]} src={img_src}")
        if "Open rendering history" in text and "Open prototype photos" in text:
            ok("Prototype Photos link appears even when rendering preview wins")
        else:
            fail("history/prototype links", text[:400])
        if "Current blade-side rendering." in text and "Rendering" in text:
            ok("Rendering metadata and source note render")
        else:
            fail("rendering metadata", text[:400])
        page.screenshot(path=str(ARTIFACT_DIR / "v13-build04-rendering-desktop.png"), full_page=True)

        mobile = browser.new_page(viewport={"width": 375, "height": 900})
        login_page(mobile)
        mobile.goto(f"{BASE}/projects/{mixed_id}")
        mobile.wait_for_load_state("networkidle")
        overflow = mobile.evaluate("""
            () => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > window.innerWidth + 1
        """)
        img_box_ok = mobile.evaluate("""
            () => {
              const section = document.querySelector('#renderings-overview');
              const img = section && section.querySelector('img');
              if (!section || !img) return false;
              return img.getBoundingClientRect().width <= section.getBoundingClientRect().width + 1;
            }
        """)
        if not overflow and img_box_ok:
            ok("Mobile Renderings overview has no horizontal overflow")
        else:
            fail("mobile overflow", f"overflow={overflow} img_box_ok={img_box_ok}")
        mobile.screenshot(path=str(ARTIFACT_DIR / "v13-build04-rendering-mobile.png"), full_page=True)

        page.goto(f"{BASE}/projects/{proto_id}")
        page.wait_for_load_state("networkidle")
        proto_text = page.locator("#renderings-overview").inner_text()
        proto_src = page.locator("#renderings-overview img").first.get_attribute("src")
        if "prototype-only.png" in proto_text and proto_src and "prototype_only" in proto_src:
            ok("Prototype photo is used when no rendering image exists")
        else:
            fail("prototype fallback", f"text={proto_text[:300]} src={proto_src}")

        page.goto(f"{BASE}/projects/{doc_id}")
        page.wait_for_load_state("networkidle")
        doc_section = page.locator("#renderings-overview")
        doc_text = doc_section.inner_text()
        if (
            doc_section.locator("img").count() == 0
            and doc_section.locator(".renderings-overview-doc").count() == 1
            and "factory-rendering-brief.pdf" in doc_text
            and "24.0 KB" in doc_text
            and "Open file" in doc_text
        ):
            ok("Non-image rendering renders document fallback card")
        else:
            fail("document fallback", doc_text[:500])

        viewer_page = browser.new_page(viewport={"width": 1280, "height": 900})
        login_page(viewer_page, VIEWER_USER, VIEWER_PWD)
        viewer_page.goto(f"{BASE}/projects/{mixed_id}")
        viewer_page.wait_for_load_state("networkidle")
        viewer_section = viewer_page.locator("#renderings-overview")
        viewer_text = viewer_section.inner_text()
        viewer_controls = viewer_section.locator(
            "button, form, a:has-text('Upload'), a:has-text('Upload (Files section')"
        )
        if "newest-rendering.png" in viewer_text and viewer_controls.count() == 0:
            ok("Viewer sees preview without overview mutation controls")
        else:
            fail("viewer controls", f"text={viewer_text[:300]} controls={viewer_controls.count()}")

        upload_response = upload_rendering(admin_s, upload_id)
        if upload_response.status_code == 303 and upload_response.headers.get("location", "").endswith("#files"):
            ok("Existing Files upload still works for rendering category")
        else:
            fail("files upload route", f"status={upload_response.status_code} location={upload_response.headers.get('location')}")
        page.goto(f"{BASE}/projects/{upload_id}")
        page.wait_for_load_state("networkidle")
        upload_text = page.locator("#renderings-overview").inner_text()
        history_text = page.locator("#renderings").inner_text()
        if PREFIX + "route_upload.png" in upload_text and PREFIX + "route_upload.png" in history_text:
            ok("Uploaded rendering appears in Overview and Rendering History")
        else:
            fail("uploaded rendering display", f"overview={upload_text[:250]} history={history_text[:250]}")

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
