"""v1.5 Build 02 — Design Quest data model and service layer proof.

Run: python3 test_v15_build02.py
"""
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, inspect
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
    engine = create_engine(
        f"sqlite:///{Path(tmp.name) / 'v15_build02.db'}",
        connect_args={"check_same_thread": False},
    )
    import app.models  # noqa: F401
    from app.database import Base
    from app import migrations

    Base.metadata.create_all(bind=engine)
    migrations.run_pending(engine)
    migrations.run_pending(engine)
    Session = sessionmaker(bind=engine)
    return tmp, engine, Session


def create_user(db, username, role, display_name=None):
    from app.models import User

    user = User(
        username=username,
        display_name=display_name or username.title(),
        hashed_password="not-used-in-build02",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_project(db, name, pm_username):
    from app.models import Project

    project = Project(name=name, product_manager=pm_username, status="active")
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def create_file(db, project_id, filename):
    from app.models import ProjectFile

    pf = ProjectFile(
        project_id=project_id,
        filename=filename,
        original_filename=filename,
        file_path=f"/tmp/private-test/{filename}",
        file_type="image",
        file_category="reference",
        file_size=12345,
    )
    db.add(pf)
    db.commit()
    db.refresh(pf)
    return pf


def count_events(db, quest_id, event_type=None):
    from app.models import DesignQuestEvent

    q = db.query(DesignQuestEvent).filter(DesignQuestEvent.quest_id == quest_id)
    if event_type:
        q = q.filter(DesignQuestEvent.event_type == event_type)
    return q.count()


def ids(rows):
    return {row.id for row in rows}


def main():
    print("\n── 1. Source locks and model imports ──")
    plan = read("V15_BUILD02_DESIGN_QUEST_DATA_MODEL_PLAN.md")
    prd = read("V15_DESIGNER_PORTAL_PRD.md")
    models = read("app/models.py")
    migrations_py = read("app/migrations.py")
    crud_py = read("app/crud.py")
    ai_registry = read("AI_TOOLS_REGISTRY.md")
    ai_tools = read("app/ai/tools.py")

    contains_all(
        "Build 02 plan locks data-model-only scope",
        plan + prd,
        [
            "DesignQuest",
            "DesignQuestAssignment",
            "DesignQuestReference",
            "DesignQuestEvent",
            "no PM quest creation UI",
            "no designer submission upload",
            "Designer-visible files must not use raw public `/uploads/...` links",
        ],
    )
    contains_all(
        "Models, migration, and service helpers are present",
        models + migrations_py + crud_py,
        [
            "class DesignQuest",
            "class DesignQuestAssignment",
            "class DesignQuestReference",
            "class DesignQuestEvent",
            "011_v1_5_create_design_quest_core",
            "create_design_quest_draft",
            "publish_design_quest",
            "shape_design_quest_for_designer",
        ],
    )
    if "DesignSubmission" not in models and "DesignSubmissionVersion" not in models and "design_submission" not in migrations_py:
        ok("Build 02 does not add submission/version tables")
    else:
        fail("submission scope leak", "submission model or migration marker found")

    print("\n── 2. Fresh DB schema proof ──")
    tmp, engine, Session = build_db()
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        expected = {
            "design_quests",
            "design_quest_assignments",
            "design_quest_references",
            "design_quest_events",
        }
        missing = expected - tables
        if not missing:
            ok("All 4 design quest tables exist on a fresh DB")
        else:
            fail("design quest tables", f"missing {missing}")

        index_names = set()
        for table in expected:
            index_names.update(idx["name"] for idx in insp.get_indexes(table))
        required_indexes = {
            "uq_design_quests_one_active",
            "ix_design_quests_project_status",
            "ix_design_quest_assignments_designer",
            "ix_design_quest_references_quest",
            "ix_design_quest_events_quest",
            "ix_design_quest_events_project",
        }
        if required_indexes.issubset(index_names):
            ok("Design quest indexes exist, including one-active-per-project lock")
        else:
            fail("design quest indexes", sorted(required_indexes - index_names))
    finally:
        tmp.cleanup()

    print("\n── 3. Service behavior and visibility ──")
    import app.crud as crud

    tmp, engine, Session = build_db()
    db = Session()
    try:
        admin = create_user(db, "v15_admin", "admin")
        pm = create_user(db, "v15_pm", "pm", display_name="V15 PM")
        designer = create_user(db, "v15_designer", "designer")
        other_designer = create_user(db, "v15_other_designer", "designer")
        designer_manager = create_user(db, "v15_design_manager", "designer_manager")
        viewer = create_user(db, "v15_viewer", "viewer")

        project = create_project(db, "Design Quest Project", pm.username)
        other_project = create_project(db, "Other Project", pm.username)
        reference_file = create_file(db, project.id, "safe-reference.png")
        other_file = create_file(db, other_project.id, "wrong-project.png")

        quest = crud.create_design_quest_draft(
            db,
            project.id,
            pm.id,
            title="Handle concept exploration",
            brief="Create three handle concepts around a light outdoor knife.",
            must_keep="Slim profile",
            must_avoid="Aggressive fantasy styling",
            soft_deadline=date(2026, 7, 1),
            visibility="all_active_designers",
            is_timeline_blocking=True,
        )
        if quest.status == "draft" and count_events(db, quest.id, "quest_created") == 1:
            ok("Draft quest creation writes quest and audit event")
        else:
            fail("draft quest create", {"status": quest.status, "events": count_events(db, quest.id)})

        if quest.id not in ids(crud.list_design_quests_for_designer(db, designer.id)):
            ok("Draft quest is invisible to regular designer listing")
        else:
            fail("draft visibility", "designer saw draft quest")

        try:
            crud.create_design_quest_draft(
                db,
                project.id,
                pm.id,
                title="Second active quest",
                brief="This should be blocked by the MVP one-active-quest lock.",
            )
            fail("one active quest lock", "second active quest was created")
        except ValueError as exc:
            if str(exc) == "active_design_quest_exists":
                ok("One-active-quest-per-project service guard blocks duplicates")
            else:
                fail("one active quest error", str(exc))

        published = crud.publish_design_quest(db, quest.id, pm.id)
        if published.status == "open" and published.published_at and count_events(db, quest.id, "quest_published") == 1:
            ok("Publishing draft quest opens designer visibility and audits")
        else:
            fail("publish quest", {"status": published.status, "published_at": published.published_at})

        if quest.id in ids(crud.list_design_quests_for_designer(db, designer.id)):
            ok("Open all-designers quest is visible to designer")
        else:
            fail("open all-designers visibility", "quest missing")

        ref = crud.link_design_quest_reference(db, quest.id, reference_file.id, pm.id, label="Mood reference")
        payload = crud.shape_design_quest_for_designer(published, designer)
        forbidden_payload_keys = {"project_id", "factory", "target_msrp", "target_factory_cost", "journal", "timeline", "file_path"}
        payload_text = json.dumps(payload, default=str)
        if (
            ref.id
            and payload["title"] == "Handle concept exploration"
            and payload["soft_deadline"] == "2026-07-01"
            and "safe-reference.png" in payload_text
            and "/tmp/private-test" not in payload_text
            and not (forbidden_payload_keys & set(payload.keys()))
        ):
            ok("Designer-safe payload includes brief/reference metadata but no PM-only fields or raw file path")
        else:
            fail("designer-safe payload", payload)

        try:
            crud.link_design_quest_reference(db, quest.id, other_file.id, pm.id)
            fail("same-project reference validation", "cross-project reference linked")
        except ValueError as exc:
            if str(exc) == "reference_file_not_in_quest_project":
                ok("Reference linking rejects files from another project")
            else:
                fail("same-project reference error", str(exc))

        assigned_project = create_project(db, "Assigned Quest Project", pm.username)
        assigned_quest = crud.create_design_quest_draft(
            db,
            assigned_project.id,
            admin.id,
            title="Assigned-only visual work",
            brief="Assigned designer only should see this.",
            visibility="assigned_designers_only",
        )
        crud.assign_designers_to_quest(db, assigned_quest.id, [designer.id], admin.id)
        crud.publish_design_quest(db, assigned_quest.id, admin.id)
        assigned_visible = ids(crud.list_design_quests_for_designer(db, designer.id))
        assigned_hidden = ids(crud.list_design_quests_for_designer(db, other_designer.id))
        manager_visible = ids(crud.list_design_quests_for_designer(db, designer_manager.id))
        if assigned_quest.id in assigned_visible and assigned_quest.id not in assigned_hidden and assigned_quest.id in manager_visible:
            ok("Assigned-only quest visibility is limited to assigned designer plus designer manager")
        else:
            fail("assigned-only visibility", {
                "assigned": assigned_visible,
                "other": assigned_hidden,
                "manager": manager_visible,
            })

        if crud.list_design_quests_for_designer(db, viewer.id) == []:
            ok("Non-designer user gets no designer quest listing")
        else:
            fail("viewer quest listing", "viewer saw designer quests")

        closed = crud.close_design_quest(db, quest.id, pm.id, reason="Superseded")
        if (
            closed.status == "closed"
            and closed.closed_at
            and quest.id not in ids(crud.list_design_quests_for_designer(db, designer.id))
            and count_events(db, quest.id, "quest_closed") == 1
        ):
            ok("Closing quest hides it from designer open listing and audits")
        else:
            fail("close quest", {"status": closed.status, "events": count_events(db, quest.id)})
    finally:
        db.close()
        tmp.cleanup()

    print("\n── 4. AI registry and UI non-scope ──")
    contains_all(
        "AI registry lists planned design quest tools",
        ai_registry,
        ["draft_design_quest", "publish_design_quest", "close_design_quest", "planned after v1.5 manual UI"],
    )
    if all(name not in ai_tools for name in ("draft_design_quest", "publish_design_quest", "close_design_quest")):
        ok("Build 02 does not wire AI handlers for design quest writes")
    else:
        fail("AI handler scope leak", "design quest tool found in app/ai/tools.py")

    designer_route = read("app/routes/designer.py")
    project_template = read("app/templates/project_detail.html")
    if "DesignSubmission" not in designer_route and "design submission" not in project_template.lower():
        ok("Later quest UI still has no designer submission workflow")
    else:
        fail("submission UI scope leak", "designer submission marker found in route/template")

    print("\n── 5. i18n parity unchanged ──")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    if set(en) == set(zh) and len(en) >= 817:
        ok(f"i18n parity remains exact with Build 02 baseline keys ({len(en)}/{len(zh)})")
    else:
        fail("i18n parity", {"en": len(en), "zh": len(zh), "diff": sorted(set(en) ^ set(zh))[:8]})

    return summary()


def summary():
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
