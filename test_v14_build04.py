"""v1.4 Build 04 — Planning Sandbox module palette + node editing.

Requires the app running at http://localhost:8000 for route/browser smoke.
Run: python3 test_v14_build04.py
"""
import json
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
ROOT = Path(__file__).resolve().parent
ARTIFACTS = ROOT / "test_artifacts"
ADMIN = os.environ.get("TEST_ADMIN_USERNAME", "admin")
ADMIN_PWD = os.environ.get("TEST_ADMIN_PASSWORD", "show me the money")
PASS, FAIL = [], []


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


def build_db():
    tmp = tempfile.TemporaryDirectory()
    engine = create_engine(f"sqlite:///{Path(tmp.name) / 'v14_build04.db'}")
    import app.models  # noqa: F401
    from app.database import Base
    from app import migrations

    Base.metadata.create_all(bind=engine)
    migrations.run_pending(engine)
    Session = sessionmaker(bind=engine)
    return tmp, engine, Session


def create_project(db, name):
    from app.models import Project

    project = Project(name=name, status="active", product_manager=ADMIN)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def live_login():
    s = requests.Session()
    r = s.post(
        f"{BASE}/auth/login",
        data={"username": ADMIN, "password": ADMIN_PWD},
        allow_redirects=False,
        timeout=8,
    )
    return s if r.status_code in (302, 303) else None


def cleanup_live(prefix="v14_b04"):
    from app.database import SessionLocal
    from app.models import Project

    db = SessionLocal()
    try:
        projects = db.query(Project).filter(Project.name.like(prefix + "%")).all()
        for project in projects:
            db.delete(project)
        db.commit()
    finally:
        db.close()


def live_fixture():
    from app import crud
    from app.database import SessionLocal

    cleanup_live()
    db = SessionLocal()
    try:
        project = create_project(db, "v14_b04_live_project")
        sandbox = crud.create_sandbox_blank(db, project.id, user_id=None)
        module = crud.list_planning_modules(db)[0]
        before_phase_count = len(project.phases)
        return project.id, sandbox.id, module.module_key, before_phase_count
    finally:
        db.close()


def count_project_phases(project_id):
    conn = sqlite3.connect(ROOT / "pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM project_phases WHERE project_id=?", (project_id,))
        return cur.fetchone()[0]
    finally:
        conn.close()


def main():
    ARTIFACTS.mkdir(exist_ok=True)

    print("\n── 1. Source locks and i18n ──")
    plan = read("V14_BUILD04_EXECUTION_PLAN.md")
    routes = read("app/routes/projects.py")
    template = read("app/templates/planning_sandbox.html")
    js = read("app/static/js/planning_sandbox.js")
    css = read("app/static/css/styles.css")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))

    contains_all(
        "Build 04 plan locks scope and revised route shape",
        plan,
        [
            "/projects/{project_id}/sandbox/{sandbox_id}/nodes/add",
            "fetch + JSON payload replacement",
            "viewer mutation affordances are hidden",
            "no `project_phases` mutation",
            "No Apply route",
            "18 keys",
        ],
    )
    route_markers = [
        "/projects/{project_id}/sandbox/{sandbox_id}/nodes/add",
        "/projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/update",
        "/projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/position",
        "/projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/delete",
        "JSONResponse",
        "crud.create_sandbox_node_from_module",
        "crud.update_sandbox_node",
        "crud.update_sandbox_node_position",
        "crud.delete_sandbox_node",
    ]
    contains_all("Build 04 JSON routes are registered in source", routes, route_markers)
    if "/sandbox/nodes/add" not in routes:
        ok("Old no-sandbox-id node route shape is absent")
    else:
        fail("old route shape", "found /sandbox/nodes/add")
    contains_all(
        "Sandbox template renders palette/property panel and hides viewer controls by can_edit",
        template,
        [
            "data-sandbox-workspace",
            "sandbox_payload_json",
            "data-sandbox-palette",
            "sandbox-module-card",
            "sandbox-add-module-btn",
            "data-sandbox-properties",
            "data-node-form",
            "data-delete-node",
            "{% if can_edit %}",
            "viewer_read_only",
        ],
    )
    contains_all(
        "Sandbox JS has add/select/edit/position/delete hooks",
        js,
        [
            "postForm",
            "refreshFromPayload",
            "dragfree",
            "data-sandbox-palette",
            "data-node-form",
            "nodes/add",
            "/position",
            "/delete",
        ],
    )
    contains_all(
        "Sandbox CSS has palette and property panel styling",
        css,
        [
            ".sandbox-module-card",
            ".sandbox-property-panel",
            ".sandbox-property-actions",
            ".sandbox-node-message",
        ],
    )
    if set(en) == set(zh) and len(en) >= 758:
        ok(f"i18n parity preserved with Build 04 keys present ({len(en)}/{len(zh)})")
    else:
        fail("i18n parity/count", f"en={len(en)} zh={len(zh)} diff={sorted(set(en) ^ set(zh))[:8]}")

    required_keys = [
        "sandbox.module_library",
        "sandbox.module_library_hint",
        "sandbox.drag_to_canvas",
        "sandbox.add_module",
        "sandbox.node_properties",
        "sandbox.select_node_hint",
        "sandbox.no_node_selected",
        "sandbox.field_title",
        "sandbox.field_duration_days",
        "sandbox.field_owner_role",
        "sandbox.field_deliverable",
        "sandbox.field_exit_criteria",
        "sandbox.save_node",
        "sandbox.delete_node",
        "sandbox.delete_node_confirm",
        "sandbox.viewer_read_only",
        "sandbox.node_saved",
        "sandbox.node_error",
    ]
    missing = [key for key in required_keys if key not in en or key not in zh]
    if not missing:
        ok("All 18 Build 04 i18n keys are present")
    else:
        fail("Build 04 i18n keys", missing)

    print("\n── 2. Service helpers with temp DB ──")
    import app.crud as crud
    from app.models import PlanningSandboxEdge

    tmp, engine, Session = build_db()
    try:
        db = Session()
        project = create_project(db, "v14_b04_service_project")
        sandbox = crud.create_sandbox_blank(db, project.id)
        modules = crud.list_planning_modules(db)
        module = modules[0]
        node = crud.create_sandbox_node_from_module(
            db, project.id, sandbox.id, module.module_key, 111, 222
        )
        if (
            node.module_key == module.module_key
            and node.title == module.title
            and node.duration_days == module.default_duration_days
            and node.x_position == 111
            and node.y_position == 222
        ):
            ok("Add module creates node with copied defaults and requested position")
        else:
            fail("create node defaults", node.__dict__)

        payload = crud.get_sandbox_canvas_payload(db, sandbox.id)
        if payload["modules"] and payload["elements"] and "deliverable" in payload["elements"][0]["data"]:
            ok("Canvas payload includes modules, elements, schedule, and editable node fields")
        else:
            fail("payload shape", payload)

        updated = crud.update_sandbox_node(db, project.id, sandbox.id, node.id, {
            "title": "Updated node",
            "duration_days": "9",
            "owner_role": "pm",
            "deliverable": "Updated deliverable",
            "exit_criteria": "Updated exit",
        })
        if (
            updated.title == "Updated node"
            and updated.duration_days == 9
            and updated.owner_role == "pm"
            and updated.deliverable == "Updated deliverable"
            and updated.exit_criteria == "Updated exit"
        ):
            ok("Update node changes only editable node fields")
        else:
            fail("update node", updated.__dict__)

        try:
            crud.update_sandbox_node(db, project.id, sandbox.id, node.id, {
                "title": "Bad duration",
                "duration_days": "0",
            })
            fail("invalid duration", "expected ValueError")
        except ValueError as exc:
            if str(exc) == "invalid_duration":
                ok("Invalid duration is rejected")
            else:
                fail("invalid duration error", str(exc))

        moved = crud.update_sandbox_node_position(db, project.id, sandbox.id, node.id, 333.5, 444.25)
        if moved.x_position == 333.5 and moved.y_position == 444.25:
            ok("Position helper persists x/y only inside sandbox")
        else:
            fail("position update", moved.__dict__)

        node2 = crud.create_sandbox_node_from_module(db, project.id, sandbox.id, modules[1].module_key, 200, 300)
        db.add(PlanningSandboxEdge(
            sandbox_id=sandbox.id,
            from_node_id=node.id,
            to_node_id=node2.id,
            dependency_type="finish_to_start",
        ))
        db.commit()
        crud.delete_sandbox_node(db, project.id, sandbox.id, node.id)
        edge_count = db.query(PlanningSandboxEdge).filter(PlanningSandboxEdge.sandbox_id == sandbox.id).count()
        if edge_count == 0:
            ok("Delete node removes attached sandbox-only edges")
        else:
            fail("delete edge cascade", f"edges left={edge_count}")

        for fn, args, expected in [
            (crud.create_sandbox_node_from_module, (db, project.id, sandbox.id, "missing_module"), "module_not_found"),
            (crud.update_sandbox_node_position, (db, project.id + 999, sandbox.id, node2.id, 1, 1), "sandbox_not_found"),
        ]:
            try:
                fn(*args)
                fail(f"{expected} guard", "expected ValueError")
            except ValueError as exc:
                if str(exc) == expected:
                    ok(f"{expected} guard works")
                else:
                    fail(f"{expected} guard", str(exc))

        sandbox.status = "applied"
        db.commit()
        try:
            crud.update_sandbox_node_position(db, project.id, sandbox.id, node2.id, 1, 1)
            fail("draft-only guard", "expected ValueError")
        except ValueError as exc:
            if str(exc) == "sandbox_not_draft":
                ok("Draft-only guard rejects applied sandboxes")
            else:
                fail("draft-only guard", str(exc))
        if len(project.phases) == 0:
            ok("Sandbox node edits do not create project phases")
        else:
            fail("project phase mutation", f"phase count={len(project.phases)}")
        db.close()
    finally:
        tmp.cleanup()

    print("\n── 3. Live route + browser smoke ──")
    session = live_login()
    if not session:
        fail("live login", f"could not login to {BASE}")
    else:
        project_id, sandbox_id, module_key, phase_count = live_fixture()
        try:
            add = session.post(
                f"{BASE}/projects/{project_id}/sandbox/{sandbox_id}/nodes/add",
                data={"module_key": module_key, "x_position": "140", "y_position": "180"},
                timeout=8,
            )
            if add.status_code == 200 and add.json().get("ok") and add.json()["sandbox_payload"]["elements"]:
                ok("Add-node route returns JSON payload with elements")
            else:
                fail("add-node route", f"status={add.status_code} body={add.text[:200]}")
            node_ids = [
                el["data"]["db_id"]
                for el in add.json()["sandbox_payload"]["elements"]
                if str(el["data"].get("id", "")).startswith("node-")
            ]
            node_id = node_ids[0]
            update = session.post(
                f"{BASE}/projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/update",
                data={
                    "title": "Route updated node",
                    "duration_days": "7",
                    "owner_role": "engineer",
                    "deliverable": "Route deliverable",
                    "exit_criteria": "Route exit",
                },
                timeout=8,
            )
            if update.status_code == 200 and update.json().get("ok"):
                ok("Update-node route returns JSON success")
            else:
                fail("update-node route", f"status={update.status_code} body={update.text[:200]}")
            pos = session.post(
                f"{BASE}/projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/position",
                data={"x_position": "410", "y_position": "220"},
                timeout=8,
            )
            if pos.status_code == 200 and pos.json().get("ok"):
                ok("Position route returns JSON success")
            else:
                fail("position route", f"status={pos.status_code} body={pos.text[:200]}")
            wrong = session.post(
                f"{BASE}/projects/{project_id + 9999}/sandbox/{sandbox_id}/nodes/{node_id}/position",
                data={"x_position": "1", "y_position": "1"},
                timeout=8,
            )
            if wrong.status_code in (400, 404):
                ok("Wrong project/sandbox route is rejected")
            else:
                fail("wrong project guard", f"status={wrong.status_code} body={wrong.text[:200]}")
            if count_project_phases(project_id) == phase_count:
                ok("Live sandbox routes do not mutate project_phases")
            else:
                fail("live project_phases mutation", f"before={phase_count} after={count_project_phases(project_id)}")

            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1440, "height": 950})
                page = context.new_page()
                page.goto(f"{BASE}/auth/login")
                if "/auth/login" in page.url:
                    page.fill("input[name='username']", ADMIN)
                    page.fill("input[name='password']", ADMIN_PWD)
                    page.click("form[action='/auth/login'] button[type='submit']")
                    page.wait_for_load_state("networkidle")
                page.goto(f"{BASE}/projects/{project_id}/sandbox")
                page.wait_for_load_state("networkidle")
                page.locator(".sandbox-workspace").screenshot(
                    path=str(ARTIFACTS / "v14_build04_sandbox_desktop.png")
                )
                desktop = page.evaluate(
                    """
                    () => ({
                      hasPalette: !!document.querySelector('[data-sandbox-palette]'),
                      hasAdd: !!document.querySelector('.sandbox-add-module-btn'),
                      hasProperties: !!document.querySelector('[data-sandbox-properties]'),
                      hasCanvas: !!document.querySelector('#sandboxCanvas'),
                      moduleCount: document.querySelectorAll('.sandbox-module-card').length,
                      hasOldReadOnlyOnly: document.body.innerText.includes('editing arrives in a later build'),
                    })
                    """
                )
                page.locator("#sandboxCanvas").click(position={"x": 120, "y": 120})
                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(f"{BASE}/projects/{project_id}/sandbox")
                page.wait_for_load_state("networkidle")
                page.locator(".sandbox-workspace").screenshot(
                    path=str(ARTIFACTS / "v14_build04_sandbox_mobile.png")
                )
                mobile = page.evaluate(
                    """
                    () => ({
                      docScrollWidth: document.documentElement.scrollWidth,
                      viewportWidth: window.innerWidth,
                      hasPalette: !!document.querySelector('[data-sandbox-palette]'),
                      hasCanvas: !!document.querySelector('#sandboxCanvas')
                    })
                    """
                )
                browser.close()
            if desktop["hasPalette"] and desktop["hasAdd"] and desktop["hasProperties"] and desktop["hasCanvas"] and desktop["moduleCount"] > 0:
                ok("Desktop sandbox renders editable palette, property panel, and canvas")
            else:
                fail("desktop sandbox render", desktop)
            if not desktop["hasOldReadOnlyOnly"]:
                ok("Sandbox no longer presents itself as read-only-only to editors")
            else:
                fail("read-only copy", desktop)
            if mobile["hasPalette"] and mobile["hasCanvas"] and mobile["docScrollWidth"] <= mobile["viewportWidth"] + 1:
                ok("Mobile sandbox has palette/canvas without horizontal document overflow")
            else:
                fail("mobile sandbox render", mobile)
        except Exception as exc:
            fail("live route/browser smoke", repr(exc))
        finally:
            cleanup_live()

    print(f"\nPassed: {len(PASS)} / {len(PASS) + len(FAIL)}")
    if FAIL:
        print("Failures:")
        for name, reason in FAIL:
            print(f" - {name}: {reason}")
        return False
    return True


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
