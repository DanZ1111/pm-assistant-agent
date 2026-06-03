"""Build 30C — PM draft delete tests.

Policy locked in plan: PM can delete only when project's PM matches them AND
every phase is still 'not_started' AND no phase has actual_start_date set.
Admin can delete any project. Viewer can delete nothing.

Once any phase advances, the project leaves draft state — PM must use
Archive instead. This ties deletability to a real workflow event rather
than a clock, so a PM who created a project, went on vacation, and came
back can still clean up their own untouched draft.
"""
import os
import re
import sqlite3
import sys

import requests

BASE = "http://localhost:8000"
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
    r = s.post(f"{BASE}/auth/login", data={"username": u, "password": p}, allow_redirects=False, timeout=5)
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


def mint_token(session):
    page = session.get(f"{BASE}/projects/new").text
    m = re.search(r'name="submission_token"\s+value="([a-f0-9]+)"', page)
    return m.group(1) if m else None


def create_project(session, name, pm_username):
    """Create a fresh draft project via the manual form. Returns its id."""
    tok = mint_token(session)
    r = session.post(
        f"{BASE}/projects/new",
        data={
            "name": name,
            "product_manager": pm_username,
            "prototype_rounds": "single",
            "submission_token": tok,
        },
        allow_redirects=False,
        timeout=5,
    )
    if r.status_code != 303:
        return None
    return int(r.headers["location"].rstrip("/").split("/")[-1])


def cleanup(*names):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        for n in names:
            cur.execute("SELECT id FROM projects WHERE name = ?", (n,))
            for (pid,) in cur.fetchall():
                cur.execute("DELETE FROM project_changes WHERE project_id = ?", (pid,))
                cur.execute("DELETE FROM project_phases WHERE project_id = ?", (pid,))
                cur.execute("DELETE FROM project_files WHERE project_id = ?", (pid,))
                cur.execute("DELETE FROM ai_messages WHERE project_id = ?", (pid,))
                cur.execute("DELETE FROM project_creation_tokens WHERE project_id = ?", (pid,))
                cur.execute("DELETE FROM projects WHERE id = ?", (pid,))
        conn.commit()
    finally:
        conn.close()


def main():
    admin_s = login(ADMIN, ADMIN_PWD)
    pm_s = login(PM_USER, PM_PWD)
    viewer_s = login(VIEWER_USER, VIEWER_PWD)
    if not all([admin_s, pm_s, viewer_s]):
        fail("setup", "could not log in all three roles"); _p(); return False
    ok("All three roles can log in")

    # Pre-cleanup
    for n in ("b30c_pm_draft", "b30c_pm_advanced", "b30c_other_pm_draft",
              "b30c_admin_owned", "b30c_pm_for_viewer_test"):
        cleanup(n)

    # ── 1. can_delete_project helper exists ──
    print("\n── 1. Helper presence ──")
    try:
        from app.dependencies import can_delete_project
        ok("can_delete_project import from app.dependencies")
    except ImportError as e:
        fail("import", str(e)); _p(); return False

    # ── 2. PM creates a fresh draft → can delete it (UI + API) ──
    print("\n── 2. PM deletes own untouched-draft project ──")
    pm_draft = create_project(pm_s, "b30c_pm_draft", PM_USER)
    if not pm_draft:
        fail("create draft", "could not create draft"); _p(); return False
    ok(f"PM created draft project (id={pm_draft})")

    # The Delete button should appear on the project detail page
    detail = pm_s.get(f"{BASE}/projects/{pm_draft}").text
    if 'action="/projects/' + str(pm_draft) + '/delete"' in detail:
        ok("PM sees Delete button on their fresh draft")
    else:
        fail("PM delete button visible", "Delete <form> action missing from detail HTML")

    # POST the delete
    r = pm_s.post(f"{BASE}/projects/{pm_draft}/delete", allow_redirects=False)
    if r.status_code == 303 and r.headers.get("location") == "/projects":
        ok("PM delete POST → 303 to /projects")
    else:
        fail("PM delete status", f"status={r.status_code} loc={r.headers.get('location')}")
    if not db_query("SELECT id FROM projects WHERE id = ?", (pm_draft,)):
        ok("Project row is gone from DB")
    else:
        fail("project gone", "row still present")

    # ── 3. PM cannot delete once first phase has advanced ──
    print("\n── 3. PM cannot delete after first phase advance ──")
    pm_adv = create_project(pm_s, "b30c_pm_advanced", PM_USER)
    if not pm_adv:
        fail("create adv", "could not create"); _p(); return False
    # Simulate phase advance by setting the first phase's status to in_progress
    db_exec(
        "UPDATE project_phases SET status = 'in_progress', actual_start_date = DATE('now') "
        "WHERE project_id = ? AND phase_order = 1",
        (pm_adv,),
    )
    # PM should NOT see the Delete button now
    detail2 = pm_s.get(f"{BASE}/projects/{pm_adv}").text
    if 'action="/projects/' + str(pm_adv) + '/delete"' not in detail2:
        ok("PM does NOT see Delete button after first phase advance")
    else:
        fail("PM delete hidden after advance", "Delete button still showing on advanced project")
    # POST the delete should be 403
    r = pm_s.post(f"{BASE}/projects/{pm_adv}/delete", allow_redirects=False)
    if r.status_code == 403:
        ok("PM delete POST on advanced project → 403")
    else:
        fail("PM delete blocked", f"expected 403, got {r.status_code}")
    if db_query("SELECT id FROM projects WHERE id = ?", (pm_adv,)):
        ok("Advanced project row still present in DB (delete refused)")
    else:
        fail("delete leak", "project was deleted despite 403")
    cleanup("b30c_pm_advanced")

    # ── 4. PM cannot delete another PM's draft ──
    print("\n── 4. PM cannot delete a project owned by another PM ──")
    # Admin creates a project owned by admin (a different "PM" from testpm_b8)
    other = create_project(admin_s, "b30c_other_pm_draft", ADMIN)
    if not other:
        fail("create other", "could not create"); _p(); return False
    detail3 = pm_s.get(f"{BASE}/projects/{other}").text
    if 'action="/projects/' + str(other) + '/delete"' not in detail3:
        ok("PM does NOT see Delete button on project owned by another PM")
    else:
        fail("PM cross-PM delete hidden", "Delete button leaks across PMs")
    r = pm_s.post(f"{BASE}/projects/{other}/delete", allow_redirects=False)
    if r.status_code == 403:
        ok(f"PM delete POST on cross-PM project → 403")
    else:
        fail("PM cross-PM delete blocked", f"expected 403, got {r.status_code}")
    cleanup("b30c_other_pm_draft")

    # ── 5. Admin can delete any project (including ones with advanced phases) ──
    print("\n── 5. Admin can delete any project ──")
    admin_proj = create_project(admin_s, "b30c_admin_owned", ADMIN)
    if not admin_proj:
        fail("create admin proj", "could not create"); _p(); return False
    # Advance a phase to confirm admin isn't restricted by the draft rule
    db_exec(
        "UPDATE project_phases SET status = 'in_progress', actual_start_date = DATE('now') "
        "WHERE project_id = ? AND phase_order = 1",
        (admin_proj,),
    )
    detail4 = admin_s.get(f"{BASE}/projects/{admin_proj}").text
    if 'action="/projects/' + str(admin_proj) + '/delete"' in detail4:
        ok("Admin sees Delete button even on advanced project")
    else:
        fail("admin delete visible", "Delete button missing on admin's view")
    r = admin_s.post(f"{BASE}/projects/{admin_proj}/delete", allow_redirects=False)
    if r.status_code == 303:
        ok("Admin delete POST → 303 (succeeds on advanced project)")
    else:
        fail("admin delete status", f"status={r.status_code}")
    if not db_query("SELECT id FROM projects WHERE id = ?", (admin_proj,)):
        ok("Advanced project deleted by admin")
    else:
        fail("admin delete persistence", "project still present")

    # ── 6. Viewer cannot delete anything ──
    print("\n── 6. Viewer cannot delete anything ──")
    viewer_target = create_project(pm_s, "b30c_pm_for_viewer_test", PM_USER)
    if not viewer_target:
        fail("create viewer target", "could not create"); _p(); return False
    detail5 = viewer_s.get(f"{BASE}/projects/{viewer_target}").text
    if 'action="/projects/' + str(viewer_target) + '/delete"' not in detail5:
        ok("Viewer does NOT see Delete button")
    else:
        fail("viewer delete hidden", "Delete button shown to viewer")
    r = viewer_s.post(f"{BASE}/projects/{viewer_target}/delete", allow_redirects=False)
    if r.status_code in (403, 303):
        # 403 from can_delete_project check; 303 redirect if viewer hit some upstream auth gate
        ok(f"Viewer delete POST refused (status={r.status_code})")
    else:
        fail("viewer delete blocked", f"expected 403/303, got {r.status_code}")
    if db_query("SELECT id FROM projects WHERE id = ?", (viewer_target,)):
        ok("Project still present in DB after viewer attempt")
    else:
        fail("viewer leak", "project was deleted")
    cleanup("b30c_pm_for_viewer_test")

    # ── 7. can_delete_project unit-style: helper returns expected boolean ──
    print("\n── 7. Helper unit checks ──")
    from app.database import SessionLocal
    from app.models import User, ProjectPhase
    # Build a fake fresh project + the three roles
    pid_fresh = create_project(pm_s, "b30c_unit_fresh", PM_USER)
    pid_adv = create_project(pm_s, "b30c_unit_adv", PM_USER)
    db_exec(
        "UPDATE project_phases SET status = 'in_progress', actual_start_date = DATE('now') "
        "WHERE project_id = ? AND phase_order = 1",
        (pid_adv,),
    )
    db = SessionLocal()
    from app.crud import get_project
    admin_user = db.query(User).filter(User.username == ADMIN).first()
    pm_user = db.query(User).filter(User.username == PM_USER).first()
    viewer_user = db.query(User).filter(User.username == VIEWER_USER).first()
    fresh = get_project(db, pid_fresh)
    advanced = get_project(db, pid_adv)
    checks = [
        ("admin + fresh", can_delete_project(admin_user, fresh), True),
        ("admin + advanced", can_delete_project(admin_user, advanced), True),
        ("pm + own fresh", can_delete_project(pm_user, fresh), True),
        ("pm + own advanced", can_delete_project(pm_user, advanced), False),
        ("viewer + fresh", can_delete_project(viewer_user, fresh), False),
        ("None user + fresh", can_delete_project(None, fresh), False),
    ]
    db.close()
    for label, got, want in checks:
        if got is want:
            ok(f"can_delete_project({label}) → {got}")
        else:
            fail(f"helper {label}", f"expected {want}, got {got}")
    cleanup("b30c_unit_fresh", "b30c_unit_adv")

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
