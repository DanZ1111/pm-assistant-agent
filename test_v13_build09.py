"""v1.3 Build 09 — Planning Sandbox Engineering Design (design-only) tests.

Amended 2026-06-06: the original Build 09 doc shipped at fc064a6 was
form-based + persisted-on-project. After PRD review with ChatGPT, the
user clarified the actual product is a VISUAL WORKFLOW CANVAS with
EXPLICIT DRAFT/APPLY SEPARATION. The doc was rewritten as an engineering
response to the PRD; the PRD is captured as Appendix A.

This test asserts the AMENDED structure: PRD appendix presence,
Cytoscape.js library decision lock, 10 PRD open questions locked with
defaults, 8-sub-build v1.4 sequence (not 4), 7-table schema sketch,
draft/apply separation as a non-negotiable, AND the design-only
invariants (no migrations, no new tables, no i18n drift, no new AI
tools).
"""
import json
import os
import sqlite3
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
    # ── 1. Design doc exists + is substantial ──
    print("\n── 1. Design doc exists + is substantial ──")
    if os.path.exists(DESIGN_DOC):
        size = os.path.getsize(DESIGN_DOC)
        # Amended doc is ~35-50 KB (engineering response + PRD appendix)
        if size >= 20000:
            ok(f"{DESIGN_DOC} exists, {size} bytes (≥ 20 KB amended target)")
        else:
            fail("doc too small", f"only {size} bytes — amendment may not have landed")
    else:
        fail("doc missing", f"{DESIGN_DOC} not found")
        _p(); return False

    with open(DESIGN_DOC, encoding="utf-8") as f:
        doc = f.read()

    # ── 2. Amendment note present ──
    print("\n── 2. Amendment note explicitly present ──")
    if "Amendment note (2026-06-06)" in doc:
        ok("Dated amendment note present")
    else:
        fail("amendment note", "missing — readers won't know this is the revised version")

    # ── 3. PRD captured verbatim as Appendix A ──
    print("\n── 3. PRD captured as Appendix A ──")
    if "Appendix A — Planning Sandbox PRD" in doc:
        ok("Appendix A header present")
    else:
        fail("appendix header", "missing — PRD should travel with the doc")
    prd_section_markers = [
        ("A.1 Purpose",       "PRD §1 Purpose"),
        ("A.3 Product Definition",  "PRD §3 Product Definition"),
        ("A.5 Key Product Principle", "PRD §5 (draft/apply separation — non-negotiable)"),
        ("A.11 Schedule Calculation Rule", "PRD §11 Schedule Calculation"),
        ("A.22 Template System", "PRD §22 Template System"),
        ("A.28 Open Questions",  "PRD §28 Open Questions"),
    ]
    for marker, label in prd_section_markers:
        if marker in doc:
            ok(f"PRD appendix carries: {label}")
        else:
            fail(f"PRD section missing: {label}", f"'{marker}' not found in Appendix A")

    # ── 4. Visual canvas + draft/apply separation locked in body ──
    print("\n── 4. Engineering response locks visual canvas + draft/apply separation ──")
    if "visual workflow canvas" in doc.lower():
        ok("Doc identifies the product as a 'visual workflow canvas'")
    else:
        fail("product identity", "'visual workflow canvas' phrase missing")
    if "draft/apply separation" in doc or "draft / apply separation" in doc:
        ok("Doc locks the draft/apply separation explicitly")
    else:
        fail("draft/apply lock", "missing — non-negotiable principle isn't locked")
    if "Sandbox edits never mutate live phases" in doc or "Sandbox edits never mutate" in doc:
        ok("Engineering invariant: sandbox edits do NOT mutate live phases")
    else:
        fail("non-mutation invariant", "missing")

    # ── 5. Cytoscape.js canvas library decision locked ──
    print("\n── 5. Canvas-rendering library decision locked ──")
    if "Cytoscape.js" in doc and "cytoscape-dagre" in doc:
        ok("Cytoscape.js + cytoscape-dagre named as the locked choice")
    else:
        fail("library lock", "Cytoscape.js or cytoscape-dagre not in doc")
    if "React Flow" in doc and "D3" in doc and "Bespoke SVG" in doc:
        ok("Alternatives (React Flow / D3 / Bespoke SVG) considered + rejected")
    else:
        fail("alternatives", "library comparison table incomplete")

    # ── 6. All 10 PRD open questions locked with defaults ──
    print("\n── 6. All 10 PRD §28 open questions locked ──")
    for qn in ("Q1.", "Q2.", "Q3.", "Q4.", "Q5.", "Q6.", "Q7.", "Q8.", "Q9.", "Q10."):
        if qn in doc:
            ok(f"PRD open question {qn} addressed in §6")
        else:
            fail(f"open Q {qn} missing", "not in engineering decisions")

    # ── 7. v1.4 sequence is 8 sub-builds (not 4) ──
    print("\n── 7. v1.4 sequence is 8 sub-builds ──")
    subbuilds = ["v1.4-01", "v1.4-02", "v1.4-03", "v1.4-04",
                 "v1.4-05", "v1.4-06", "v1.4-07", "v1.4-08"]
    for sb in subbuilds:
        if sb in doc:
            ok(f"v1.4 sub-build present: {sb}")
        else:
            fail(f"v1.4 sub-build missing: {sb}", "")
    # And explicitly NOT the old 4-sub-build wording
    if "v1.4 Build 01" not in doc and "v1.4 Build 04" not in doc:
        ok("Old 4-sub-build naming ('v1.4 Build 01') no longer present")
    else:
        fail("old naming lingers", "doc still references old 4-build sequence")

    # ── 8. Schema sketch covers 7 new tables ──
    print("\n── 8. Schema sketch covers 7 new tables ──")
    expected_tables = [
        "planning_module_library",
        "planning_sandboxes",
        "planning_sandbox_nodes",
        "planning_sandbox_edges",
        "planning_apply_events",
        "planning_templates",
        "planning_template_nodes",
    ]
    for t in expected_tables:
        if t in doc:
            ok(f"Schema names table: {t}")
        else:
            fail(f"table missing in schema: {t}", "")

    # ── 9. Migration plan: 007 → 010 (4 migrations across v1.4) ──
    print("\n── 9. Migration plan 007–010 ──")
    for mig in ("Migration 007", "Migration 009", "Migration 010"):
        # Migration 008 is a "placeholder" so accept its absence/presence
        if mig in doc:
            ok(f"Migration plan names: {mig}")
        else:
            fail(f"migration plan missing: {mig}", "")

    # ── 10. 6 PRD-named templates all referenced ──
    print("\n── 10. 6 PRD-named templates present ──")
    template_names = [
        "Simple OEM Knife",
        "Standard Folding Knife",
        "New Mechanism",
        "Gift Set",
        "Packaging-heavy Retail",
        "Amazon Launch",
    ]
    for name in template_names:
        if name in doc:
            ok(f"Template named: {name}")
        else:
            fail(f"template missing: {name}", "")

    # ── 11. Backend Honesty Mapping discipline applied ──
    print("\n── 11. Backend Honesty Mapping section present ──")
    if "Backend Honesty Mapping" in doc:
        ok("Backend Honesty Mapping discipline applied (per project pattern)")
    else:
        fail("BHM missing", "every display surface should trace to source-of-truth")

    # ── 12. Risk register present with mitigation notes ──
    print("\n── 12. Risk register present ──")
    if "Risk register" in doc and "Mitigation" in doc:
        ok("Risk register + mitigation notes present")
    else:
        fail("risk register", "missing")

    # ── 13. Decision log includes the 2026-06-06 amendment row ──
    print("\n── 13. Decision log carries the amendment row ──")
    if "AMENDMENT: visual canvas + draft/apply separation" in doc:
        ok("Decision log row for the amendment is present")
    else:
        fail("decision log amendment", "row missing — doc instruction requires this")

    # ── 14. INVARIANTS — no schema / no migration / no i18n drift ──
    # Build 09 (amended OR original) ships ZERO code. The test enforces this
    # by asserting the runtime state hasn't moved.
    print("\n── 14. Invariants — no schema / no migration / no i18n drift ──")
    from app.migrations import MIGRATIONS
    if len(MIGRATIONS) == 6:
        ok("MIGRATIONS count still 6 (Build 09 amendment added zero migrations)")
    else:
        fail("migration drift", f"expected 6, got {len(MIGRATIONS)}")

    with open("app/i18n/en.json", encoding="utf-8") as f: en = json.load(f)
    with open("app/i18n/zh.json", encoding="utf-8") as f: zh = json.load(f)
    if len(en) == 714 and len(zh) == 714 and set(en) == set(zh):
        ok("i18n parity unchanged at 714/714 (Build 09 added zero keys)")
    else:
        fail("i18n drift", f"en={len(en)} zh={len(zh)}")

    # No Planning Sandbox tables present in dev DB
    conn = sqlite3.connect("pm_tracker.db")
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    finally:
        conn.close()
    sandbox_tables = {"planning_sandboxes", "planning_sandbox_nodes",
                      "planning_sandbox_edges", "planning_module_library",
                      "planning_apply_events", "planning_templates",
                      "planning_template_nodes", "planning_template_edges"}
    present = sandbox_tables & tables
    if not present:
        ok("No Planning Sandbox tables present in DB (design-only respected)")
    else:
        fail("table drift", f"unexpected tables: {present}")

    # No new AI tools for sandbox/templates
    from app.ai.tools import TOOL_SCHEMAS
    tool_names = {t["function"]["name"] for t in TOOL_SCHEMAS}
    forbidden_tools = {"list_timeline_templates", "apply_timeline_template",
                       "apply_sandbox_to_project", "create_timeline_template",
                       "add_phase_dependency", "remove_phase_dependency"}
    leaked = forbidden_tools & tool_names
    if not leaked:
        ok("No Planning Sandbox AI tools registered (deferred to v1.4)")
    else:
        fail("AI tool drift", f"unexpected tools: {leaked}")

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
