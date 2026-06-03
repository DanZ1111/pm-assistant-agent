"""Build 19 — My Projects tab + Attention banner cleanup + last-project memory."""
import os
import sys
import sqlite3
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
    # Build 30A — POST /projects/new now requires a submission_token minted
    # by the GET. Grab one before each create.
    import re as _re
    form_page = admin_s.get(f"{BASE}/projects/new").text
    tok_match = _re.search(r'name="submission_token"\s+value="([a-f0-9]+)"', form_page)
    submission_token = tok_match.group(1) if tok_match else ""
    r = admin_s.post(f"{BASE}/projects/new",
                     data={
                         "name": name,
                         "prototype_rounds": "single",
                         "submission_token": submission_token,
                     },
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
    admin_s = login(ADMIN, ADMIN_PWD)
    pm_s = login(PM_USER, PM_PWD)
    viewer_s = login(VIEWER_USER, VIEWER_PWD)
    if not all([admin_s, pm_s, viewer_s]):
        fail("setup", "could not log in all three roles"); _p(); return False
    ok("All three roles can log in")

    # Make a fresh PM-owned project so the PM view has at least one entry.
    pid = make_pm_owned_project(admin_s, PM_USER, f"Build19 PM Proj {os.getpid()}")
    ok(f"Created PM-owned test project pid={pid}")

    # ── /my-projects access control ──
    print("\n── /my-projects access control ──")
    r = admin_s.get(f"{BASE}/my-projects", allow_redirects=False)
    if r.status_code == 200 and "My Projects" in r.text:
        ok("Admin can access /my-projects (200, page renders)")
    else:
        fail("Admin access", f"status={r.status_code}")

    r = pm_s.get(f"{BASE}/my-projects", allow_redirects=False)
    if r.status_code == 200 and "My Projects" in r.text:
        ok("PM can access /my-projects (200, page renders)")
    else:
        fail("PM access", f"status={r.status_code}")

    r = viewer_s.get(f"{BASE}/my-projects", allow_redirects=False)
    if r.status_code in (302, 303):
        loc = r.headers.get("location", "")
        if loc.endswith("/projects"):
            ok("Viewer redirected away from /my-projects → /projects")
        else:
            fail("Viewer redirect target", f"location={loc}")
    else:
        fail("Viewer redirect", f"status={r.status_code} (expected 303)")

    # ── PM view contains the PM's project; admin view contains it too ──
    print("\n── PM / admin row contents ──")
    pm_page = pm_s.get(f"{BASE}/my-projects").text
    if f"/projects/{pid}" in pm_page:
        ok("PM view contains the PM-owned project")
    else:
        fail("PM view content", f"project link /projects/{pid} not found")

    admin_page = admin_s.get(f"{BASE}/my-projects").text
    if f"/projects/{pid}" in admin_page:
        ok("Admin view also contains the PM-owned project (admin sees all)")
    else:
        fail("Admin view content", "PM-owned project not visible to admin")

    # ── PM does NOT see projects where they're not the PM ──
    # Make a second project owned by a different fake PM
    other_pid = make_pm_owned_project(admin_s, "someone_else_99", f"Build19 Other {os.getpid()}")
    pm_page2 = pm_s.get(f"{BASE}/my-projects").text
    if f"/projects/{other_pid}" not in pm_page2:
        ok("PM does NOT see projects where someone else is the PM")
    else:
        fail("PM isolation", f"PM unexpectedly sees /projects/{other_pid}")

    # ── Navbar visibility ──
    print("\n── Navbar visibility ──")
    if 'href="/my-projects"' in admin_page:
        ok("Admin sees My Projects link in navbar")
    else:
        fail("Admin navbar", "My Projects link missing from admin /my-projects page")
    if 'href="/my-projects"' in pm_page:
        ok("PM sees My Projects link in navbar")
    else:
        fail("PM navbar", "My Projects link missing from PM /my-projects page")
    viewer_proj = viewer_s.get(f"{BASE}/projects").text
    if 'href="/my-projects"' not in viewer_proj:
        ok("Viewer does NOT see My Projects link in navbar")
    else:
        fail("Viewer navbar", "My Projects link unexpectedly visible to viewer")

    # ── Attention banner cleanup ──
    print("\n── Attention banner is delay-only ──")
    plist = pm_s.get(f"{BASE}/projects").text
    # Find the attention banner block. Look between "attention-section" and the closing div near filter-tabs.
    if "attention-section" in plist:
        att_start = plist.find("attention-section")
        att_end = plist.find("filter-tabs", att_start)
        att_block = plist[att_start:att_end] if att_end > 0 else plist[att_start:att_start + 5000]
        if "badge-needs-info" not in att_block:
            ok("Attention banner does NOT contain badge-needs-info")
        else:
            fail("Banner cleanup", "badge-needs-info still appears inside the attention banner block")
    else:
        ok("No attention banner present (acceptable — banner only shows when there is at least one delayed/due item)")

    # Filter tab still has "Needs Info"
    if 'needs_info=1' in plist and 'Needs Info' in plist:
        ok("Needs-Info filter tab still present")
    else:
        fail("Filter tab", "Needs-Info filter tab missing from /projects")

    # ── localStorage memory wiring ──
    print("\n── localStorage memory wiring ──")
    detail = pm_s.get(f"{BASE}/projects/{pid}").text
    if "pm_last_project_id" in detail and f"'{pid}'" in detail:
        ok("Project detail page contains localStorage writer with the correct project id")
    else:
        fail("LocalStorage writer", "pm_last_project_id setItem not found on project detail page")

    base_html_in_response = pm_s.get(f"{BASE}/projects").text
    if "navProjectsLink" in base_html_in_response:
        ok("Projects nav link has id=navProjectsLink (handler attachment point present)")
    else:
        fail("Nav link id", "id=navProjectsLink missing from rendered base.html")

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
