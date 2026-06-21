"""v1.5 Build 09 — Designer manager operations.

Run: python3 test_v15_build09.py
"""
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

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
        admin = create_user(db, f"v15_b09_admin_{RUN_TAG}", "admin")
        manager = create_user(db, f"v15_b09_manager_{RUN_TAG}", "designer_manager", "Design Manager")
        designer = create_user(db, f"v15_b09_designer_{RUN_TAG}", "designer", "Designer A")
        create_session(db, admin, f"v15-b09-admin-{RUN_TAG}")
        create_session(db, manager, f"v15-b09-manager-{RUN_TAG}")
        create_session(db, designer, f"v15-b09-designer-{RUN_TAG}")
        db.commit()

        project = create_project(db, f"Manager Ops Project {RUN_TAG}", admin.username)
        publish_project = create_project(db, f"Manager Publish Project {RUN_TAG}", admin.username)
        db.commit()
        quest = crud.create_design_quest_draft(
            db,
            project.id,
            admin.id,
            title="Assigned-only manager quest",
            brief="Manager should assign a designer without PM workspace access.",
            visibility="assigned_designers_only",
            soft_deadline=date(2026, 12, 1),
        )
        crud.publish_design_quest(db, quest.id, admin.id)

        return {
            "project_id": project.id,
            "publish_project_id": publish_project.id,
            "quest_id": quest.id,
            "user_ids": [admin.id, manager.id, designer.id],
            "designer_id": designer.id,
            "admin_token": f"v15-b09-admin-{RUN_TAG}",
            "manager_token": f"v15-b09-manager-{RUN_TAG}",
            "designer_token": f"v15-b09-designer-{RUN_TAG}",
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
        for project_id in (fx.get("project_id"), fx.get("publish_project_id")):
            project = db.query(Project).filter(Project.id == project_id).first()
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


def upload(client, quest_id, filename, content):
    return client.post(
        f"/designer/quests/{quest_id}/submissions/upload",
        data={"title": "Manager Ops Direction", "designer_note": "manager ops note"},
        files={"file": (filename, content, "image/png")},
        follow_redirects=False,
    )


def get_state(project_id):
    from app.database import SessionLocal
    from app.models import DesignQuestAssignment, DesignQuestEvent, DesignSubmission, ProjectPhase

    db = SessionLocal()
    try:
        assignments = db.query(DesignQuestAssignment).all()
        submissions = db.query(DesignSubmission).filter(DesignSubmission.project_id == project_id).all()
        for submission in submissions:
            list(submission.versions)
        events = db.query(DesignQuestEvent).filter(DesignQuestEvent.project_id == project_id).all()
        phases = db.query(ProjectPhase).filter(ProjectPhase.project_id == project_id).all()
        return assignments, submissions, events, phases
    finally:
        db.close()


def get_project_quest(project_id):
    from app.database import SessionLocal
    from app.models import DesignQuest

    db = SessionLocal()
    try:
        return (
            db.query(DesignQuest)
            .filter(DesignQuest.project_id == project_id)
            .order_by(DesignQuest.id.desc())
            .first()
        )
    finally:
        db.close()


def main():
    print("\n── 1. Source locks ──")
    plan = read("V15_BUILD09_DESIGNER_MANAGER_OPERATIONS_PLAN.md")
    crud_py = read("app/crud.py")
    routes = read("app/routes/designer.py")
    template = read("app/templates/designer/manager.html") + read("app/templates/designer/dashboard.html")
    ai_tools = read("app/ai/tools.py")

    contains_all(
        "Build 09 plan locks restricted manager operations and excludes admin/AI scope",
        plan + read("DM_DESIGN_QUEST_PUBLISHING_PLAN.md"),
        [
            "Designer Manager Operations",
            "unable to access `/projects/:id`",
            "no admin invite PIN/user deletion controls",
            "no AI write handlers",
            "DM can create and publish Design Quests from the manager console",
        ],
    )
    contains_all(
        "Manager services, routes, and templates are present",
        crud_py + routes + template,
        [
            "list_designer_manager_operations",
            "manager_assign_designer_to_quest",
            "manager_reopen_design_submission",
            "/designer/manager",
            "/designer/manager/quests/create",
            "allow_designer_manager=True",
            "data-designer-manager-dashboard",
            "data-manager-quest-publishing",
            "data-manager-quest-assignments",
        ],
    )
    if "manager_assign_designer_to_quest" not in ai_tools and "manager_reopen_design_submission" not in ai_tools:
        ok("Build 09 adds no AI manager operation handler")
    else:
        fail("AI scope leak", "manager operation marker found in AI tools")

    print("\n── 2. Designer manager operations ──")
    from app.main import app

    fx = setup_fixture()
    try:
        admin = client_with_token(app, fx["admin_token"])
        manager = client_with_token(app, fx["manager_token"])
        designer = client_with_token(app, fx["designer_token"])

        before_designer_detail = designer.get(f"/designer/quests/{fx['quest_id']}", follow_redirects=False)
        manager_page = manager.get("/designer/manager")
        designer_manager_page = designer.get("/designer/manager", follow_redirects=False)
        if (
            manager_page.status_code == 200
            and "Designer Manager Operations" in manager_page.text
            and "Assigned-only manager quest" in manager_page.text
            and f"Manager Publish Project {RUN_TAG}" in manager_page.text
            and f"/projects/{fx['project_id']}" not in manager_page.text
            and before_designer_detail.status_code in (302, 303)
            and designer_manager_page.status_code in (302, 303)
        ):
            ok("Manager dashboard is manager-only and exposes safe portal data")
        else:
            fail("manager dashboard", {
                "manager": manager_page.status_code,
                "designer_manager_page": designer_manager_page.status_code,
                "designer_detail_before": before_designer_detail.status_code,
                "project_link": f"/projects/{fx['project_id']}" in manager_page.text,
            })

        designer_create = designer.post(
            "/designer/manager/quests/create",
            data={
                "project_id": str(fx["publish_project_id"]),
                "title": "Designer must not create this",
                "brief": "Regular designer should be rejected.",
            },
            follow_redirects=False,
        )
        quest_after_designer = get_project_quest(fx["publish_project_id"])
        manager_create = manager.post(
            "/designer/manager/quests/create",
            data={
                "project_id": str(fx["publish_project_id"]),
                "title": "DM published visual direction",
                "brief": "Create three visual directions for manager review.",
                "must_keep": "Compact proportions",
                "must_avoid": "Fantasy styling",
                "soft_deadline": "2026-12-15",
                "visibility": "all_active_designers",
                "is_timeline_blocking": "true",
            },
            follow_redirects=False,
        )
        manager_quest = get_project_quest(fx["publish_project_id"])
        draft_page = manager.get("/designer/manager")
        manager_publish = manager.post(
            f"/designer/manager/quests/{manager_quest.id}/publish",
            follow_redirects=False,
        )
        published_quest = get_project_quest(fx["publish_project_id"])
        published_detail = designer.get(f"/designer/quests/{manager_quest.id}")
        if (
            designer_create.status_code in (302, 303)
            and quest_after_designer is None
            and manager_create.status_code in (302, 303)
            and manager_quest
            and manager_quest.status == "draft"
            and "DM published visual direction" in draft_page.text
            and manager_publish.status_code in (302, 303)
            and published_quest.status == "open"
            and published_detail.status_code == 200
        ):
            ok("Designer manager creates and publishes a quest; regular designer cannot")
        else:
            fail("manager quest publishing", {
                "designer_create": designer_create.status_code,
                "quest_after_designer": getattr(quest_after_designer, "id", None),
                "manager_create": manager_create.status_code,
                "draft_status": getattr(manager_quest, "status", None),
                "draft_visible": "DM published visual direction" in draft_page.text,
                "manager_publish": manager_publish.status_code,
                "published_status": getattr(published_quest, "status", None),
                "designer_detail": published_detail.status_code,
            })

        assign = manager.post(
            f"/designer/manager/quests/{fx['quest_id']}/assign",
            data={"designer_user_id": str(fx["designer_id"])},
            follow_redirects=False,
        )
        assignments, submissions, events, phases = get_state(fx["project_id"])
        after_designer_detail = designer.get(f"/designer/quests/{fx['quest_id']}")
        event_types = {event.event_type for event in events}
        if (
            assign.status_code in (302, 303)
            and any(a.designer_user_id == fx["designer_id"] and a.status == "assigned" for a in assignments)
            and after_designer_detail.status_code == 200
            and "manager_designer_assigned" in event_types
        ):
            ok("Manager assigns designer to assigned-only quest and designer gains access")
        else:
            fail("manager assign", {
                "status": assign.status_code,
                "assignments": [(a.designer_user_id, a.status) for a in assignments],
                "designer_detail_after": after_designer_detail.status_code,
                "events": sorted(event_types),
            })

        uploaded = upload(designer, fx["quest_id"], "manager-ops.png", b"manager-ops")
        assignments, submissions, events, phases = get_state(fx["project_id"])
        submission = submissions[0] if submissions else None
        rejected = admin.post(
            f"/projects/{fx['project_id']}/design-quests/{fx['quest_id']}/submissions/{submission.id}/reject",
            data={"reason": "Mistaken rejection"},
            follow_redirects=False,
        )
        assignments, submissions, events, phases = get_state(fx["project_id"])
        rejected_submission = submissions[0]
        before_phase_snapshot = [(phase.id, phase.status, phase.actual_end_date) for phase in phases]
        reopen = manager.post(
            f"/designer/manager/submissions/{rejected_submission.id}/reopen",
            follow_redirects=False,
        )
        assignments, submissions, events, phases = get_state(fx["project_id"])
        reopened_submission = submissions[0]
        after_phase_snapshot = [(phase.id, phase.status, phase.actual_end_date) for phase in phases]
        event_types = {event.event_type for event in events}
        if (
            uploaded.status_code in (302, 303)
            and rejected.status_code in (302, 303)
            and reopen.status_code in (302, 303)
            and reopened_submission.status == "submitted"
            and "manager_submission_reopened" in event_types
            and before_phase_snapshot == after_phase_snapshot
        ):
            ok("Manager reopens rejected submission with audit and no phase mutation")
        else:
            fail("manager reopen", {
                "uploaded": uploaded.status_code,
                "rejected": rejected.status_code,
                "reopen": reopen.status_code,
                "submission_status": reopened_submission.status if reopened_submission else None,
                "events": sorted(event_types),
                "phase_before": before_phase_snapshot,
                "phase_after": after_phase_snapshot,
            })

        project_access = manager.get(f"/projects/{fx['project_id']}", follow_redirects=False)
        if project_access.status_code in (302, 303, 403):
            ok("Designer manager still cannot access PM project page")
        else:
            fail("manager project access", project_access.status_code)
    finally:
        cleanup_fixture(fx)

    print("\n── 3. i18n parity ──")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    required = [
        "designer.manager.title",
        "designer.manager.assign_button",
        "designer.manager.reopen_button",
        "designer.manager.no_rejected_submissions",
        "designer.manager.publish_quest_title",
        "designer.manager.create_draft_button",
        "designer.manager.drafts_title",
    ]
    missing = [key for key in required if key not in en or key not in zh]
    if set(en) == set(zh) and not missing and len(en) >= 935:
        ok(f"i18n parity preserved with DM publishing keys ({len(en)}/{len(zh)})")
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
