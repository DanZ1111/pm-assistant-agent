"""v1.3 Build 09 — Planning Sandbox Engineering Design (design-only) tests.

Amended TWICE on 2026-06-06:
- Amendment 1: rewrite as engineering response to ChatGPT PRD (visual canvas
  + draft/apply separation).
- Amendment 2: fold Codex's V14_PLANNING_SANDBOX_IMPLEMENTATION_PLAN.md
  additions: 9-build v1.4 sequence (was 8), active-blocker check on Apply,
  10-step Apply transaction, semantic soft warnings, "edge crosses sandbox
  boundary" hard error, concrete route URL list, service-helper checklist,
  mobile guidance, sections 12-14 added to body.

This test asserts the doubly-amended structure: PRD appendix presence,
Cytoscape.js library decision lock, 10 PRD open questions locked, 9-build
v1.4 sequence (not 4 or 8), 7-table schema sketch with Codex's column
additions, Apply preconditions including active-blocker check, route +
service helper enumeration, mobile guidance, AND the design-only
invariants (no migrations, no new tables, no i18n drift, no new AI tools).
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
        # Doubly-amended doc is ~50-70 KB (engineering response + PRD appendix
        # + Codex-folded sections 12-14)
        if size >= 40000:
            ok(f"{DESIGN_DOC} exists, {size} bytes (≥ 40 KB doubly-amended target)")
        else:
            fail("doc too small", f"only {size} bytes — Amendment 2 may not have landed")
    else:
        fail("doc missing", f"{DESIGN_DOC} not found")
        _p(); return False

    with open(DESIGN_DOC, encoding="utf-8") as f:
        doc = f.read()

    # ── 2. Both amendment notes present ──
    print("\n── 2. Amendment 1 + Amendment 2 notes both present ──")
    if "Amendment 1 note (2026-06-06)" in doc:
        ok("Amendment 1 note present")
    else:
        fail("amendment 1 note", "missing")
    if "Amendment 2 note (2026-06-06)" in doc:
        ok("Amendment 2 note present (Codex additions folded in)")
    else:
        fail("amendment 2 note", "missing — readers won't see Codex additions")

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

    # ── 7. v1.4 sequence is 9 sub-builds (Amendment 2: was 8) ──
    print("\n── 7. v1.4 sequence is 9 sub-builds ──")
    subbuilds = ["v1.4-01", "v1.4-02", "v1.4-03", "v1.4-04",
                 "v1.4-05", "v1.4-06", "v1.4-07", "v1.4-08", "v1.4-09"]
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
    # Codex's two new slices are named explicitly
    if "Canvas Interaction Hardening" in doc:
        ok("v1.4-06 named 'Canvas Interaction Hardening' (Codex addition)")
    else:
        fail("v1.4-06 name", "Canvas Interaction Hardening slice missing")
    if "Release Hardening" in doc:
        ok("v1.4-09 named 'Release Hardening' (Codex addition)")
    else:
        fail("v1.4-09 name", "Release Hardening slice missing")

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

    # ── 13. Decision log includes both amendment rows ──
    print("\n── 13. Decision log carries both amendment rows ──")
    if "AMENDMENT: visual canvas + draft/apply separation" in doc:
        ok("Decision log row for Amendment 1 present")
    else:
        fail("decision log amendment 1", "row missing")
    if "Amendment 2" in doc and "Folded Codex" in doc:
        ok("Decision log row for Amendment 2 (Codex additions) present")
    else:
        fail("decision log amendment 2", "row missing")

    # ── 14. Codex-folded sections 12/13/14 present ──
    print("\n── 14. Codex-folded sections 12/13/14 present ──")
    for header, label in [
        ("## 12. Apply detailed semantics", "§12 Apply detailed semantics"),
        ("## 13. Routes and service-layer helpers", "§13 Routes + service helpers"),
        ("## 14. Mobile guidance", "§14 Mobile guidance"),
    ]:
        if header in doc:
            ok(f"Section present: {label}")
        else:
            fail(f"section missing: {label}", "")

    # ── 15. Active-blocker precondition on Apply (Codex addition) ──
    print("\n── 15. Active-blocker check on Apply (Codex addition) ──")
    if "active_blocker_attached" in doc and "ProjectBlocker" in doc:
        ok("Apply precondition: no active ProjectBlocker on existing phases")
    else:
        fail("active-blocker check", "Q2 + §12.3 should reference ProjectBlocker check")

    # ── 16. 10-step Apply transaction sequence ──
    print("\n── 16. Apply transaction is enumerated 10 steps ──")
    if "Apply transaction sequence (10 steps)" in doc:
        ok("10-step Apply sequence documented")
    else:
        fail("Apply sequence", "§12.5 should list the 10-step transaction")

    # ── 17. Hard error 'edge crosses sandbox boundary' (Codex addition) ──
    print("\n── 17. 'edge crosses sandbox boundary' hard error ──")
    if "cross_sandbox_edge" in doc:
        ok("Hard error 'cross_sandbox_edge' documented in §12.1")
    else:
        fail("cross-sandbox-edge hard error", "§12.1 should include this code")

    # ── 18. Semantic soft warnings (Codex addition) ──
    print("\n── 18. Semantic soft warnings (Codex addition) ──")
    semantic_warnings = ["packaging_before_design", "production_before_sample",
                          "terminal_not_launch_like", "missing_deliverable"]
    for w in semantic_warnings:
        if w in doc:
            ok(f"Soft warning: {w}")
        else:
            fail(f"soft warning missing: {w}", "")

    # ── 19. Route URL list enumerated (Codex addition) ──
    print("\n── 19. Route URLs enumerated in §13 ──")
    expected_routes = [
        "/projects/{project_id}/sandbox/create",
        "/projects/{project_id}/sandbox/{sandbox_id}/apply",
        "/projects/{project_id}/sandbox/{sandbox_id}/nodes",
        "/projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/update",
        "/projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/position",
        "/projects/{project_id}/sandbox/{sandbox_id}/edges",
        "/projects/{project_id}/sandbox/{sandbox_id}/save-template",
    ]
    for url in expected_routes:
        if url in doc:
            ok(f"Route URL: {url}")
        else:
            fail(f"route missing: {url}", "")

    # ── 20. Service helper checklist (Codex addition) ──
    print("\n── 20. Service helpers enumerated in §13.2 ──")
    expected_helpers = [
        "create_sandbox_blank", "create_sandbox_from_template",
        "list_modules", "list_templates",
        "create_sandbox_node", "update_sandbox_node",
        "delete_sandbox_node", "create_sandbox_edge",
        "compute_sandbox_schedule", "validate_sandbox_for_apply",
        "apply_sandbox_to_project", "save_sandbox_as_template",
    ]
    for h in expected_helpers:
        if h in doc:
            ok(f"Service helper: {h}")
        else:
            fail(f"helper missing: {h}", "")

    # ── 21. Schema additions: phase_type on nodes, lifecycle timestamps,
    #        updated_project_planned_launch_date on apply_events ──
    print("\n── 21. Schema additions (Codex) ──")
    schema_additions = [
        ("phase_type", "phase_type carried to planning_sandbox_nodes"),
        ("updated_project_planned_launch_date", "updated_project_planned_launch_date on apply_events"),
        ("uq_planning_sandboxes_one_draft", "partial unique index for draft lifecycle"),
    ]
    for marker, label in schema_additions:
        if marker in doc:
            ok(f"Schema addition: {label}")
        else:
            fail(f"schema addition missing: {label}", "")

    # ── 22. Sandbox lifecycle explicit ──
    print("\n── 22. Sandbox lifecycle is explicit (draft / applied / archived) ──")
    if "draft" in doc and "applied" in doc and "archived" in doc:
        ok("All 3 lifecycle states named")
    else:
        fail("lifecycle states", "missing one of draft/applied/archived")

    # ── 23. AI_TOOLS_REGISTRY.md requirement before v1.4 release ──
    print("\n── 23. AI_TOOLS_REGISTRY.md requirement before v1.4 release ──")
    if "AI_TOOLS_REGISTRY.md" in doc and "v1.4 release" in doc:
        ok("AI_TOOLS_REGISTRY.md required to be updated before v1.4 release")
    else:
        fail("AI registry req", "missing")

    # ── 24. Mobile guidance specifics ──
    print("\n── 24. Mobile guidance specifics ──")
    mobile_markers = [
        ("Horizontal scroll", "Canvas horizontal scroll allowed"),
        ("44×44", "Touch target minimum"),
        ("drawer", "Library/property panel drawer treatment"),
        ("390×844", "iPhone 13 screenshot target"),
    ]
    for marker, label in mobile_markers:
        if marker in doc:
            ok(f"Mobile guidance: {label}")
        else:
            fail(f"mobile spec missing: {label}", "")

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
