"""Build 20 — AI Tools Architecture + Permission Guard tests.

Unlike previous builds, this one runs against the app's internal modules
directly (no HTTP server needed) — the dispatcher is an in-process function,
not a route. We still set up real DB sessions and real users via the
existing models.
"""
import os
import sys
import requests
import sqlite3

# Add project root for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import User
from app.ai.tools import (
    TOOL_SCHEMAS, TOOL_PERMISSIONS, UPDATE_PROJECT_FIELD_ALLOWED, dispatch,
)
from app.dependencies import is_forbidden_ai_question


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
    db = SessionLocal()
    admin_u = db.query(User).filter(User.username == ADMIN).first()
    pm_u = db.query(User).filter(User.username == PM_USER).first()
    viewer_u = db.query(User).filter(User.username == VIEWER_USER).first()
    if not all([admin_u, pm_u, viewer_u]):
        fail("setup", "missing one of the test users in DB"); _p(); return False
    ok("All three test users present in DB")

    # We still need HTTP to create a PM-owned project (uses route logic),
    # then we drop back into in-process dispatch.
    admin_s = login(ADMIN, ADMIN_PWD)
    if not admin_s:
        fail("setup", "admin HTTP login failed"); _p(); return False
    pid = make_pm_owned_project(admin_s, PM_USER, f"Build20 PM Proj {os.getpid()}")
    ok(f"Created PM-owned test project pid={pid}")

    # ── Schema & dispatcher correctness ──
    print("\n── Schema & dispatcher correctness ──")
    if len(TOOL_SCHEMAS) == 19:
        ok("TOOL_SCHEMAS has 19 entries after Build 27 adds read-only lookup tools")
    else:
        fail("schema count", f"expected 17, got {len(TOOL_SCHEMAS)}")

    schema_names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    perm_names = set(TOOL_PERMISSIONS.keys())
    if schema_names == perm_names:
        ok("Every TOOL_SCHEMAS name has a matching TOOL_PERMISSIONS entry")
    else:
        fail("schema/perm match", f"diff: {schema_names ^ perm_names}")

    bad = []
    for s in TOOL_SCHEMAS:
        if s.get("type") != "function":
            bad.append((s, "missing type=function")); continue
        fn = s.get("function") or {}
        if not fn.get("name") or not fn.get("description"):
            bad.append((fn.get("name"), "missing name or description"))
        params = fn.get("parameters") or {}
        if params.get("type") != "object" or "properties" not in params:
            bad.append((fn.get("name"), "parameters not a valid JSON Schema object"))
    if not bad:
        ok("Every schema has shape {type:function, function:{name, description, parameters}}")
    else:
        fail("schema shape", str(bad[:3]))

    # ── Confirmed create_journal_entry handler ──
    print("\n── create_journal_entry handler (confirmed in Build 27) ──")
    res = dispatch(
        "create_journal_entry",
        {"project_id": pid, "entry_text": "Build 20 test entry", "entry_type": "general"},
        db, admin_u,
    )
    if res.get("error") == "confirmation_required":
        ok("Admin journal proposal waits for explicit confirmation")
        res = dispatch(
            "create_journal_entry",
            {"project_id": pid, "entry_text": "Build 20 test entry", "entry_type": "general"},
            db, admin_u, confirmed=True,
        )
    if res.get("ok") and isinstance(res.get("entry_id"), int):
        ok(f"Admin can confirm journal entry via dispatcher (entry_id={res['entry_id']})")
        # DB confirms
        rows = db_query("SELECT id, entry_text FROM project_journal_entries WHERE id=?", (res["entry_id"],))
        if rows and rows[0][1].startswith("Build 20 test"):
            ok("Journal entry row exists in DB with correct text")
        else:
            fail("journal DB row", f"row missing or text mismatch: {rows}")
    else:
        fail("admin journal create", str(res))

    res = dispatch(
        "create_journal_entry",
        {"project_id": pid, "entry_text": "viewer should not write", "entry_type": "general"},
        db, viewer_u,
    )
    if not res.get("ok") and res.get("error") == "forbidden":
        ok("Viewer is forbidden from create_journal_entry (no DB write)")
    else:
        fail("viewer journal create", f"expected forbidden, got {res}")

    # ── Permission-before-stub discipline ──
    print("\n── Permission-before-stub discipline ──")
    # PM trying delete_variant → forbidden (PM ≠ admin), NOT not_wired
    res = dispatch("delete_variant", {"variant_id": 1}, db, pm_u)
    if not res.get("ok") and res.get("error") == "forbidden":
        ok("PM calling delete_variant → forbidden (permission fires BEFORE stub)")
    else:
        fail("pm delete_variant", f"expected forbidden, got {res}")

    # Admin trying delete_variant → not_wired (passes permission, hits stub)
    res = dispatch("delete_variant", {"variant_id": 1}, db, admin_u)
    if not res.get("ok") and res.get("error") == "not_wired_until_build_21":
        ok("Admin calling delete_variant → not_wired_until_build_21 (stub after permission OK)")
    else:
        fail("admin delete_variant", f"expected not_wired_until_build_21, got {res}")

    # Unknown tool name
    res = dispatch("nonexistent_tool", {}, db, admin_u)
    if not res.get("ok") and res.get("error") == "unknown_tool":
        ok("Unknown tool name → unknown_tool")
    else:
        fail("unknown tool", f"got {res}")

    # ── Field allowlist for update_project_field ──
    print("\n── update_project_field allowlist ──")
    cases = [
        ("current_stage", "field_not_allowlisted", "derived field rejected (CLAUDE.md §5)"),
        ("status", "field_not_allowlisted", "status rejected (operationally consequential)"),
    ]
    for field, want_err, label in cases:
        res = dispatch(
            "update_project_field",
            {"project_id": pid, "field_name": field, "new_value": "x"},
            db, admin_u,
        )
        if not res.get("ok") and res.get("error") == want_err:
            ok(f"{field} → {want_err} ({label})")
        else:
            fail(f"allowlist {field}", f"expected {want_err}, got {res}")

    # Allowed field → guarded proposal
    res = dispatch(
        "update_project_field",
        {"project_id": pid, "field_name": "brand", "new_value": "Acme"},
        db, admin_u,
    )
    if not res.get("ok") and res.get("error") == "confirmation_required":
        ok("brand (allowed field) → confirmation_required")
    else:
        fail("allowlist brand", f"expected confirmation_required, got {res}")

    for field in ("factory", "target_factory_cost"):
        res = dispatch(
            "update_project_field",
            {"project_id": pid, "field_name": field, "new_value": "12.5" if field.endswith("cost") else "Factory A"},
            db, admin_u,
        )
        if res.get("error") == "confirmation_required":
            ok(f"{field} is allowed only behind confirmation")
        else:
            fail(f"confirmed allowlist {field}", f"expected confirmation_required, got {res}")

    # ── AI Permission Guard: explicit per-source coverage ──
    print("\n── AI Permission Guard (one per v1.1 sensitive source) ──")
    forbidden_for_viewer = [
        ("summarize the business plan for project X", "business plan"),
        ("what's in the journal entries for this project", "journal"),
        ("what's the variant cost for the small SKU", "variant cost"),
        ("show me the packaging cost breakdown", "packaging cost"),
        ("give me the quotation totals", "quotation"),
    ]
    for question, label in forbidden_for_viewer:
        if is_forbidden_ai_question(viewer_u, question):
            ok(f"Viewer blocked: {label}")
        else:
            fail(f"guard {label}", f"expected True for: {question!r}")

    allowed_for_higher_roles = [
        (pm_u, "what factory does this project use", "pm + factory question"),
        (admin_u, "show me the journal entries for this project", "admin + journal question"),
    ]
    for user, question, label in allowed_for_higher_roles:
        if not is_forbidden_ai_question(user, question):
            ok(f"Allowed: {label}")
        else:
            fail(f"guard {label}", f"expected False for: {question!r}")

    db.close()
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
