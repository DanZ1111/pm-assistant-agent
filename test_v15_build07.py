"""v1.5 Build 07 — Select final and promote rendering.

Run: python3 test_v15_build07.py
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
        f"sqlite:///{Path(tmp.name) / 'v15_build07.db'}",
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
        admin = create_user(db, f"v15_b07_admin_{RUN_TAG}", "admin")
        designer = create_user(db, f"v15_b07_designer_{RUN_TAG}", "designer", "Designer A")
        other = create_user(db, f"v15_b07_other_{RUN_TAG}", "designer", "Designer B")
        create_session(db, admin, f"v15-b07-admin-{RUN_TAG}")
        create_session(db, designer, f"v15-b07-designer-{RUN_TAG}")
        create_session(db, other, f"v15-b07-other-{RUN_TAG}")
        db.commit()

        project = create_project(db, f"Final Selection Project {RUN_TAG}", admin.username)
        db.commit()
        quest = crud.create_design_quest_draft(
            db,
            project.id,
            admin.id,
            title="Final selection quest",
            brief="Submit final direction candidates.",
            visibility="all_active_designers",
            soft_deadline=date(2026, 10, 15),
        )
        crud.publish_design_quest(db, quest.id, admin.id)

        return {
            "project_id": project.id,
            "quest_id": quest.id,
            "user_ids": [admin.id, designer.id, other.id],
            "admin_token": f"v15-b07-admin-{RUN_TAG}",
            "designer_token": f"v15-b07-designer-{RUN_TAG}",
            "other_token": f"v15-b07-other-{RUN_TAG}",
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


def upload(client, quest_id, filename, content, title):
    return client.post(
        f"/designer/quests/{quest_id}/submissions/upload",
        data={"title": title, "designer_note": f"note for {title}"},
        files={"file": (filename, content, "image/png")},
        follow_redirects=False,
    )


def get_state(project_id):
    from app.database import SessionLocal
    from app.models import DesignQuest, DesignSubmission, ProjectFile, ProjectPhase

    db = SessionLocal()
    try:
        quest = db.query(DesignQuest).filter(DesignQuest.project_id == project_id).first()
        submissions = (
            db.query(DesignSubmission)
            .filter(DesignSubmission.project_id == project_id)
            .order_by(DesignSubmission.id)
            .all()
        )
        for submission in submissions:
            list(submission.versions)
            submission.designer
        renderings = (
            db.query(ProjectFile)
            .filter(ProjectFile.project_id == project_id, ProjectFile.file_category == "rendering")
            .order_by(ProjectFile.uploaded_at.desc())
            .all()
        )
        phases = db.query(ProjectPhase).filter(ProjectPhase.project_id == project_id).all()
        return quest, submissions, renderings, phases
    finally:
        db.close()


def main():
    print("\n── 1. Source locks ──")
    plan = read("V15_BUILD07_SELECT_FINAL_PROMOTE_PLAN.md")
    models = read("app/models.py")
    migrations_py = read("app/migrations.py")
    crud_py = read("app/crud.py")
    routes = read("app/routes/projects.py")
    template = read("app/templates/project_detail.html")
    ai_tools = read("app/ai/tools.py")

    contains_all(
        "Build 07 plan locks select-final/promotion and excludes later scope",
        plan,
        [
            "Select Final & Promote Rendering",
            "no `Mark Design Complete`",
            "no Timeline/Pulse display",
            "no AI write handlers",
        ],
    )
    contains_all(
        "Selected metadata, service, route, and template markers are present",
        models + migrations_py + crud_py + routes + template,
        [
            "014_v1_5_select_final_promote_rendering",
            "selected_version_id",
            "source_metadata",
            "select_final_design_submission_version",
            "get_selected_design_rendering_source",
            "select-final",
            "data-design-selected-source",
        ],
    )
    if "no `Mark Design Complete`" in plan and "no Timeline/Pulse display" in plan and "no AI write handlers" in plan:
        ok("Build 07 plan locks no design-complete, Timeline/Pulse, or AI scope")
    else:
        fail("Build 07 plan scope lock", "design-complete/Timeline/Pulse/AI deferral missing")

    print("\n── 2. Fresh DB schema proof ──")
    tmp, engine, _Session = build_db()
    try:
        insp = inspect(engine)
        quest_cols = {col["name"] for col in insp.get_columns("design_quests")}
        submission_cols = {col["name"] for col in insp.get_columns("design_submissions")}
        file_cols = {col["name"] for col in insp.get_columns("project_files")}
        required = {
            "quest": {"selected_submission_id", "selected_version_id", "selected_by_user_id", "selected_at", "promoted_project_file_id"},
            "submission": {"selected_version_id", "selected_by_user_id", "selected_at"},
            "file": {"source_type", "source_id", "source_metadata"},
        }
        if required["quest"].issubset(quest_cols) and required["submission"].issubset(submission_cols) and required["file"].issubset(file_cols):
            ok("Selected metadata and project file source columns exist")
        else:
            fail("selected schema", {
                "quest": sorted(required["quest"] - quest_cols),
                "submission": sorted(required["submission"] - submission_cols),
                "file": sorted(required["file"] - file_cols),
            })
        index_names = set()
        for table in ("design_quests", "design_submissions", "project_files"):
            index_names.update(idx["name"] for idx in insp.get_indexes(table))
        required_indexes = {
            "ix_project_files_source",
            "ix_design_quests_selected_version",
            "ix_design_submissions_selected_version",
        }
        if required_indexes.issubset(index_names):
            ok("Selected/promotion indexes exist")
        else:
            fail("selected indexes", sorted(required_indexes - index_names))
    finally:
        tmp.cleanup()

    print("\n── 3. Select final and promote rendering ──")
    from app.main import app

    fx = setup_fixture()
    try:
        admin = client_with_token(app, fx["admin_token"])
        designer = client_with_token(app, fx["designer_token"])
        other = client_with_token(app, fx["other_token"])

        first_upload = upload(designer, fx["quest_id"], "direction-a.png", b"direction-a", "Direction A")
        second_upload = upload(other, fx["quest_id"], "direction-b.png", b"direction-b", "Direction B")
        quest, submissions, renderings, phases = get_state(fx["project_id"])
        first_submission = submissions[0]
        second_submission = submissions[1]
        first_version = first_submission.versions[0]
        second_version = second_submission.versions[0]
        if first_upload.status_code in (302, 303) and second_upload.status_code in (302, 303) and len(submissions) == 2:
            ok("Two designers create candidate submissions")
        else:
            fail("candidate uploads", {"first": first_upload.status_code, "second": second_upload.status_code, "submissions": len(submissions)})

        forbidden = designer.post(
            f"/projects/{fx['project_id']}/design-quests/{fx['quest_id']}/submissions/{first_submission.id}/versions/{first_version.id}/select-final",
            follow_redirects=False,
        )
        quest, submissions, renderings, phases = get_state(fx["project_id"])
        if forbidden.status_code in (302, 303, 403) and not renderings and quest.status == "open":
            ok("Regular designer cannot select or promote final rendering")
        else:
            fail("designer forbidden select", {"status": forbidden.status_code, "renderings": len(renderings), "quest_status": quest.status})

        select_first = admin.post(
            f"/projects/{fx['project_id']}/design-quests/{fx['quest_id']}/submissions/{first_submission.id}/versions/{first_version.id}/select-final",
            follow_redirects=False,
        )
        quest, submissions, renderings, phases = get_state(fx["project_id"])
        selected_first = next(sub for sub in submissions if sub.id == first_submission.id)
        rendering = renderings[0] if renderings else None
        source = rendering.source_metadata if rendering else {}
        if (
            select_first.status_code in (302, 303)
            and quest.status == "selected"
            and quest.selected_version_id == first_version.id
            and selected_first.status == "selected"
            and selected_first.selected_version_id == first_version.id
            and rendering
            and rendering.file_category == "rendering"
            and rendering.source_type == "design_submission_version"
            and rendering.source_id == first_version.id
            and source.get("designer_display") == "Designer A"
            and all(phase.status == "in_progress" for phase in phases)
        ):
            ok("PM selects a specific version and promotes it to rendering without completing timeline")
        else:
            fail("select first", {
                "status": select_first.status_code,
                "quest_status": quest.status if quest else None,
                "selected_version": quest.selected_version_id if quest else None,
                "renderings": len(renderings),
                "source": source,
                "phase_statuses": [phase.status for phase in phases],
            })

        promoted_path = os.path.join(__import__("app.crud").crud.UPLOAD_DIR, rendering.filename)
        original_submission_path = os.path.join(__import__("app.crud").crud.UPLOAD_DIR, first_version.filename)
        if rendering.filename != first_version.filename and os.path.exists(promoted_path) and os.path.exists(original_submission_path):
            ok("Promoted rendering is a copied file, not the immutable submission file")
        else:
            fail("promoted copy", {"rendering": rendering.filename if rendering else None, "version": first_version.filename})

        select_second = admin.post(
            f"/projects/{fx['project_id']}/design-quests/{fx['quest_id']}/submissions/{second_submission.id}/versions/{second_version.id}/select-final",
            follow_redirects=False,
        )
        quest, submissions, renderings, phases = get_state(fx["project_id"])
        selected_first = next(sub for sub in submissions if sub.id == first_submission.id)
        selected_second = next(sub for sub in submissions if sub.id == second_submission.id)
        latest_rendering = renderings[0] if renderings else None
        if (
            select_second.status_code in (302, 303)
            and quest.selected_version_id == second_version.id
            and selected_first.status == "shortlisted"
            and selected_first.selected_version_id is None
            and selected_second.status == "selected"
            and selected_second.selected_version_id == second_version.id
            and len(renderings) == 2
            and latest_rendering.source_id == second_version.id
        ):
            ok("Selecting a second final clears prior selected submission and creates newer rendering")
        else:
            fail("select second", {
                "status": select_second.status_code,
                "quest_selected": quest.selected_version_id if quest else None,
                "first_status": selected_first.status,
                "second_status": selected_second.status,
                "renderings": len(renderings),
            })

        pm_detail = admin.get(f"/projects/{fx['project_id']}")
        if (
            pm_detail.status_code == 200
            and "Selected final rendering" in pm_detail.text
            and "Designer B" in pm_detail.text
            and "Selected final" in pm_detail.text
            and "direction-b.png" in pm_detail.text
            and f"/projects/{fx['project_id']}/files/{latest_rendering.id}/download" in pm_detail.text
        ):
            ok("PM page shows selected source metadata and promoted rendering in existing file route")
        else:
            fail("PM selected rendering UI", {"status": pm_detail.status_code, "has_source": "Selected final rendering" in pm_detail.text})
    finally:
        cleanup_fixture(fx)

    print("\n── 4. i18n parity ──")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    required = [
        "design_quest.selected_final_title",
        "design_quest.select_final_button",
        "design_quest.open_promoted_rendering",
    ]
    missing = [key for key in required if key not in en or key not in zh]
    if set(en) == set(zh) and not missing and len(en) >= 888:
        ok(f"i18n parity preserved with Build 07 keys ({len(en)}/{len(zh)})")
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
