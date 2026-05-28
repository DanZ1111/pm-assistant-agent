"""Build 17 — Timeline 2.0 (Plan / Reality split + Finish Phase) tests."""
import os
import re
import sys
import sqlite3
from datetime import date, timedelta
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


def get_phases(project_id):
    return db_query(
        "SELECT id, phase_name, phase_order, status, "
        "planned_start_date, planned_end_date, actual_start_date, actual_end_date "
        "FROM project_phases WHERE project_id=? ORDER BY phase_order",
        (project_id,),
    )


def main():
    admin_s = login(ADMIN, ADMIN_PWD)
    pm_s = login(PM_USER, PM_PWD)
    viewer_s = login(VIEWER_USER, VIEWER_PWD)
    if not all([admin_s, pm_s, viewer_s]):
        fail("setup", "could not log in all three roles"); _p(); return False
    ok("All three roles can log in")

    pm_proj = make_pm_owned_project(admin_s, PM_USER, f"Build17 PM Proj {os.getpid()}")
    phases = get_phases(pm_proj)
    if len(phases) >= 2:
        ok(f"Project created with {len(phases)} phases")
    else:
        fail("Setup phases", f"expected ≥2 phases, got {len(phases)}")
        _p(); return False

    p1_id, p1_name = phases[0][0], phases[0][1]
    p2_id, p2_name = phases[1][0], phases[1][1]

    # ── Plan / Reality split renders ──
    print("\n── Plan / Reality split renders ──")
    det = pm_s.get(f"{BASE}/projects/{pm_proj}").text
    if "timeline-table-v2" in det and "th-plan" in det and "th-reality" in det:
        ok("Timeline table renders with Plan/Reality column groups")
    else:
        fail("Plan/Reality columns", "v2 markup missing")

    # ── Phase edit without reason on plan-date change → blocked with banner ──
    print("\n── Plan-date change requires a reason ──")
    today = date.today()
    new_planned_end = (today + timedelta(days=30)).isoformat()
    r = pm_s.post(f"{BASE}/projects/{pm_proj}/phases/{p1_id}/edit", data={
        "phase_name": p1_name,
        "phase_type": "design",
        "status": "not_started",
        "planned_start_date": "",
        "planned_end_date": new_planned_end,
        "actual_start_date": "",
        "actual_end_date": "",
        "owner": "",
        "notes": "",
        "plan_change_reason": "",  # intentionally empty
    }, allow_redirects=False)
    loc = r.headers.get("location") or ""
    if r.status_code in (302, 303) and "timeline_error=reason_required" in loc:
        ok("Plan-date change without reason → redirected with reason_required flash")
    else:
        fail("Reason guard", f"status {r.status_code} loc {loc}")
    # Verify no phase_plan_changes row was written
    pre_count = db_query("SELECT COUNT(*) FROM phase_plan_changes WHERE phase_id=?", (p1_id,))[0][0]
    if pre_count == 0:
        ok("No phase_plan_changes row written when reason missing")
    else:
        fail("Reason guard row", f"unexpected {pre_count} rows")

    # Verify the banner renders on the redirect target
    banner = pm_s.get(f"{BASE}/projects/{pm_proj}?timeline_error=reason_required").text
    if "Plan-date changes require a reason" in banner:
        ok("timeline_error=reason_required banner renders")
    else:
        fail("Reason banner", "banner text missing")

    # ── Plan-date change WITH reason → succeeds + plan_changes row written ──
    print("\n── Plan-date change with reason ──")
    r = pm_s.post(f"{BASE}/projects/{pm_proj}/phases/{p1_id}/edit", data={
        "phase_name": p1_name,
        "phase_type": "design",
        "status": "not_started",
        "planned_start_date": "",
        "planned_end_date": new_planned_end,
        "actual_start_date": "",
        "actual_end_date": "",
        "owner": "",
        "notes": "",
        "plan_change_reason": "Factory pushed sample delivery by 4 weeks",
    }, allow_redirects=False)
    if r.status_code in (302, 303) and "timeline_error" not in (r.headers.get("location") or ""):
        ok("Plan-date change with reason → redirect (no error)")
    else:
        fail("Plan-date with reason", f"unexpected: status {r.status_code} loc {r.headers.get('location')}")
    rows = db_query(
        "SELECT field_changed, old_date, new_date, reason FROM phase_plan_changes WHERE phase_id=?",
        (p1_id,))
    if len(rows) == 1 and rows[0][0] == "planned_end_date" and rows[0][2] == new_planned_end and "Factory pushed" in rows[0][3]:
        ok(f"phase_plan_changes row written ({rows[0][0]} {rows[0][1]} → {rows[0][2]})")
    else:
        fail("Plan change row", f"got {rows}")

    # ── Asterisk marker + history accordion render ──
    print("\n── Visual markers ──")
    det = pm_s.get(f"{BASE}/projects/{pm_proj}").text
    if "plan-changed-marker" in det:
        ok("'*' asterisk marker rendered on adjusted plan date")
    else:
        fail("Asterisk marker", "plan-changed-marker class missing")
    if f'id="plan-history-{p1_id}"' in det and "Factory pushed" in det:
        ok("Plan-history accordion row rendered with reason")
    else:
        fail("History accordion", "history row or reason missing")

    # ── Finish Phase: marks current done + advances next ──
    print("\n── Finish Phase one-click ──")
    # First, set p1 to in_progress so it makes sense to finish
    pm_s.post(f"{BASE}/projects/{pm_proj}/phases/{p1_id}/edit", data={
        "phase_name": p1_name, "phase_type": "design", "status": "in_progress",
        "planned_start_date": "", "planned_end_date": new_planned_end,
        "actual_start_date": "", "actual_end_date": "",
        "owner": "", "notes": "",
        "plan_change_reason": "",  # no plan change here so no reason needed
    }, allow_redirects=False)

    # Now Finish Phase
    r = pm_s.post(f"{BASE}/projects/{pm_proj}/phases/{p1_id}/finish",
                  allow_redirects=False)
    if r.status_code in (302, 303):
        ok("Finish Phase POST redirects")
    else:
        fail("Finish redirect", f"status {r.status_code}")

    after = get_phases(pm_proj)
    p1_row = next(r for r in after if r[0] == p1_id)
    p2_row = next(r for r in after if r[0] == p2_id)
    # status_index = 3, actual_end = 7, actual_start = 6
    today_iso = today.isoformat()
    if p1_row[3] == "done" and p1_row[7] == today_iso:
        ok(f"Phase 1 ({p1_name}) is done with actual_end={today_iso}")
    else:
        fail("Finish p1", f"status={p1_row[3]} actual_end={p1_row[7]}")
    if p2_row[3] == "in_progress" and p2_row[6] == today_iso:
        ok(f"Phase 2 ({p2_name}) advanced to in_progress with actual_start={today_iso}")
    else:
        fail("Advance p2", f"status={p2_row[3]} actual_start={p2_row[6]}")

    # Verify current_stage was updated on the project
    proj_row = db_query("SELECT current_stage FROM projects WHERE id=?", (pm_proj,))[0]
    if proj_row[0] == p2_name:
        ok(f"project.current_stage updated to '{p2_name}'")
    else:
        fail("current_stage", f"got '{proj_row[0]}'")

    # Change log should record the transition
    det = pm_s.get(f"{BASE}/projects/{pm_proj}").text
    if "marked done" in det and "is now in progress" in det:
        ok("Change log records the Finish Phase event_note")
    else:
        fail("Change log finish", "no marked done / now in progress text in detail HTML")

    # ── Permission: viewer cannot finish phase ──
    print("\n── Viewer cannot Finish Phase ──")
    # Pick a still-active phase (p2 just advanced; let's try to finish it as viewer)
    r = viewer_s.post(f"{BASE}/projects/{pm_proj}/phases/{p2_id}/finish",
                      allow_redirects=False)
    after = get_phases(pm_proj)
    p2_row = next(r for r in after if r[0] == p2_id)
    if p2_row[3] != "done":
        ok("Viewer Finish Phase blocked — phase status unchanged")
    else:
        fail("Viewer block", "phase was finished by viewer")

    # ── PM cannot finish phase on someone else's project ──
    print("\n── PM cannot finish on non-owned project ──")
    admin_proj = make_pm_owned_project(admin_s, ADMIN, f"Build17 Admin Only {os.getpid()}")
    admin_phases = get_phases(admin_proj)
    a_p1_id = admin_phases[0][0]
    pm_s.post(f"{BASE}/projects/{admin_proj}/phases/{a_p1_id}/finish",
              allow_redirects=False)
    after = get_phases(admin_proj)
    if after[0][3] != "done":
        ok("PM cannot finish phase on non-owned project")
    else:
        fail("PM cross-project block", "phase was finished")

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
