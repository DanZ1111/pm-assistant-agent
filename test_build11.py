"""
Build 11 — Good Ideas board + project linkage + AI dual-mode intake.
Run: python3 test_build11.py
"""

import sys
import requests
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
PASS, FAIL = [], []

ADMIN_USER = "admin"
ADMIN_PASS = "show me the money"
PM_USER = "testpm_b8"
PM_PASS = "pmpassword8!"
VIEWER_USER = "testviewer_b8"
VIEWER_PASS = "viewerpass8!"


def ok(name): PASS.append(name); print(f"  ✓  {name}")
def fail(name, reason): FAIL.append((name, reason)); print(f"  ✗  {name}: {reason}")


def login(username, password):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login",
               data={"username": username, "password": password},
               allow_redirects=False)
    if r.status_code in (302, 303) and "pm_session" in s.cookies:
        return s
    return None


def run_tests():
    admin_s = login(ADMIN_USER, ADMIN_PASS)
    pm_s = login(PM_USER, PM_PASS)
    viewer_s = login(VIEWER_USER, VIEWER_PASS)

    if not (admin_s and pm_s and viewer_s):
        fail("Setup", "Could not log in as admin/pm/viewer")
        _print_summary()
        return False
    ok("All three roles can log in")

    # ── Ideas board accessible by all roles ─────────────────────────────
    print("\n── Ideas Board Access ──")
    for label, sess in [("Admin", admin_s), ("PM", pm_s), ("Viewer", viewer_s)]:
        r = sess.get(f"{BASE}/ideas")
        if r.status_code == 200 and "Good Ideas" in r.text:
            ok(f"{label} can GET /ideas")
        else:
            fail(f"{label} /ideas access", f"status {r.status_code}")

    # ── All roles can create ideas ──────────────────────────────────────
    print("\n── Idea Creation (all roles) ──")
    created_ids = {}
    for label, sess, key in [("admin", admin_s, "a"), ("pm", pm_s, "p"), ("viewer", viewer_s, "v")]:
        r = sess.post(f"{BASE}/ideas/new", data={
            "name": f"B11 Test Idea by {label}",
            "description": f"smoke test from {label}",
            "idea_type": "material",
            "source": "team",
            "source_detail": "smoke test",
            "contributor": label,
        }, allow_redirects=False)
        if r.status_code in (302, 303):
            ok(f"{label} created an idea")
            # Extract idea id from highlight param
            import re
            m = re.search(r"highlight=(\d+)", r.headers.get("location", ""))
            if m:
                created_ids[key] = int(m.group(1))
        else:
            fail(f"{label} create idea", f"status {r.status_code}")

    # ── PM can edit any idea ────────────────────────────────────────────
    print("\n── Edit Permissions ──")
    if "v" in created_ids:
        # PM edits the viewer's idea
        r = pm_s.post(f"{BASE}/ideas/{created_ids['v']}/edit", data={
            "name": "B11 Test Idea by viewer (edited by PM)",
            "description": "edited by PM",
            "idea_type": "material",
            "source": "team",
            "source_detail": "smoke",
            "contributor": "viewer",
            "notes": "",
            "status": "open",
        }, allow_redirects=False)
        if r.status_code in (302, 303):
            ok("PM can edit any idea")
        else:
            fail("PM edit idea", f"status {r.status_code}")

    # ── Viewer CANNOT edit (redirected) ─────────────────────────────────
    if "a" in created_ids:
        r = viewer_s.post(f"{BASE}/ideas/{created_ids['a']}/edit", data={
            "name": "Viewer Trying To Edit",
            "idea_type": "material",
            "source": "team",
        }, allow_redirects=False)
        if r.status_code in (302, 303) and "/ideas" in r.headers.get("location", ""):
            # And verify the name was NOT changed
            board = admin_s.get(f"{BASE}/ideas").text
            if "Viewer Trying To Edit" not in board:
                ok("Viewer blocked from editing (name unchanged)")
            else:
                fail("Viewer edit block", "name was actually changed!")
        else:
            fail("Viewer edit redirect", f"status {r.status_code}")

    # Also block on GET /ideas/{id}/edit
    if "a" in created_ids:
        r = viewer_s.get(f"{BASE}/ideas/{created_ids['a']}/edit", allow_redirects=False)
        if r.status_code in (302, 303):
            ok("Viewer blocked from edit form (GET)")
        else:
            fail("Viewer edit form block", f"status {r.status_code}")

    # ── Only admin can delete ──────────────────────────────────────────
    print("\n── Delete Permissions ──")
    if "p" in created_ids:
        # PM tries to delete — should fail
        r = pm_s.post(f"{BASE}/ideas/{created_ids['p']}/delete", allow_redirects=False)
        # Should redirect to /ideas WITHOUT deleting
        board = admin_s.get(f"{BASE}/ideas").text
        if f"B11 Test Idea by pm" in board:
            ok("PM cannot delete (idea still on board)")
        else:
            fail("PM delete block", "idea was deleted by PM!")

        # Admin can delete
        r = admin_s.post(f"{BASE}/ideas/{created_ids['p']}/delete", allow_redirects=False)
        board2 = admin_s.get(f"{BASE}/ideas").text
        if f"B11 Test Idea by pm" not in board2:
            ok("Admin can delete idea")
        else:
            fail("Admin delete", "idea still present after admin delete")

    # ── Navbar shows Good Ideas link for all roles ─────────────────────
    print("\n── Navbar Visibility ──")
    for label, sess in [("admin", admin_s), ("pm", pm_s), ("viewer", viewer_s)]:
        html = sess.get(f"{BASE}/projects").text
        if 'href="/ideas"' in html:
            ok(f"{label} sees Good Ideas nav link")
        else:
            fail(f"{label} Good Ideas link", "missing from navbar")

    # ── Project ↔ Idea linkage ─────────────────────────────────────────
    print("\n── Project ↔ Idea Linkage ──")
    # Need a project and an idea
    projects = admin_s.get(f"{BASE}/projects").text
    import re
    pid_match = re.search(r'href="/projects/(\d+)"', projects)
    if pid_match and "a" in created_ids:
        pid = int(pid_match.group(1))
        idea_id = created_ids["a"]

        # Link
        r = admin_s.post(f"{BASE}/projects/{pid}/ideas/link", data={
            "idea_id": idea_id, "note": "Build 11 smoke test"
        }, allow_redirects=False)
        if r.status_code in (302, 303):
            ok("POST link idea → redirect")

        # Verify on detail
        detail = admin_s.get(f"{BASE}/projects/{pid}").text
        if "Inspired By" in detail and f"IDEA-{idea_id:03d}" in detail:
            ok("Idea appears in 'Inspired By' section on project detail")
        else:
            fail("Idea on project detail", "IDEA serial not found")

        if "Build 11 smoke test" in detail:
            ok("Link note rendered on project detail")
        else:
            fail("Link note", "note not visible")

        # Unlink
        r = admin_s.post(f"{BASE}/projects/{pid}/ideas/{idea_id}/unlink", allow_redirects=False)
        detail2 = admin_s.get(f"{BASE}/projects/{pid}").text
        if f"IDEA-{idea_id:03d}" not in detail2 or "No linked ideas yet" in detail2 or "Inspired By" in detail2:
            # Detail page may still show "Inspired By (0)" but not the specific idea row
            inspired_section = detail2.split("Inspired By")[1][:500] if "Inspired By" in detail2 else ""
            if f"IDEA-{idea_id:03d}" not in inspired_section:
                ok("Idea removed from project after unlink")
            else:
                fail("Unlink", "idea still visible after unlink")

    # ── Cleanup: delete remaining test ideas ───────────────────────────
    print("\n── Cleanup ──")
    for key, iid in created_ids.items():
        if key == "p":
            continue  # already deleted
        admin_s.post(f"{BASE}/ideas/{iid}/delete", allow_redirects=False)
    ok("Test ideas cleaned up")

    _print_summary()
    return len(FAIL) == 0


def _print_summary():
    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        print("\nFailed tests:")
        for name, reason in FAIL:
            print(f"  ✗ {name}: {reason}")
    print("=" * 60)


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
