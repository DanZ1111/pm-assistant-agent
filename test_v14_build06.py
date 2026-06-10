"""v1.4 Build 06 — Planning Sandbox canvas interaction hardening.

Requires the app running at http://localhost:8000 for route/browser smoke.
Run: python3 test_v14_build06.py
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
    engine = create_engine(f"sqlite:///{Path(tmp.name) / 'v14_build06.db'}")
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


def create_nodes_with_durations(db, project_id, sandbox_id, durations):
    import app.crud as crud

    modules = crud.list_planning_modules(db)
    nodes = []
    for index, days in enumerate(durations):
        node = crud.create_sandbox_node_from_module(
            db, project_id, sandbox_id, modules[index % len(modules)].module_key, 80 + index * 120, 90
        )
        crud.update_sandbox_node(db, project_id, sandbox_id, node.id, {
            "title": f"Node {index + 1}",
            "duration_days": str(days),
            "owner_role": "pm",
            "deliverable": "done",
            "exit_criteria": "approved",
        })
        nodes.append(node)
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


def cleanup_live(prefix="v14_b06"):
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


def live_fixture(applied=False, cleanup=True):
    import app.crud as crud
    from app.database import SessionLocal

    if cleanup:
        cleanup_live()
    db = SessionLocal()
    try:
        project = create_project(db, "v14_b06_live_project")
        sandbox = crud.create_sandbox_blank(db, project.id, user_id=None)
        nodes = create_nodes_with_durations(db, project.id, sandbox.id, [5, 14, 30, 60])
        crud.create_sandbox_edge(db, project.id, sandbox.id, nodes[0].id, nodes[1].id)
        nodes[-1].owner_role = None
        if applied:
            sandbox.status = "applied"
        db.commit()
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
    plan = read("V14_BUILD06_EXECUTION_PLAN.md")
    routes = read("app/routes/projects.py")
    crud_source = read("app/crud.py")
    template = read("app/templates/planning_sandbox.html")
    js = read("app/static/js/planning_sandbox.js")
    css = read("app/static/css/styles.css")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))

    contains_all(
        "Build 06 plan locks hardening scope",
        plan,
        [
            "Tidy changes positions only",
            "No Apply route",
            "No migration",
            "no `project_phases` mutation",
            "775/775",
            "scenario contract runner",
        ],
    )
    contains_all(
        "Build 06 backend route/service markers exist",
        crud_source + routes,
        [
            "def update_sandbox_node_positions",
            "def _sandbox_duration_bin",
            "/projects/{project_id}/sandbox/{sandbox_id}/nodes/positions",
            "positions_json",
        ],
    )
    contains_all(
        "Build 06 template hardening markers exist",
        template,
        [
            "data-tidy-canvas",
            "sandbox.snapshot_view",
            "sandbox.empty_canvas_editable",
            "sandbox-warning-chip",
            "cytoscape-dagre",
        ],
    )
    if "sandbox_id: int | None" in routes:
        ok("Sandbox page route can address explicit snapshot sandbox_id")
    else:
        fail("snapshot route parameter", "missing sandbox_id query parameter")
    contains_all(
        "Build 06 JS hardening markers exist",
        js,
        [
            "tidyCanvas",
            "dagre",
            "runFallbackTidy",
            "positions_json",
            "duration_bin",
            "sandbox-canvas-loading",
        ],
    )
    contains_all(
        "Build 06 CSS hardening markers exist",
        css,
        [
            ".sandbox-toolbar-actions",
            ".sandbox-warning-chip",
            ".sandbox-canvas-loading",
            "@keyframes sandbox-spin",
        ],
    )
    if set(en) == set(zh) and len(en) >= 775:
        ok(f"i18n parity preserved with Build 06 keys present ({len(en)}/{len(zh)})")
    else:
        fail("i18n parity/count", f"en={len(en)} zh={len(zh)} diff={sorted(set(en) ^ set(zh))[:8]}")

    print("\n── 2. Service hardening with temp DB ──")
    import app.crud as crud

    tmp, engine, Session = build_db()
    try:
        db = Session()
        project = create_project(db, "v14_b06_service_project")
        sandbox = crud.create_sandbox_blank(db, project.id)
        nodes = create_nodes_with_durations(db, project.id, sandbox.id, [7, 8, 22, 46])
        before = {node.id: (node.title, node.duration_days, node.x_position, node.y_position) for node in nodes}
        updated_count = crud.update_sandbox_node_positions(db, project.id, sandbox.id, [
            {"node_id": nodes[0].id, "x_position": 111, "y_position": 222},
            {"node_id": nodes[1].id, "x_position": 333, "y_position": 444},
        ])
        db.refresh(nodes[0])
        db.refresh(nodes[1])
        if (
            updated_count == 2
            and nodes[0].x_position == 111
            and nodes[1].y_position == 444
            and nodes[0].title == before[nodes[0].id][0]
            and nodes[1].duration_days == before[nodes[1].id][1]
        ):
            ok("Tidy position helper updates positions only")
        else:
            fail("bulk position update", {"count": updated_count, "node0": nodes[0].__dict__, "node1": nodes[1].__dict__})

        payload = crud.get_sandbox_canvas_payload(db, sandbox.id)
        bins = [
            el["data"]["duration_bin"]
            for el in payload["elements"]
            if str(el["data"].get("id", "")).startswith("node-")
        ]
        if bins == ["S", "M", "L", "XL"]:
            ok("Duration bins are emitted as S/M/L/XL")
        else:
            fail("duration bins", bins)

        sandbox.status = "applied"
        db.commit()
        try:
            crud.update_sandbox_node_positions(db, project.id, sandbox.id, [
                {"node_id": nodes[0].id, "x_position": 1, "y_position": 1},
            ])
            fail("applied position guard", "expected ValueError")
        except ValueError as exc:
            if str(exc) == "sandbox_not_draft":
                ok("Applied sandboxes reject Tidy position writes")
            else:
                fail("applied position guard", str(exc))
        if len(project.phases) == 0:
            ok("Canvas hardening does not create project phases")
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
        try:
            positions = [
                {"node_id": node_ids[0], "x_position": 180, "y_position": 260},
                {"node_id": node_ids[1], "x_position": 420, "y_position": 260},
            ]
            route = session.post(
                f"{BASE}/projects/{project_id}/sandbox/{sandbox_id}/nodes/positions",
                data={"positions_json": json.dumps(positions)},
                timeout=8,
            )
            if route.status_code == 200 and route.json().get("ok"):
                ok("Bulk position route returns JSON success")
            else:
                fail("bulk position route", f"status={route.status_code} body={route.text[:200]}")
            if count_project_phases(project_id) == phase_count:
                ok("Live Tidy route does not mutate project_phases")
            else:
                fail("live project_phases mutation", f"before={phase_count} after={count_project_phases(project_id)}")

            applied_project_id, applied_sandbox_id, applied_node_ids, _ = live_fixture(applied=True, cleanup=False)
            denied = session.post(
                f"{BASE}/projects/{applied_project_id}/sandbox/{applied_sandbox_id}/nodes/positions",
                data={"positions_json": json.dumps([{"node_id": applied_node_ids[0], "x_position": 1, "y_position": 1}])},
                timeout=8,
            )
            if denied.status_code == 400 and denied.json().get("error") == "sandbox_not_draft":
                ok("Applied snapshot rejects mutation routes")
            else:
                fail("applied route guard", f"status={denied.status_code} body={denied.text[:200]}")

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
                page.click("[data-tidy-canvas]")
                page.wait_for_timeout(1200)
                page.locator(".sandbox-workspace").screenshot(
                    path=str(ARTIFACTS / "v14_build06_sandbox_hardened_desktop.png")
                )
                desktop = page.evaluate(
                    """
                    () => {
                      const payload = JSON.parse(document.querySelector('[data-sandbox-workspace]').dataset.payload || '{}');
                      return {
                        hasTidy: !!document.querySelector('[data-tidy-canvas]'),
                      hasWarningChip: !!document.querySelector('.sandbox-warning-chip'),
                        hasDurationBins: (payload.elements || []).some(el => el.data && el.data.duration_bin === 'XL'),
                        hasCanvas: !!document.querySelector('#sandboxCanvas canvas'),
                        hasDagreScript: [...document.scripts].some(s => s.src.includes('cytoscape-dagre')),
                      };
                    }
                    """
                )
                page.goto(f"{BASE}/projects/{applied_project_id}/sandbox?sandbox_id={applied_sandbox_id}")
                page.wait_for_load_state("networkidle")
                applied = page.evaluate(
                    """
                    () => ({
                      hasTidy: !!document.querySelector('[data-tidy-canvas]'),
                      hasAdd: !!document.querySelector('.sandbox-add-module-btn'),
                      hasSave: !!document.querySelector('[data-node-form] button[type="submit"]'),
                      hasSnapshotCopy: document.body.innerText.includes('Snapshot view'),
                    })
                    """
                )
                page.set_viewport_size({"width": 390, "height": 844})
                page.goto(f"{BASE}/projects/{project_id}/sandbox")
                page.wait_for_load_state("networkidle")
                page.locator(".sandbox-workspace").screenshot(
                    path=str(ARTIFACTS / "v14_build06_sandbox_hardened_mobile.png")
                )
                mobile = page.evaluate(
                    """
                    () => ({
                      docScrollWidth: document.documentElement.scrollWidth,
                      viewportWidth: window.innerWidth,
                      hasTidy: !!document.querySelector('[data-tidy-canvas]'),
                      hasCanvas: !!document.querySelector('#sandboxCanvas')
                    })
                    """
                )
                browser.close()
            if all(desktop.values()):
                ok("Desktop sandbox renders Tidy, duration bins, warning chips, and dagre script")
            else:
                fail("desktop hardening render", desktop)
            if not applied["hasTidy"] and not applied["hasAdd"] and not applied["hasSave"] and applied["hasSnapshotCopy"]:
                ok("Applied snapshot renders read-only affordances")
            else:
                fail("applied snapshot render", applied)
            if mobile["hasTidy"] and mobile["hasCanvas"] and mobile["docScrollWidth"] <= mobile["viewportWidth"] + 1:
                ok("Mobile hardened canvas has no horizontal document overflow")
            else:
                fail("mobile hardening render", mobile)
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
