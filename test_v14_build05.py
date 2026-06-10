"""v1.4 Build 05 — Planning Sandbox dependency edges.

Requires the app running at http://localhost:8000 for route/browser smoke.
Run: python3 test_v14_build05.py
"""
import json
import os
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
    engine = create_engine(f"sqlite:///{Path(tmp.name) / 'v14_build05.db'}")
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


def create_three_nodes(db, project_id, sandbox_id):
    import app.crud as crud

    modules = crud.list_planning_modules(db)
    nodes = [
        crud.create_sandbox_node_from_module(db, project_id, sandbox_id, modules[0].module_key, 80, 80),
        crud.create_sandbox_node_from_module(db, project_id, sandbox_id, modules[1].module_key, 280, 80),
        crud.create_sandbox_node_from_module(db, project_id, sandbox_id, modules[2].module_key, 480, 80),
    ]
    for node, days in zip(nodes, [5, 7, 3]):
        crud.update_sandbox_node(db, project_id, sandbox_id, node.id, {
            "title": node.title,
            "duration_days": str(days),
            "owner_role": "pm",
            "deliverable": "done",
            "exit_criteria": "approved",
        })
    return nodes


def live_login():
    s = requests.Session()
    r = s.post(
        f"{BASE}/auth/login",
        data={"username": ADMIN, "password": ADMIN_PWD},
        allow_redirects=False,
        timeout=8,
    )
    return s if r.status_code in (302, 303) else None


def cleanup_live(prefix="v14_b05"):
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
    import app.crud as crud
    from app.database import SessionLocal

    cleanup_live()
    db = SessionLocal()
    try:
        project = create_project(db, "v14_b05_live_project")
        sandbox = crud.create_sandbox_blank(db, project.id, user_id=None)
        nodes = create_three_nodes(db, project.id, sandbox.id)
        before_phase_count = len(project.phases)
        return project.id, sandbox.id, [node.id for node in nodes], before_phase_count
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
    plan = read("V14_BUILD05_EXECUTION_PLAN.md")
    routes = read("app/routes/projects.py")
    crud_source = read("app/crud.py")
    template = read("app/templates/planning_sandbox.html")
    js = read("app/static/js/planning_sandbox.js")
    css = read("app/static/css/styles.css")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))

    contains_all(
        "Build 05 plan locks dependency scope",
        plan,
        [
            "Property-panel dependency editing must ship",
            "No Apply route",
            "No migrations",
            "no `project_phases` mutation",
            "766/766",
        ],
    )
    contains_all(
        "Build 05 services are present",
        crud_source,
        [
            "def create_sandbox_edge",
            "def delete_sandbox_edge",
            "def replace_sandbox_node_dependencies",
            "self_dependency",
            "cross_sandbox_edge",
            "_raise_if_sandbox_has_hard_graph_error",
        ],
    )
    contains_all(
        "Build 05 JSON routes are registered",
        routes,
        [
            "/projects/{project_id}/sandbox/{sandbox_id}/edges",
            "/projects/{project_id}/sandbox/{sandbox_id}/edges/{edge_id}/delete",
            "/projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/dependencies",
            "crud.create_sandbox_edge",
            "crud.delete_sandbox_edge",
            "crud.replace_sandbox_node_dependencies",
        ],
    )
    contains_all(
        "Dependency UI markers exist",
        template,
        [
            "data-dependency-form",
            "data-node-dependencies",
            "sandbox.field_depends_on",
            "sandbox.save_dependencies",
            "{% if can_edit %}",
        ],
    )
    contains_all(
        "Dependency JS uses fetch + JSON payload replacement",
        js,
        [
            "data-node-dependencies",
            "/dependencies",
            "depends_on_ids",
            "data-delete-edge-id",
            "circular_dependency",
            "refreshFromPayload",
        ],
    )
    contains_all(
        "Dependency CSS exists",
        css,
        [
            ".sandbox-dependency-form",
            ".sandbox-dependency-list",
            ".sandbox-dependency-row",
        ],
    )
    if set(en) == set(zh) and len(en) >= 766:
        ok(f"i18n parity preserved with Build 05 keys present ({len(en)}/{len(zh)})")
    else:
        fail("i18n parity/count", f"en={len(en)} zh={len(zh)} diff={sorted(set(en) ^ set(zh))[:8]}")

    print("\n── 2. Service graph behavior with temp DB ──")
    import app.crud as crud
    from app.models import PlanningSandboxEdge

    tmp, engine, Session = build_db()
    try:
        db = Session()
        project = create_project(db, "v14_b05_service_project")
        sandbox = crud.create_sandbox_blank(db, project.id)
        a, b, c = create_three_nodes(db, project.id, sandbox.id)
        before_total = crud.compute_sandbox_schedule(db, sandbox.id)["total_days"]
        edge = crud.create_sandbox_edge(db, project.id, sandbox.id, a.id, b.id)
        after_total = crud.compute_sandbox_schedule(db, sandbox.id)["total_days"]
        if edge.from_node_id == a.id and edge.to_node_id == b.id and after_total == 12 and before_total == 7:
            ok("Create edge persists dependency and updates schedule estimate")
        else:
            fail("create edge schedule", {"edge": edge.__dict__, "before": before_total, "after": after_total})

        duplicate = crud.create_sandbox_edge(db, project.id, sandbox.id, a.id, b.id)
        edge_count = db.query(PlanningSandboxEdge).filter(PlanningSandboxEdge.sandbox_id == sandbox.id).count()
        if duplicate.id == edge.id and edge_count == 1:
            ok("Duplicate edge create is idempotent")
        else:
            fail("duplicate edge", {"duplicate": duplicate.id, "edge_count": edge_count})

        replaced = crud.replace_sandbox_node_dependencies(db, project.id, sandbox.id, b.id, [a.id, c.id])
        b_payload = next(el for el in crud.get_sandbox_canvas_payload(db, sandbox.id)["elements"] if el["data"].get("db_id") == b.id)
        if len(replaced) == 2 and set(b_payload["data"]["depends_on_ids"]) == {a.id, c.id}:
            ok("Replace dependencies accepts multiple parents and payload exposes depends_on_ids")
        else:
            fail("replace dependencies", {"replaced": [e.id for e in replaced], "payload": b_payload})

        for label, call, expected in [
            ("self dependency", lambda: crud.create_sandbox_edge(db, project.id, sandbox.id, a.id, a.id), "self_dependency"),
            ("cycle dependency", lambda: crud.create_sandbox_edge(db, project.id, sandbox.id, b.id, a.id), "circular_dependency"),
            ("replace cycle", lambda: crud.replace_sandbox_node_dependencies(db, project.id, sandbox.id, a.id, [b.id]), "circular_dependency"),
        ]:
            try:
                call()
                fail(label, "expected ValueError")
            except ValueError as exc:
                if str(exc) == expected:
                    ok(f"{label} is rejected")
                else:
                    fail(label, str(exc))

        edge_count_after_rejects = db.query(PlanningSandboxEdge).filter(PlanningSandboxEdge.sandbox_id == sandbox.id).count()
        if edge_count_after_rejects == 2:
            ok("Rejected cycle writes leave original graph unchanged")
        else:
            fail("cycle rollback", f"edge_count={edge_count_after_rejects}")

        other_project = create_project(db, "v14_b05_other_project")
        other_sandbox = crud.create_sandbox_blank(db, other_project.id)
        other_node = crud.create_sandbox_node_from_module(
            db, other_project.id, other_sandbox.id, crud.list_planning_modules(db)[0].module_key, 80, 80
        )
        try:
            crud.create_sandbox_edge(db, project.id, sandbox.id, a.id, other_node.id)
            fail("cross sandbox edge", "expected ValueError")
        except ValueError as exc:
            if str(exc) == "cross_sandbox_edge":
                ok("Cross-sandbox edge is rejected")
            else:
                fail("cross sandbox edge", str(exc))

        crud.delete_sandbox_edge(db, project.id, sandbox.id, edge.id)
        remaining = db.query(PlanningSandboxEdge).filter(PlanningSandboxEdge.sandbox_id == sandbox.id).count()
        if remaining == 1:
            ok("Delete edge removes one dependency")
        else:
            fail("delete edge", f"remaining={remaining}")
        if len(project.phases) == 0:
            ok("Sandbox dependency edits do not create project phases")
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
        project_id, sandbox_id, node_ids, phase_count = live_fixture()
        a_id, b_id, c_id = node_ids
        try:
            add = session.post(
                f"{BASE}/projects/{project_id}/sandbox/{sandbox_id}/edges",
                data={"from_node_id": a_id, "to_node_id": b_id},
                timeout=8,
            )
            if add.status_code == 200 and add.json().get("ok"):
                ok("Create-edge route returns JSON success")
            else:
                fail("create-edge route", f"status={add.status_code} body={add.text[:200]}")

            dep = session.post(
                f"{BASE}/projects/{project_id}/sandbox/{sandbox_id}/nodes/{b_id}/dependencies",
                data=[("depends_on_ids", str(a_id)), ("depends_on_ids", str(c_id))],
                timeout=8,
            )
            payload = dep.json().get("sandbox_payload", {}) if dep.headers.get("content-type", "").startswith("application/json") else {}
            if dep.status_code == 200 and dep.json().get("ok") and payload.get("elements"):
                ok("Dependency replace route returns JSON payload")
            else:
                fail("dependency route", f"status={dep.status_code} body={dep.text[:200]}")

            cycle = session.post(
                f"{BASE}/projects/{project_id}/sandbox/{sandbox_id}/edges",
                data={"from_node_id": b_id, "to_node_id": a_id},
                timeout=8,
            )
            if cycle.status_code == 400 and cycle.json().get("error") == "circular_dependency":
                ok("Cycle route rejects dependency before commit")
            else:
                fail("cycle route", f"status={cycle.status_code} body={cycle.text[:200]}")

            edge_ids = [
                el["data"]["db_id"]
                for el in payload.get("elements", [])
                if str(el["data"].get("id", "")).startswith("edge-")
            ]
            delete = session.post(
                f"{BASE}/projects/{project_id}/sandbox/{sandbox_id}/edges/{edge_ids[0]}/delete",
                timeout=8,
            )
            if delete.status_code == 200 and delete.json().get("ok"):
                ok("Delete-edge route returns JSON success")
            else:
                fail("delete-edge route", f"status={delete.status_code} body={delete.text[:200]}")

            if count_project_phases(project_id) == phase_count:
                ok("Live dependency routes do not mutate project_phases")
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
                    path=str(ARTIFACTS / "v14_build05_sandbox_dependencies_desktop.png")
                )
                desktop = page.evaluate(
                    """
                    () => ({
                      hasDependencyForm: !!document.querySelector('[data-dependency-form]'),
                      hasDependencySelect: !!document.querySelector('[data-node-dependencies]'),
                      hasDependencyList: !!document.querySelector('[data-dependency-list]'),
                      hasCanvas: !!document.querySelector('#sandboxCanvas canvas'),
                      scriptVersioned: [...document.scripts].some(s => s.src.includes('/static/js/planning_sandbox.js?v=')),
                    })
                    """
                )
                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(f"{BASE}/projects/{project_id}/sandbox")
                page.wait_for_load_state("networkidle")
                page.locator(".sandbox-workspace").screenshot(
                    path=str(ARTIFACTS / "v14_build05_sandbox_dependencies_mobile.png")
                )
                mobile = page.evaluate(
                    """
                    () => ({
                      docScrollWidth: document.documentElement.scrollWidth,
                      viewportWidth: window.innerWidth,
                      hasDependencyForm: !!document.querySelector('[data-dependency-form]'),
                      hasCanvas: !!document.querySelector('#sandboxCanvas')
                    })
                    """
                )
                browser.close()
            if all(desktop.values()):
                ok("Desktop sandbox renders dependency controls and versioned sandbox JS")
            else:
                fail("desktop dependency render", desktop)
            if mobile["hasDependencyForm"] and mobile["hasCanvas"] and mobile["docScrollWidth"] <= mobile["viewportWidth"] + 1:
                ok("Mobile sandbox dependency controls do not cause horizontal overflow")
            else:
                fail("mobile dependency render", mobile)
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
