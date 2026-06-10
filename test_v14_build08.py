"""v1.4 Build 08 — Save Planning Sandbox as reusable template.

Requires the app running at http://localhost:8000 for route/browser smoke.
Run: python3 test_v14_build08.py
"""
import json
import os
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
    engine = create_engine(f"sqlite:///{Path(tmp.name) / 'v14_build08.db'}")
    import app.models  # noqa: F401
    from app.database import Base
    from app import migrations

    Base.metadata.create_all(bind=engine)
    migrations.run_pending(engine)
    Session = sessionmaker(bind=engine)
    return tmp, engine, Session


def create_user(db, username, role="pm", display_name=None):
    from app.models import User

    user = User(
        username=username,
        display_name=display_name or username,
        hashed_password="test",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_project(db, name, pm_name=ADMIN):
    from app.models import Project

    project = Project(name=name, status="active", product_manager=pm_name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def make_valid_sandbox(db, project_id):
    import app.crud as crud

    sandbox = crud.create_sandbox_blank(db, project_id)
    modules = crud.list_planning_modules(db)
    first = crud.create_sandbox_node_from_module(db, project_id, sandbox.id, modules[0].module_key, 80, 80)
    second = crud.create_sandbox_node_from_module(db, project_id, sandbox.id, modules[1].module_key, 260, 220)
    crud.update_sandbox_node(db, project_id, sandbox.id, first.id, {
        "title": "Concept Lock",
        "duration_days": "4",
        "owner_role": "PM",
        "deliverable": "Positioning approved",
        "exit_criteria": "Concept review complete",
    })
    crud.update_sandbox_node(db, project_id, sandbox.id, second.id, {
        "title": "Sample Build",
        "duration_days": "9",
        "owner_role": "Factory",
        "deliverable": "Prototype in hand",
        "exit_criteria": "Sample photos reviewed",
    })
    crud.create_sandbox_edge(db, project_id, sandbox.id, first.id, second.id)
    return sandbox


def live_login():
    s = requests.Session()
    r = s.post(
        f"{BASE}/auth/login",
        data={"username": ADMIN, "password": ADMIN_PWD},
        allow_redirects=False,
        timeout=8,
    )
    return s if r.status_code in (302, 303) else None


def cleanup_live(prefix="v14_b08"):
    from app.database import SessionLocal
    from app.models import PlanningTemplate, Project

    db = SessionLocal()
    try:
        for project in db.query(Project).filter(Project.name.like(prefix + "%")).all():
            db.delete(project)
        for template in db.query(PlanningTemplate).filter(PlanningTemplate.name.like(prefix + "%")).all():
            db.delete(template)
        db.commit()
    finally:
        db.close()


def live_fixture():
    from app.database import SessionLocal

    cleanup_live()
    db = SessionLocal()
    try:
        source_project = create_project(db, "v14_b08_source_project")
        sandbox = make_valid_sandbox(db, source_project.id)
        picker_project = create_project(db, "v14_b08_picker_project")
        return source_project.id, sandbox.id, picker_project.id
    finally:
        db.close()


def main():
    ARTIFACTS.mkdir(exist_ok=True)

    print("\n── 1. Source locks and i18n ──")
    plan = read("V14_BUILD08_EXECUTION_PLAN.md")
    crud_source = read("app/crud.py")
    routes = read("app/routes/projects.py")
    template = read("app/templates/planning_sandbox.html")
    styles = read("app/static/css/styles.css")
    registry = read("AI_TOOLS_REGISTRY.md")
    ai_tools = read("app/ai/tools.py")
    migrations = read("app/migrations.py")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))

    contains_all(
        "Build 08 plan locks template-save scope",
        plan,
        [
            "Save Workflow As Template",
            "No migration by default",
            "Templates are global reusable records",
            "Draft and applied snapshots can be saved",
            "805/805",
        ],
    )
    contains_all(
        "Build 08 service/route/template markers exist",
        crud_source + routes + template + styles,
        [
            "def list_planning_templates_for_user",
            "def save_sandbox_as_template",
            "/projects/{project_id}/sandbox/{sandbox_id}/save-template",
            "can_save_template",
            "sandbox-save-template-card",
            "sandbox-template-badge",
        ],
    )
    if "save_sandbox_as_template" in registry and "save_sandbox_as_template" not in ai_tools:
        ok("AI registry documents save-template while chat tool stays unwired")
    else:
        fail("AI save-template registry lock", "registry/tools mismatch")
    if "011_v1_4" not in migrations and "save_sandbox_as_template" not in migrations:
        ok("Build 08 does not add a new migration")
    else:
        fail("Build 08 migration lock", "unexpected migration marker")
    if set(en) == set(zh) and len(en) == 805:
        ok("i18n parity locked at 805/805")
    else:
        fail("i18n parity/count", f"en={len(en)} zh={len(zh)} diff={sorted(set(en) ^ set(zh))[:8]}")

    print("\n── 2. Service graph-copy behavior ──")
    import app.crud as crud
    from app.models import PlanningTemplate, PlanningTemplateEdge, PlanningTemplateNode

    tmp, engine, Session = build_db()
    try:
        db = Session()
        owner = create_user(db, "owner_pm", "pm")
        admin = create_user(db, "admin_user", "admin")
        other = create_user(db, "other_pm", "pm")
        project = create_project(db, "v14_b08_service_project", owner.username)
        sandbox = make_valid_sandbox(db, project.id)

        saved = crud.save_sandbox_as_template(
            db,
            project.id,
            sandbox.id,
            "v14_b08 Saved Workflow",
            "Reusable two-step knife workflow",
            owner.id,
        )
        node_count = db.query(PlanningTemplateNode).filter(PlanningTemplateNode.template_id == saved.id).count()
        edge_count = db.query(PlanningTemplateEdge).filter(PlanningTemplateEdge.template_id == saved.id).count()
        if (
            isinstance(saved, PlanningTemplate)
            and saved.is_system is False
            and saved.created_by_user_id == owner.id
            and saved.template_key.startswith("v14-b08-saved-workflow-")
            and node_count == 2
            and edge_count == 1
        ):
            ok("save_sandbox_as_template creates owned template with copied graph")
        else:
            fail("saved template graph", {"template": getattr(saved, "__dict__", saved), "nodes": node_count, "edges": edge_count})

        first_node = sorted(saved.nodes, key=lambda n: n.sort_order)[0]
        if (
            first_node.title == "Concept Lock"
            and first_node.duration_days == 4
            and first_node.owner_role == "PM"
            and first_node.module_key
        ):
            ok("Saved template node preserves module key and editable fields")
        else:
            fail("saved template node fields", getattr(first_node, "__dict__", first_node))

        duplicate = crud.save_sandbox_as_template(db, project.id, sandbox.id, "v14_b08 Saved Workflow", "", owner.id)
        if duplicate.template_key != saved.template_key and duplicate.name == saved.name:
            ok("Duplicate template names get unique service-generated keys")
        else:
            fail("duplicate template key", {"first": saved.template_key, "second": duplicate.template_key})

        clone_project = create_project(db, "v14_b08_clone_project", owner.username)
        clone = crud.create_sandbox_from_template(db, clone_project.id, saved.template_key, owner.id, owner.role)
        clone_payload = crud.get_sandbox_canvas_payload(db, clone.id)
        clone_nodes = [el for el in clone_payload["elements"] if el["data"]["id"].startswith("node-")]
        clone_edges = [el for el in clone_payload["elements"] if el["data"]["id"].startswith("edge-")]
        if clone.base_template_key == saved.template_key and len(clone_nodes) == 2 and len(clone_edges) == 1:
            ok("Saved template can create a new sandbox graph")
        else:
            fail("create from saved template", {"base": clone.base_template_key, "nodes": clone_nodes, "edges": clone_edges})

        denied_project = create_project(db, "v14_b08_denied_project", other.username)
        try:
            crud.create_sandbox_from_template(db, denied_project.id, saved.template_key, other.id, other.role)
            fail("private template visibility for non-owner", "expected template_not_found")
        except ValueError as exc:
            if str(exc) == "template_not_found":
                ok("Non-owner PM cannot create from private user template")
            else:
                fail("private template non-owner error", str(exc))

        admin_project = create_project(db, "v14_b08_admin_project", admin.username)
        admin_clone = crud.create_sandbox_from_template(db, admin_project.id, saved.template_key, admin.id, admin.role)
        if admin_clone.base_template_key == saved.template_key:
            ok("Admin can create from a user template")
        else:
            fail("admin template clone", admin_clone.base_template_key)

        owner_visible = crud.list_planning_templates_for_user(db, owner)
        other_visible = crud.list_planning_templates_for_user(db, other)
        admin_visible = crud.list_planning_templates_for_user(db, admin)
        if saved.id in {t.id for t in owner_visible} and saved.id not in {t.id for t in other_visible} and saved.id in {t.id for t in admin_visible}:
            ok("Template visibility is creator + admin, not other PMs")
        else:
            fail("template visibility", {
                "owner": [t.name for t in owner_visible],
                "other": [t.name for t in other_visible],
                "admin": [t.name for t in admin_visible],
            })

        applied_project = create_project(db, "v14_b08_applied_project", owner.username)
        applied_sandbox = make_valid_sandbox(db, applied_project.id)
        applied_sandbox.status = "applied"
        db.commit()
        applied_saved = crud.save_sandbox_as_template(db, applied_project.id, applied_sandbox.id, "v14_b08 Applied Template", "", owner.id)
        if applied_saved.id:
            ok("Applied sandbox snapshot can be saved as template")
        else:
            fail("applied save", applied_saved)

        applied_sandbox.status = "archived"
        db.commit()
        try:
            crud.save_sandbox_as_template(db, applied_project.id, applied_sandbox.id, "v14_b08 Archived Template", "", owner.id)
            fail("archived sandbox save guard", "expected sandbox_not_templateable")
        except ValueError as exc:
            if str(exc) == "sandbox_not_templateable":
                ok("Archived sandbox cannot be saved as template")
            else:
                fail("archived save error", str(exc))

        try:
            crud.save_sandbox_as_template(db, project.id, sandbox.id, "   ", "", owner.id)
            fail("blank template name guard", "expected template_name_required")
        except ValueError as exc:
            if str(exc) == "template_name_required":
                ok("Blank template name is rejected")
            else:
                fail("blank template name error", str(exc))
    finally:
        tmp.cleanup()

    print("\n── 3. Route source and live browser smoke ──")
    contains_all(
        "Routes enforce project edit access and scoped template creation",
        routes,
        [
            "can_edit_project(current_user, project)",
            "save_planning_sandbox_template",
            "template_name_required",
            "save_template_error",
            "current_user.role",
            "list_planning_templates_for_user",
        ],
    )
    if "{% if can_save_template %}" in template and "{% if can_edit %}" in template and "sandbox.no_user_templates" in template:
        ok("Template hides save/create affordances behind permission gates")
    else:
        fail("template permission gates", "missing expected Jinja guards")

    session = live_login()
    if not session:
        fail("Live login", "could not log in as admin")
    else:
        source_project_id, sandbox_id, picker_project_id = live_fixture()
        r = session.post(
            f"{BASE}/projects/{source_project_id}/sandbox/{sandbox_id}/save-template",
            data={"template_name": "v14_b08 Live Workflow", "template_description": "Live browser saved template"},
            allow_redirects=False,
            timeout=10,
        )
        if r.status_code in (302, 303) and "template_saved=1" in r.headers.get("location", ""):
            ok("Save-template route redirects with success")
        else:
            fail("save-template route success", {"status": r.status_code, "location": r.headers.get("location")})

        bad = session.post(
            f"{BASE}/projects/{source_project_id}/sandbox/{sandbox_id}/save-template",
            data={"template_name": "   ", "template_description": ""},
            allow_redirects=False,
            timeout=10,
        )
        if bad.status_code in (302, 303) and "save_template_error=template_name_required" in bad.headers.get("location", ""):
            ok("Save-template route rejects blank name")
        else:
            fail("save-template blank route", {"status": bad.status_code, "location": bad.headers.get("location")})

        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 1366, "height": 900})
            context.add_cookies([
                {"name": cookie.name, "value": cookie.value, "url": BASE}
                for cookie in session.cookies
            ])
            page = context.new_page()
            page.goto(f"{BASE}/projects/{source_project_id}/sandbox?sandbox_id={sandbox_id}")
            page.wait_for_selector(".sandbox-save-template-card")
            page.click(".sandbox-save-template-card > summary")
            page.wait_for_selector(".sandbox-save-template-form")
            save_text = page.locator(".sandbox-save-template-card").inner_text()
            if "Save Workflow as Template" in save_text and "live timeline" in save_text:
                ok("Browser shows Save as Template panel")
            else:
                fail("save panel browser text", save_text)
            page.screenshot(path=str(ARTIFACTS / "v14_build08_save_template_panel.png"), full_page=True)

            page.goto(f"{BASE}/projects/{picker_project_id}/sandbox")
            page.wait_for_selector(".sandbox-template-library")
            picker_text = page.locator(".sandbox-template-library").inner_text()
            picker_lower = picker_text.lower()
            if "system templates" in picker_lower and "my templates" in picker_lower and "v14_b08 Live Workflow" in picker_text:
                ok("Browser picker includes saved user template")
            else:
                fail("picker saved template", picker_text)
            page.screenshot(path=str(ARTIFACTS / "v14_build08_template_picker.png"), full_page=True)

            page.set_viewport_size({"width": 390, "height": 860})
            page.goto(f"{BASE}/projects/{picker_project_id}/sandbox")
            page.wait_for_selector(".sandbox-template-library")
            overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            if not overflow:
                ok("Template picker has no mobile horizontal overflow")
            else:
                fail("mobile overflow", "document overflowed horizontally")
            page.screenshot(path=str(ARTIFACTS / "v14_build08_template_picker_mobile.png"), full_page=True)
            context.close()
            browser.close()

    cleanup_live()

    print(f"\nPassed: {len(PASS)} / {len(PASS) + len(FAIL)}")
    if FAIL:
        print("\nFailures:")
        for name, reason in FAIL:
            print(f"- {name}: {reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
