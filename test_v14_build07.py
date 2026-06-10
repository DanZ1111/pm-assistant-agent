"""v1.4 Build 07 — Planning Sandbox Apply to live timeline.

Requires the app running at http://localhost:8000 for route/browser smoke.
Run: python3 test_v14_build07.py
"""
import json
import os
import sqlite3
import sys
import tempfile
from datetime import date
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
    engine = create_engine(f"sqlite:///{Path(tmp.name) / 'v14_build07.db'}")
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


def add_phase(db, project_id, name, status="not_started", actual_start=None, actual_end=None):
    from app.models import ProjectPhase

    order = db.query(ProjectPhase).filter(ProjectPhase.project_id == project_id).count() + 1
    phase = ProjectPhase(
        project_id=project_id,
        phase_name=name,
        phase_order=order,
        status=status,
        actual_start_date=actual_start,
        actual_end_date=actual_end,
    )
    db.add(phase)
    db.commit()
    db.refresh(phase)
    return phase


def make_valid_sandbox(db, project_id):
    import app.crud as crud

    sandbox = crud.create_sandbox_blank(db, project_id)
    modules = crud.list_planning_modules(db)
    first = crud.create_sandbox_node_from_module(db, project_id, sandbox.id, modules[0].module_key, 80, 80)
    second = crud.create_sandbox_node_from_module(db, project_id, sandbox.id, modules[1].module_key, 260, 220)
    crud.update_sandbox_node(db, project_id, sandbox.id, first.id, {
        "title": "Concept",
        "duration_days": "3",
        "owner_role": "pm",
        "deliverable": "Brief approved",
        "exit_criteria": "PM signoff",
    })
    crud.update_sandbox_node(db, project_id, sandbox.id, second.id, {
        "title": "Sample",
        "duration_days": "5",
        "owner_role": "factory",
        "deliverable": "",
        "exit_criteria": "Sample received",
    })
    crud.create_sandbox_edge(db, project_id, sandbox.id, first.id, second.id)
    return sandbox, first, second


def live_login():
    s = requests.Session()
    r = s.post(
        f"{BASE}/auth/login",
        data={"username": ADMIN, "password": ADMIN_PWD},
        allow_redirects=False,
        timeout=8,
    )
    return s if r.status_code in (302, 303) else None


def cleanup_live(prefix="v14_b07"):
    from app.database import SessionLocal
    from app.models import Project

    db = SessionLocal()
    try:
        for project in db.query(Project).filter(Project.name.like(prefix + "%")).all():
            db.delete(project)
        db.commit()
    finally:
        db.close()


def live_fixture(blocked=False):
    from app.database import SessionLocal

    cleanup_live()
    db = SessionLocal()
    try:
        project = create_project(db, "v14_b07_live_project")
        if blocked:
            add_phase(db, project.id, "Already started", status="in_progress", actual_start=date(2026, 6, 1))
        sandbox, _, _ = make_valid_sandbox(db, project.id)
        return project.id, sandbox.id
    finally:
        db.close()


def count_live_phases(project_id):
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
    plan = read("V14_BUILD07_EXECUTION_PLAN.md")
    models = read("app/models.py")
    migrations = read("app/migrations.py")
    crud_source = read("app/crud.py")
    routes = read("app/routes/projects.py")
    template = read("app/templates/planning_sandbox.html")
    history_template = read("app/templates/project_detail.html")
    ai_tools = read("app/ai/tools.py")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))

    contains_all(
        "Build 07 plan locks Apply safety",
        plan,
        [
            "`delayed` phases now block Apply",
            "No active execution overwrite",
            "Delete predicate is explicit",
            "No phase plan change rows",
            "No AI tool can call Apply",
            "Build 07 should add these keys",
        ],
    )
    contains_all(
        "Build 07 model/migration markers exist",
        models + migrations,
        [
            "class PlanningApplyEvent",
            "__tablename__ = \"planning_apply_events\"",
            "009_v1_4_create_planning_apply_events",
            "snapshot_json JSON NOT NULL",
        ],
    )
    contains_all(
        "Build 07 service/route/template markers exist",
        crud_source + routes + template,
        [
            "def validate_sandbox_for_apply",
            "def get_sandbox_apply_preview",
            "def apply_sandbox_to_project",
            "/projects/{project_id}/sandbox/{sandbox_id}/apply",
            "data-apply-preview",
            "sandbox.apply_confirm_title",
        ],
    )
    if "apply_sandbox_to_project" not in ai_tools:
        ok("No AI Apply tool or handler is registered")
    else:
        fail("AI Apply registry lock", "apply_sandbox_to_project appears in app/ai/tools.py")
    if "history.plan_applied" in history_template and "planning_apply_events" in crud_source:
        ok("Timeline History includes plan-applied event mapping")
    else:
        fail("Timeline History apply event", "missing history marker")
    build07_keys = {
        "sandbox.apply",
        "sandbox.apply_confirm_title",
        "sandbox.apply_confirm_body",
        "sandbox.apply_node_count",
        "sandbox.apply_total_days",
        "sandbox.apply_start_date",
        "sandbox.apply_end_date",
        "sandbox.apply_update_launch",
        "sandbox.apply_replaces",
        "sandbox.apply_no_existing_phases",
        "sandbox.apply_blocked",
        "sandbox.apply_invalid_graph",
        "sandbox.apply_active_execution",
        "sandbox.apply_success",
        "sandbox.apply_error",
        "history.plan_applied",
    }
    if set(en) == set(zh) and build07_keys.issubset(en):
        ok(f"i18n parity preserved with Build 07 keys present ({len(en)}/{len(zh)})")
    else:
        fail("i18n parity/count", f"en={len(en)} zh={len(zh)} diff={sorted(set(en) ^ set(zh))[:8]}")

    print("\n── 2. Apply transaction with temp DB ──")
    import app.crud as crud
    from app.models import PlanningApplyEvent, ProjectChange, ProjectPhase, PhasePlanChange, ProjectBlocker

    tmp, engine, Session = build_db()
    try:
        db = Session()
        project = create_project(db, "v14_b07_service_project")
        add_phase(db, project.id, "Old Design", status="not_started")
        add_phase(db, project.id, "Old Skipped", status="skipped")
        sandbox, _, _ = make_valid_sandbox(db, project.id)
        preview = crud.get_sandbox_apply_preview(db, project.id, sandbox.id, date(2026, 6, 10))
        if preview["ok"] and preview["node_count"] == 2 and preview["total_days"] == 8 and preview["replaceable_phase_count"] == 2:
            ok("Apply preview reports node count, total days, and replaceable phases")
        else:
            fail("Apply preview", preview)
        event = crud.apply_sandbox_to_project(db, project.id, sandbox.id, date(2026, 6, 10), True, user_id=None)
        phases = db.query(ProjectPhase).filter(ProjectPhase.project_id == project.id).order_by(ProjectPhase.phase_order).all()
        changes = db.query(ProjectChange).filter(ProjectChange.project_id == project.id).all()
        plan_changes = db.query(PhasePlanChange).all()
        db.refresh(project)
        db.refresh(sandbox)
        if (
            len(phases) == 2
            and phases[0].phase_name == "Concept"
            and phases[0].planned_start_date == date(2026, 6, 10)
            and phases[0].planned_end_date == date(2026, 6, 13)
            and phases[1].planned_start_date == date(2026, 6, 13)
            and phases[1].planned_end_date == date(2026, 6, 18)
            and phases[1].notes == "Sample received"
        ):
            ok("Apply creates phases with computed dates and clean notes")
        else:
            fail("Applied phase rows", [(p.phase_name, p.planned_start_date, p.planned_end_date, p.notes) for p in phases])
        if (
            isinstance(event, PlanningApplyEvent)
            and event.node_count == 2
            and event.total_days == 8
            and event.phases_deleted == 2
            and event.phases_created == 2
            and event.phases_updated == 0
            and event.updated_project_planned_launch_date is True
            and project.planned_launch_date == date(2026, 6, 18)
            and sandbox.status == "applied"
        ):
            ok("Apply writes audit event, launch toggle, and applied snapshot state")
        else:
            fail("Apply event/sandbox state", getattr(event, "__dict__", event))
        if any(c.change_type == "plan_applied" and c.source_type == "planning_sandbox" for c in changes):
            ok("Apply writes project change log row")
        else:
            fail("project change log", [(c.change_type, c.source_type) for c in changes])
        if len(plan_changes) == 0:
            ok("Apply creates no phase_plan_changes rows")
        else:
            fail("phase_plan_changes", len(plan_changes))
        timeline = crud.get_timeline_events(db, project.id)
        if any(e["source_table"] == "planning_apply_events" and e["subtype"] == "plan_applied" for e in timeline["events"]):
            ok("Timeline History derives plan-applied event")
        else:
            fail("timeline apply event", timeline["events"])

        # Launch-date off path.
        project2 = create_project(db, "v14_b07_no_launch_update")
        project2.planned_launch_date = date(2026, 12, 31)
        add_phase(db, project2.id, "Old", status="not_started")
        sandbox2, _, _ = make_valid_sandbox(db, project2.id)
        crud.apply_sandbox_to_project(db, project2.id, sandbox2.id, date(2026, 7, 1), False)
        db.refresh(project2)
        if project2.planned_launch_date == date(2026, 12, 31):
            ok("Apply leaves launch date unchanged when checkbox is off")
        else:
            fail("launch unchanged", project2.planned_launch_date)

        # Separate precondition checks.
        checks = [
            ("actual start blocks Apply", {"actual_start": date(2026, 6, 1)}, "phase_has_actual_start"),
            ("actual end blocks Apply", {"actual_end": date(2026, 6, 2)}, "phase_has_actual_end"),
            ("in progress status blocks Apply", {"status": "in_progress"}, "phase_active_status"),
            ("done status blocks Apply", {"status": "done"}, "phase_active_status"),
            ("delayed status blocks Apply", {"status": "delayed"}, "phase_active_status"),
        ]
        for label, kwargs, code in checks:
            blocked_project = create_project(db, "v14_b07_" + label.replace(" ", "_"))
            add_phase(db, blocked_project.id, "Blocked phase", **kwargs)
            blocked_sandbox, _, _ = make_valid_sandbox(db, blocked_project.id)
            result = crud.validate_sandbox_for_apply(db, blocked_project.id, blocked_sandbox.id)
            if not result["ok"] and any(item["code"] == code for item in result["preconditions"]):
                ok(label)
            else:
                fail(label, result)

        blocker_project = create_project(db, "v14_b07_blocker")
        phase = add_phase(db, blocker_project.id, "Blocked by issue", status="not_started")
        db.add(ProjectBlocker(project_id=blocker_project.id, phase_id=phase.id, title="Factory issue", status="active"))
        db.commit()
        blocker_sandbox, _, _ = make_valid_sandbox(db, blocker_project.id)
        blocker_result = crud.validate_sandbox_for_apply(db, blocker_project.id, blocker_sandbox.id)
        if not blocker_result["ok"] and any(item["code"] == "active_blocker_attached" for item in blocker_result["preconditions"]):
            ok("Active phase-linked blocker blocks Apply")
        else:
            fail("blocker precondition", blocker_result)

        empty_project = create_project(db, "v14_b07_empty")
        empty_sandbox = crud.create_sandbox_blank(db, empty_project.id)
        try:
            crud.apply_sandbox_to_project(db, empty_project.id, empty_sandbox.id, date(2026, 6, 10))
            fail("zero-node apply guard", "expected ValueError")
        except ValueError as exc:
            if str(exc) == "zero_nodes":
                ok("Zero-node sandbox cannot apply")
            else:
                fail("zero-node apply guard", str(exc))
    finally:
        tmp.cleanup()

    print("\n── 3. Live route + browser smoke ──")
    session = live_login()
    if not session:
        fail("Live login", "could not log in as admin")
    else:
        project_id, sandbox_id = live_fixture(blocked=False)
        before_count = count_live_phases(project_id)
        r = session.post(
            f"{BASE}/projects/{project_id}/sandbox/{sandbox_id}/apply",
            data={"apply_start_date": "2026-06-10", "update_launch_date": "1"},
            allow_redirects=False,
            timeout=10,
        )
        after_count = count_live_phases(project_id)
        if r.status_code in (302, 303) and "applied=1" in r.headers.get("location", "") and before_count == 0 and after_count == 2:
            ok("Apply route creates live phases only after explicit POST")
        else:
            fail("Apply route", {"status": r.status_code, "location": r.headers.get("location"), "before": before_count, "after": after_count})

        blocked_project_id, blocked_sandbox_id = live_fixture(blocked=True)
        blocked = session.post(
            f"{BASE}/projects/{blocked_project_id}/sandbox/{blocked_sandbox_id}/apply",
            data={"apply_start_date": "2026-06-10"},
            allow_redirects=False,
            timeout=10,
        )
        if blocked.status_code in (302, 303) and "apply_error=preconditions_failed" in blocked.headers.get("location", ""):
            ok("Apply route refuses active execution")
        else:
            fail("blocked Apply route", {"status": blocked.status_code, "location": blocked.headers.get("location")})

        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 1366, "height": 900})
            context.add_cookies([
                {"name": cookie.name, "value": cookie.value, "url": BASE}
                for cookie in session.cookies
            ])
            page = context.new_page()
            page.goto(f"{BASE}/projects/{blocked_project_id}/sandbox")
            page.wait_for_selector("[data-apply-preview]")
            blocked_text = page.locator("[data-apply-preview]").inner_text()
            if "Apply blocked" in blocked_text and "Existing timeline has active execution" in blocked_text:
                ok("Browser shows blocked Apply state")
            else:
                fail("blocked Apply browser text", blocked_text)
            page.screenshot(path=str(ARTIFACTS / "v14_build07_apply_blocked_desktop.png"), full_page=True)

            ok_project_id, _ = live_fixture(blocked=False)
            page.goto(f"{BASE}/projects/{ok_project_id}/sandbox")
            page.wait_for_selector(".sandbox-apply-summary")
            page.click(".sandbox-apply-summary")
            page.wait_for_selector(".sandbox-apply-form")
            if page.locator('input[name="update_launch_date"]').count() and page.locator("[data-apply-end-date]").inner_text():
                ok("Browser shows Apply confirmation panel")
            else:
                fail("Apply confirmation browser", "missing checkbox or computed end date")
            overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            if not overflow:
                ok("Apply panel has no desktop horizontal overflow")
            else:
                fail("desktop overflow", "document overflowed horizontally")
            page.screenshot(path=str(ARTIFACTS / "v14_build07_apply_modal_desktop.png"), full_page=True)

            page.set_viewport_size({"width": 390, "height": 860})
            page.goto(f"{BASE}/projects/{ok_project_id}/sandbox")
            page.wait_for_selector(".sandbox-apply-summary")
            page.click(".sandbox-apply-summary")
            mobile_overflow = page.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth")
            if not mobile_overflow:
                ok("Apply panel has no mobile horizontal overflow")
            else:
                fail("mobile overflow", "document overflowed horizontally")
            page.screenshot(path=str(ARTIFACTS / "v14_build07_apply_mobile.png"), full_page=True)
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
