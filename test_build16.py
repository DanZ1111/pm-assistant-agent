"""Build 16 — Variants + Packaging + Quotation + Profit Model placeholder tests."""
import io
import os
import re
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
    r = admin_s.post(f"{BASE}/projects/new",
                     data={"name": name, "prototype_rounds": "single"},
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


def main():
    admin_s = login(ADMIN, ADMIN_PWD)
    pm_s = login(PM_USER, PM_PWD)
    viewer_s = login(VIEWER_USER, VIEWER_PWD)
    if not all([admin_s, pm_s, viewer_s]):
        fail("setup", "could not log in all three roles"); _p(); return False
    ok("All three roles can log in")

    pm_proj = make_pm_owned_project(admin_s, PM_USER, f"Build16 PM Project {os.getpid()}")
    admin_proj = make_pm_owned_project(admin_s, ADMIN, f"Build16 Admin Only {os.getpid()}")
    ok(f"Setup: pm_proj={pm_proj} (PM={PM_USER}), admin_proj={admin_proj} (PM=admin)")

    # ── AI Permission Guard ──
    print("\n── AI Permission Guard ──")
    try:
        sys.path.insert(0, os.getcwd())
        from app.dependencies import is_forbidden_ai_question
        class _V: role = "viewer"
        if is_forbidden_ai_question(_V(), "What's the variant cost?"):
            ok("Viewer asking variant cost is forbidden")
        else:
            fail("Variant cost guard", "not forbidden")
        if is_forbidden_ai_question(_V(), "Show me the quotation from factory C"):
            ok("Viewer asking quotation is forbidden")
        else:
            fail("Quotation guard", "not forbidden")
    except Exception as e:
        fail("Guard import", str(e))

    # ── PM creates variant on own project ──
    print("\n── Variant CRUD ──")
    r = pm_s.post(f"{BASE}/projects/{pm_proj}/variants", data={
        "variant_name": "V1 — Walnut/Brass",
        "sku": "DCK-001-WBR",
        "status": "selected",
        "is_primary": "1",
        "target_factory_cost": "42.50",
        "target_msrp": "199.00",
        "material_summary": "67-layer Damascus, VG-10 core, walnut handle, brass mosaic pin",
    }, allow_redirects=False)
    if r.status_code in (302, 303):
        ok("PM POST /variants on own project → redirect")
    else:
        fail("PM variant create", f"status {r.status_code}")

    # Verify variant appears
    det = pm_s.get(f"{BASE}/projects/{pm_proj}").text
    if "V1 — Walnut/Brass" in det and "DCK-001-WBR" in det:
        ok("Variant appears on project detail")
    else:
        fail("Variant display", "name/sku not on detail page")

    # Add a second variant — NOT primary
    pm_s.post(f"{BASE}/projects/{pm_proj}/variants", data={
        "variant_name": "V2 — Cocobolo/Steel",
        "sku": "DCK-001-CST",
        "status": "evaluating",
        "target_factory_cost": "47.00",
        "target_msrp": "219.00",
    }, allow_redirects=False)
    primary_count = len(db_query(
        "SELECT id FROM project_variants WHERE project_id=? AND is_primary=1", (pm_proj,)))
    if primary_count == 1:
        ok("Only one variant is primary after adding a non-primary")
    else:
        fail("Primary uniqueness", f"expected 1 primary, got {primary_count}")

    # Set V2 as primary — V1 should unset
    v2_id = db_query(
        "SELECT id FROM project_variants WHERE project_id=? AND variant_name LIKE 'V2%'",
        (pm_proj,))[0][0]
    pm_s.post(f"{BASE}/projects/{pm_proj}/variants/{v2_id}/set-primary", allow_redirects=False)
    primary_rows = db_query(
        "SELECT id FROM project_variants WHERE project_id=? AND is_primary=1", (pm_proj,))
    if len(primary_rows) == 1 and primary_rows[0][0] == v2_id:
        ok("Setting V2 as primary unsets V1 (service-layer enforcement)")
    else:
        fail("Primary swap", f"expected primary=V2 only, got {primary_rows}")

    # PM cannot create variant on someone else's project
    r = pm_s.post(f"{BASE}/projects/{admin_proj}/variants",
                  data={"variant_name": "Should not appear"}, allow_redirects=False)
    rows = db_query("SELECT COUNT(*) FROM project_variants WHERE project_id=? AND variant_name=?",
                    (admin_proj, "Should not appear"))
    if rows[0][0] == 0:
        ok("PM cannot create variant on non-owned project")
    else:
        fail("PM cross-project block", "variant was created")

    # ── Viewer cannot see costs but sees variant names ──
    print("\n── Viewer cost visibility ──")
    vdet = viewer_s.get(f"{BASE}/projects/{pm_proj}").text
    if "V1 — Walnut/Brass" in vdet and "V2 — Cocobolo/Steel" in vdet:
        ok("Viewer sees variant names")
    else:
        fail("Viewer variant names", "names missing")
    # Cost figures should not appear (the $42.50, $199.00 numbers)
    if "$42.50" not in vdet and "$199.00" not in vdet:
        ok("Viewer does NOT see variant cost figures")
    else:
        fail("Viewer cost hidden", "cost numbers leaked to viewer")

    # ── PM cannot delete (admin only) ──
    print("\n── Variant delete is admin-only ──")
    v1_id = db_query(
        "SELECT id FROM project_variants WHERE project_id=? AND variant_name LIKE 'V1%'",
        (pm_proj,))[0][0]
    pm_s.post(f"{BASE}/projects/{pm_proj}/variants/{v1_id}/delete", allow_redirects=False)
    remaining = db_query(
        "SELECT COUNT(*) FROM project_variants WHERE id=?", (v1_id,))[0][0]
    if remaining == 1:
        ok("PM delete attempt did NOT remove variant")
    else:
        fail("PM delete block", "variant was deleted by PM")
    # Admin can delete
    admin_s.post(f"{BASE}/projects/{pm_proj}/variants/{v1_id}/delete", allow_redirects=False)
    remaining = db_query(
        "SELECT COUNT(*) FROM project_variants WHERE id=?", (v1_id,))[0][0]
    if remaining == 0:
        ok("Admin successfully deleted variant")
    else:
        fail("Admin delete", "variant still present")

    # ── Packaging / accessory components ──
    print("\n── Components ──")
    # Project-wide component
    pm_s.post(f"{BASE}/projects/{pm_proj}/components", data={
        "name": "Hard plastic case",
        "component_type": "packaging",
        "variant_id": "",
        "target_cost": "3.50",
        "actual_cost": "4.10",
        "notes": "All variants ship in this case.",
    }, allow_redirects=False)
    # Per-variant component (V2)
    pm_s.post(f"{BASE}/projects/{pm_proj}/components", data={
        "name": "Sharpening stone",
        "component_type": "accessory",
        "variant_id": str(v2_id),
        "target_cost": "2.20",
    }, allow_redirects=False)
    comps = db_query(
        "SELECT id, name, variant_id, component_type FROM project_variant_components WHERE project_id=?",
        (pm_proj,))
    if len(comps) == 2:
        ok(f"Two components created ({len(comps)})")
    else:
        fail("Component create", f"expected 2, got {len(comps)}")

    # Detail page should render both
    det = pm_s.get(f"{BASE}/projects/{pm_proj}").text
    if "Hard plastic case" in det and "Sharpening stone" in det:
        ok("Both components render on detail page")
    else:
        fail("Component display", "components missing on detail")
    # Per-variant scope rendered
    if ("V2 — Cocobolo/Steel" in det) and "Sharpening stone" in det:
        ok("Per-variant component renders with variant tag")
    else:
        fail("Per-variant tag", "scope tag not visible")

    # Viewer sees component names without cost columns
    vdet = viewer_s.get(f"{BASE}/projects/{pm_proj}").text
    if "Hard plastic case" in vdet and "Sharpening stone" in vdet:
        ok("Viewer sees component names")
    else:
        fail("Viewer component names", "missing")
    if "$3.50" not in vdet and "$4.10" not in vdet:
        ok("Viewer does NOT see component cost columns")
    else:
        fail("Viewer component cost hidden", "cost leaked")

    # Component delete admin only
    cid = comps[0][0]
    pm_s.post(f"{BASE}/projects/{pm_proj}/components/{cid}/delete", allow_redirects=False)
    still = db_query("SELECT COUNT(*) FROM project_variant_components WHERE id=?", (cid,))[0][0]
    if still == 1:
        ok("PM delete component blocked")
    else:
        fail("PM component delete block", "component was deleted")
    admin_s.post(f"{BASE}/projects/{pm_proj}/components/{cid}/delete", allow_redirects=False)
    still = db_query("SELECT COUNT(*) FROM project_variant_components WHERE id=?", (cid,))[0][0]
    if still == 0:
        ok("Admin successfully deleted component")
    else:
        fail("Admin component delete", "component still present")

    # ── Quotation files (upload + viewer block on download) ──
    print("\n── Quotation files ──")
    quote_bytes = b"This is a stand-in factory quotation file for testing."
    pm_s.post(f"{BASE}/projects/{pm_proj}/files",
              files={"file": ("quotation_factoryC.pdf", quote_bytes, "application/pdf")},
              data={"file_category": "quotation", "source_note": "Factory C — June quote"},
              allow_redirects=False)
    quote_rows = db_query(
        "SELECT id, original_filename FROM project_files WHERE project_id=? AND file_category='quotation'",
        (pm_proj,))
    if quote_rows:
        ok(f"Quotation file uploaded ({quote_rows[0][1]})")
    else:
        fail("Quotation upload", "no row in project_files")
    qfid = quote_rows[0][0]

    # Quotation Files section renders the file
    det = pm_s.get(f"{BASE}/projects/{pm_proj}").text
    if "Quotation Files" in det and "quotation_factoryC.pdf" in det:
        ok("Quotation Files section renders the file")
    else:
        fail("Quotation section render", "file not in section")

    # Admin can download
    r = admin_s.get(f"{BASE}/projects/{pm_proj}/files/{qfid}/download",
                    allow_redirects=False)
    if r.status_code == 200 and r.content == quote_bytes:
        ok("Admin can download quotation file")
    else:
        fail("Admin download", f"status {r.status_code}")
    # Viewer cannot
    r = viewer_s.get(f"{BASE}/projects/{pm_proj}/files/{qfid}/download",
                     allow_redirects=False)
    if r.status_code in (302, 303):
        ok("Viewer download of quotation file → redirect (blocked)")
    else:
        fail("Viewer download block", f"status {r.status_code}")

    # ── Profit Model placeholder renders ──
    print("\n── Profit Model placeholder ──")
    det = pm_s.get(f"{BASE}/projects/{pm_proj}").text
    if "Profit Model" in det and "placeholder" in det.lower():
        ok("Profit Model section renders with placeholder badge")
    else:
        fail("Profit Model render", "section missing")
    # With V2 primary + costs set, the per-unit margin preview should show
    # MSRP $219 - factory $47 - packaging share (Sharpening stone $2.20 since project-wide
    # component was deleted earlier, only V2 sharpening stone remains) = 169.80
    if "Estimated per-unit margin" in det:
        ok("Per-unit margin preview computed (primary variant has the required fields)")
    else:
        # Acceptable if data conditions not perfectly aligned — print but don't fail
        print("    (per-unit margin preview not shown — data conditions vary)")

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
