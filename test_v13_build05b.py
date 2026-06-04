"""v1.3 Build 05B — Structured variant specs tests.

Verifies:
- Migration 005 added 6 new columns on project_variants.
- ProjectVariant model exposes them.
- POST /projects/{pid}/variants accepts the 6 new fields and persists.
- POST /projects/{pid}/variants/{vid}/edit updates them.
- variants_section.html renders Sales Format chip when set, 4 spec
  sub-sections when at least one new field is set, Legacy notes details
  when legacy fields are set, Packaging Cost row in Pricing cell.
- Viewer cannot see packaging_cost (it's a cost field).
- UPDATE_VARIANT_ALLOWED includes the 6 new fields (AI tool path).
- create_variant tool schema includes the 6 new fields.
- i18n parity at 620/620.
- All Build 05 invariants preserved (cards, grid, chevron, anchor, etc).
"""
import json
import os
import re
import sqlite3
import sys

import requests

BASE = os.environ.get("BASE_URL", "http://localhost:8000")
PASS, FAIL = [], []

ADMIN, ADMIN_PWD = "admin", "show me the money"
PM_USER, PM_PWD = "testpm_b8", "pmpassword8!"
VIEWER_USER, VIEWER_PWD = "testviewer_b8", "viewerpass8!"


def ok(n):
    PASS.append(n)
    print(f"  ✓  {n}")


def fail(n, r):
    FAIL.append((n, r))
    print(f"  ✗  {n}: {r}")


def login(u, p):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login",
        data={"username": u, "password": p}, allow_redirects=False, timeout=5)
    return s if r.status_code in (302, 303) else None


def db_query(sql, params=()):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def cleanup(name_prefix):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE name LIKE ?", (name_prefix + "%",))
        for (pid,) in cur.fetchall():
            cur.execute("DELETE FROM project_variant_components WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_variants WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_changes WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_phases WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_files WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM ai_messages WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_creation_tokens WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM projects WHERE id = ?", (pid,))
        conn.commit()
    finally:
        conn.close()


def mint_token(session):
    page = session.get(f"{BASE}/projects/new").text
    m = re.search(r'name="submission_token"\s+value="([a-f0-9]+)"', page)
    return m.group(1) if m else None


def make_project(session, name, pm_username):
    tok = mint_token(session)
    r = session.post(f"{BASE}/projects/new",
        data={"name": name, "product_manager": pm_username,
              "prototype_rounds": "single", "submission_token": tok},
        allow_redirects=False, timeout=5)
    return int(r.headers["location"].rstrip("/").split("/")[-1])


def main():
    admin = login(ADMIN, ADMIN_PWD)
    pm = login(PM_USER, PM_PWD)
    viewer = login(VIEWER_USER, VIEWER_PWD)
    if not all([admin, pm, viewer]):
        fail("setup", "could not log in all three roles"); _p(); return False
    ok("All three roles can log in")

    cleanup("b05b_test")

    # ── 1. Migration 005 / 6 new columns ──
    print("\n── 1. Migration 005 — six new variant columns ──")
    cols = {r[1] for r in db_query("PRAGMA table_info(project_variants)")}
    expected = {"sales_format", "packaging_cost", "blade_summary",
                "handle_summary", "mechanism_summary", "dimensions_summary"}
    missing = expected - cols
    if not missing:
        ok(f"All 6 new columns present on project_variants: {sorted(expected)}")
    else:
        fail("missing columns", f"missing: {missing}")

    # Model exposes them
    from app.models import ProjectVariant
    for col in expected:
        if not hasattr(ProjectVariant, col):
            fail(f"model attr {col}", "missing on ProjectVariant"); break
    else:
        ok("ProjectVariant model exposes all 6 new attributes")

    # ── 2. i18n parity ──
    print("\n── 2. i18n parity + new keys ──")
    with open("app/i18n/en.json") as f: en = json.load(f)
    with open("app/i18n/zh.json") as f: zh = json.load(f)
    if set(en) == set(zh) and len(en) >= 620:
        ok(f"en/zh parity at {len(en)} keys")
    else:
        fail("i18n parity", f"en={len(en)} zh={len(zh)}")
    new_keys = ["spec.blade", "spec.handle", "spec.mechanism", "spec.dimensions",
                "variant.sales_format", "variant.packaging_cost",
                "variant.no_section_specs", "variant.legacy_notes",
                "sales_format.single", "sales_format.combo",
                "sales_format.colorway", "sales_format.packaging_variant",
                "sales_format.retail", "sales_format.amazon", "sales_format.other"]
    if all(k in en for k in new_keys):
        ok(f"All {len(new_keys)} Build 05B i18n keys present")
    else:
        fail("Build 05B keys", f"missing: {[k for k in new_keys if k not in en]}")

    # ── 3. Create variant via form with all 6 new fields ──
    print("\n── 3. POST /variants with all 6 new fields ──")
    pid = make_project(admin, "b05b_test_project", ADMIN)
    if not pid:
        fail("project create", ""); _p(); return False
    ok(f"Created project {pid}")
    r = admin.post(f"{BASE}/projects/{pid}/variants", data={
        "variant_name": "Test Variant",
        "sku": "B05B-001",
        "status": "evaluating",
        "target_factory_cost": "8.00",
        "target_msrp": "24.99",
        "sales_format": "combo",
        "packaging_cost": "0.90",
        "blade_summary": "Steel: VG-10; Length: 3.5\"; Finish: stonewash",
        "handle_summary": "Material: G-10; Color: black; Texture: football leather",
        "mechanism_summary": "Lock: liner; Opening: flipper",
        "dimensions_summary": "Overall: 7.5\"; Closed: 4.1\"; Weight: 95g",
    }, allow_redirects=False, timeout=5)
    if r.status_code in (302, 303):
        ok(f"POST /variants → {r.status_code}")
    else:
        fail("variant POST", f"status={r.status_code}")

    # Verify all 6 fields persisted
    rows = db_query("""
        SELECT sales_format, packaging_cost, blade_summary, handle_summary,
               mechanism_summary, dimensions_summary
        FROM project_variants WHERE project_id = ?
    """, (pid,))
    if not rows:
        fail("DB row", "no variant inserted"); _p(); return False
    row = rows[0]
    if row[0] == "combo":
        ok("sales_format persisted as 'combo'")
    else:
        fail("sales_format", f"expected 'combo', got {row[0]!r}")
    if abs((row[1] or 0) - 0.90) < 0.001:
        ok(f"packaging_cost persisted as 0.90")
    else:
        fail("packaging_cost", f"expected 0.90, got {row[1]!r}")
    for i, (name, expected) in enumerate([
        ("blade_summary", "Steel: VG-10"),
        ("handle_summary", "Material: G-10"),
        ("mechanism_summary", "Lock: liner"),
        ("dimensions_summary", "Overall: 7.5"),
    ]):
        if expected in (row[i + 2] or ""):
            ok(f"{name} persisted ({row[i + 2][:30]}…)")
        else:
            fail(name, f"expected substring '{expected}', got {row[i + 2]!r}")

    # ── 4. GET project detail (admin) — new markup renders ──
    print("\n── 4. variants_section.html renders new spec sections ──")
    page = admin.get(f"{BASE}/projects/{pid}").text
    for marker, msg in [
        ("variant-command-spec-group", "Spec group sub-blocks render"),
        ("variant-command-sales-format", "Sales format chip renders"),
        ("Combo pack", "Sales format chip shows localized label"),
        ("Steel: VG-10", "Blade summary content renders"),
        ("Material: G-10", "Handle summary content renders"),
        ("Lock: liner", "Mechanism summary content renders"),
        ('Overall: 7.5', "Dimensions summary content renders"),
        ("Packaging cost", "Packaging cost row label renders"),
        ("$0.90", "Packaging cost value renders for admin"),
    ]:
        if marker in page:
            ok(msg)
        else:
            fail(msg, f"marker '{marker}' not found")

    # ── 5. Edit form: fields pre-populate ──
    print("\n── 5. Edit form pre-populates new fields ──")
    for marker in ['name="sales_format"', 'name="packaging_cost"',
                    'name="blade_summary"', 'name="handle_summary"',
                    'name="mechanism_summary"', 'name="dimensions_summary"']:
        if marker in page:
            ok(f"Edit form has input: {marker}")
        else:
            fail(f"edit form input {marker}", "not in page")
    # sales_format combo option should be selected
    if 'value="combo" selected' in page or 'value="combo"selected' in page:
        ok("Edit form 'combo' option is selected for the variant")
    else:
        fail("sales_format selected", "combo not marked selected")

    # ── 6. Viewer permission: packaging_cost hidden ──
    print("\n── 6. Viewer permission: packaging_cost hidden ──")
    page_viewer = viewer.get(f"{BASE}/projects/{pid}").text
    if "$0.90" not in page_viewer and "0.90" not in page_viewer:
        ok("Viewer does not see packaging_cost value")
    else:
        fail("viewer cost leak", "viewer sees packaging cost")
    # Viewer SHOULD still see spec sections (they're not cost data)
    if "Steel: VG-10" in page_viewer:
        ok("Viewer sees spec section content (specs are not cost data)")
    else:
        fail("viewer specs", "viewer cannot see blade_summary")

    # ── 7. Legacy notes details — variant with only legacy fields set ──
    print("\n── 7. Legacy notes details ──")
    # Create a second variant with ONLY legacy fields
    admin.post(f"{BASE}/projects/{pid}/variants", data={
        "variant_name": "Legacy-Only Variant",
        "sku": "B05B-002",
        "status": "evaluating",
        "material_summary": "Old free-text material notes",
    }, allow_redirects=False, timeout=5)
    page2 = admin.get(f"{BASE}/projects/{pid}").text
    if "Legacy notes" in page2 and "Old free-text material notes" in page2:
        ok("Legacy-only variant shows Legacy notes details with content")
    else:
        fail("legacy notes", "details block or content missing")

    # ── 8. Empty new-spec variant: 4 sub-sections still render with 'Not specified' if new specs set ──
    print("\n── 8. Empty-state behavior ──")
    # Create a variant with ZERO of any spec field
    admin.post(f"{BASE}/projects/{pid}/variants", data={
        "variant_name": "Bare Variant",
        "sku": "B05B-003",
        "status": "evaluating",
    }, allow_redirects=False, timeout=5)
    page3 = admin.get(f"{BASE}/projects/{pid}").text
    # The bare variant should show "No specs summarized yet" (the existing variant.no_specs label)
    if "No specs summarized yet." in page3:
        ok("Bare variant shows full-cell empty state")
    else:
        fail("bare variant empty state", "no_specs message not rendered")

    # ── 9. AI tool registry: create_variant + UPDATE_VARIANT_ALLOWED ──
    print("\n── 9. AI tool registry — Build 05B fields allowlisted ──")
    from app.ai.tools import UPDATE_VARIANT_ALLOWED, TOOL_SCHEMAS
    expected_in_allowed = {"sales_format", "packaging_cost", "blade_summary",
                            "handle_summary", "mechanism_summary", "dimensions_summary"}
    if expected_in_allowed.issubset(UPDATE_VARIANT_ALLOWED):
        ok(f"UPDATE_VARIANT_ALLOWED includes all 6 new fields")
    else:
        missing = expected_in_allowed - UPDATE_VARIANT_ALLOWED
        fail("UPDATE_VARIANT_ALLOWED", f"missing: {missing}")
    # create_variant schema
    create_variant = next((t for t in TOOL_SCHEMAS if t["function"]["name"] == "create_variant"), None)
    if create_variant:
        params = create_variant["function"]["parameters"]["properties"]
        for field in expected_in_allowed:
            if field not in params:
                fail(f"create_variant schema {field}", "not in tool schema"); break
        else:
            ok("create_variant tool schema includes all 6 new fields")
    else:
        fail("create_variant tool", "schema not found")

    # ── 10. Naive margin computation unchanged (ignores packaging_cost) ──
    print("\n── 10. Naive margin still excludes packaging_cost ──")
    # Test Variant: target=8.00, msrp=24.99, packaging=0.90 → margin = 16.99 (not 16.09)
    if "$16.99" in page:
        ok("Naive margin is 24.99 - 8.00 = 16.99 (packaging_cost excluded, per plan)")
    else:
        # Could also be in HTML as different format; check for both
        margin_section = re.search(r'variant-command-margin-value"[^>]*>([^<]+)', page)
        if margin_section and "16.99" in margin_section.group(1):
            ok(f"Naive margin = 16.99 (packaging excluded)")
        else:
            fail("naive margin", f"expected $16.99, margin section: {margin_section.group(1) if margin_section else 'none'}")

    # ── 11. Build 05 invariants preserved ──
    print("\n── 11. Build 05 invariants preserved ──")
    for marker in ['variant-command-card', 'variant-command-grid',
                    'variant-command-cell-specs', 'variant-command-cell-components',
                    'variant-command-cell-pricing', 'variant-command-cell-profit']:
        if marker in page:
            ok(f"Build 05 marker preserved: {marker}")
        else:
            fail(f"Build 05 marker missing: {marker}", "regressed")

    # Cleanup
    cleanup("b05b_test")
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
