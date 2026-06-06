"""v1.4 Build 03 — Planning Sandbox static canvas renderer regression.

Build 03 introduces the project-level sandbox page, template/blank draft
creation, and read-only Cytoscape rendering. It must not add node editing,
apply behavior, or live ProjectPhase mutation.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = Path(__file__).resolve().parent
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
    engine = create_engine(f"sqlite:///{Path(tmp.name) / 'v14_build03.db'}")
    import app.models  # noqa: F401
    from app.database import Base
    from app import migrations

    Base.metadata.create_all(bind=engine)
    migrations.run_pending(engine)
    Session = sessionmaker(bind=engine)
    return tmp, engine, Session


def create_project(db, name):
    from app.models import Project
    project = Project(name=name, status="active")
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def count_rows(db, table):
    return db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def main():
    import app.crud as crud
    from app.main import app

    print("\n── 1. Route and template shell ──")
    route_paths = {getattr(route, "path", "") for route in app.routes}
    if "/projects/{project_id}/sandbox" in route_paths and "/projects/{project_id}/sandbox/create" in route_paths:
        ok("Project sandbox GET and create POST routes are registered")
    else:
        fail("sandbox route table", sorted(path for path in route_paths if "sandbox" in path))
    forbidden_routes = [
        path for path in route_paths
        if "sandbox" in path and any(fragment in path for fragment in ("/apply", "/nodes", "/edges", "/save-template"))
    ]
    if not forbidden_routes:
        ok("Build 03 does not expose apply/node/edge/template mutation routes")
    else:
        fail("forbidden sandbox routes", forbidden_routes)

    template = read("app/templates/planning_sandbox.html")
    js = read("app/static/js/planning_sandbox.js")
    base = read("app/templates/base.html")
    contains_all(
        "planning_sandbox.html renders picker, summary, canvas, and Cytoscape only locally",
        template,
        [
            "sandboxCanvas",
            "sandbox_elements_json",
            "planning_templates",
            "/projects/{{ project.id }}/sandbox/create",
            "cytoscape@3.28.1",
            "/static/js/planning_sandbox.js",
            "read_only_build",
        ],
    )
    contains_all(
        "planning_sandbox.js parses server elements and uses preset read-only layout",
        js,
        [
            "JSON.parse",
            "autoungrabify: true",
            "layout: {",
            "name: 'preset'",
            "sandbox-canvas-empty",
        ],
    )
    if "cytoscape" not in base.lower():
        ok("Cytoscape is not loaded globally in base.html")
    else:
        fail("global Cytoscape load", "base.html should not load sandbox renderer")

    print("\n── 2. Blank sandbox creation is idempotent and isolated ──")
    tmp, engine, Session = build_db()
    try:
        db = Session()
        project = create_project(db, "Blank Sandbox Project")
        before_phases = count_rows(db, "project_phases")
        first = crud.create_sandbox_blank(db, project.id, user_id=None)
        second = crud.create_sandbox_blank(db, project.id, user_id=None)
        payload = crud.get_sandbox_canvas_payload(db, first.id)
        after_phases = count_rows(db, "project_phases")
        if first.id == second.id and first.status == "draft" and payload["elements"] == []:
            ok("Blank sandbox returns one empty draft on repeated calls")
        else:
            fail("blank sandbox idempotency", {"first": first.id, "second": second.id, "payload": payload})
        if before_phases == after_phases == 0:
            ok("Blank sandbox creation does not mutate project_phases")
        else:
            fail("blank sandbox phase mutation", f"before={before_phases} after={after_phases}")
        db.close()
    finally:
        tmp.cleanup()

    print("\n── 3. Template clone + canvas payload ──")
    tmp, engine, Session = build_db()
    try:
        db = Session()
        project = create_project(db, "Template Sandbox Project")
        before_phases = count_rows(db, "project_phases")
        sandbox = crud.create_sandbox_from_template(db, project.id, "simple_oem_knife", user_id=None)
        payload = crud.get_sandbox_canvas_payload(db, sandbox.id)
        after_phases = count_rows(db, "project_phases")
        node_elements = [el for el in payload["elements"] if el["data"]["id"].startswith("node-")]
        edge_elements = [el for el in payload["elements"] if el["data"]["id"].startswith("edge-")]
        if sandbox.base_template_key == "simple_oem_knife" and node_elements and edge_elements:
            ok("Template sandbox clones nodes/edges and exposes Cytoscape elements")
        else:
            fail("template clone payload", {"sandbox": sandbox.base_template_key, "payload": payload})
        if payload["schedule"]["total_days"] > 0 and not payload["schedule"]["hard_errors"]:
            ok("Canvas payload includes computed read-only schedule")
        else:
            fail("canvas schedule", payload["schedule"])
        if all("position" in el and "label" in el["data"] for el in node_elements):
            ok("Node elements preserve template positions and labels")
        else:
            fail("node element shape", node_elements[:2])
        if before_phases == after_phases == 0:
            ok("Template sandbox creation does not mutate project_phases")
        else:
            fail("template sandbox phase mutation", f"before={before_phases} after={after_phases}")
        reused = crud.create_sandbox_from_template(db, project.id, "standard_folding_knife", user_id=None)
        if reused.id == sandbox.id and reused.base_template_key == "simple_oem_knife":
            ok("Template creation returns existing draft instead of replacing it")
        else:
            fail("existing draft reuse", {"original": sandbox.id, "reused": reused.id, "template": reused.base_template_key})
        db.close()
    finally:
        tmp.cleanup()

    print("\n── 4. Invalid template and active draft lookup ──")
    tmp, engine, Session = build_db()
    try:
        db = Session()
        project = create_project(db, "Invalid Template Project")
        try:
            crud.create_sandbox_from_template(db, project.id, "not_a_template", user_id=None)
            fail("invalid template", "expected ValueError")
        except ValueError as exc:
            if str(exc) == "template_not_found":
                ok("Invalid template key raises template_not_found")
            else:
                fail("invalid template error", str(exc))
        blank = crud.create_sandbox_blank(db, project.id, user_id=None)
        active = crud.get_active_planning_sandbox(db, project.id)
        if active and active.id == blank.id:
            ok("get_active_planning_sandbox returns the draft sandbox")
        else:
            fail("active sandbox lookup", active)
        db.close()
    finally:
        tmp.cleanup()

    print("\n── 5. Permissions and i18n proof ──")
    route_source = read("app/routes/projects.py")
    contains_all(
        "Sandbox routes require login and can_edit_project for creation",
        route_source,
        [
            "require_auth(current_user)",
            "can_edit_project(current_user, project)",
            "not_authorized",
            "template_not_found",
            "json.dumps(payload[\"elements\"] if payload else [])",
        ],
    )
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    sandbox_keys = {
        "sandbox.title",
        "sandbox.back_to_project",
        "sandbox.subtitle",
        "sandbox.estimate",
        "sandbox.days",
        "sandbox.nodes",
        "sandbox.warnings",
        "sandbox.error_not_authorized",
        "sandbox.error_template_not_found",
        "sandbox.error_generic",
        "sandbox.start_title",
        "sandbox.start_copy",
        "sandbox.start_blank",
        "sandbox.viewer_picker_hint",
        "sandbox.start_from_template",
        "sandbox.read_only_build",
        "sandbox.hard_errors",
        "sandbox.empty_canvas",
        "sandbox.details_title",
        "sandbox.day_range",
    }
    if set(en) == set(zh) and sandbox_keys.issubset(en):
        ok("English/Chinese i18n parity includes Build 03 sandbox keys")
    else:
        fail("i18n parity", {"missing_en": sorted(sandbox_keys - set(en)), "missing_zh": sorted(sandbox_keys - set(zh)), "parity": set(en) == set(zh)})

    print("\n── Summary ──")
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        print("\nFailures:")
        for name, reason in FAIL:
            print(f" - {name}: {reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
