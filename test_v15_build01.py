"""v1.5 Build 01 — Designer roles and portal shell.

Requires the app running at BASE_URL (default http://localhost:8000) for the
HTTP auth/route-boundary checks.

Run: python3 test_v15_build01.py
"""
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = Path(__file__).resolve().parent
BASE = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ADMIN = os.environ.get("TEST_ADMIN_USERNAME", "admin")
ADMIN_PWD = os.environ.get("TEST_ADMIN_PASSWORD", "show me the money")
PASS, FAIL = [], []
RUN_TAG = str(int(time.time()))


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, reason):
    FAIL.append((name, reason))
    print(f"  ✗  {name}: {reason}")


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def contains_all(label, text_value, needles):
    missing = [needle for needle in needles if needle not in text_value]
    if missing:
        fail(label, f"missing: {missing}")
    else:
        ok(label)


def cleanup_live_usernames(usernames):
    from app.database import SessionLocal
    from app.models import InvitePin, User, UserSession

    db = SessionLocal()
    try:
        users = db.query(User).filter(User.username.in_(usernames)).all()
        ids = [u.id for u in users]
        if ids:
            db.query(UserSession).filter(UserSession.user_id.in_(ids)).delete(synchronize_session=False)
            db.query(InvitePin).filter(InvitePin.used_by_user_id.in_(ids)).delete(synchronize_session=False)
            for user in users:
                db.delete(user)
        db.commit()
    finally:
        db.close()


def live_login(username, password):
    session = requests.Session()
    response = session.post(
        f"{BASE}/auth/login",
        data={"username": username, "password": password},
        allow_redirects=False,
        timeout=8,
    )
    return session, response


def generate_pin(admin_session, role):
    response = admin_session.post(
        f"{BASE}/admin/users/generate-pin",
        data={"role": role},
        allow_redirects=False,
        timeout=8,
    )
    if response.status_code not in (302, 303):
        return None, response
    query = parse_qs(urlparse(response.headers.get("location", "")).query)
    return query.get("new_pin", [None])[0], response


def register_with_pin(username, pin):
    return requests.post(
        f"{BASE}/auth/register",
        data={
            "username": username,
            "display_name": username.title(),
            "password": "designer-pass-123",
            "confirm_password": "designer-pass-123",
            "invite_pin": pin,
        },
        allow_redirects=False,
        timeout=8,
    )


def user_role(username):
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        return user.role if user else None
    finally:
        db.close()


def main():
    print("\n── 1. Source locks ──")
    plan = read("V15_BUILD01_ROLES_PORTAL_SHELL_PLAN.md")
    masterplan = read("V15_MASTERPLAN.md")
    deps = read("app/dependencies.py")
    main_py = read("app/main.py")
    auth = read("app/routes/auth.py")
    admin_users = read("app/routes/admin_users.py")
    base = read("app/templates/base.html")
    designer_route = read("app/routes/designer.py")
    designer_template = read("app/templates/designer/dashboard.html")
    migrations = read("app/migrations.py")
    ai_tools = read("app/ai/tools.py")

    contains_all(
        "Build 01 plan and masterplan lock designer boundary scope",
        plan + masterplan,
        [
            "designer_manager is a portal operations role",
            "Build 01 must only add roles, invite support, /designer shell, and route blocking",
            "No implementation should begin until",
        ],
    )
    contains_all(
        "Designer role helpers, route, middleware, and chrome markers exist",
        deps + main_py + auth + base + designer_route + designer_template,
        [
            "DESIGNER_ROLES",
            "auth_landing_path",
            "require_designer_portal_user",
            "designer_portal_boundary",
            'href="/designer"',
            "data-designer-empty-state",
        ],
    )
    contains_all(
        "Admin invite support includes designer roles and distinct prefixes",
        admin_users,
        [
            '"designer": "DS"',
            '"designer_manager": "DM"',
            "INVITE_ROLES",
        ],
    )
    models = read("app/models.py")
    if (
        "DesignSubmission" not in models
        and "design_submission" not in migrations
        and all(name not in ai_tools for name in ("draft_design_quest", "publish_design_quest", "close_design_quest"))
    ):
        ok("Build 01 boundary remains intact after later v1.5 data-model additions")
    else:
        fail("Build 01 scope leak", "submission model/migration or AI quest handler found")

    print("\n── 2. i18n parity and locked keys ──")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    required_keys = [
        "nav.designer_portal",
        "designer.title",
        "designer.subtitle",
        "designer.portal_label",
        "designer.empty_title",
        "designer.empty_body",
        "designer.role_designer",
        "designer.role_designer_manager",
        "admin.role_pm",
        "admin.role_viewer",
        "admin.role_designer",
        "admin.role_designer_manager",
    ]
    missing = [key for key in required_keys if key not in en or key not in zh]
    if set(en) == set(zh) and not missing and len(en) >= 817:
        ok(f"i18n parity preserved with v1.5 Build 01 keys ({len(en)}/{len(zh)})")
    else:
        fail("i18n parity/count", {
            "en": len(en),
            "zh": len(zh),
            "missing": missing,
            "diff": sorted(set(en) ^ set(zh))[:8],
        })

    print("\n── 3. Live auth and route boundary ──")
    try:
        requests.get(f"{BASE}/healthz", timeout=4)
    except Exception as exc:
        fail("live server", f"{BASE} unreachable: {exc}")
        _print_summary()
        return False

    designer_username = f"v15_designer_{RUN_TAG}"
    manager_username = f"v15_manager_{RUN_TAG}"
    cleanup_live_usernames([designer_username, manager_username])

    admin_session, admin_login = live_login(ADMIN, ADMIN_PWD)
    if admin_login.status_code in (302, 303) and admin_session.cookies.get("pm_session"):
        ok("Admin login works before creating designer invites")
    else:
        fail("admin login", f"status={admin_login.status_code}")
        _print_summary()
        return False

    ds_pin, ds_resp = generate_pin(admin_session, "designer")
    dm_pin, dm_resp = generate_pin(admin_session, "designer_manager")
    if ds_pin and re.match(r"^DS-[A-Z0-9]{6}$", ds_pin):
        ok("Admin can generate Designer invite PIN")
    else:
        fail("designer PIN", {"pin": ds_pin, "status": ds_resp.status_code})
    if dm_pin and re.match(r"^DM-[A-Z0-9]{6}$", dm_pin):
        ok("Admin can generate Designer Manager invite PIN")
    else:
        fail("designer manager PIN", {"pin": dm_pin, "status": dm_resp.status_code})

    reg_designer = register_with_pin(designer_username, ds_pin)
    reg_manager = register_with_pin(manager_username, dm_pin)
    if reg_designer.status_code in (302, 303) and user_role(designer_username) == "designer":
        ok("Registration with Designer PIN creates designer user")
    else:
        fail("designer registration", {"status": reg_designer.status_code, "role": user_role(designer_username)})
    if reg_manager.status_code in (302, 303) and user_role(manager_username) == "designer_manager":
        ok("Registration with Designer Manager PIN creates designer_manager user")
    else:
        fail("manager registration", {"status": reg_manager.status_code, "role": user_role(manager_username)})

    designer_session, designer_login = live_login(designer_username, "designer-pass-123")
    if designer_login.status_code in (302, 303) and designer_login.headers.get("location") == "/designer":
        ok("Designer login lands at /designer")
    else:
        fail("designer login redirect", {"status": designer_login.status_code, "location": designer_login.headers.get("location")})

    manager_session, manager_login = live_login(manager_username, "designer-pass-123")
    if manager_login.status_code in (302, 303) and manager_login.headers.get("location") == "/designer":
        ok("Designer manager login lands at /designer")
    else:
        fail("manager login redirect", {"status": manager_login.status_code, "location": manager_login.headers.get("location")})

    designer_page = designer_session.get(f"{BASE}/designer", timeout=8)
    if (
        designer_page.status_code == 200
        and "No design quests yet." in designer_page.text
        and 'id="bottomChatBar"' not in designer_page.text
        and 'id="navProjectsLink"' not in designer_page.text
        and 'href="/projects"' not in designer_page.text
    ):
        ok("/designer renders restricted empty portal shell without PM chrome")
    else:
        fail("designer portal shell", {
            "status": designer_page.status_code,
            "has_empty": "No design quests yet." in designer_page.text,
            "has_chat": 'id="bottomChatBar"' in designer_page.text,
            "has_projects_nav": 'id="navProjectsLink"' in designer_page.text,
        })

    for path in ("/projects", "/projects/1", "/calendar", "/ideas", "/admin/users", "/ai/conversations"):
        response = designer_session.get(f"{BASE}{path}", allow_redirects=False, timeout=8)
        if response.status_code in (302, 303) and response.headers.get("location") == "/designer":
            ok(f"Designer GET {path} redirects to /designer")
        else:
            fail(f"Designer GET {path}", {"status": response.status_code, "location": response.headers.get("location")})

    post_response = designer_session.post(f"{BASE}/projects/new", data={"name": "Should Not Create"}, timeout=8)
    if post_response.status_code == 403:
        ok("Designer POST to PM project route is forbidden")
    else:
        fail("Designer POST /projects/new", post_response.status_code)

    admin_projects = admin_session.get(f"{BASE}/projects", timeout=8)
    admin_designer = admin_session.get(f"{BASE}/designer", timeout=8)
    if admin_projects.status_code == 200 and admin_designer.status_code == 200:
        ok("Admin keeps PM Workspace access and can inspect /designer")
    else:
        fail("admin access regression", {"projects": admin_projects.status_code, "designer": admin_designer.status_code})

    cleanup_live_usernames([designer_username, manager_username])
    return _print_summary()


def _print_summary():
    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        print("\nFailures:")
        for name, reason in FAIL:
            print(f" - {name}: {reason}")
    print("=" * 60)
    return not FAIL


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
