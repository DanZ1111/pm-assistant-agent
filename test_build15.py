"""Build 15 — Business Plan Upload + Thesis Extraction tests."""
import io
import os
import re
import sys
import tempfile
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


def make_business_plan_docx(text: str) -> bytes:
    """Build a minimal .docx in-memory using python-docx and return the bytes."""
    from docx import Document
    doc = Document()
    for para in text.split("\n\n"):
        doc.add_paragraph(para)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def get_project_change_log(admin_s, project_id):
    html = admin_s.get(f"{BASE}/projects/{project_id}").text
    return html


def get_pm_owned_project(admin_s, pm_username):
    """Find or create a project owned by the PM."""
    # Try existing first
    html = admin_s.get(f"{BASE}/projects").text
    pids = [int(m) for m in re.findall(r'href="/projects/(\d+)"', html)]
    for pid in pids[:5]:
        det = admin_s.get(f"{BASE}/projects/{pid}").text
        if pm_username.lower() in det.lower():
            return pid
    # Create one and assign PM
    r = admin_s.post(f"{BASE}/projects/new",
                     data={"name": "Build15 PM Project", "prototype_rounds": "single"},
                     allow_redirects=False)
    new_id = int(r.headers["location"].rstrip("/").split("/")[-1])
    admin_s.post(f"{BASE}/projects/{new_id}/edit",
                 data={"name": "Build15 PM Project", "product_manager": pm_username,
                       "status": "active"},
                 allow_redirects=False)
    return new_id


def count_thesis_extractions(admin_s, project_id):
    """Use the change log + a heuristic to count extractions. Since we don't
    expose ai_messages over HTTP, we go via the SQLite DB directly."""
    import sqlite3
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM ai_messages WHERE project_id=? AND message='thesis_extraction'",
            (project_id,),
        )
        return cur.fetchone()[0]
    finally:
        conn.close()


def latest_extraction_id(project_id):
    import sqlite3
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM ai_messages WHERE project_id=? AND message='thesis_extraction' "
            "ORDER BY id DESC LIMIT 1", (project_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def main():
    admin_s = login(ADMIN, ADMIN_PWD)
    pm_s = login(PM_USER, PM_PWD)
    viewer_s = login(VIEWER_USER, VIEWER_PWD)
    if not all([admin_s, pm_s, viewer_s]):
        fail("setup", "could not log in all three roles"); _p(); return False
    ok("All three roles can log in")

    pm_proj = get_pm_owned_project(admin_s, PM_USER)
    # Make a project NOT owned by PM (so we can test PM-blocked extract)
    r = admin_s.post(f"{BASE}/projects/new",
                     data={"name": f"Build15 Admin Only {os.getpid()}",
                           "prototype_rounds": "single"},
                     allow_redirects=False)
    admin_proj = int(r.headers["location"].rstrip("/").split("/")[-1])
    admin_s.post(f"{BASE}/projects/{admin_proj}/edit",
                 data={"name": f"Build15 Admin Only {os.getpid()}",
                       "product_manager": ADMIN, "status": "active"},
                 allow_redirects=False)
    ok(f"Setup: pm_proj={pm_proj} (PM={PM_USER}), admin_proj={admin_proj} (PM=admin)")

    # ── Build 15 unit: AI Permission Guard rejects business-plan queries for viewer ──
    print("\n── AI Permission Guard ──")
    try:
        import sys as _sys, os as _os
        _sys.path.insert(0, _os.getcwd())
        from app.dependencies import is_forbidden_ai_question
        class _U: role = "viewer"
        if is_forbidden_ai_question(_U(), "Show me the business plan margin target."):
            ok("Viewer AI question about business plan is forbidden")
        else:
            fail("Viewer guard", "business plan query was NOT forbidden")
    except Exception as e:
        fail("Viewer guard import", str(e))

    # ── Permission: viewer cannot POST extract-upload ──
    print("\n── Viewer cannot trigger extract ──")
    docx_bytes = make_business_plan_docx(
        "This is a small Build15 test plan describing a chef knife product.")
    r = viewer_s.post(
        f"{BASE}/projects/{admin_proj}/thesis/extract-upload",
        files={"business_plan": ("plan.docx", docx_bytes,
                                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        allow_redirects=False,
    )
    if r.status_code in (302, 303) and "/thesis/preview" not in (r.headers.get("location") or ""):
        ok("Viewer extract-upload redirected (not to preview)")
    else:
        fail("Viewer extract block", f"status {r.status_code} loc {r.headers.get('location')}")

    # ── Permission: PM cannot extract on someone else's project ──
    print("\n── PM cannot extract on non-owned project ──")
    r = pm_s.post(
        f"{BASE}/projects/{admin_proj}/thesis/extract-upload",
        files={"business_plan": ("plan.docx", docx_bytes,
                                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        allow_redirects=False,
    )
    if r.status_code in (302, 303) and "/thesis/preview" not in (r.headers.get("location") or ""):
        ok("PM extract-upload on non-owned project redirected (not to preview)")
    else:
        fail("PM extract block", f"status {r.status_code} loc {r.headers.get('location')}")

    # ── Detail page button visibility ──
    print("\n── Detail-page button visibility ──")
    det = admin_s.get(f"{BASE}/projects/{pm_proj}").text
    if "Extract from Business Plan" in det or "thesisExtractForm" in det:
        ok("Admin sees Extract from Business Plan button")
    else:
        fail("Admin extract button", "button missing on detail page")

    det_viewer = viewer_s.get(f"{BASE}/projects/{pm_proj}").text
    if "Extract from Business Plan" not in det_viewer and "Re-extract" not in det_viewer:
        ok("Viewer does NOT see Extract button")
    else:
        fail("Viewer extract hidden", "Extract button leaked to viewer")

    # ── DOCX extraction happy path (PM on own project) ──
    print("\n── DOCX extraction happy path ──")
    plan_text = (
        "Damascus Chef Knife — Spring 2027 Launch Plan\n\n"
        "Why this product exists: Our customers in the home-cook segment have asked for "
        "a high-end Damascus blade with VG-10 core, suitable for serious cooking but priced "
        "below the $300 mark. The core problem is that existing Damascus chef knives are "
        "either kitchen-display pieces priced over $400 or low-quality lookalikes under $80. "
        "We see room for a $180-220 MSRP product that delivers genuine cutting performance.\n\n"
        "Differentiation: 67-layer Damascus pattern, hand-finished edge, walnut handle with "
        "brass mosaic pin. Brand fit: aligns with our 'serious tools at fair prices' positioning.\n\n"
        "Inspirations the team has been considering:\n"
        "- A magnetic sheath close mechanism we saw on a SHOT Show competitor\n"
        "- Forged Damascus from Yangjiang Factory C\n\n"
        "Main risk: edge retention at the price point. We need to validate on the first 100 samples."
    )
    docx_bytes = make_business_plan_docx(plan_text)
    before_count = count_thesis_extractions(admin_s, pm_proj)
    r = pm_s.post(
        f"{BASE}/projects/{pm_proj}/thesis/extract-upload",
        files={"business_plan": ("plan.docx", docx_bytes,
                                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        allow_redirects=False,
    )
    after_count = count_thesis_extractions(admin_s, pm_proj)
    loc = r.headers.get("location") or ""
    if r.status_code in (302, 303) and "/thesis/preview?extraction_id=" in loc:
        ok(f"DOCX extract POST redirected to preview ({loc})")
    else:
        fail("DOCX extract redirect", f"status {r.status_code} loc {loc}")
    if after_count == before_count + 1:
        ok("Exactly one ai_messages thesis_extraction row was created")
    else:
        fail("Extraction row count", f"before={before_count} after={after_count}")

    # ── Preview page renders + refreshing does NOT re-trigger AI ──
    print("\n── Preview page + refresh-safety ──")
    extraction_id = latest_extraction_id(pm_proj)
    if not extraction_id:
        fail("Latest extraction", "no extraction id found"); _p(); return False
    preview_url = f"{BASE}/projects/{pm_proj}/thesis/preview?extraction_id={extraction_id}"
    pre = pm_s.get(preview_url)
    if pre.status_code == 200 and "Review Thesis Extraction" in pre.text:
        ok("Preview page renders")
    else:
        fail("Preview render", f"status {pre.status_code}")
    # Refresh twice — count should be unchanged
    pm_s.get(preview_url)
    pm_s.get(preview_url)
    refresh_count = count_thesis_extractions(admin_s, pm_proj)
    if refresh_count == after_count:
        ok("Refreshing the preview does NOT re-trigger AI extraction")
    else:
        fail("Refresh AI cost", f"after={after_count} refreshed={refresh_count}")

    # ── Confirm path writes thesis ──
    print("\n── Confirm writes thesis + audit row ──")
    # Parse the preview HTML for inspiration count and reconstruct form data
    preview_html = pre.text
    # Find max inspiration index
    indices = sorted(set(int(i) for i in re.findall(r'name="inspiration_name_(\d+)"', preview_html)))
    confirmed_thesis = (
        "Build15 confirmed thesis: this product exists because home cooks want a Damascus "
        "blade that performs at the $180-220 price band. The product bet is that 67-layer "
        "Damascus + VG-10 core can deliver real cutting performance without lookalike compromises. "
        "Brand fit is direct. Main risks: edge retention validation and Yangjiang Factory C MOQ."
    )
    form_data = {"extraction_id": str(extraction_id), "project_thesis": confirmed_thesis}
    for i in indices:
        # Skip all inspirations to keep the test deterministic about idea creation
        form_data[f"inspiration_action_{i}"] = "skip"
        form_data[f"inspiration_name_{i}"] = ""
        form_data[f"inspiration_description_{i}"] = ""
        form_data[f"inspiration_idea_type_{i}"] = "other"
        form_data[f"inspiration_source_{i}"] = "other"
        form_data[f"inspiration_source_detail_{i}"] = ""
        form_data[f"inspiration_idea_id_{i}"] = ""
    r = pm_s.post(f"{BASE}/projects/{pm_proj}/thesis/confirm",
                  data=form_data, allow_redirects=False)
    if r.status_code in (302, 303) and f"/projects/{pm_proj}" in (r.headers.get("location") or ""):
        ok("Confirm POST redirects to project detail")
    else:
        fail("Confirm redirect", f"status {r.status_code} loc {r.headers.get('location')}")
    det = admin_s.get(f"{BASE}/projects/{pm_proj}").text
    if "Build15 confirmed thesis" in det:
        ok("Confirmed thesis appears on project detail")
    else:
        fail("Confirm thesis visible", "new thesis text not on detail page")
    # Audit: change log should have a row tagged with ai source and "Thesis extracted"
    if "Thesis extracted from business plan" in det:
        ok("Change log shows AI-sourced thesis extraction event_note")
    else:
        fail("Change log audit", "no 'Thesis extracted from business plan' in detail HTML")

    # ── Inline thesis edit on detail page (PM, own project) ──
    print("\n── Inline thesis edit ──")
    new_inline_text = (
        "Build15 inline edit: updated thesis text — this exists to confirm that PM can "
        "tweak the thesis directly from the project detail page without opening the full "
        "edit form, and the per-field change log row is written automatically."
    )
    r = pm_s.post(f"{BASE}/projects/{pm_proj}/thesis/inline-edit",
                  data={"project_thesis": new_inline_text}, allow_redirects=False)
    if r.status_code in (302, 303):
        ok("Inline edit POST redirects")
    det = pm_s.get(f"{BASE}/projects/{pm_proj}").text
    if "Build15 inline edit" in det:
        ok("Inline-edited thesis visible on detail page")
    else:
        fail("Inline edit visible", "new thesis text not visible")

    # Inline edit: empty rejection (only if user really tries to clear it)
    r = pm_s.post(f"{BASE}/projects/{pm_proj}/thesis/inline-edit",
                  data={"project_thesis": ""}, allow_redirects=False)
    if r.status_code in (302, 303) and "thesis_error=empty" in (r.headers.get("location") or ""):
        ok("Inline edit with empty body redirects with thesis_error=empty")
    else:
        fail("Inline empty guard", f"status {r.status_code} loc {r.headers.get('location')}")

    # ── AI failure path: unsupported file type ──
    print("\n── Unsupported file type → friendly error preserved on preview ──")
    before_count = count_thesis_extractions(admin_s, pm_proj)
    r = pm_s.post(
        f"{BASE}/projects/{pm_proj}/thesis/extract-upload",
        files={"business_plan": ("plan.xyz", b"some bytes here", "application/octet-stream")},
        allow_redirects=False,
    )
    after_count = count_thesis_extractions(admin_s, pm_proj)
    loc = r.headers.get("location") or ""
    if r.status_code in (302, 303) and "/thesis/preview" in loc:
        ok("Unsupported file still redirects to preview (graceful)")
    else:
        fail("Unsupported file redirect", f"status {r.status_code} loc {loc}")
    if after_count == before_count + 1:
        ok("Unsupported file recorded as ai_messages row (auditable failure)")
    else:
        fail("Unsupported file audit", f"before={before_count} after={after_count}")
    eid = latest_extraction_id(pm_proj)
    pv = pm_s.get(f"{BASE}/projects/{pm_proj}/thesis/preview?extraction_id={eid}").text
    if "Extraction failed" in pv or "Unsupported" in pv:
        ok("Preview page surfaces friendly error banner")
    else:
        fail("Error banner", "no 'Extraction failed' message on preview")
    # Confirm existing thesis is still preserved (we didn't write a new one on failure)
    det2 = pm_s.get(f"{BASE}/projects/{pm_proj}").text
    if "Build15 inline edit" in det2:
        ok("Existing thesis preserved through extraction failure (no silent overwrite)")
    else:
        fail("Thesis preservation", "thesis text changed after extraction failure")

    _p()
    return len(FAIL) == 0


def _p():
    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        for n, r in FAIL: print(f"  ✗ {n}: {r}")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
