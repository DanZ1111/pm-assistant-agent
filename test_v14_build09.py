"""v1.4 Build 09 — v1.4.0 release-hardening proof.

This test is intentionally scenario-shaped: it exercises every seeded system
Planning Sandbox template through the PM workflow contract instead of only
checking source strings.

Run: python3 test_v14_build09.py
"""
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = Path(__file__).resolve().parent
PASS, FAIL = [], []

SYSTEM_TEMPLATE_KEYS = [
    "simple_oem_knife",
    "standard_folding_knife",
    "new_mechanism_knife",
    "gift_set_combo_pack",
    "packaging_heavy_retail",
    "amazon_launch_product",
]


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
    engine = create_engine(f"sqlite:///{Path(tmp.name) / 'v14_build09.db'}")
    import app.models  # noqa: F401
    from app.database import Base
    from app import migrations

    Base.metadata.create_all(bind=engine)
    migrations.run_pending(engine)
    Session = sessionmaker(bind=engine)
    return tmp, engine, Session


def count_rows(db, table):
    return db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()


def create_user(db, username="release_pm", role="pm"):
    from app.models import User

    user = User(
        username=username,
        display_name=username,
        hashed_password="test",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_project(db, name, pm_name):
    from app.models import Project

    project = Project(name=name, status="active", product_manager=pm_name)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def main():
    print("\n── 1. Runtime version and release docs ──")
    from app.version import CURRENT_BUILD_NAME, CURRENT_VERSION, LAST_UPDATED

    if CURRENT_VERSION == "1.4.0":
        ok("Runtime CURRENT_VERSION is v1.4.0")
    else:
        fail("CURRENT_VERSION", CURRENT_VERSION)
    if CURRENT_BUILD_NAME and "Planning Sandbox Release" in CURRENT_BUILD_NAME:
        ok("Runtime build name identifies the Planning Sandbox release")
    else:
        fail("CURRENT_BUILD_NAME", CURRENT_BUILD_NAME)
    if LAST_UPDATED == "2026-06-10":
        ok("Runtime LAST_UPDATED is the v1.4.0 release date")
    else:
        fail("LAST_UPDATED", LAST_UPDATED)

    version_md = read("VERSION.md")
    changelog = read("CHANGELOG.md")
    user_guide = read("USER_GUIDE.md")
    masterplan = read("MASTERPLAN.md")
    contains_all(
        "VERSION.md documents v1.4.0 and preserves earlier releases",
        version_md,
        [
            "**Current Version:** v1.4.0",
            "v1.4.0 released",
            "## What's new in v1.4.0",
            "## What's new in v1.3.0",
            "## What's new in v1.2.1",
        ],
    )
    contains_all(
        "CHANGELOG.md has v1.4.0 rollup",
        changelog,
        [
            "## v1.4.0 — Planning Sandbox Release",
            "scenario contract runner",
            "Apply",
            "Save Workflow as Template",
        ],
    )
    contains_all(
        "USER_GUIDE.md explains the Planning Sandbox workflow",
        user_guide,
        [
            "## What's new in v1.4.0",
            "Planning Sandbox",
            "Apply to Timeline",
            "sandbox edits do **not** change live project phases",
        ],
    )
    contains_all(
        "MASTERPLAN.md marks v1.4.0 shipped",
        masterplan,
        [
            "### v1.4.0 — Planning Sandbox Release ✓ SHIPPED v1.4.0",
            "test_v14_build09.py",
            "No new migration in release hardening",
        ],
    )

    print("\n── 2. Registry, test inventory, and i18n ──")
    registry = read("AI_TOOLS_REGISTRY.md")
    ai_tools = read("app/ai/tools.py")
    contains_all(
        "AI registry documents the v1.4 sandbox tool surface",
        registry,
        [
            "list_timeline_templates",
            "apply_timeline_template",
            "apply_sandbox_to_project",
            "save_sandbox_as_template",
            "explain_sandbox_estimate",
            "propose_sandbox_edits",
        ],
    )
    if all(tool not in ai_tools for tool in [
        "list_timeline_templates",
        "apply_timeline_template",
        "apply_sandbox_to_project",
        "save_sandbox_as_template",
        "explain_sandbox_estimate",
        "propose_sandbox_edits",
    ]):
        ok("Sandbox AI tools are documented but not silently wired")
    else:
        fail("AI tool handler lock", "sandbox AI tool name appears in app/ai/tools.py")

    missing_tests = [
        f"test_v14_build{idx:02d}.py"
        for idx in range(1, 10)
        if not (ROOT / f"test_v14_build{idx:02d}.py").exists()
    ]
    if not missing_tests:
        ok("All v1.4 regression files exist (01-09)")
    else:
        fail("v1.4 regression inventory", missing_tests)

    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    if set(en) == set(zh) and len(en) >= 805:
        ok(f"i18n parity preserved with v1.4 keys present ({len(en)}/{len(zh)})")
    else:
        fail("i18n parity", f"en={len(en)} zh={len(zh)} diff={sorted(set(en) ^ set(zh))[:8]}")

    print("\n── 3. Migration and seed invariants ──")
    migrations = read("app/migrations.py")
    contains_all(
        "v1.4 migration markers exist and release hardening adds no v1.4-09 migration",
        migrations,
        [
            "007_v1_4_create_planning_sandbox_core",
            "009_v1_4_create_planning_apply_events",
            "010_v1_4_create_planning_templates",
        ],
    )
    if "011_v1_4" not in migrations and "v1_4_09" not in migrations:
        ok("No release-hardening migration was added")
    else:
        fail("release migration lock", "unexpected v1.4 release migration marker")

    print("\n── 4. PM scenario contract runner ──")
    import app.crud as crud
    from app.models import PlanningApplyEvent, PlanningTemplate, ProjectPhase

    tmp, engine, Session = build_db()
    try:
        db = Session()
        module_count = count_rows(db, "planning_module_library")
        system_template_rows = (
            db.query(PlanningTemplate)
            .filter(PlanningTemplate.is_system.is_(True), PlanningTemplate.is_active.is_(True))
            .order_by(PlanningTemplate.sort_order)
            .all()
        )
        system_keys = [template.template_key for template in system_template_rows]
        if module_count >= 24 and system_keys == SYSTEM_TEMPLATE_KEYS:
            ok("Seed invariants: 24+ modules and the six system templates in order")
        else:
            fail("seed invariants", {"module_count": module_count, "system_keys": system_keys})

        user = create_user(db)
        scenario_ok = True
        scenario_details = []
        for idx, template_key in enumerate(SYSTEM_TEMPLATE_KEYS, 1):
            project = create_project(db, f"v14_b09_{template_key}", user.username)
            sandbox = crud.create_sandbox_from_template(db, project.id, template_key, user.id, user.role)
            schedule_before = crud.compute_sandbox_schedule(db, sandbox.id, require_nodes=True)
            if schedule_before.get("hard_errors"):
                scenario_ok = False
                scenario_details.append((template_key, "hard_errors_before", schedule_before["hard_errors"]))
                continue
            first_node = sorted(sandbox.nodes, key=lambda node: (node.sort_order, node.id))[0]
            edited_title = f"{first_node.title} Release Check"
            crud.update_sandbox_node(db, project.id, sandbox.id, first_node.id, {
                "title": edited_title,
                "duration_days": str(first_node.duration_days + 1),
                "owner_role": first_node.owner_role or "pm",
                "deliverable": first_node.deliverable or "Release proof deliverable",
                "exit_criteria": first_node.exit_criteria or "Release proof exit",
            })
            crud.update_sandbox_node_position(db, project.id, sandbox.id, first_node.id, 42 + idx, 84 + idx)
            saved_template = crud.save_sandbox_as_template(
                db,
                project.id,
                sandbox.id,
                f"v14_b09 {template_key} reusable",
                "Release proof saved template",
                user.id,
            )
            phase_count_before_apply = (
                db.query(ProjectPhase)
                .filter(ProjectPhase.project_id == project.id)
                .count()
            )
            schedule_after_edit = crud.compute_sandbox_schedule(db, sandbox.id, require_nodes=True)
            event = crud.apply_sandbox_to_project(
                db,
                project.id,
                sandbox.id,
                date(2026, 6, 10),
                update_launch_date=False,
                user_id=user.id,
            )
            phases = (
                db.query(ProjectPhase)
                .filter(ProjectPhase.project_id == project.id)
                .order_by(ProjectPhase.phase_order)
                .all()
            )
            apply_events = (
                db.query(PlanningApplyEvent)
                .filter(PlanningApplyEvent.project_id == project.id)
                .all()
            )
            timeline = crud.get_timeline_events(db, project.id)
            plan_applied = any(
                item.get("source_table") == "planning_apply_events"
                and item.get("subtype") == "plan_applied"
                for item in timeline["events"]
            )
            expected_nodes = len(schedule_after_edit.get("nodes") or [])
            checks = {
                "saved_template": bool(saved_template and not saved_template.is_system),
                "no_phases_before_apply": phase_count_before_apply == 0,
                "phase_count_matches_schedule": len(phases) == expected_nodes,
                "first_phase_edited": bool(phases and phases[0].phase_name == edited_title),
                "apply_event": event in apply_events and len(apply_events) == 1,
                "history": plan_applied,
            }
            if not all(checks.values()):
                scenario_ok = False
                scenario_details.append((template_key, checks))

        if scenario_ok:
            ok("Scenario contract passes for all six system templates")
        else:
            fail("scenario contract", scenario_details)
    finally:
        tmp.cleanup()

    print(f"\nPassed: {len(PASS)} / {len(PASS) + len(FAIL)}")
    if FAIL:
        print("\nFailures:")
        for name, reason in FAIL:
            print(f"- {name}: {reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
