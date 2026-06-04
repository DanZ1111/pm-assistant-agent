"""v1.3 Build 06 — Timeline Command Center Shell tests.

Verifies (per V13_BUILD06_EXECUTION_PLAN.md):
- New #timeline-command-center section renders inside workspace-panel-timeline.
- Phase strip emits one block per phase with data-status (done/current/next/later/skipped).
- 3-tile row renders Current Phase, Next Action, Deadline tiles.
- Health band derivation matches Lock 3 (on_track / at_risk / delayed / not_scheduled).
- Days-left / overdue derivation matches Lock 4 (red overdue, amber ≤7, neutral >7).
- Pressure dots derivation matches Lock 5.
- Main blocker + AI Nudge render as EXPLICIT placeholders.
- Action button permissions per role (admin/PM see 5; viewer sees 0).
- [Add Blocker] disabled with Build 07 tooltip.
- [Finish Current Phase] link targets #phase-row-{current_phase.id}.
- Detailed Table wrapped in <details id="timelineDetailedTable"> NOT open by default.
- Phase <tr> rows have id="phase-row-{phase.id}".
- i18n parity at 651/651.
- No new migration (still 5).
- All v1.3 Build 01-05B layout invariants preserved.
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

    cleanup("b06_test")

    # ── 1. i18n parity at 651/651 + Build 06 keys present ──
    print("\n── 1. i18n parity + Build 06 keys ──")
    with open("app/i18n/en.json") as f: en = json.load(f)
    with open("app/i18n/zh.json") as f: zh = json.load(f)
    if set(en) == set(zh):
        ok(f"en/zh parity ({len(en)} keys)")
    else:
        fail("i18n parity", f"en={len(en)} zh={len(zh)} diff={set(en) ^ set(zh)}")
    if len(en) >= 651:
        ok(f"key count ≥ 651 (got {len(en)})")
    else:
        fail("key count", f"expected ≥ 651, got {len(en)}")
    must_have = [
        "timeline.command_center", "timeline.phase_strip", "timeline.current_phase",
        "timeline.next_action", "timeline.deadline", "timeline.started",
        "timeline.not_started_yet", "timeline.no_due_date", "timeline.days_left",
        "timeline.days_overdue", "timeline.health_on_track", "timeline.health_at_risk",
        "timeline.health_delayed", "timeline.health_not_scheduled",
        "timeline.owner_not_assigned", "timeline.move_phase_forward",
        "timeline.blocker_placeholder_title", "timeline.blocker_placeholder_body",
        "timeline.blocker_open_journal", "timeline.ai_nudge_title",
        "timeline.ai_nudge_body", "timeline.ai_nudge_open_panel",
        "timeline.btn_finish_phase", "timeline.btn_adjust_due_date",
        "timeline.btn_add_update", "timeline.btn_add_blocker_disabled",
        "timeline.btn_open_ai_intake", "timeline.detailed_table",
        "timeline.placeholder_label",
    ]
    missing = [k for k in must_have if k not in en]
    if not missing:
        ok(f"All {len(must_have)} Build 06 i18n keys present")
    else:
        fail("Build 06 keys", f"missing: {missing}")

    # ── 2. No new migration ──
    print("\n── 2. Migrations count unchanged ──")
    from app.migrations import MIGRATIONS
    if len(MIGRATIONS) == 5:
        ok(f"MIGRATIONS still 5 entries (no schema change in Build 06)")
    else:
        fail("migration count", f"expected 5, got {len(MIGRATIONS)}")

    # ── 3. Set up a "happy path" project ──
    print("\n── 3. Happy-path project — Command Center renders ──")
    pid = make_project(admin, "b06_test_happy", ADMIN)
    page = admin.get(f"{BASE}/projects/{pid}").text
    for marker, msg in [
        ('id="timeline-command-center"', "Command Center section renders"),
        ("workspace-panel-timeline", "Inside workspace timeline panel"),
        ("timeline-phase-strip", "Phase strip container renders"),
        ("timeline-phase-block", "Phase block elements render"),
        ("timeline-tiles-grid", "3-tile grid renders"),
        ("timeline-tile-current", "Current Phase tile renders"),
        ("timeline-tile-next-action", "Next Action tile renders"),
        ("timeline-tile-deadline", "Deadline tile renders"),
        ('data-placeholder="blocker"', "Main blocker placeholder renders"),
        ('data-placeholder="ai-nudge"', "AI Nudge placeholder renders"),
        ('id="timelineDetailedTable"', "Detailed Table <details> wrapper renders"),
    ]:
        if marker in page:
            ok(msg)
        else:
            fail(msg, f"marker '{marker}' not found")

    # 8 phases × admin should have 8 .timeline-phase-block instances
    block_count = page.count('class="timeline-phase-block"')
    if block_count == 8:
        ok(f"Phase strip has 8 blocks (single-prototype template)")
    else:
        fail("phase block count", f"expected 8, got {block_count}")

    # ── 4. Phase strip data-status values ──
    print("\n── 4. Phase strip data-status — fresh project ──")
    # Fresh project: all phases not_started. Phase 1 (order=1) is current,
    # phase 2 is next, phases 3-8 are later.
    statuses = re.findall(r'class="timeline-phase-block"\s+data-status="([^"]+)"', page)
    if statuses and statuses[0] == "current":
        ok("First phase has data-status='current'")
    else:
        fail("first phase status", f"got {statuses[:3] if statuses else 'none'}")
    if len(statuses) >= 2 and statuses[1] == "next":
        ok("Second phase has data-status='next'")
    else:
        fail("second phase status", f"got {statuses[:3] if statuses else 'none'}")
    if all(s == "later" for s in statuses[2:]):
        ok(f"Phases 3..8 all data-status='later' ({len(statuses) - 2} blocks)")
    else:
        fail("later phases", f"got {statuses[2:]}")

    # ── 5. Health band — "not_scheduled" (no planned_end_date) ──
    print("\n── 5. Health band — not_scheduled (fresh phase, no due date) ──")
    if 'timeline-health-not_scheduled' in page:
        ok("Health badge class is timeline-health-not_scheduled")
    else:
        fail("health badge class", "timeline-health-not_scheduled not in page")

    # No due date → "No due date set" empty state in Deadline tile
    if "No due date set" in page:
        ok("Deadline tile shows 'No due date set' when planned_end is NULL")
    else:
        fail("deadline empty state", "'No due date set' not in page")

    # ── 6. Health band — at_risk (3 days late) ──
    print("\n── 6. Health band — at_risk (3 days overdue) ──")
    # Get current_phase id, set planned_end_date to 3 days ago, status='in_progress'
    rows = db_query("SELECT id FROM project_phases WHERE project_id=? ORDER BY phase_order LIMIT 1", (pid,))
    first_phase_id = rows[0][0]
    three_days_ago = (date.today() - timedelta(days=3)).isoformat()
    db_execute("UPDATE project_phases SET planned_end_date=?, status='in_progress' WHERE id=?",
               (three_days_ago, first_phase_id))
    page = admin.get(f"{BASE}/projects/{pid}").text
    if "timeline-health-at_risk" in page:
        ok("Health band='at_risk' when days_late ≤ 3")
    else:
        fail("at_risk", "timeline-health-at_risk not in page")
    if "3 days overdue" in page or "days overdue" in page:
        ok("Deadline tile shows 'days overdue' badge for past planned_end")
    else:
        fail("overdue badge", "'days overdue' not in page")
    if "timeline-days-overdue" in page:
        ok("Days badge has overdue (red) class")
    else:
        fail("overdue class", "timeline-days-overdue class missing")

    # ── 7. Health band — delayed (>3 days late) ──
    print("\n── 7. Health band — delayed (10 days overdue) ──")
    ten_days_ago = (date.today() - timedelta(days=10)).isoformat()
    db_execute("UPDATE project_phases SET planned_end_date=? WHERE id=?",
               (ten_days_ago, first_phase_id))
    page = admin.get(f"{BASE}/projects/{pid}").text
    if "timeline-health-delayed" in page:
        ok("Health band='delayed' when days_late > 3")
    else:
        fail("delayed", "timeline-health-delayed not in page")

    # ── 8. Health band — on_track (future planned_end, no delay) ──
    print("\n── 8. Health band — on_track (5 days in future, amber) ──")
    five_days_future = (date.today() + timedelta(days=5)).isoformat()
    db_execute("UPDATE project_phases SET planned_end_date=? WHERE id=?",
               (five_days_future, first_phase_id))
    page = admin.get(f"{BASE}/projects/{pid}").text
    if "timeline-health-on_track" in page:
        ok("Health band='on_track' when no phase is delayed")
    else:
        fail("on_track", "timeline-health-on_track not in page")
    if "5 days left" in page:
        ok("Deadline tile shows '5 days left'")
    else:
        fail("days_left text", "'5 days left' not in page")
    if "timeline-days-amber" in page:
        ok("Days badge has amber class (≤ 7 days)")
    else:
        fail("amber class", "timeline-days-amber class missing")

    # ── 9. Days badge neutral (>7 days) ──
    print("\n── 9. Days badge — neutral (15 days, >7) ──")
    fifteen_days_future = (date.today() + timedelta(days=15)).isoformat()
    db_execute("UPDATE project_phases SET planned_end_date=? WHERE id=?",
               (fifteen_days_future, first_phase_id))
    page = admin.get(f"{BASE}/projects/{pid}").text
    if "timeline-days-neutral" in page:
        ok("Days badge has neutral class (> 7 days)")
    else:
        fail("neutral class", "timeline-days-neutral class missing")
    if "15 days left" in page:
        ok("Deadline tile shows '15 days left'")
    else:
        fail("15 days_left", "'15 days left' not in page")

    # ── 10. Owner tile honest field rendering ──
    print("\n── 10. Owner tile — assigned vs unassigned ──")
    if "Not assigned" in page:
        ok("Next Action tile shows 'Not assigned' when phase.owner is NULL")
    else:
        fail("not assigned", "'Not assigned' not in page")
    db_execute("UPDATE project_phases SET owner='Test Owner Alice' WHERE id=?", (first_phase_id,))
    page = admin.get(f"{BASE}/projects/{pid}").text
    if "Test Owner Alice" in page:
        ok("Next Action tile renders phase.owner when set")
    else:
        fail("owner render", "'Test Owner Alice' not in page")

    # ── 11. Action buttons — admin sees all 5 ──
    print("\n── 11. Action buttons — admin permission ──")
    for action, msg in [
        ('data-action="finish"', "[Finish Current Phase] visible to admin"),
        ('data-action="adjust-due-date"', "[Adjust Due Date] visible to admin"),
        ('data-action="add-update"', "[Add Update] visible to admin"),
        ('data-action="add-blocker-disabled"', "[Add Blocker] (disabled) visible to admin"),
        ('data-action="open-ai-intake"', "[Open AI Intake] visible to admin"),
    ]:
        if action in page:
            ok(msg)
        else:
            fail(msg, f"'{action}' not in page")

    # [Add Blocker] is disabled
    add_blocker_match = re.search(r'<button[^>]*data-action="add-blocker-disabled"[^>]*>', page)
    if add_blocker_match and "disabled" in add_blocker_match.group(0):
        ok("[Add Blocker] button has disabled attribute")
    else:
        fail("add_blocker disabled", f"button tag: {add_blocker_match.group(0) if add_blocker_match else 'not found'}")

    # [Finish Current Phase] anchors to #phase-row-{id}
    finish_match = re.search(rf'data-action="finish"[^>]*href="#phase-row-{first_phase_id}"|href="#phase-row-{first_phase_id}"[^>]*data-action="finish"', page)
    if finish_match:
        ok(f"[Finish Current Phase] link targets #phase-row-{first_phase_id}")
    else:
        # Be more permissive — just look for href + data-action="finish" in same anchor
        finish_anchor = re.search(r'<a[^>]*data-action="finish"[^>]*>', page)
        if finish_anchor and f"#phase-row-{first_phase_id}" in finish_anchor.group(0):
            ok(f"[Finish Current Phase] link targets #phase-row-{first_phase_id} (anchor form)")
        else:
            fail("finish anchor", f"anchor: {finish_anchor.group(0) if finish_anchor else 'not found'}")

    # ── 12. Action buttons — viewer sees zero (per can_use_ai_intake admin/pm only) ──
    print("\n── 12. Action buttons — viewer permission ──")
    page_viewer = viewer.get(f"{BASE}/projects/{pid}").text
    for action, msg in [
        ('data-action="finish"', "[Finish] hidden from viewer"),
        ('data-action="adjust-due-date"', "[Adjust] hidden from viewer"),
        ('data-action="add-update"', "[Add Update] hidden from viewer"),
        ('data-action="add-blocker-disabled"', "[Add Blocker] hidden from viewer"),
        ('data-action="open-ai-intake"', "[AI Intake] hidden from viewer (can_use_ai_intake=False)"),
    ]:
        if action not in page_viewer:
            ok(msg)
        else:
            fail(msg, f"viewer sees '{action}' — should be hidden")

    # Viewer still sees the command center structure + placeholders
    if 'id="timeline-command-center"' in page_viewer:
        ok("Viewer still sees Command Center section")
    else:
        fail("viewer cc", "viewer cannot see Command Center")
    if 'data-placeholder="blocker"' in page_viewer:
        ok("Viewer sees blocker placeholder")
    else:
        fail("viewer blocker", "blocker placeholder hidden from viewer")
    # Viewer should NOT see "Open Journal" link (can_view_journal=False for viewer)
    if "Open Journal" not in page_viewer:
        ok("Viewer does NOT see 'Open Journal' link (can_view_journal=False)")
    else:
        fail("viewer journal link", "viewer sees 'Open Journal' — should be hidden")

    # ── 13. Detailed Table is in <details> NOT open by default ──
    print("\n── 13. Detailed Table <details> wrapper ──")
    details_match = re.search(r'<details[^>]*id="timelineDetailedTable"[^>]*>', page)
    if details_match:
        ok("<details id='timelineDetailedTable'> wrapper exists")
        if "open" not in details_match.group(0):
            ok("Detailed Table is NOT open by default")
        else:
            fail("details open", "Detailed Table has 'open' attribute")
    else:
        fail("details wrapper", "<details id='timelineDetailedTable'> not found")
    # Existing table inside the details
    if "timeline-table-v2" in page:
        ok("Existing timeline-table-v2 markup preserved inside <details>")
    else:
        fail("legacy table", "timeline-table-v2 missing")

    # ── 14. Phase row id anchors (Build 06 navigation) ──
    print("\n── 14. Phase row id='phase-row-N' anchors ──")
    if f'id="phase-row-{first_phase_id}"' in page:
        ok(f"Phase row id='phase-row-{first_phase_id}' anchor exists")
    else:
        fail("phase-row anchor", f"id='phase-row-{first_phase_id}' missing")

    # ── 15. Pressure dots derivation ──
    print("\n── 15. Pressure dots (Lock 5) ──")
    # current state: 15 days left → pressure_dots = 0, so no dots
    if "timeline-pressure-dots" not in page:
        ok("No pressure dots when days_left > 7")
    else:
        fail("no dots", "pressure dots rendered when they shouldn't be")
    # Set to 2 days left → 2 amber dots
    two_days_future = (date.today() + timedelta(days=2)).isoformat()
    db_execute("UPDATE project_phases SET planned_end_date=? WHERE id=?",
               (two_days_future, first_phase_id))
    page = admin.get(f"{BASE}/projects/{pid}").text
    # Count individual dot spans (class="timeline-pressure-dot" with no trailing 's')
    dot_count = len(re.findall(r'class="timeline-pressure-dot"', page))
    if dot_count == 2:
        ok("2 pressure dots when days_left ≤ 3")
    else:
        fail("2 dots", f"got {dot_count} dots")

    # ── 16. v1.3 Build 01-05B invariants preserved ──
    print("\n── 16. v1.3 Build 01-05B layout invariants preserved ──")
    for marker, msg in [
        ('workspace-panel-timeline', "Build 01 workspace shell (timeline panel)"),
        ('workspaceTabTimeline', "Build 01 Timeline tab control"),
        ('workspace-panel-overview', "Build 01 workspace shell (overview panel)"),
    ]:
        if marker in page:
            ok(msg)
        else:
            fail(msg, f"'{marker}' missing")

    # ── 17. Project with NO phases — Command Center is hidden ──
    print("\n── 17. No-phase edge case — Command Center hidden ──")
    pid_empty = make_project(admin, "b06_test_empty", ADMIN)
    db_execute("DELETE FROM project_phases WHERE project_id=?", (pid_empty,))
    page_empty = admin.get(f"{BASE}/projects/{pid_empty}").text
    if 'id="timeline-command-center"' not in page_empty:
        ok("Command Center hidden when project has no phases")
    else:
        fail("empty hidden", "Command Center rendered with no phases")

    # ── 18. PM with edit access sees same 5 action buttons ──
    print("\n── 18. PM permission — sees all 5 action buttons ──")
    # Re-assign happy project to PM
    db_execute("UPDATE projects SET product_manager=? WHERE id=?", (PM_USER, pid))
    page_pm = pm.get(f"{BASE}/projects/{pid}").text
    pm_actions = sum(1 for action in [
        'data-action="finish"', 'data-action="adjust-due-date"',
        'data-action="add-update"', 'data-action="add-blocker-disabled"',
        'data-action="open-ai-intake"',
    ] if action in page_pm)
    if pm_actions == 5:
        ok("PM (owner) sees all 5 action buttons")
    else:
        fail("PM actions", f"expected 5, got {pm_actions}")

    cleanup("b06_test")
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
