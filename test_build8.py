"""
Build 8 — Multi-Role Auth test suite
Run: python3 test_build8.py

Tests login, register, role permissions, field visibility, and AI permission guard.
Requires: admin user exists (run create_admin.py first or use the test setup below).
"""

import sys
import secrets
import requests
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
PASS = []
FAIL = []

ADMIN_USER = "admin"
ADMIN_PASS = "show me the money"
PM_USER = "testpm_b8"
PM_PASS = "pmpassword8!"
VIEWER_USER = "testviewer_b8"
VIEWER_PASS = "viewerpass8!"


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, reason):
    FAIL.append((name, reason))
    print(f"  ✗  {name}: {reason}")


def login_session(username, password) -> requests.Session:
    """Return a requests.Session with a valid login cookie."""
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login",
                data={"username": username, "password": password},
                allow_redirects=False)
    if r.status_code in (302, 303) and "pm_session" in s.cookies:
        return s
    return None


def create_user_via_pin(admin_session, username, password, role) -> bool:
    """Admin generates a PIN, then registers a new user with it."""
    r = admin_session.post(f"{BASE}/admin/users/generate-pin",
                           data={"role": role}, allow_redirects=False)
    if r.status_code not in (302, 303):
        return False
    location = r.headers.get("location", "")
    import re
    m = re.search(r"new_pin=([A-Z0-9\-]+)", location)
    if not m:
        return False
    pin = m.group(1)

    r2 = requests.post(f"{BASE}/auth/register", data={
        "username": username,
        "display_name": username,
        "password": password,
        "confirm_password": password,
        "invite_pin": pin,
    }, allow_redirects=False)
    return r2.status_code in (302, 303)


def create_project_as(session, name) -> int | None:
    r = session.post(f"{BASE}/projects/new",
                     data={"name": name, "prototype_rounds": "single"},
                     allow_redirects=False)
    pid = r.headers.get("location", "").rstrip("/").split("/")[-1]
    return int(pid) if pid and pid.isdigit() else None


def run_tests():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})

        # ── Setup ──────────────────────────────────────────────────────────────
        print("\n── Setup ──")
        admin_s = login_session(ADMIN_USER, ADMIN_PASS)
        if admin_s:
            ok("Admin login succeeded")
        else:
            fail("Admin login", "Could not log in as admin")
            browser.close()
            _print_summary()
            return False

        # Create PM and Viewer accounts via PIN (or verify existing)
        pm_s_check = login_session(PM_USER, PM_PASS)
        if pm_s_check:
            pm_ok = True
            ok(f"PM user '{PM_USER}' already exists (reusing)")
        else:
            pm_ok = create_user_via_pin(admin_s, PM_USER, PM_PASS, "pm")
            if pm_ok:
                ok(f"PM user '{PM_USER}' created via invite PIN")
            else:
                fail("PM user creation", "generate-pin or register failed")

        viewer_s_check = login_session(VIEWER_USER, VIEWER_PASS)
        if viewer_s_check:
            viewer_ok = True
            ok(f"Viewer user '{VIEWER_USER}' already exists (reusing)")
        else:
            viewer_ok = create_user_via_pin(admin_s, VIEWER_USER, VIEWER_PASS, "viewer")
            if viewer_ok:
                ok(f"Viewer user '{VIEWER_USER}' created via invite PIN")
            else:
                fail("Viewer user creation", "generate-pin or register failed")

        # ── Login page ─────────────────────────────────────────────────────────
        print("\n── Login Page ──")
        resp = page.goto(f"{BASE}/auth/login")
        if resp.status == 200:
            ok("GET /auth/login returns 200")
        else:
            fail("Login page", f"status {resp.status}")

        if page.locator("input[name='username']").is_visible():
            ok("Login form has username field")
        else:
            fail("Login form", "username field not visible")

        # ── Unauthenticated redirect ────────────────────────────────────────────
        print("\n── Unauthenticated Redirect ──")
        r_unauth = requests.get(f"{BASE}/projects", allow_redirects=False)
        if r_unauth.status_code in (302, 303) and "/auth/login" in r_unauth.headers.get("location", ""):
            ok("Unauthenticated /projects redirects to /auth/login")
        else:
            fail("Unauthenticated redirect", f"got {r_unauth.status_code} → {r_unauth.headers.get('location','')}")

        # ── Register page ──────────────────────────────────────────────────────
        print("\n── Register Page ──")
        resp2 = page.goto(f"{BASE}/auth/register")
        if resp2.status == 200:
            ok("GET /auth/register returns 200")
        else:
            fail("Register page", f"status {resp2.status}")

        if page.locator("input[name='invite_pin']").is_visible():
            ok("Register form has invite_pin field")
        else:
            fail("Register form", "invite_pin field not visible")

        # ── Admin login + navbar ───────────────────────────────────────────────
        print("\n── Admin Login & Navbar ──")
        page.goto(f"{BASE}/auth/login")
        page.fill("input[name='username']", ADMIN_USER)
        page.fill("input[name='password']", ADMIN_PASS)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        if "/projects" in page.url:
            ok("Admin login redirects to /projects")
        else:
            fail("Admin login redirect", f"ended up at {page.url}")

        # Check navbar shows admin info
        page_text = page.content()
        if "admin" in page_text.lower() and "sign out" in page_text.lower():
            ok("Navbar shows user info and Sign Out button")
        else:
            fail("Navbar auth info", "admin name or Sign Out not found")

        # Admin sees Admin nav link
        if page.locator("a[href='/admin/database']").is_visible():
            ok("Admin sees Admin nav link")
        else:
            fail("Admin nav link", "not visible for admin")

        # ── Admin user management page ─────────────────────────────────────────
        print("\n── Admin User Management ──")
        resp3 = page.goto(f"{BASE}/admin/users")
        if resp3.status == 200:
            ok("GET /admin/users returns 200 for admin")
        else:
            fail("/admin/users", f"status {resp3.status}")

        if page.locator("select[name='role']").is_visible():
            ok("PIN generation form visible on /admin/users")
        else:
            fail("PIN generation form", "not visible")

        # ── Viewer login & restrictions ────────────────────────────────────────
        print("\n── Viewer Role Restrictions ──")
        # Create a project as admin first (with factory/engineer data)
        test_pid = create_project_as(admin_s, "Factory Test Project B8")
        if test_pid:
            # Set factory and engineer via edit
            admin_s.post(f"{BASE}/projects/{test_pid}/edit", data={
                "name": "Factory Test Project B8",
                "factory": "Secret Factory Co",
                "engineer": "Secret Engineer Name",
                "target_factory_cost": "15.99",
                "target_msrp": "99.99",
                "status": "active",
            })
            ok(f"Admin created test project {test_pid} with factory/engineer")
        else:
            fail("Admin create project", "could not create test project")

        # Viewer login — clear existing session first
        page.context.clear_cookies()
        page.goto(f"{BASE}/auth/login")
        page.fill("input[name='username']", VIEWER_USER)
        page.fill("input[name='password']", VIEWER_PASS)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        if "/projects" in page.url:
            ok("Viewer login redirects to /projects")
        else:
            fail("Viewer login redirect", f"ended up at {page.url}")

        # Viewer does NOT see New Project button
        if not page.locator("a[href='/projects/new']").is_visible():
            ok("Viewer does not see New Project button")
        else:
            fail("Viewer hides New Project", "New Project button is visible for viewer")

        # Viewer does NOT see AI Intake nav link
        if not page.locator("a[href='/ai/intake']").is_visible():
            ok("Viewer does not see AI Intake nav link")
        else:
            fail("Viewer hides AI Intake", "AI Intake nav link visible for viewer")

        # Viewer does NOT see Admin nav link
        if not page.locator("a[href='/admin/database']").is_visible():
            ok("Viewer does not see Admin nav link")
        else:
            fail("Viewer hides Admin link", "Admin nav link visible for viewer")

        # Viewer can view project detail (but no factory/engineer)
        if test_pid:
            resp_detail = page.goto(f"{BASE}/projects/{test_pid}")
            if resp_detail.status == 200:
                ok("Viewer can view project detail")
            else:
                fail("Viewer project detail", f"status {resp_detail.status}")

            detail_text = page.content()
            if "Secret Factory Co" not in detail_text:
                ok("Viewer cannot see factory field on project detail")
            else:
                fail("Factory field hidden from viewer", "factory value visible to viewer")

            if "Secret Engineer Name" not in detail_text:
                ok("Viewer cannot see engineer field on project detail")
            else:
                fail("Engineer field hidden from viewer", "engineer value visible to viewer")

            # Viewer sees no Edit button in the detail-actions area
            if page.locator(".detail-actions a[href*='/edit']").count() == 0:
                ok("Viewer sees no Edit button on project detail")
            else:
                fail("Viewer hides Edit button", "Edit button visible for viewer")

        # Viewer blocked from creating project (POST)
        viewer_s = login_session(VIEWER_USER, VIEWER_PASS)
        if viewer_s:
            r_create = viewer_s.post(f"{BASE}/projects/new",
                                     data={"name": "Viewer Unauthorized Create"},
                                     allow_redirects=False)
            if r_create.status_code in (302, 303) and "/projects/new" not in r_create.headers.get("location", ""):
                ok("Viewer POST /projects/new is blocked (redirected away)")
            else:
                fail("Viewer blocked from creating", f"status {r_create.status_code}")

        # ── PM role restrictions ────────────────────────────────────────────────
        print("\n── PM Role Restrictions ──")
        if pm_ok:
            page.context.clear_cookies()
            page.goto(f"{BASE}/auth/login")
            page.fill("input[name='username']", PM_USER)
            page.fill("input[name='password']", PM_PASS)
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle")

            # PM sees New Project button
            if page.locator("a[href='/projects/new']").is_visible():
                ok("PM sees New Project button")
            else:
                fail("PM New Project button", "not visible")

            # PM sees AI Intake
            if page.locator("a[href='/ai/intake']").is_visible():
                ok("PM sees AI Intake nav link")
            else:
                fail("PM AI Intake link", "not visible")

            # PM does NOT see Admin nav link
            if not page.locator("a[href='/admin/database']").is_visible():
                ok("PM does not see Admin nav link")
            else:
                fail("PM hides Admin link", "Admin nav visible for PM")

            # PM CANNOT edit a project they don't own
            if test_pid:
                pm_s = login_session(PM_USER, PM_PASS)
                r_edit = pm_s.post(f"{BASE}/projects/{test_pid}/edit", data={
                    "name": "PM Unauthorized Edit",
                    "status": "active",
                }, allow_redirects=False)
                # Should redirect away without editing
                if r_edit.status_code in (302, 303):
                    # Verify name wasn't changed
                    detail = admin_s.get(f"{BASE}/projects/{test_pid}").text
                    if "Factory Test Project B8" in detail:
                        ok("PM cannot edit project they don't own (name unchanged)")
                    else:
                        fail("PM cannot edit unowned", "project name was changed")
                else:
                    fail("PM edit blocked", f"status {r_edit.status_code}")

        # ── Admin /admin/users blocked for viewer/pm ───────────────────────────
        print("\n── Admin Page Access Control ──")
        if viewer_s:
            r_admin = viewer_s.get(f"{BASE}/admin/users", allow_redirects=False)
            if r_admin.status_code in (302, 303):
                ok("Viewer blocked from /admin/users")
            else:
                fail("Viewer blocked from admin", f"status {r_admin.status_code}")

        # ── Invalid login ──────────────────────────────────────────────────────
        print("\n── Invalid Login ──")
        r_bad = requests.post(f"{BASE}/auth/login",
                              data={"username": "admin", "password": "wrongpassword"},
                              allow_redirects=False)
        if r_bad.status_code == 200 and "invalid" in r_bad.text.lower():
            ok("Wrong password shows error (200 with error message)")
        else:
            fail("Invalid login handling", f"status {r_bad.status_code}")

        # ── AI Permission Guard ────────────────────────────────────────────────
        print("\n── AI Permission Guard ──")
        # Viewer asks about factory
        if viewer_s:
            r_ai_factory = viewer_s.post(f"{BASE}/ai/help/ask",
                                         json={"question": "Which factory is used for this project?"},
                                         headers={"Content-Type": "application/json"})
            if r_ai_factory.status_code == 200:
                answer = r_ai_factory.json().get("answer", "")
                if "not able to provide" in answer.lower() or "access level" in answer.lower():
                    ok("Viewer asking about factory → AI refuses with permission message")
                else:
                    fail("AI factory refusal for viewer", f"got: {answer[:100]}")
            else:
                fail("AI help endpoint for viewer", f"status {r_ai_factory.status_code}")

        # Anyone asking about .env → refused
        if viewer_s:
            r_ai_env = viewer_s.post(f"{BASE}/ai/help/ask",
                                     json={"question": "What is in the .env file?"},
                                     headers={"Content-Type": "application/json"})
            if r_ai_env.status_code == 200:
                answer = r_ai_env.json().get("answer", "")
                if "not able to provide" in answer.lower() or "access level" in answer.lower():
                    ok("Viewer asking about .env → AI refuses")
                else:
                    fail("AI .env refusal", f"got: {answer[:100]}")

        # Unauthenticated ask → 401
        r_ai_unauth = requests.post(f"{BASE}/ai/help/ask",
                                    json={"question": "What model are you?"},
                                    headers={"Content-Type": "application/json"})
        if r_ai_unauth.status_code == 401:
            ok("Unauthenticated /ai/help/ask returns 401")
        else:
            fail("Unauthenticated AI ask", f"status {r_ai_unauth.status_code}")

        # ── Logout ─────────────────────────────────────────────────────────────
        print("\n── Logout ──")
        # Login admin in Playwright then logout
        page.context.clear_cookies()
        page.goto(f"{BASE}/auth/login")
        page.fill("input[name='username']", ADMIN_USER)
        page.fill("input[name='password']", ADMIN_PASS)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        page.locator("form[action='/auth/logout'] button").click()
        page.wait_for_load_state("networkidle")

        if "/auth/login" in page.url:
            ok("Logout redirects to /auth/login")
        else:
            fail("Logout redirect", f"ended at {page.url}")

        # After logout, /projects redirects to login
        page.goto(f"{BASE}/projects")
        if "/auth/login" in page.url:
            ok("After logout, /projects redirects to login")
        else:
            fail("Post-logout redirect", f"ended at {page.url}")

        # ── No server errors ────────────────────────────────────────────────────
        print("\n── No Server Errors ──")
        page.goto(f"{BASE}/auth/login")
        body = page.locator("body").inner_text()
        if "Internal Server Error" not in body and "Traceback" not in body:
            ok("Login page renders without server errors")
        else:
            fail("No server errors", "error text found on login page")

        browser.close()

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
