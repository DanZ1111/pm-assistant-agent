"""v1.3 Build 07A — Timeline Command Center Actions Backend tests.

Verifies (per V13_BUILD07_EXECUTION_PLAN.md, 07A scope):
- POST /command/finish-phase advances current → done + next → in_progress,
  rejects stale phase_id (Lock 3), rejects viewer/non-owner-PM.
- POST /command/adjust-due-date shifts planned_end_date, writes
  phase_plan_changes with reason, rejects empty reason (Lock 4),
  rejects viewer.
- POST /command/add-update creates a journal entry with author + type,
  rejects empty text, rejects viewer (can_view_journal=False), rejects
  non-owner PM.
- PRG: all 3 routes redirect to #timeline-command-center with
  ?cc_result=... + ?cc_action=...
- Result banner renders with data-cc-result attribute.
- [Add Blocker] tooltip updated to "Build 07B".
- AI Intake button still triggers side-panel opener (Build 06 invariant).
- Detailed Table /phases/{id}/edit + /finish unchanged (regression).
- Build 06 invariants preserved (#timeline-command-center, phase strip,
  3 tiles, placeholders, Detailed Table <details> closed by default,
  phase-row id anchors).
- i18n parity at 666/666.
- No new migration (still 5).
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

    cleanup("b07_test")

    # ── 1. i18n parity + Build 07A keys ──
    print("\n── 1. i18n parity + Build 07A keys ──")
    with open("app/i18n/en.json") as f: en = json.load(f)
    with open("app/i18n/zh.json") as f: zh = json.load(f)
    if set(en) == set(zh):
        ok(f"en/zh parity ({len(en)} keys)")
    else:
        fail("i18n parity", f"en={len(en)} zh={len(zh)}")
    if len(en) >= 666:
        ok(f"key count ≥ 666 (got {len(en)})")
    else:
        fail("key count", f"expected ≥ 666, got {len(en)}")
    cc_keys = [
        "timeline.cc_finish_confirm_title", "timeline.cc_finish_checklist",
        "timeline.cc_finish_note_label", "timeline.cc_adjust_new_date",
        "timeline.cc_adjust_reason_label", "timeline.cc_adjust_reason_placeholder",
        "timeline.cc_update_text_label", "timeline.cc_update_type_label",
        "timeline.cc_btn_confirm", "timeline.cc_btn_cancel",
        "timeline.cc_result_ok", "timeline.cc_result_reason_required",
        "timeline.cc_result_empty_update", "timeline.cc_result_phase_already_done",
        "timeline.cc_result_not_authorized",
    ]
    missing = [k for k in cc_keys if k not in en]
    if not missing:
        ok(f"All {len(cc_keys)} Build 07A cc_ keys present")
    else:
        fail("cc keys", f"missing: {missing}")
    # Build 07B removed timeline.btn_add_blocker_tooltip when the button was
    # promoted from disabled-placeholder to enabled form trigger. Assertion
    # rewritten: just confirm the key no longer exists (key churn was planned).
    if "timeline.btn_add_blocker_tooltip" not in en:
        ok("Build 07B removed the disabled-button tooltip key (key churn planned)")
    else:
        fail("tooltip key churn", "key still present — 07B removal not applied")

    # ── 2. Migration count (forward-compatible with 07B's migration 006) ──
    print("\n── 2. Migrations count ──")
    from app.migrations import MIGRATIONS
    if len(MIGRATIONS) >= 5:
        ok(f"MIGRATIONS count >= 5 (got {len(MIGRATIONS)})")
    else:
        fail("migration count", f"expected >= 5, got {len(MIGRATIONS)}")

    # ── 3. Set up a project with first phase in_progress + planned_end_date ──
    print("\n── 3. Project setup ──")
    pid = make_project(admin, "b07_test_main", PM_USER)
    rows = db_query("SELECT id, phase_order FROM project_phases WHERE project_id=? ORDER BY phase_order", (pid,))
    p1_id, p1_order = rows[0]
    p2_id, _ = rows[1]
    db_execute("UPDATE project_phases SET planned_end_date=?, status='in_progress' WHERE id=?",
               ((date.today() + timedelta(days=5)).isoformat(), p1_id))
    ok(f"Project {pid} ready with current_phase={p1_id} (in_progress, +5 days)")

    # ── 4. Markup: form-trigger buttons + form mount present (PM owner) ──
    print("\n── 4. Template markup — form triggers + form mount ──")
    page = pm.get(f"{BASE}/projects/{pid}").text
    for marker, msg in [
        ('data-cc-form="finish"', "Finish button has data-cc-form='finish'"),
        ('data-cc-form="adjust"', "Adjust button has data-cc-form='adjust'"),
        ('data-cc-form="add-update"', "Add Update button has data-cc-form='add-update'"),
        ('id="cc-action-form"', "Shared form mount #cc-action-form renders"),
        ('data-cc-panel="finish"', "Finish form panel renders"),
        ('data-cc-panel="adjust"', "Adjust form panel renders"),
        ('data-cc-panel="add-update"', "Add Update form panel renders"),
        (f'/projects/{pid}/command/finish-phase', "Finish form posts to /command/finish-phase"),
        (f'/projects/{pid}/command/adjust-due-date', "Adjust form posts to /command/adjust-due-date"),
        (f'/projects/{pid}/command/add-update', "Add Update form posts to /command/add-update"),
        ('data-cc-disable-on-submit', "Add Update form has client-side disable hook (Lock 7 amendment)"),
        (f'name="phase_id" value="{p1_id}"', "Finish form embeds current phase_id"),
    ]:
        if marker in page:
            ok(msg)
        else:
            fail(msg, f"marker '{marker}' missing")
    # Pre-filled current planned_end_date in Adjust form
    if f'value="{(date.today() + timedelta(days=5)).isoformat()}"' in page:
        ok("Adjust form pre-fills current planned_end_date")
    else:
        fail("adjust prefill", "current planned_end_date not in form")

    # ── 5. Viewer never sees the forms ──
    print("\n── 5. Viewer cannot see forms or action buttons ──")
    page_viewer = viewer.get(f"{BASE}/projects/{pid}").text
    if 'data-cc-form="finish"' not in page_viewer:
        ok("Viewer does NOT see Finish form-trigger button")
    else:
        fail("viewer finish", "button leaked to viewer")
    if 'id="cc-action-form"' not in page_viewer:
        ok("Viewer does NOT see form mount at all")
    else:
        fail("viewer mount", "form mount leaked to viewer")
    if "07B" in page_viewer:  # Add Blocker tooltip is still visible — but viewer can't see Add Blocker either (gated on can_edit)
        fail("viewer 07B leak", "viewer sees [Add Blocker] (should be gated on can_edit)")
    else:
        ok("Viewer does NOT see [Add Blocker] (gated on can_edit)")

    # ── 6. Finish Current Phase — happy path ──
    print("\n── 6. POST /command/finish-phase — happy path (PM owner) ──")
    r = pm.post(f"{BASE}/projects/{pid}/command/finish-phase",
        data={"phase_id": p1_id, "completion_note": "All sample checks passed"},
        allow_redirects=False, timeout=5)
    if r.status_code == 303 and "cc_result=ok" in r.headers["location"] and "#timeline-command-center" in r.headers["location"]:
        ok("Finish redirect: 303 + cc_result=ok + #timeline-command-center")
    else:
        fail("finish redirect", f"status={r.status_code} loc={r.headers.get('location')}")
    # Phase 1 is done, phase 2 is in_progress
    p1_status, p1_actual_end = db_query("SELECT status, actual_end_date FROM project_phases WHERE id=?", (p1_id,))[0]
    p2_status = db_query("SELECT status FROM project_phases WHERE id=?", (p2_id,))[0][0]
    if p1_status == "done" and p1_actual_end:
        ok("Phase 1 status='done', actual_end_date set")
    else:
        fail("phase 1 state", f"status={p1_status} actual_end={p1_actual_end}")
    if p2_status == "in_progress":
        ok("Phase 2 advanced to status='in_progress'")
    else:
        fail("phase 2 state", f"status={p2_status}")
    # Completion note appears as an event_note change
    notes = db_query("SELECT change_type, summary FROM project_changes WHERE project_id=? AND summary LIKE '%sample checks passed%'", (pid,))
    if notes and notes[0][0] == "event_note":
        ok("Completion note recorded as event_note change")
    else:
        fail("completion note", f"notes={notes}")

    # ── 7. Finish — stale phase_id (Lock 3 race protection) ──
    print("\n── 7. POST /command/finish-phase — stale phase_id rejected ──")
    # p1_id is now done; resubmitting with p1_id should redirect with phase_already_done
    r = pm.post(f"{BASE}/projects/{pid}/command/finish-phase",
        data={"phase_id": p1_id, "completion_note": ""},
        allow_redirects=False, timeout=5)
    if "cc_result=phase_already_done" in r.headers["location"]:
        ok("Stale phase_id (already-done) rejected with phase_already_done")
    else:
        fail("stale phase", f"loc={r.headers['location']}")
    # Verify p2 was NOT advanced again (still in_progress, not done)
    p2_status_after = db_query("SELECT status FROM project_phases WHERE id=?", (p2_id,))[0][0]
    if p2_status_after == "in_progress":
        ok("Stale Finish did NOT advance the next phase")
    else:
        fail("stale advance", f"p2 status={p2_status_after}")

    # ── 8. Finish — viewer 403 (not_authorized) ──
    print("\n── 8. Finish — viewer rejected ──")
    # Reset p1 to in_progress for this test (so the "valid phase" branch is hit)
    db_execute("UPDATE project_phases SET status='in_progress', actual_end_date=NULL WHERE id=?", (p1_id,))
    db_execute("UPDATE project_phases SET status='not_started' WHERE id=?", (p2_id,))
    r = viewer.post(f"{BASE}/projects/{pid}/command/finish-phase",
        data={"phase_id": p1_id, "completion_note": ""},
        allow_redirects=False, timeout=5)
    if "cc_result=not_authorized" in r.headers["location"]:
        ok("Viewer Finish rejected with not_authorized")
    else:
        fail("viewer finish", f"loc={r.headers['location']}")
    p1_check = db_query("SELECT status FROM project_phases WHERE id=?", (p1_id,))[0][0]
    if p1_check == "in_progress":
        ok("Viewer Finish did NOT mutate phase state")
    else:
        fail("viewer mutation", f"p1 status={p1_check}")

    # ── 9. Finish — non-owner PM rejected ──
    print("\n── 9. Finish — non-owner PM rejected ──")
    # Re-assign project to admin so PM is no longer owner
    db_execute("UPDATE projects SET product_manager=? WHERE id=?", (ADMIN, pid))
    r = pm.post(f"{BASE}/projects/{pid}/command/finish-phase",
        data={"phase_id": p1_id, "completion_note": ""},
        allow_redirects=False, timeout=5)
    if "cc_result=not_authorized" in r.headers["location"]:
        ok("Non-owner PM Finish rejected with not_authorized")
    else:
        fail("non-owner pm", f"loc={r.headers['location']}")
    # Restore PM ownership
    db_execute("UPDATE projects SET product_manager=? WHERE id=?", (PM_USER, pid))

    # ── 10. Adjust Due Date — happy path ──
    print("\n── 10. POST /command/adjust-due-date — happy path ──")
    new_date = (date.today() + timedelta(days=12)).isoformat()
    r = pm.post(f"{BASE}/projects/{pid}/command/adjust-due-date",
        data={"phase_id": p1_id, "new_planned_end_date": new_date,
              "reason": "Factory pushed sample 1 week"},
        allow_redirects=False, timeout=5)
    if "cc_result=ok" in r.headers["location"]:
        ok("Adjust redirect: cc_result=ok")
    else:
        fail("adjust redirect", f"loc={r.headers['location']}")
    pe = db_query("SELECT planned_end_date FROM project_phases WHERE id=?", (p1_id,))[0][0]
    if pe == new_date:
        ok(f"planned_end_date updated to {new_date}")
    else:
        fail("planned_end_date", f"got {pe}")
    plan_changes = db_query("SELECT field_changed, reason FROM phase_plan_changes WHERE phase_id=? ORDER BY changed_at DESC LIMIT 1", (p1_id,))
    if plan_changes and "Factory pushed" in plan_changes[0][1]:
        ok(f"phase_plan_changes row written with reason ({plan_changes[0][0]})")
    else:
        fail("plan_changes", f"got {plan_changes}")

    # ── 11. Adjust — empty reason rejected (Lock 4) ──
    print("\n── 11. Adjust — empty reason rejected ──")
    r = pm.post(f"{BASE}/projects/{pid}/command/adjust-due-date",
        data={"phase_id": p1_id, "new_planned_end_date": (date.today() + timedelta(days=20)).isoformat(),
              "reason": "   "},  # whitespace only
        allow_redirects=False, timeout=5)
    if "cc_result=reason_required" in r.headers["location"]:
        ok("Empty/whitespace reason rejected with reason_required")
    else:
        fail("empty reason", f"loc={r.headers['location']}")
    # Date should NOT have changed
    pe_after = db_query("SELECT planned_end_date FROM project_phases WHERE id=?", (p1_id,))[0][0]
    if pe_after == new_date:
        ok("Empty-reason Adjust did NOT change planned_end_date")
    else:
        fail("empty reason mutation", f"date changed to {pe_after}")

    # ── 12. Adjust — viewer rejected ──
    print("\n── 12. Adjust — viewer rejected ──")
    r = viewer.post(f"{BASE}/projects/{pid}/command/adjust-due-date",
        data={"phase_id": p1_id, "new_planned_end_date": (date.today() + timedelta(days=30)).isoformat(),
              "reason": "trying to inject"},
        allow_redirects=False, timeout=5)
    if "cc_result=not_authorized" in r.headers["location"]:
        ok("Viewer Adjust rejected with not_authorized")
    else:
        fail("viewer adjust", f"loc={r.headers['location']}")

    # ── 13. Add Update — happy path ──
    print("\n── 13. POST /command/add-update — happy path ──")
    r = pm.post(f"{BASE}/projects/{pid}/command/add-update",
        data={"entry_text": "Sample arrived; blade finish a bit too matte.",
              "entry_type": "risk"},
        allow_redirects=False, timeout=5)
    if "cc_result=ok" in r.headers["location"] and "#timeline-command-center" in r.headers["location"]:
        ok("Add Update redirect: cc_result=ok + #timeline-command-center")
    else:
        fail("add update redirect", f"loc={r.headers['location']}")
    rows = db_query("SELECT entry_text, entry_type, author_user_id FROM project_journal_entries WHERE project_id=? ORDER BY id DESC LIMIT 1", (pid,))
    if rows and "blade finish" in rows[0][0] and rows[0][1] == "risk":
        ok(f"Journal row written with entry_type='risk' (text len={len(rows[0][0])})")
    else:
        fail("journal row", f"got {rows}")
    pm_user_id = db_query("SELECT id FROM users WHERE username=?", (PM_USER,))[0][0]
    if rows and rows[0][2] == pm_user_id:
        ok(f"Journal author_user_id = PM ({pm_user_id})")
    else:
        fail("journal author", f"expected {pm_user_id}, got {rows[0][2] if rows else None}")

    # ── 14. Add Update — empty text rejected ──
    print("\n── 14. Add Update — empty text rejected ──")
    r = pm.post(f"{BASE}/projects/{pid}/command/add-update",
        data={"entry_text": "   ", "entry_type": "general"},
        allow_redirects=False, timeout=5)
    if "cc_result=empty_update" in r.headers["location"]:
        ok("Empty/whitespace text rejected with empty_update")
    else:
        fail("empty text", f"loc={r.headers['location']}")

    # ── 15. Add Update — viewer rejected (can_view_journal=False) ──
    print("\n── 15. Add Update — viewer rejected ──")
    r = viewer.post(f"{BASE}/projects/{pid}/command/add-update",
        data={"entry_text": "viewer trying to write", "entry_type": "general"},
        allow_redirects=False, timeout=5)
    if "cc_result=not_authorized" in r.headers["location"]:
        ok("Viewer Add Update rejected with not_authorized")
    else:
        fail("viewer add-update", f"loc={r.headers['location']}")
    # No row written
    cnt = db_query("SELECT COUNT(*) FROM project_journal_entries WHERE project_id=? AND entry_text LIKE '%viewer trying%'", (pid,))[0][0]
    if cnt == 0:
        ok("Viewer Add Update did NOT write a journal entry")
    else:
        fail("viewer wrote", f"got {cnt} rows")

    # ── 16. Result banner renders on PRG ──
    print("\n── 16. Result banner renders on PRG ──")
    page_banner = pm.get(f"{BASE}/projects/{pid}?cc_action=adjust&cc_result=ok").text
    if 'data-cc-result="ok"' in page_banner and "cc-result-banner" in page_banner:
        ok("Result banner renders with data-cc-result='ok'")
    else:
        fail("banner ok", "banner markup missing")
    page_banner_err = pm.get(f"{BASE}/projects/{pid}?cc_action=adjust&cc_result=reason_required").text
    if 'data-cc-result="reason_required"' in page_banner_err and "cc-result-error" in page_banner_err:
        ok("Result banner renders error variant for reason_required")
    else:
        fail("banner error", "error banner markup missing")

    # ── 17. AI Intake button still triggers side-panel opener (Build 06 invariant) ──
    print("\n── 17. AI Intake button still opens side panel ──")
    if "side-panel-open" in page and "aiSidePanel" in page:
        ok("AI Intake side-panel opener JS preserved")
    else:
        fail("ai intake", "side-panel opener missing")

    # ── 18. Detailed Table /phases/{id}/edit + /finish unchanged (regression) ──
    print("\n── 18. Detailed Table phase edit + finish still work ──")
    # Reset for clean test: restore p1 in_progress
    db_execute("UPDATE project_phases SET status='in_progress', actual_end_date=NULL WHERE id=?", (p1_id,))
    db_execute("UPDATE project_phases SET status='not_started' WHERE id=?", (p2_id,))
    # Send current planned_end_date back unchanged so the route doesn't treat
    # this as a plan-date change (which would short-circuit to reason_required).
    current_pe = db_query("SELECT planned_end_date FROM project_phases WHERE id=?", (p1_id,))[0][0] or ""
    r = pm.post(f"{BASE}/projects/{pid}/phases/{p1_id}/edit",
        data={"phase_name": "Design", "phase_type": "design", "status": "in_progress",
              "planned_start_date": "", "planned_end_date": current_pe,
              "actual_start_date": "", "actual_end_date": "",
              "owner": "RegressionOwner", "notes": "", "plan_change_reason": ""},
        allow_redirects=False, timeout=5)
    if r.status_code == 303:
        owner_check = db_query("SELECT owner FROM project_phases WHERE id=?", (p1_id,))[0][0]
        if owner_check == "RegressionOwner":
            ok("Detailed Table /phases/{id}/edit still mutates owner field")
        else:
            fail("dt edit", f"owner={owner_check}")
    else:
        fail("dt edit status", f"status={r.status_code}")
    r = pm.post(f"{BASE}/projects/{pid}/phases/{p1_id}/finish", allow_redirects=False, timeout=5)
    if r.status_code == 303:
        p1_after = db_query("SELECT status FROM project_phases WHERE id=?", (p1_id,))[0][0]
        if p1_after == "done":
            ok("Detailed Table /phases/{id}/finish still works")
        else:
            fail("dt finish", f"status={p1_after}")
    else:
        fail("dt finish status", f"status={r.status_code}")

    # ── 19. Build 06 invariants preserved ──
    print("\n── 19. Build 06 invariants preserved ──")
    page_after = pm.get(f"{BASE}/projects/{pid}").text
    for marker, msg in [
        ('id="timeline-command-center"', "Command Center section"),
        ("timeline-phase-strip", "Phase strip"),
        ("timeline-tile-current", "Current tile"),
        ("timeline-tile-deadline", "Deadline tile"),
        # v1.3 Build 07B replaced the blocker placeholder with the honest tile.
        ('timeline-blocker-tile', "Blocker tile (Build 07B)"),
        ('data-placeholder="ai-nudge"', "AI nudge placeholder"),
        ('id="timelineDetailedTable"', "Detailed Table <details> wrapper"),
        (f'id="phase-row-{p1_id}"', f"phase-row-{p1_id} anchor"),
    ]:
        if marker in page_after:
            ok(f"Build 06 marker preserved: {msg}")
        else:
            fail(f"build 06 invariant: {msg}", f"'{marker}' missing")

    cleanup("b07_test")
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
