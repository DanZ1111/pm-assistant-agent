"""v1.3 Build 09 — Planning Sandbox Design (design-only) tests.

This build ships ONE markdown file and zero code. The test exists as a
regression guard against scope drift: assert the design doc exists,
covers all 8 locked sections from the user's spec, and that no app code,
schema, i18n, or migration count changed in this build.

Per the design doc: 'If any of the above lands in this build, it's a Lock
violation — revert.'
"""
import json
import os
import re
import sys


PASS, FAIL = [], []
DESIGN_DOC = "V13_BUILD09_PLANNING_SANDBOX_DESIGN.md"


def ok(n):
    PASS.append(n)
    print(f"  ✓  {n}")


def fail(n, r):
    FAIL.append((n, r))
    print(f"  ✗  {n}: {r}")


def main():
    # ── 1. Design doc exists ──
    print("\n── 1. Design doc exists ──")
    if os.path.exists(DESIGN_DOC):
        size = os.path.getsize(DESIGN_DOC)
        ok(f"{DESIGN_DOC} exists ({size} bytes)")
    else:
        fail("doc missing", f"{DESIGN_DOC} not found"); _p(); return False

    with open(DESIGN_DOC, encoding="utf-8") as f:
        doc = f.read()

    # ── 2. All 8 locked sections present ──
    # User-specified lock list (verbatim from the Build 09 brief):
    # purpose / 6 template types / module model / dependency+overlap /
    # estimated launch / save-current-as-template / open schema /
    # v1.4 implementation sequence.
    print("\n── 2. All 8 user-locked sections present ──")
    locked_sections = [
        ("1. Purpose of the Planning Sandbox",   "purpose"),
        ("2. The 6 template types",              "6 templates"),
        ("3. The Module model",                  "module model"),
        ("4. Dependency / overlap concepts",     "dependency + overlap"),
        ("5. Estimated launch date logic",       "estimated launch"),
        ("6. Save-current-as-template concept",  "save-as-template"),
        ("7. Open schema decisions",             "open schema"),
        ("8. Recommended v1.4 implementation sequence", "v1.4 sequence"),
    ]
    for heading, label in locked_sections:
        if heading in doc:
            ok(f"Section present: {label}")
        else:
            fail(f"section missing: {label}", f"heading '{heading}' not found")

    # ── 3. 6 template types named ──
    print("\n── 3. All 6 template types named in doc ──")
    template_names = [
        "Simple OEM Knife",
        "Standard Folding Knife",
        "New Mechanism Knife",
        "Gift Set / Combo Pack",
        "Packaging-heavy Retail Product",
        "Amazon Launch Product",
    ]
    for name in template_names:
        if name in doc:
            ok(f"Template named: {name}")
        else:
            fail(f"template missing: {name}", "not in design doc")

    # ── 4. All 6 open schema questions answered (Q1..Q6) ──
    print("\n── 4. All 6 open schema decisions present (Q1..Q6) ──")
    for q in ("Q1.", "Q2.", "Q3.", "Q4.", "Q5.", "Q6."):
        if q in doc:
            ok(f"Schema decision {q} present")
        else:
            fail(f"schema decision {q} missing", "")

    # ── 5. v1.4 sequence is 4 sub-builds ──
    print("\n── 5. v1.4 implementation sequence — 4 sub-builds ──")
    subbuilds = ["v1.4 Build 01", "v1.4 Build 02", "v1.4 Build 03", "v1.4 Build 04"]
    for sb in subbuilds:
        if sb in doc:
            ok(f"v1.4 sub-build present: {sb}")
        else:
            fail(f"v1.4 sub-build missing: {sb}", "")

    # ── 6. NO app code, schema, i18n, or migration changes in this build ──
    # Static checks per the Codex brief: "no app code changed; baseline still passes."
    # We don't run git diff here (env may not have git); instead we assert the
    # invariants that Build 09 promises to leave untouched.
    print("\n── 6. Invariants — no schema / no migration / parity unchanged ──")

    # Migration count still 6 (Build 07B added 006; no Build 09 migration)
    from app.migrations import MIGRATIONS
    if len(MIGRATIONS) == 6:
        ok("MIGRATIONS still 6 entries (Build 09 added zero migrations)")
    else:
        fail("migration count drift", f"expected 6, got {len(MIGRATIONS)}")

    # i18n parity still 714/714 (Build 08 added 26 keys; Build 09 adds zero)
    with open("app/i18n/en.json", encoding="utf-8") as f: en = json.load(f)
    with open("app/i18n/zh.json", encoding="utf-8") as f: zh = json.load(f)
    if len(en) == 714 and len(zh) == 714 and set(en) == set(zh):
        ok("i18n parity unchanged at 714/714 (Build 09 added zero keys)")
    else:
        fail("i18n drift", f"en={len(en)} zh={len(zh)} parity={set(en)==set(zh)}")

    # No new ProjectBlocker / ProjectPhase columns and no new template tables
    import sqlite3
    conn = sqlite3.connect("pm_tracker.db")
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    finally:
        conn.close()
    forbidden = {"timeline_templates", "timeline_template_modules",
                 "timeline_template_module_dependencies",
                 "project_phase_dependencies"}
    present_forbidden = forbidden & tables
    if not present_forbidden:
        ok("No Planning Sandbox tables present (Build 09 = design-only)")
    else:
        fail("table drift", f"forbidden tables present: {present_forbidden}")

    # No can_overlap / overlap_group on project_phases yet
    cols = {r[1] for r in sqlite3.connect("pm_tracker.db").execute(
        "PRAGMA table_info(project_phases)"
    ).fetchall()}
    if "can_overlap" not in cols and "overlap_group" not in cols:
        ok("project_phases unchanged (no can_overlap / overlap_group columns)")
    else:
        fail("schema drift", f"unexpected cols: {{'can_overlap','overlap_group'}} & {cols}")

    # No new AI tools for templates
    from app.ai.tools import TOOL_SCHEMAS
    tool_names = {t["function"]["name"] for t in TOOL_SCHEMAS}
    template_tools = {"create_timeline_template", "list_timeline_templates",
                       "apply_timeline_template", "add_phase_dependency",
                       "remove_phase_dependency", "create_template_from_project"}
    leaked_tools = template_tools & tool_names
    if not leaked_tools:
        ok("No Planning Sandbox AI tools registered (deferred to v1.4)")
    else:
        fail("AI tool drift", f"unexpected tools: {leaked_tools}")

    # ── 7. Decision log timestamp present ──
    print("\n── 7. Decision log entries present ──")
    if "2026-06-06" in doc and "Decision log" in doc:
        ok("Decision log present with at least one dated row")
    else:
        fail("decision log", "missing log or dated row")

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
