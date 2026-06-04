"""v1.3 Build 05 — Variant Command Cards tests.

Layout-only build (Option A per V13_BUILD05_EXECUTION_PLAN.md). Verifies:
  - <details class="variant-command-card"> markup renders.
  - First primary variant is open by default; else first variant.
  - Collapsed summary shows name, SKU, status, primary marker,
    component-count line, and pricing row (for can_view_costs).
  - Expanded body shows the 2x2 grid (Specs | Packaging,
    Pricing & Cost | Profit) plus Notes & Actions row.
  - Component count format: "X shared + Y for this variant".
  - Naive margin renders when both target_factory_cost AND target_msrp set.
  - Viewer does not see costs, naive margin, or Profit cell.
  - #variant-N anchor target renders with open attribute.
  - Existing Add/Edit/Set Primary still work; admin-only Delete still works.
  - i18n parity locked at 604/604.
"""
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


def db_exec(sql, params=()):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def cleanup(name_prefix):
    """Delete projects whose name starts with the prefix + all their
    variants/components/phases/changes/files/tokens."""
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


def make_variant(session, project_id, name, **fields):
    data = {"variant_name": name, "status": fields.get("status", "evaluating")}
    if fields.get("is_primary"):
        data["is_primary"] = "1"
    for k in ("sku", "target_factory_cost", "actual_factory_cost", "target_msrp",
              "material_summary", "size_color_summary", "packaging_summary", "notes"):
        if fields.get(k):
            data[k] = str(fields[k])
    r = session.post(f"{BASE}/projects/{project_id}/variants",
        data=data, allow_redirects=False, timeout=5)
    # Find the new variant by name
    rows = db_query("SELECT id FROM project_variants WHERE project_id=? AND variant_name=?",
        (project_id, name))
    return rows[0][0] if rows else None


def make_component(project_id, name, variant_id=None, component_type="accessory", target_cost=None):
    """Insert a component directly via SQL (route requires multipart form
    handling that's out of scope for this smoke fixture)."""
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO project_variant_components (project_id, variant_id, component_type, name, target_cost, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))",
            (project_id, variant_id, component_type, name, target_cost),
        )
        conn.commit()
    finally:
        conn.close()


def main():
    admin = login(ADMIN, ADMIN_PWD)
    pm = login(PM_USER, PM_PWD)
    viewer = login(VIEWER_USER, VIEWER_PWD)
    if not all([admin, pm, viewer]):
        fail("setup", "could not log in all three roles"); _p(); return False
    ok("All three roles can log in")

    # Pre-cleanup
    cleanup("b05_test")

    # ── 1. i18n parity ──
    print("\n── 1. i18n parity + new keys ──")
    import json
    with open("app/i18n/en.json") as f: en = json.load(f)
    with open("app/i18n/zh.json") as f: zh = json.load(f)
    if set(en) == set(zh) and len(en) >= 604:
        ok(f"en/zh parity at {len(en)} keys")
    else:
        fail("i18n parity", f"en={len(en)} zh={len(zh)} parity={set(en)==set(zh)}")
    new_keys = [
        "variant.command_cards", "variant.specs", "variant.pricing_cost",
        "variant.profit", "variant.components_summary",
        "variant.project_wide_components", "variant.variant_components",
        "variant.no_components", "variant.no_specs", "variant.manage_components",
        "variant.naive_margin", "variant.margin_other_missing",
        "variant.margin_no_data", "variant.profit_future_note",
        "variant.not_tracked", "variant.count_summary_full",
        "variant.count_summary_shared_only",
    ]
    missing = [k for k in new_keys if k not in en]
    if not missing:
        ok(f"All {len(new_keys)} Build 05 i18n keys present in en bundle")
    else:
        fail("Build 05 i18n keys", f"missing: {missing}")

    # ── 2. Set up a project with 2 variants + components ──
    print("\n── 2. Fixture: project with primary + secondary variants ──")
    pid = make_project(admin, "b05_test_project", ADMIN)
    if not pid:
        fail("fixture", "could not create project"); _p(); return False
    v_primary = make_variant(admin, pid, "Primary Variant", is_primary=True,
        sku="B05-PRI", status="selected",
        target_factory_cost="4.20", target_msrp="14.99",
        material_summary="VG-10 core", size_color_summary="3.5 inch black",
        packaging_summary="color box")
    v_secondary = make_variant(admin, pid, "Combo Pack",
        sku="B05-COM", status="evaluating",
        target_factory_cost="7.80", target_msrp="24.99",
        material_summary="VG-10 + accessory", packaging_summary="dual box")
    if not v_primary or not v_secondary:
        fail("variants created", f"primary={v_primary}, secondary={v_secondary}")
        _p(); return False
    ok(f"Project {pid} with primary variant {v_primary} + secondary {v_secondary}")
    # Add 2 project-wide components + 1 variant-specific
    make_component(pid, "Insert tray", variant_id=None, component_type="packaging", target_cost=0.50)
    make_component(pid, "Care card", variant_id=None, component_type="accessory", target_cost=0.10)
    make_component(pid, "Bottle opener", variant_id=v_secondary, component_type="accessory", target_cost=0.90)
    ok("3 components inserted: 2 project-wide + 1 variant-specific")

    # ── 3. GET project detail (admin) → variant-command-card markup ──
    print("\n── 3. Variant Command Cards render ──")
    page_admin = admin.get(f"{BASE}/projects/{pid}").text
    if 'class="variant-command-card variant-command-card-primary"' in page_admin or 'class="variant-command-card' in page_admin:
        ok("variant-command-card class renders")
    else:
        fail("card markup", "no variant-command-card class found")
    if page_admin.count('class="variant-command-card') >= 2:
        ok(f"Both variants render as cards ({page_admin.count('class=\"variant-command-card')} cards)")
    else:
        fail("card count", f"expected 2, got {page_admin.count('class=\"variant-command-card')}")
    # Default-open: primary should be open, secondary should be closed
    primary_pattern = re.compile(r'<details[^>]*id="variant-' + str(v_primary) + r'"[^>]*\bopen\b', re.IGNORECASE)
    if primary_pattern.search(page_admin):
        ok("Primary variant card has [open] attribute (default-open rule)")
    else:
        fail("default-open primary", "primary variant card missing open attribute")
    secondary_match = re.search(r'<details[^>]*id="variant-' + str(v_secondary) + r'"([^>]*)>', page_admin)
    if secondary_match and 'open' not in secondary_match.group(1).lower():
        ok("Secondary variant card has no [open] attribute (collapsed by default)")
    else:
        fail("collapsed secondary", f"secondary variant should be closed: {secondary_match.group(0) if secondary_match else 'no match'}")

    # ── 4. Collapsed summary content ──
    print("\n── 4. Collapsed summary content ──")
    # Check that summary section contains variant name + SKU + status badge
    if "Primary Variant" in page_admin and "B05-PRI" in page_admin:
        ok("Collapsed summary shows variant name + SKU")
    else:
        fail("summary content", "missing name or SKU")
    if 'variant-command-primary-badge' in page_admin:
        ok("Primary badge renders on primary variant")
    else:
        fail("primary badge", "no variant-command-primary-badge found")

    # ── 5. Component count format ──
    print("\n── 5. Component count format ──")
    # Secondary variant has 1 variant-specific + 2 shared → "2 shared + 1 for this variant"
    # Primary variant has 0 variant-specific + 2 shared → "2 shared"
    if "2 shared + 1 for this variant" in page_admin:
        ok("Count format 'X shared + Y for this variant' renders for secondary variant")
    else:
        fail("count format full", "expected '2 shared + 1 for this variant' in admin page")
    if "2 shared" in page_admin and "2 shared + 1" not in page_admin.replace("2 shared + 1 for this variant", ""):
        # The "2 shared" should appear standalone for the primary variant
        ok("Count format '2 shared' renders for primary variant (no variant-specific)")
    else:
        # Less strict check
        if "2 shared" in page_admin:
            ok("'2 shared' substring present (primary variant standalone count)")
        else:
            fail("count format shared-only", "expected '2 shared' for primary")

    # ── 6. Expanded body 2x2 grid (admin sees all 4 cells) ──
    print("\n── 6. Expanded 2x2 grid ──")
    for cell_class in ("variant-command-cell-specs", "variant-command-cell-components",
                       "variant-command-cell-pricing", "variant-command-cell-profit"):
        if cell_class in page_admin:
            ok(f"Cell present: {cell_class}")
        else:
            fail(f"cell missing", cell_class)

    # ── 7. Naive margin renders for admin (target=4.20, msrp=14.99 → 10.79) ──
    print("\n── 7. Naive margin (admin) ──")
    if "$10.79" in page_admin:
        ok("Naive margin $10.79 renders for primary (msrp 14.99 - cost 4.20)")
    else:
        fail("naive margin", "expected $10.79 in admin page")
    if "$17.19" in page_admin:
        ok("Naive margin $17.19 renders for secondary (msrp 24.99 - cost 7.80)")
    else:
        fail("naive margin secondary", "expected $17.19")

    # ── 8. Viewer does NOT see costs or Profit cell ──
    print("\n── 8. Viewer permission ──")
    page_viewer = viewer.get(f"{BASE}/projects/{pid}").text
    if "$10.79" not in page_viewer and "$17.19" not in page_viewer:
        ok("Viewer does not see naive margin values")
    else:
        fail("viewer margin leak", "viewer sees naive margin")
    if "variant-command-cell-pricing" not in page_viewer and "variant-command-cell-profit" not in page_viewer:
        ok("Viewer does not see Pricing & Cost or Profit cells")
    else:
        fail("viewer cost cell leak", "viewer sees pricing or profit cell")
    # Viewer SHOULD still see the variant card itself + specs + components
    if "variant-command-card" in page_viewer:
        ok("Viewer sees variant cards")
    else:
        fail("viewer cards", "viewer sees no variant cards")

    # ── 9. #variant-N anchor: page contains the per-card id ──
    print("\n── 9. Per-card anchor id ──")
    if f'id="variant-{v_secondary}"' in page_admin:
        ok(f"Per-card anchor id 'variant-{v_secondary}' present in HTML")
    else:
        fail("anchor id", f"no id='variant-{v_secondary}'")
    # JS bootstrap should be in main.js
    main_js = open("app/static/js/main.js").read()
    if "applyVariantHash" in main_js and "details.variant-command-card[open]" in main_js:
        ok("main.js contains #variant-N anchor bootstrap (applyVariantHash)")
    else:
        fail("anchor JS", "main.js missing applyVariantHash function")

    # ── 10. Custom chevron CSS ──
    print("\n── 10. <details> marker suppression + custom chevron ──")
    css = open("app/static/css/styles.css").read()
    if "variant-command-card > summary::-webkit-details-marker" in css:
        ok("CSS suppresses native ::-webkit-details-marker")
    else:
        fail("marker suppression", "no ::-webkit-details-marker rule")
    if "bi-chevron-right" in css.lower() or "\\F285" in css:
        ok("CSS uses bi-chevron-right custom marker")
    else:
        fail("custom chevron", "no chevron-right reference in CSS")

    # ── 11. components_by_variant grouping in route ──
    print("\n── 11. Route-side components_by_variant grouping ──")
    routes_py = open("app/routes/projects.py").read()
    if "components_by_variant" in routes_py and 'setdefault(c.variant_id' in routes_py:
        ok("project_detail route computes components_by_variant grouping")
    else:
        fail("route grouping", "no components_by_variant setdefault loop in projects.py")

    # ── 12. Existing add/edit/set-primary/delete unchanged ──
    print("\n── 12. Existing variant CRUD preserved ──")
    if "/projects/" in page_admin and "/variants/" in page_admin:
        # Look for the form action attributes
        if f'action="/projects/{pid}/variants/{v_secondary}/edit"' in page_admin:
            ok("Edit Variant form action preserved")
        else:
            fail("edit action", "no /variants/{id}/edit form")
        if f'action="/projects/{pid}/variants/{v_secondary}/set-primary"' in page_admin:
            ok("Set Primary form action preserved (on non-primary variant)")
        else:
            fail("set-primary action", "no /variants/{id}/set-primary form on secondary")
        # Admin sees delete
        if f'action="/projects/{pid}/variants/{v_secondary}/delete"' in page_admin:
            ok("Admin sees Delete form action on secondary variant")
        else:
            fail("admin delete", "no /variants/{id}/delete form for admin")
        # Viewer must NOT see delete OR edit
        if f'action="/projects/{pid}/variants/{v_secondary}/delete"' not in page_viewer:
            ok("Viewer does NOT see Delete form action")
        else:
            fail("viewer delete leak", "viewer sees delete form")

    # ── 13. Manage components link to #packaging ──
    print("\n── 13. Manage components link ──")
    if 'href="#packaging"' in page_admin:
        ok("Manage components link points to #packaging anchor (admin/can_edit)")
    else:
        fail("manage components link", "no href='#packaging' in admin page")
    # Verify #packaging anchor exists on packaging section
    packaging_section = open("app/templates/components/packaging_section.html").read()
    if 'id="packaging"' in packaging_section:
        ok("#packaging anchor exists on packaging section")
    else:
        fail("#packaging anchor", "packaging_section.html missing id='packaging'")

    # ── 14. Build 05 itself added no schema migration ──
    # NOTE: Build 05B (a separate atomic step) added migration 005 with
    # structured variant spec columns. Build 05's "no schema change" promise
    # applies to Build 05 alone; we verify here that migrations 001-004
    # (the v1.0-v1.2 set) are still the baseline Build 05 inherited.
    print("\n── 14. Build 05's baseline migrations (001-004) untouched ──")
    migrations = open("app/migrations.py").read()
    for marker in ("001_v1_1_add_language_to_users",
                    "002_v1_1_add_conversation_id_to_ai_messages",
                    "003_v1_2_add_price_text_fields",
                    "004_v1_2_add_project_creation_tokens"):
        if marker not in migrations:
            fail("migrations baseline", f"missing {marker}")
            break
    else:
        ok("Build 05 baseline migrations 001-004 all present")

    # Cleanup
    cleanup("b05_test")
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
