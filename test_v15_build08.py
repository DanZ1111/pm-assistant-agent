"""v1.5 Build 08 — Design status in Timeline/Pulse.

Run: python3 test_v15_build08.py
"""
import json
import os
import sys
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = Path(__file__).resolve().parent
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


def build_db():
    tmp = tempfile.TemporaryDirectory()
    engine = create_engine(
        f"sqlite:///{Path(tmp.name) / 'v15_build08.db'}",
        connect_args={"check_same_thread": False},
    )
    import app.models  # noqa: F401
    from app.database import Base
    from app import migrations

    Base.metadata.create_all(bind=engine)
    migrations.run_pending(engine)
    Session = sessionmaker(bind=engine)
    return tmp, engine, Session


def create_user(db, username, role, display_name=None):
    from app.models import User

    user = User(
        username=username,
        display_name=display_name or username.title(),
        hashed_password="not-used",
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def create_session(db, user, token):
    from app.models import UserSession

    db.add(UserSession(
        token=token,
        user_id=user.id,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=2),
    ))


def create_project(db, name, pm_username):
    from app.models import Project, ProjectPhase

    project = Project(name=name, product_manager=pm_username, status="active")
    db.add(project)
    db.flush()
    db.add(ProjectPhase(
        project_id=project.id,
        phase_name="Design",
        phase_type="design",
        phase_order=1,
        status="in_progress",
        actual_start_date=date(2026, 1, 1),
    ))
    db.flush()
    return project


def setup_fixture():
    from app.database import Base, SessionLocal, engine
    from app import migrations
    import app.crud as crud

    Base.metadata.create_all(bind=engine)
    migrations.run_pending(engine)

    db = SessionLocal()
    try:
        admin = create_user(db, f"v15_b08_admin_{RUN_TAG}", "admin")
        designer = create_user(db, f"v15_b08_designer_{RUN_TAG}", "designer", "Designer A")
        create_session(db, admin, f"v15-b08-admin-{RUN_TAG}")
        create_session(db, designer, f"v15-b08-designer-{RUN_TAG}")
        db.commit()

        project = create_project(db, f"Design Status Project {RUN_TAG}", admin.username)
        db.commit()
        quest = crud.create_design_quest_draft(
            db,
            project.id,
            admin.id,
            title="Timeline status quest",
            brief="Submit status-driven design work.",
            visibility="all_active_designers",
            soft_deadline=date(2026, 11, 1),
            is_timeline_blocking=True,
        )
        crud.publish_design_quest(db, quest.id, admin.id)

        return {
            "project_id": project.id,
            "quest_id": quest.id,
            "user_ids": [admin.id, designer.id],
            "admin_token": f"v15-b08-admin-{RUN_TAG}",
            "designer_token": f"v15-b08-designer-{RUN_TAG}",
        }
    finally:
        db.close()


def cleanup_fixture(fx):
    from app.database import SessionLocal
    from app.models import DesignSubmissionVersion, Project, ProjectFile, User, UserSession
    import app.crud as crud

    db = SessionLocal()
    filenames = []
    try:
        versions = (
            db.query(DesignSubmissionVersion)
            .filter(DesignSubmissionVersion.project_id == fx.get("project_id"))
            .all()
        )
        files = (
            db.query(ProjectFile)
            .filter(ProjectFile.project_id == fx.get("project_id"))
            .all()
        )
        filenames = [version.filename for version in versions] + [file.filename for file in files]
        if fx.get("user_ids"):
            db.query(UserSession).filter(UserSession.user_id.in_(fx["user_ids"])).delete(synchronize_session=False)
        project = db.query(Project).filter(Project.id == fx.get("project_id")).first()
        if project:
            db.delete(project)
        for user_id in fx.get("user_ids", []):
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                db.delete(user)
        db.commit()
    finally:
        db.close()
    for filename in set(filenames):
        disk_path = os.path.join(crud.UPLOAD_DIR, filename)
        if os.path.exists(disk_path):
            os.remove(disk_path)


def client_with_token(app, token):
    client = TestClient(app)
    client.cookies.set("pm_session", token)
    return client


def upload(client, quest_id, filename, content, revision_request_id=None):
    data = {"title": "Status Direction", "designer_note": "status note"}
    if revision_request_id:
        data["revision_request_id"] = str(revision_request_id)
    return client.post(
        f"/designer/quests/{quest_id}/submissions/upload",
        data=data,
        files={"file": (filename, content, "image/png")},
        follow_redirects=False,
    )


def get_state(project_id):
    from app.database import SessionLocal
    from app.models import DesignQuest, DesignQuestEvent, DesignSubmission, ProjectChange, ProjectPhase

    db = SessionLocal()
    try:
        quest = db.query(DesignQuest).filter(DesignQuest.project_id == project_id).first()
        submissions = db.query(DesignSubmission).filter(DesignSubmission.project_id == project_id).all()
        for submission in submissions:
            list(submission.versions)
            list(submission.revision_requests)
            for revision in submission.revision_requests:
                list(revision.items)
        phases = db.query(ProjectPhase).filter(ProjectPhase.project_id == project_id).all()
        events = db.query(DesignQuestEvent).filter(DesignQuestEvent.project_id == project_id).all()
        changes = db.query(ProjectChange).filter(ProjectChange.project_id == project_id).all()
        return quest, submissions, phases, events, changes
    finally:
        db.close()


def design_status(project_id):
    from app.database import SessionLocal
    import app.crud as crud

    db = SessionLocal()
    try:
        return crud.get_project_design_status(db, project_id)
    finally:
        db.close()


def main():
    print("\n── 1. Source locks ──")
    plan = read("V15_BUILD08_DESIGN_STATUS_TIMELINE_PULSE_PLAN.md")
    models = read("app/models.py")
    migrations_py = read("app/migrations.py")
    crud_py = read("app/crud.py")
    routes = read("app/routes/projects.py")
    template = read("app/templates/project_detail.html")
    ai_tools = read("app/ai/tools.py")

    contains_all(
        "Build 08 plan locks display and explicit completion scope",
        plan,
        [
            "Design Status In Timeline/Pulse",
            "no automatic phase completion",
            "no direct mutation of `project_phases`",
            "no AI write handlers",
        ],
    )
    contains_all(
        "Design status metadata, service, route, and UI markers are present",
        models + migrations_py + crud_py + routes + template,
        [
            "015_v1_5_design_status_timeline_pulse",
            "design_completed_at",
            "get_project_design_status",
            "mark_design_quest_complete",
            "mark-complete",
            "data-design-pulse-status",
            "data-design-timeline-status",
        ],
    )
    if "project_phases" not in crud_py[crud_py.find("def mark_design_quest_complete"):crud_py.find("def create_or_append_design_submission_version")]:
        ok("Mark complete service does not mutate project phases")
    else:
        fail("phase mutation scope", "project_phases marker found inside mark complete service")
    if "design_completed" not in ai_tools and "mark_design_quest_complete" not in ai_tools:
        ok("Build 08 adds no AI design-complete handler")
    else:
        fail("AI scope leak", "design-complete AI marker found")

    print("\n── 2. Fresh DB schema proof ──")
    tmp, engine, _Session = build_db()
    try:
        insp = inspect(engine)
        quest_cols = {col["name"] for col in insp.get_columns("design_quests")}
        required = {"design_completed_at", "design_completed_by_user_id"}
        if required.issubset(quest_cols):
            ok("Design completion columns exist")
        else:
            fail("completion schema", sorted(required - quest_cols))
        index_names = {idx["name"] for idx in insp.get_indexes("design_quests")}
        if "ix_design_quests_completed_at" in index_names:
            ok("Design completion index exists")
        else:
            fail("completion index", sorted(index_names))
    finally:
        tmp.cleanup()

    print("\n── 3. Design status and completion workflow ──")
    from app.main import app

    fx = setup_fixture()
    try:
        admin = client_with_token(app, fx["admin_token"])
        designer = client_with_token(app, fx["designer_token"])

        if design_status(fx["project_id"])["key"] == "waiting_for_submissions":
            ok("Design status derives waiting for submissions")
        else:
            fail("waiting status", design_status(fx["project_id"]))

        before_final = admin.post(
            f"/projects/{fx['project_id']}/design-quest/{fx['quest_id']}/mark-complete",
            follow_redirects=False,
        )
        quest, submissions, phases, events, changes = get_state(fx["project_id"])
        if before_final.status_code in (302, 303) and quest.design_completed_at is None:
            ok("Mark Design Complete is rejected before final selection")
        else:
            fail("pre-final completion", {"status": before_final.status_code, "completed": bool(quest.design_completed_at)})

        first_upload = upload(designer, fx["quest_id"], "status-initial.png", b"initial")
        if first_upload.status_code in (302, 303) and design_status(fx["project_id"])["key"] == "pm_review_needed":
            ok("Design status derives PM review needed after submission")
        else:
            fail("review status", {"upload": first_upload.status_code, "status": design_status(fx["project_id"])})

        quest, submissions, phases, events, changes = get_state(fx["project_id"])
        submission = submissions[0]
        revision = admin.post(
            f"/projects/{fx['project_id']}/design-quests/{fx['quest_id']}/submissions/{submission.id}/request-revision",
            data={"general_comment": "Show alternate handle.", "checklist_text": "Alternate handle"},
            follow_redirects=False,
        )
        if revision.status_code in (302, 303) and design_status(fx["project_id"])["key"] == "revision_requested":
            ok("Design status derives revision requested")
        else:
            fail("revision status", {"status": revision.status_code, "design": design_status(fx["project_id"])})

        quest, submissions, phases, events, changes = get_state(fx["project_id"])
        revision_request = submissions[0].revision_requests[0]
        revised = upload(designer, fx["quest_id"], "status-revised.png", b"revised", revision_request_id=revision_request.id)
        quest, submissions, phases, events, changes = get_state(fx["project_id"])
        submission = submissions[0]
        selected_version = submission.versions[-1]
        selected = admin.post(
            f"/projects/{fx['project_id']}/design-quests/{fx['quest_id']}/submissions/{submission.id}/versions/{selected_version.id}/select-final",
            follow_redirects=False,
        )
        if revised.status_code in (302, 303) and selected.status_code in (302, 303) and design_status(fx["project_id"])["key"] == "final_selected":
            ok("Design status derives final selected after promotion")
        else:
            fail("final selected status", {"revised": revised.status_code, "selected": selected.status_code, "design": design_status(fx["project_id"])})

        designer_forbidden = designer.post(
            f"/projects/{fx['project_id']}/design-quest/{fx['quest_id']}/mark-complete",
            follow_redirects=False,
        )
        if designer_forbidden.status_code in (302, 303, 403) and design_status(fx["project_id"])["key"] == "final_selected":
            ok("Regular designer cannot mark design complete")
        else:
            fail("designer completion forbidden", {"status": designer_forbidden.status_code, "design": design_status(fx["project_id"])})

        before_phase_snapshot = [(phase.id, phase.status, phase.actual_end_date) for phase in phases]
        complete = admin.post(
            f"/projects/{fx['project_id']}/design-quest/{fx['quest_id']}/mark-complete",
            follow_redirects=False,
        )
        quest, submissions, phases, events, changes = get_state(fx["project_id"])
        after_phase_snapshot = [(phase.id, phase.status, phase.actual_end_date) for phase in phases]
        event_types = {event.event_type for event in events}
        change_sources = {change.source_type for change in changes}
        if (
            complete.status_code in (302, 303)
            and quest.design_completed_at is not None
            and design_status(fx["project_id"])["key"] == "design_complete"
            and before_phase_snapshot == after_phase_snapshot
            and "design_completed" in event_types
            and "design_quest" in change_sources
        ):
            ok("PM marks design complete with audit and no phase mutation")
        else:
            fail("mark complete", {
                "status": complete.status_code,
                "completed": bool(quest.design_completed_at),
                "design": design_status(fx["project_id"]),
                "phase_before": before_phase_snapshot,
                "phase_after": after_phase_snapshot,
                "events": sorted(event_types),
                "change_sources": sorted(change_sources),
            })

        pm_detail = admin.get(f"/projects/{fx['project_id']}")
        if (
            pm_detail.status_code == 200
            and 'data-design-pulse-status="design_complete"' in pm_detail.text
            and 'data-design-timeline-status="design_complete"' in pm_detail.text
            and "Design complete" in pm_detail.text
            and "Timeline blocking" in pm_detail.text
        ):
            ok("Project Pulse and Timeline render design status")
        else:
            fail("design status UI", {"status": pm_detail.status_code, "pulse": "data-design-pulse-status" in pm_detail.text})
    finally:
        cleanup_fixture(fx)

    print("\n── 4. i18n parity ──")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    required = [
        "design_quest.mark_complete_button",
        "design_quest.status_design_complete",
        "pulse.design_status",
        "timeline.design_status_title",
    ]
    missing = [key for key in required if key not in en or key not in zh]
    if set(en) == set(zh) and not missing and len(en) == 906:
        ok("i18n parity locked at 906/906 with Build 08 keys")
    else:
        fail("i18n parity/count", {"en": len(en), "zh": len(zh), "missing": missing, "diff": sorted(set(en) ^ set(zh))[:8]})

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
