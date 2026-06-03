"""Build 18 — Rendering History + Prototype Photos tests."""
import os
import io
import sys
import sqlite3
import requests

BASE = "http://localhost:8000"
PASS, FAIL = [], []

ADMIN, ADMIN_PWD = "admin", "show me the money"
PM_USER, PM_PWD = "testpm_b8", "pmpassword8!"
VIEWER_USER, VIEWER_PWD = "testviewer_b8", "viewerpass8!"


def ok(n): PASS.append(n); print(f"  ✓  {n}")
def fail(n, r): FAIL.append((n, r)); print(f"  ✗  {n}: {r}")


def login(u, p):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", data={"username": u, "password": p}, allow_redirects=False)
    return s if r.status_code in (302, 303) else None


def make_pm_owned_project(admin_s, pm_username, name):
    # Build 30A — POST /projects/new now requires a submission_token from the GET.
    import re as _re_b30
    form_page = admin_s.get(f"{BASE}/projects/new").text
    _tok_match = _re_b30.search(r'name="submission_token"\s+value="([a-f0-9]+)"', form_page)
    submission_token = _tok_match.group(1) if _tok_match else ""
    r = admin_s.post(f"{BASE}/projects/new",
                     data={"name": name, "prototype_rounds": "single",
                           "submission_token": submission_token},
                     allow_redirects=False)
    pid = int(r.headers["location"].rstrip("/").split("/")[-1])
    admin_s.post(f"{BASE}/projects/{pid}/edit",
                 data={"name": name, "product_manager": pm_username, "status": "active"},
                 allow_redirects=False)
    return pid


def db_query(sql, params=()):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def upload(sess, project_id, filename, content, content_type, category):
    return sess.post(
        f"{BASE}/projects/{project_id}/files",
        files={"file": (filename, io.BytesIO(content), content_type)},
        data={"file_category": category, "source_note": ""},
        allow_redirects=False,
    )


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


def latest_file_id(project_id, category):
    rows = db_query(
        "SELECT id FROM project_files WHERE project_id=? AND file_category=? "
        "ORDER BY uploaded_at DESC LIMIT 1",
        (project_id, category),
    )
    return rows[0][0] if rows else None


def main():
    admin_s = login(ADMIN, ADMIN_PWD)
    pm_s = login(PM_USER, PM_PWD)
    viewer_s = login(VIEWER_USER, VIEWER_PWD)
    if not all([admin_s, pm_s, viewer_s]):
        fail("setup", "could not log in all three roles"); _p(); return False
    ok("All three roles can log in")

    pid = make_pm_owned_project(admin_s, PM_USER, f"Build18 PM Proj {os.getpid()}")
    ok(f"Created PM-owned test project pid={pid}")

    # ── Empty-state copy renders ──
    print("\n── Empty state ──")
    det = pm_s.get(f"{BASE}/projects/{pid}").text
    if 'id="renderings"' in det and 'id="prototype-photos"' in det:
        ok("Both new sections render on detail page")
    else:
        fail("Empty state", "Rendering History or Prototype Photos anchor not found")
    if "no rendering history" in det.lower() and "no prototype photos" in det.lower():
        ok("Empty-state copy visible in both sections")
    else:
        fail("Empty state copy", "expected empty-state text in both sections")

    # ── Upload a rendering ──
    print("\n── Rendering upload + section render ──")
    r = upload(pm_s, pid, "rendering_v1.png", make_png(), "image/png", "rendering")
    if r.status_code in (302, 303):
        ok("PM uploaded rendering PNG (303 redirect)")
    else:
        fail("Rendering upload", f"status={r.status_code}")
    rendering_id = latest_file_id(pid, "rendering")
    if rendering_id:
        ok(f"Rendering file row created in DB id={rendering_id}")
    else:
        fail("Rendering DB row", "no project_files row with category=rendering")

    det = pm_s.get(f"{BASE}/projects/{pid}").text
    if "rendering_v1.png" in det and "media-history-list" in det:
        ok("Rendering appears in Rendering History section")
    else:
        fail("Rendering section render", "filename or list class missing from HTML")

    # ── Card thumbnail on /projects ──
    print("\n── Card thumbnail ──")
    listing = pm_s.get(f"{BASE}/projects").text
    if "card-rendering-thumb" in listing:
        ok("/projects list shows card-rendering-thumb")
    else:
        fail("Card thumb", "card-rendering-thumb class not found in /projects HTML")

    # ── Upload a prototype photo ──
    print("\n── Prototype photo upload ──")
    r = upload(pm_s, pid, "prototype_v1.png", make_png(), "image/png", "prototype_photo")
    if r.status_code in (302, 303):
        ok("PM uploaded prototype photo (303 redirect)")
    else:
        fail("Prototype upload", f"status={r.status_code}")
    proto_id = latest_file_id(pid, "prototype_photo")
    if proto_id:
        ok(f"Prototype photo row created in DB id={proto_id}")
    else:
        fail("Prototype DB row", "no project_files row with category=prototype_photo")

    det = pm_s.get(f"{BASE}/projects/{pid}").text
    if "prototype_v1.png" in det:
        ok("Prototype photo appears on detail page")
    else:
        fail("Prototype render", "filename missing from HTML")

    # Confirm renderings section does NOT contain the prototype filename
    # (extract the renderings section between its anchor and the next section)
    r_start = det.find('id="renderings"')
    r_end = det.find('id="prototype-photos"')
    if r_start != -1 and r_end != -1 and "prototype_v1.png" not in det[r_start:r_end]:
        ok("Prototype photo does NOT leak into Rendering History section")
    else:
        fail("Section isolation", "prototype filename appeared inside renderings section")

    # ── Comment edit round-trip ──
    print("\n── Comment edit round-trip ──")
    comment_text = "first rendering — client liked the matte finish"
    r = pm_s.post(
        f"{BASE}/projects/{pid}/files/{rendering_id}/comment",
        data={"comment": comment_text, "anchor": "renderings"},
        allow_redirects=False,
    )
    if r.status_code in (302, 303):
        ok("PM comment POST redirects (303)")
    else:
        fail("Comment POST", f"status={r.status_code}")
    rows = db_query("SELECT source_note FROM project_files WHERE id=?", (rendering_id,))
    if rows and rows[0][0] == comment_text:
        ok("project_files.source_note updated with comment text")
    else:
        fail("Comment persist", f"source_note={rows[0][0] if rows else None}")
    # change_log row written
    rows = db_query(
        "SELECT id FROM project_changes WHERE project_id=? AND change_type='event_note' "
        "AND summary LIKE '%Comment updated%' ORDER BY id DESC LIMIT 1",
        (pid,),
    )
    if rows:
        ok("project_changes row with change_type=event_note written")
    else:
        fail("project_changes", "no event_note row found")

    # ── Viewer cannot edit comment ──
    print("\n── Viewer cannot edit comment ──")
    r = viewer_s.post(
        f"{BASE}/projects/{pid}/files/{rendering_id}/comment",
        data={"comment": "viewer trying to overwrite", "anchor": "renderings"},
        allow_redirects=False,
    )
    rows = db_query("SELECT source_note FROM project_files WHERE id=?", (rendering_id,))
    if rows and rows[0][0] == comment_text:
        ok("Viewer comment POST did not modify source_note (still original comment)")
    else:
        fail("Viewer guard", f"source_note changed to: {rows[0][0] if rows else None}")

    # ── Admin can delete ──
    print("\n── Admin can delete a rendering ──")
    r = admin_s.post(f"{BASE}/projects/{pid}/files/{rendering_id}/delete", allow_redirects=False)
    if r.status_code in (302, 303):
        rows = db_query("SELECT id FROM project_files WHERE id=?", (rendering_id,))
        if not rows:
            ok("Admin deleted rendering — DB row removed")
        else:
            fail("Admin delete", "DB row still present after delete")
    else:
        fail("Admin delete POST", f"status={r.status_code}")

    _p()
    return len(FAIL) == 0


def _p():
    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        for n, r in FAIL:
            print(f"  ✗ {n}: {r}")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
