"""v1.3 Build 07B — Blocker model + Add Blocker wiring tests.

Verifies (per V13_BUILD07B_EXECUTION_PLAN.md, Locks 1-10):
- Migration 006: project_blockers table + 2 indexes (idempotent).
- crud.{create,update,resolve}_blocker write project_changes audit rows.
- crud.{get_active_blockers_for_project, get_active_phase_blocker_ids,
        get_blockers_by_phase} return expected shapes.
- Routes POST /command/{add,edit,resolve}-blocker enforce permissions,
  validate input, redirect with cc_result + #timeline-command-center.
- Lock 3: phase_id must belong to same project; project-level blockers
  do NOT light up any phase strip block.
- Lock 4: tile shows newest active + +N more active count badge only.
- Lock 5: Pulse cascade — active blocker beats delay/thesis/missing-field.
- Lock 6: resolve is one-click; sets resolved_at + resolved_by_user_id;
  writes blocker_resolved change-log row.
- Lock 9: AI tools confirmation-gated; no delete_blocker AI tool.
- i18n parity at 688/688.
- Build 06 / 07A / 02 invariants preserved.
"""
import json
import os
import re
import sqlite3
import sys
from datetime import date, timedelta

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


def db_execute(sql, params=()):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def cleanup(name_prefix):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE name LIKE ?", (name_prefix + "%",))
        for (pid,) in cur.fetchall():
            cur.execute("DELETE FROM project_blockers WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_variant_components WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_variants WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_changes WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM phase_plan_changes WHERE phase_id IN (SELECT id FROM project_phases WHERE project_id = ?)", (pid,))
            cur.execute("DELETE FROM project_phases WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_files WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_journal_entries WHERE project_id = ?", (pid,))
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

    cleanup("b07b_test")

    # ── 1. Migration 006: table + indexes ──
    print("\n── 1. Migration 006 — project_blockers table + indexes ──")
    cols = {r[1] for r in db_query("PRAGMA table_info(project_blockers)")}
    expected_cols = {
        "id", "project_id", "phase_id", "title", "description", "severity",
        "status", "created_at", "created_by_user_id", "resolved_at", "resolved_by_user_id",
    }
    missing = expected_cols - cols
    if not missing:
        ok(f"project_blockers has all {len(expected_cols)} columns")
    else:
        fail("table cols", f"missing: {missing}")
    idx = {r[0] for r in db_query("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='project_blockers'")}
    if "ix_pb_project_status" in idx and "ix_pb_phase" in idx:
        ok("Both ix_pb_project_status + ix_pb_phase indexes present")
    else:
        fail("indexes", f"got {idx}")
    from app.migrations import MIGRATIONS
    migration_names = [name for name, _ in MIGRATIONS]
    if len(MIGRATIONS) >= 6 and "006_v1_3_add_project_blockers" in migration_names:
        ok(f"MIGRATIONS include Build 07B migration 006 (count now {len(MIGRATIONS)})")
    else:
        fail("migration inventory", f"missing 006_v1_3_add_project_blockers in {migration_names}")

    # ── 2. Model + relationships ──
    print("\n── 2. ProjectBlocker model + relationships ──")
    from app.models import ProjectBlocker, Project, ProjectPhase
    if all(hasattr(ProjectBlocker, n) for n in ("project", "phase", "created_by", "resolved_by")):
        ok("ProjectBlocker relationships defined")
    else:
        fail("relationships", "missing one of project/phase/created_by/resolved_by")
    if hasattr(Project, "blockers") and hasattr(ProjectPhase, "blockers"):
        ok("Project.blockers + ProjectPhase.blockers back-populates")
    else:
        fail("back_populates", "missing")

    # ── 3. i18n parity at 688/688 + key removal ──
    print("\n── 3. i18n parity + key churn ──")
    with open("app/i18n/en.json") as f: en = json.load(f)
    with open("app/i18n/zh.json") as f: zh = json.load(f)
    if set(en) == set(zh):
        ok(f"en/zh parity at {len(en)} keys")
    else:
        fail("parity", f"en={len(en)} zh={len(zh)}")
    if len(en) >= 688:
        ok(f"key count ≥ 688 (got {len(en)})")
    else:
        fail("key count", f"expected ≥ 688, got {len(en)}")
    new_keys = [
        "timeline.blocker_title", "timeline.blocker_empty",
        "timeline.blocker_opened_meta", "timeline.blocker_opened_today",
        "timeline.blocker_more_count",
        "timeline.blocker_severity_low", "timeline.blocker_severity_medium", "timeline.blocker_severity_high",
        "timeline.btn_add_blocker", "timeline.btn_add_another_blocker",
        "timeline.btn_resolve_blocker", "timeline.btn_edit_blocker",
        "timeline.cc_blocker_title_label", "timeline.cc_blocker_title_placeholder",
        "timeline.cc_blocker_description_label", "timeline.cc_blocker_severity_label",
        "timeline.cc_blocker_phase_label", "timeline.cc_blocker_phase_none",
        "timeline.cc_result_blocker_resolved", "timeline.cc_result_blocker_empty_title",
        "pulse.blocker_action_title", "pulse.blocker_action_copy", "pulse.open_command_center",
    ]
    missing = [k for k in new_keys if k not in en]
    if not missing:
        ok(f"All {len(new_keys)} Build 07B i18n keys present in EN")
    else:
        fail("Build 07B keys", f"missing: {missing}")
    removed = [k for k in ("timeline.btn_add_blocker_disabled", "timeline.btn_add_blocker_tooltip") if k not in en]
    if len(removed) == 2:
        ok("Removed both Build 06/07A disabled-button strings")
    else:
        fail("removed keys", f"still present: {[k for k in ('timeline.btn_add_blocker_disabled','timeline.btn_add_blocker_tooltip') if k in en]}")

    # ── 4. Direct crud — create / update / resolve / audit ──
    print("\n── 4. crud.* blocker helpers ──")
    from app.database import SessionLocal
    from app import crud
    pid = make_project(admin, "b07b_test_main", PM_USER)
    rows = db_query("SELECT id FROM project_phases WHERE project_id=? ORDER BY phase_order LIMIT 2", (pid,))
    p1_id, p2_id = rows[0][0], rows[1][0]
    pm_user_id = db_query("SELECT id FROM users WHERE username=?", (PM_USER,))[0][0]

    sess = SessionLocal()
    try:
        b = crud.create_blocker(
            sess, pid, title="Packaging cost is missing",
            description="Vendor has not quoted yet",
            severity="high",
            phase_id=p1_id,
            created_by_user_id=pm_user_id,
            changed_by="user",
        )
    finally:
        sess.close()
    if b and b.status == "active" and b.severity == "high" and b.phase_id == p1_id:
        ok(f"create_blocker inserted active blocker id={b.id}")
    else:
        fail("create_blocker", f"got {b!r}")
    audit = db_query("SELECT change_type, summary FROM project_changes WHERE project_id=? AND change_type='blocker_opened'", (pid,))
    if audit and "Packaging" in audit[0][1]:
        ok("create_blocker wrote blocker_opened change-log row")
    else:
        fail("create audit", f"got {audit}")

    # update_blocker — allowlist enforced
    sess = SessionLocal()
    try:
        crud.update_blocker(sess, b.id, {"title": "Packaging cost still missing", "severity": "medium",
                                          "description": "updated by test",
                                          "status": "ignore_me"}, changed_by="user", changed_by_user_id=pm_user_id)
    finally:
        sess.close()
    row = db_query("SELECT title, severity, status FROM project_blockers WHERE id=?", (b.id,))[0]
    if row[0] == "Packaging cost still missing" and row[1] == "medium" and row[2] == "active":
        ok("update_blocker mutated allowlisted fields; ignored 'status' (not in whitelist)")
    else:
        fail("update_blocker", f"row={row}")
    audit2 = db_query("SELECT COUNT(*) FROM project_changes WHERE project_id=? AND change_type='blocker_updated'", (pid,))[0][0]
    if audit2 >= 1:
        ok("update_blocker wrote blocker_updated change-log row")
    else:
        fail("update audit", f"got {audit2}")

    # resolve_blocker — Lock 6 audit
    sess = SessionLocal()
    try:
        rb = crud.resolve_blocker(sess, b.id, resolved_by_user_id=pm_user_id, changed_by="user")
    finally:
        sess.close()
    row = db_query("SELECT status, resolved_at, resolved_by_user_id FROM project_blockers WHERE id=?", (b.id,))[0]
    if row[0] == "resolved" and row[1] is not None and row[2] == pm_user_id:
        ok(f"resolve_blocker sets status=resolved + resolved_at + resolved_by_user_id={pm_user_id}")
    else:
        fail("resolve_blocker fields", f"row={row}")
    audit3 = db_query("SELECT change_type FROM project_changes WHERE project_id=? AND change_type='blocker_resolved'", (pid,))
    if audit3:
        ok("resolve_blocker wrote blocker_resolved change-log row")
    else:
        fail("resolve audit", "no row")

    # Lock 3: phase_id mismatch returns None
    sess = SessionLocal()
    try:
        bad = crud.create_blocker(sess, pid, title="Bad", phase_id=99999, created_by_user_id=pm_user_id)
    finally:
        sess.close()
    if bad is None:
        ok("create_blocker rejects phase_id from another project (Lock 3)")
    else:
        fail("Lock 3", "wrong-project phase_id accepted")

    # ── 5. Query helpers ──
    print("\n── 5. crud query helpers ──")
    sess = SessionLocal()
    try:
        b2 = crud.create_blocker(sess, pid, title="Active project-level", severity="low",
                                  created_by_user_id=pm_user_id)
        b3 = crud.create_blocker(sess, pid, title="Active on phase 2", severity="high",
                                  phase_id=p2_id, created_by_user_id=pm_user_id)
        active_list = crud.get_active_blockers_for_project(sess, pid)
        phase_ids = crud.get_active_phase_blocker_ids(sess, pid)
        by_phase = crud.get_blockers_by_phase(sess, p2_id)
    finally:
        sess.close()
    if len(active_list) == 2:
        ok("get_active_blockers_for_project returns only active (2 of 3 total)")
    else:
        fail("active_list count", f"got {len(active_list)}")
    if active_list and active_list[0].id == b3.id:
        ok("Active list ordered newest first")
    else:
        fail("active_list order", f"first id={active_list[0].id if active_list else None}, expected {b3.id}")
    if phase_ids == {p2_id}:
        ok(f"get_active_phase_blocker_ids excludes project-level blockers (got {{{p2_id}}})")
    else:
        fail("phase_ids", f"got {phase_ids}")
    if len(by_phase) == 1 and by_phase[0].id == b3.id:
        ok("get_blockers_by_phase filters correctly + only active by default")
    else:
        fail("by_phase", f"got {by_phase}")

    # ── 6. Template — honest tile + phase-strip dot ──
    print("\n── 6. Template — honest blocker tile + phase-strip dot ──")
    page = pm.get(f"{BASE}/projects/{pid}").text
    for marker, msg in [
        ('data-blocker-state="active"', "Tile renders in active state"),
        ('class="timeline-blocker-tile timeline-blocker-active"', "Tile carries active class"),
        ("Active on phase 2", "Newest active blocker title rendered"),
        ('timeline-blocker-severity-high', "Severity 'high' badge class"),
        ('+1 more active', "Active count badge (+N more active) per Lock 4"),
        (f'data-blocker="active"', "Phase block with active phase-linked blocker has data-blocker attr"),
        ('timeline-phase-blocker-dot', "Phase strip red dot CSS marker"),
        ('timeline-phase-has-blocker', "Phase block class for blocker-attached phases"),
    ]:
        if marker in page:
            ok(msg)
        else:
            fail(msg, f"marker '{marker}' missing")
    # Lock 3: project-level blocker b2 must NOT light up any phase
    # Count dots — should be exactly 1 (only phase 2)
    dot_count = page.count('timeline-phase-blocker-dot')
    if dot_count == 1:
        ok(f"Project-level blocker does NOT light up a phase block (exactly 1 dot, on p2)")
    else:
        fail("project-level dot leak", f"got {dot_count} dots, expected 1")

    # Old placeholder markup is GONE
    if 'data-placeholder="blocker"' not in page:
        ok("Build 06 placeholder block removed from template")
    else:
        fail("placeholder still present", "data-placeholder='blocker' lingers")

    # ── 7. Template — empty state ──
    print("\n── 7. Template — empty state when no active blockers ──")
    # Resolve b2 + b3, then re-render
    sess = SessionLocal()
    try:
        crud.resolve_blocker(sess, b2.id, resolved_by_user_id=pm_user_id)
        crud.resolve_blocker(sess, b3.id, resolved_by_user_id=pm_user_id)
    finally:
        sess.close()
    page_empty = pm.get(f"{BASE}/projects/{pid}").text
    if 'data-blocker-state="empty"' in page_empty and "No active blockers" in page_empty:
        ok("Empty state renders 'No active blockers.'")
    else:
        fail("empty state", "missing")
    if 'data-blocker="active"' not in page_empty and 'timeline-phase-blocker-dot' not in page_empty:
        ok("Resolved blockers do NOT trigger phase dots")
    else:
        fail("resolved dot leak", "dot still present")

    # ── 8. Routes — POST /command/add-blocker happy path ──
    print("\n── 8. POST /command/add-blocker — happy path ──")
    r = pm.post(f"{BASE}/projects/{pid}/command/add-blocker",
        data={"title": "Sample arrived chipped", "description": "Needs rework",
              "severity": "medium", "phase_id": p1_id},
        allow_redirects=False, timeout=5)
    if "cc_result=ok" in r.headers["location"] and "#timeline-command-center" in r.headers["location"]:
        ok("add-blocker redirect: cc_result=ok + #timeline-command-center")
    else:
        fail("add-blocker redirect", f"loc={r.headers.get('location')}")
    rows = db_query("SELECT id, title FROM project_blockers WHERE project_id=? AND status='active'", (pid,))
    if rows and any("chipped" in row[1] for row in rows):
        ok("add-blocker created row")
    else:
        fail("add-blocker row", f"rows={rows}")

    # ── 9. add-blocker — empty title rejected ──
    print("\n── 9. add-blocker — empty title ──")
    r = pm.post(f"{BASE}/projects/{pid}/command/add-blocker",
        data={"title": "   ", "severity": "medium"}, allow_redirects=False, timeout=5)
    if "cc_result=blocker_empty_title" in r.headers["location"]:
        ok("Empty title rejected with cc_result=blocker_empty_title")
    else:
        fail("empty title", f"loc={r.headers['location']}")

    # ── 10. add-blocker — phase_id from another project (Lock 3) ──
    print("\n── 10. add-blocker — phase_id mismatch (Lock 3) ──")
    other_pid = make_project(admin, "b07b_test_other", ADMIN)
    other_phase_id = db_query("SELECT id FROM project_phases WHERE project_id=? LIMIT 1", (other_pid,))[0][0]
    r = pm.post(f"{BASE}/projects/{pid}/command/add-blocker",
        data={"title": "cross-project attack", "severity": "high", "phase_id": other_phase_id},
        allow_redirects=False, timeout=5)
    if "cc_result=not_authorized" in r.headers["location"]:
        ok("phase_id from another project rejected with not_authorized")
    else:
        fail("Lock 3", f"loc={r.headers['location']}")
    cnt = db_query("SELECT COUNT(*) FROM project_blockers WHERE title='cross-project attack'")[0][0]
    if cnt == 0:
        ok("Cross-project attack did NOT write a blocker")
    else:
        fail("cross-project leak", f"got {cnt} rows")

    # ── 11. add-blocker — viewer rejected ──
    print("\n── 11. add-blocker — viewer rejected ──")
    r = viewer.post(f"{BASE}/projects/{pid}/command/add-blocker",
        data={"title": "viewer try", "severity": "low"}, allow_redirects=False, timeout=5)
    if "cc_result=not_authorized" in r.headers["location"]:
        ok("Viewer add-blocker rejected with not_authorized")
    else:
        fail("viewer add-blocker", f"loc={r.headers['location']}")

    # ── 12. edit-blocker — happy path ──
    print("\n── 12. edit-blocker — happy path ──")
    blocker_id = rows[0][0]
    r = pm.post(f"{BASE}/projects/{pid}/command/edit-blocker",
        data={"blocker_id": blocker_id, "title": "Sample arrived chipped (updated)",
              "description": "Edited", "severity": "high", "phase_id": ""},
        allow_redirects=False, timeout=5)
    if "cc_result=ok" in r.headers["location"]:
        ok("edit-blocker redirect cc_result=ok")
    else:
        fail("edit redirect", f"loc={r.headers['location']}")
    row = db_query("SELECT title, severity, phase_id FROM project_blockers WHERE id=?", (blocker_id,))[0]
    if "updated" in row[0] and row[1] == "high" and row[2] is None:
        ok(f"edit-blocker mutated fields (severity=high, phase_id cleared)")
    else:
        fail("edit fields", f"row={row}")

    # ── 13. edit-blocker — empty title rejected ──
    print("\n── 13. edit-blocker — empty title rejected ──")
    r = pm.post(f"{BASE}/projects/{pid}/command/edit-blocker",
        data={"blocker_id": blocker_id, "title": "", "severity": "high"},
        allow_redirects=False, timeout=5)
    if "cc_result=blocker_empty_title" in r.headers["location"]:
        ok("edit-blocker empty title rejected")
    else:
        fail("edit empty title", f"loc={r.headers['location']}")

    # ── 14. edit-blocker — non-owner-project rejected ──
    print("\n── 14. edit-blocker — wrong project ID rejected ──")
    r = pm.post(f"{BASE}/projects/{other_pid}/command/edit-blocker",
        data={"blocker_id": blocker_id, "title": "hijack", "severity": "high"},
        allow_redirects=False, timeout=5)
    if "cc_result=not_authorized" in r.headers["location"]:
        ok("edit-blocker on different project rejected")
    else:
        fail("edit wrong project", f"loc={r.headers['location']}")

    # ── 15. resolve-blocker — happy path + banner i18n ──
    print("\n── 15. resolve-blocker — happy path ──")
    r = pm.post(f"{BASE}/projects/{pid}/command/resolve-blocker",
        data={"blocker_id": blocker_id}, allow_redirects=False, timeout=5)
    if "cc_result=ok" in r.headers["location"] and "cc_action=resolve-blocker" in r.headers["location"]:
        ok("resolve-blocker redirect ok")
    else:
        fail("resolve redirect", f"loc={r.headers['location']}")
    row = db_query("SELECT status, resolved_at, resolved_by_user_id FROM project_blockers WHERE id=?", (blocker_id,))[0]
    if row[0] == "resolved" and row[1] and row[2] == pm_user_id:
        ok("resolve-blocker set status + resolved_at + resolved_by_user_id")
    else:
        fail("resolve fields", f"row={row}")
    # Banner i18n
    page_banner = pm.get(f"{BASE}/projects/{pid}?cc_action=resolve-blocker&cc_result=ok").text
    if "Blocker resolved." in page_banner:
        ok("Resolve banner shows i18n cc_result_blocker_resolved string")
    else:
        fail("resolve banner i18n", "missing")

    # ── 16. resolve-blocker — viewer rejected ──
    print("\n── 16. resolve-blocker — viewer rejected ──")
    sess = SessionLocal()
    try:
        b_for_view = crud.create_blocker(sess, pid, title="for viewer test",
                                          created_by_user_id=pm_user_id)
    finally:
        sess.close()
    r = viewer.post(f"{BASE}/projects/{pid}/command/resolve-blocker",
        data={"blocker_id": b_for_view.id}, allow_redirects=False, timeout=5)
    if "cc_result=not_authorized" in r.headers["location"]:
        ok("Viewer resolve rejected with not_authorized")
    else:
        fail("viewer resolve", f"loc={r.headers['location']}")
    s = db_query("SELECT status FROM project_blockers WHERE id=?", (b_for_view.id,))[0][0]
    if s == "active":
        ok("Viewer resolve did NOT mutate state")
    else:
        fail("viewer mutation", f"status={s}")

    # ── 17. Pulse cascade — blocker beats delay (Lock 5) ──
    print("\n── 17. Pulse cascade — Lock 5 blocker > delay ──")
    # Set p1 planned_end_date 10 days in past so delay branch would otherwise fire
    db_execute("UPDATE project_phases SET planned_end_date=?, status='in_progress' WHERE id=?",
               ((date.today() - timedelta(days=10)).isoformat(), p1_id))
    page_p = pm.get(f"{BASE}/projects/{pid}").text
    if "Resolve blocker" in page_p:
        ok("Pulse cascade renders 'Resolve blocker' branch when active blockers exist")
    else:
        fail("pulse blocker branch", "missing")
    # Resolve the blocker, re-render; delay branch should now fire
    sess = SessionLocal()
    try:
        crud.resolve_blocker(sess, b_for_view.id, resolved_by_user_id=pm_user_id)
    finally:
        sess.close()
    page_p2 = pm.get(f"{BASE}/projects/{pid}").text
    if "Resolve blocker" not in page_p2:
        ok("After resolving, Pulse blocker branch falls back to delay branch")
    else:
        fail("pulse fallback", "blocker branch still rendering after resolve")

    # ── 18. AI tools — schemas + confirmation + no delete_blocker ──
    print("\n── 18. AI tools — schemas, confirmation gating, no delete tool ──")
    from app.ai.tools import TOOL_SCHEMAS, CONFIRMATION_TOOLS, UPDATE_BLOCKER_ALLOWED, _HANDLERS
    names = {t["function"]["name"] for t in TOOL_SCHEMAS}
    for n in ("create_blocker", "update_blocker", "resolve_blocker"):
        if n in names and n in CONFIRMATION_TOOLS and n in _HANDLERS:
            ok(f"AI tool {n}: schema + CONFIRMATION_TOOLS + handler")
        else:
            fail(f"AI tool {n}", f"schema={n in names} confirm={n in CONFIRMATION_TOOLS} handler={n in _HANDLERS}")
    if "delete_blocker" not in names:
        ok("delete_blocker NOT in TOOL_SCHEMAS (Lock 9 — admin-only UI path)")
    else:
        fail("delete_blocker exposed", "should be admin-only UI, not AI")
    if UPDATE_BLOCKER_ALLOWED == {"title", "description", "severity", "phase_id"}:
        ok("UPDATE_BLOCKER_ALLOWED whitelist correct")
    else:
        fail("UPDATE_BLOCKER_ALLOWED", f"got {UPDATE_BLOCKER_ALLOWED}")

    # ── 19. AI tools — confirmation gating ──
    print("\n── 19. AI dispatcher — confirmation_required without confirm flag ──")
    from app.ai.tools import dispatch
    from app.models import User
    pm_user_obj = SessionLocal().query(User).filter(User.username == PM_USER).first()
    sess = SessionLocal()
    try:
        res = dispatch("create_blocker", {"project_id": pid, "title": "AI test blocker"}, sess, pm_user_obj, confirmed=False)
    finally:
        sess.close()
    if not res.get("ok") and res.get("error") == "confirmation_required":
        ok("create_blocker dispatch returns confirmation_required when confirmed=False")
    else:
        fail("AI confirmation gate", f"got {res}")
    sess = SessionLocal()
    try:
        res2 = dispatch("create_blocker", {"project_id": pid, "title": "AI confirmed blocker", "severity": "low"},
                         sess, pm_user_obj, confirmed=True)
    finally:
        sess.close()
    if res2.get("ok") and "blocker_id" in res2:
        ok(f"create_blocker dispatch with confirmed=True creates row (id={res2['blocker_id']})")
    else:
        fail("AI confirmed create", f"got {res2}")

    # ── 20. Regression — Build 06 invariants preserved ──
    print("\n── 20. Build 06 / 07A invariants preserved ──")
    page_reg = pm.get(f"{BASE}/projects/{pid}").text
    for marker, msg in [
        ('id="timeline-command-center"', "Command Center section"),
        ("timeline-phase-strip", "Phase strip"),
        ("timeline-tile-current", "Current tile"),
        ("timeline-tile-deadline", "Deadline tile"),
        ('id="timelineDetailedTable"', "Detailed Table <details> wrapper"),
        ('data-cc-form="finish"', "Build 07A Finish button"),
        ('data-cc-form="adjust"', "Build 07A Adjust button"),
        ('data-cc-form="add-update"', "Build 07A Add Update button"),
        ('data-cc-form="add-blocker"', "Build 07B Add Blocker button (replaces disabled placeholder)"),
    ]:
        if marker in page_reg:
            ok(f"invariant: {msg}")
        else:
            fail(msg, f"'{marker}' missing")

    cleanup("b07b_test")
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
