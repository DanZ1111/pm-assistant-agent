"""v1.5 Build 06 — Revision loop and PM review actions.

Run: python3 test_v15_build06.py
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
        f"sqlite:///{Path(tmp.name) / 'v15_build06.db'}",
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
    from app.models import Project

    project = Project(name=name, product_manager=pm_username, status="active")
    db.add(project)
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
        admin = create_user(db, f"v15_b06_admin_{RUN_TAG}", "admin")
        designer = create_user(db, f"v15_b06_designer_{RUN_TAG}", "designer", "Designer A")
        other = create_user(db, f"v15_b06_other_{RUN_TAG}", "designer", "Designer B")
        create_session(db, admin, f"v15-b06-admin-{RUN_TAG}")
        create_session(db, designer, f"v15-b06-designer-{RUN_TAG}")
        create_session(db, other, f"v15-b06-other-{RUN_TAG}")
        db.commit()

        project = create_project(db, f"Revision Project {RUN_TAG}", admin.username)
        db.commit()
        quest = crud.create_design_quest_draft(
            db,
            project.id,
            admin.id,
            title="Revision loop quest",
            brief="Submit and revise handle renderings.",
            visibility="all_active_designers",
            soft_deadline=date(2026, 10, 1),
        )
        crud.publish_design_quest(db, quest.id, admin.id)

        return {
            "project_id": project.id,
            "quest_id": quest.id,
            "user_ids": [admin.id, designer.id, other.id],
            "admin_token": f"v15-b06-admin-{RUN_TAG}",
            "designer_token": f"v15-b06-designer-{RUN_TAG}",
            "other_token": f"v15-b06-other-{RUN_TAG}",
        }
    finally:
        db.close()


def cleanup_fixture(fx):
    from app.database import SessionLocal
    from app.models import DesignSubmissionVersion, Project, User, UserSession
    import app.crud as crud

    db = SessionLocal()
    filenames = []
    try:
        versions = (
            db.query(DesignSubmissionVersion)
            .filter(DesignSubmissionVersion.project_id == fx.get("project_id"))
            .all()
        )
        filenames = [version.filename for version in versions]
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
    for filename in filenames:
        disk_path = os.path.join(crud.UPLOAD_DIR, filename)
        if os.path.exists(disk_path):
            os.remove(disk_path)


def client_with_token(app, token):
    client = TestClient(app)
    client.cookies.set("pm_session", token)
    return client


def upload(client, quest_id, filename, content, revision_request_id=None):
    data = {"title": "Direction A", "designer_note": "designer note"}
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
    from app.models import DesignRevisionRequest, DesignSubmission

    db = SessionLocal()
    try:
        submission = db.query(DesignSubmission).filter(DesignSubmission.project_id == project_id).first()
        revisions = db.query(DesignRevisionRequest).filter(DesignRevisionRequest.project_id == project_id).all()
        versions = list(submission.versions) if submission else []
        for revision in revisions:
            list(revision.items)
        return submission, versions, revisions
    finally:
        db.close()


def main():
    print("\n── 1. Source locks ──")
    plan = read("V15_BUILD06_REVISION_LOOP_PLAN.md")
    models = read("app/models.py")
    migrations_py = read("app/migrations.py")
    crud_py = read("app/crud.py")
    routes = read("app/routes/projects.py") + read("app/routes/designer.py")
    templates = read("app/templates/project_detail.html") + read("app/templates/designer/quest_detail.html")
    ai_tools = read("app/ai/tools.py")

    contains_all(
        "Build 06 plan locks revision loop and excludes final selection",
        plan,
        [
            "DesignRevisionRequest",
            "DesignRevisionItem",
            "no final selection",
            "no promotion to project rendering",
            "no AI write handlers",
        ],
    )
    contains_all(
        "Revision models, migration, services, routes, and templates are present",
        models + migrations_py + crud_py + routes + templates,
        [
            "class DesignRevisionRequest",
            "class DesignRevisionItem",
            "013_v1_5_create_design_revision_requests",
            "shortlist_design_submission",
            "request_design_revision",
            "revision_request_id",
            "data-designer-revision-request",
            "data-design-submission-version-history",
        ],
    )
    if "no final selection" in plan and "no promotion" in plan and "no AI write handlers" in plan:
        ok("Build 06 plan locks no final selection, promotion, or AI write handler")
    else:
        fail("Build 06 plan scope lock", "final-selection/promotion/AI deferral missing")

    print("\n── 2. Fresh DB schema proof ──")
    tmp, engine, _Session = build_db()
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        expected = {"design_revision_requests", "design_revision_items"}
        version_cols = {col["name"] for col in insp.get_columns("design_submission_versions")}
        if expected.issubset(tables) and "revision_request_id" in version_cols:
            ok("Revision tables and version link column exist")
        else:
            fail("revision schema", {"tables": sorted(expected - tables), "version_cols": sorted(version_cols)})
        index_names = set()
        for table in expected | {"design_submission_versions"}:
            index_names.update(idx["name"] for idx in insp.get_indexes(table))
        required_indexes = {
            "ix_design_revision_requests_submission_status",
            "ix_design_revision_requests_quest_status",
            "ix_design_revision_items_request",
            "ix_design_submission_versions_revision_request",
        }
        if required_indexes.issubset(index_names):
            ok("Revision indexes exist")
        else:
            fail("revision indexes", sorted(required_indexes - index_names))
    finally:
        tmp.cleanup()

    print("\n── 3. Revision workflow ──")
    from app.main import app

    fx = setup_fixture()
    try:
        admin = client_with_token(app, fx["admin_token"])
        designer = client_with_token(app, fx["designer_token"])
        other = client_with_token(app, fx["other_token"])

        first_upload = upload(designer, fx["quest_id"], "initial.png", b"initial")
        submission, versions, _revisions = get_state(fx["project_id"])
        if first_upload.status_code in (302, 303) and submission and len(versions) == 1:
            ok("Designer creates initial submission")
        else:
            fail("initial upload", {"status": first_upload.status_code, "submission": bool(submission), "versions": len(versions)})

        shortlist = admin.post(
            f"/projects/{fx['project_id']}/design-quests/{fx['quest_id']}/submissions/{submission.id}/shortlist",
            follow_redirects=False,
        )
        submission, _versions, _revisions = get_state(fx["project_id"])
        if shortlist.status_code in (302, 303) and submission.status == "shortlisted":
            ok("PM can shortlist a submission")
        else:
            fail("shortlist", {"status": shortlist.status_code, "submission_status": submission.status})

        revision = admin.post(
            f"/projects/{fx['project_id']}/design-quests/{fx['quest_id']}/submissions/{submission.id}/request-revision",
            data={
                "general_comment": "Please slim the handle and show clip-side view.",
                "checklist_text": "Slim handle\nAdd clip-side view",
            },
            follow_redirects=False,
        )
        submission, _versions, revisions = get_state(fx["project_id"])
        revision_request = revisions[0] if revisions else None
        if (
            revision.status_code in (302, 303)
            and submission.status == "revision_requested"
            and revision_request
            and revision_request.status == "open"
            and len(revision_request.items) == 2
        ):
            ok("PM can request structured revision with checklist")
        else:
            fail("request revision", {"status": revision.status_code, "submission_status": submission.status, "revisions": len(revisions)})

        other_detail = other.get(f"/designer/quests/{fx['quest_id']}")
        designer_detail = designer.get(f"/designer/quests/{fx['quest_id']}")
        if (
            designer_detail.status_code == 200
            and "Please slim the handle" in designer_detail.text
            and "Slim handle" in designer_detail.text
            and "revision_request_id" in designer_detail.text
            and "Please slim the handle" not in other_detail.text
        ):
            ok("Designer sees own revision request and other designer does not")
        else:
            fail("designer revision visibility", {"designer": designer_detail.status_code, "other_has": "Please slim the handle" in other_detail.text})

        revised = upload(designer, fx["quest_id"], "revision-v2.png", b"revised", revision_request_id=revision_request.id)
        submission, versions, revisions = get_state(fx["project_id"])
        revision_request = revisions[0]
        if (
            revised.status_code in (302, 303)
            and submission.status == "revised"
            and len(versions) == 2
            and versions[1].revision_request_id == revision_request.id
            and revision_request.status == "resolved"
            and all(item.status == "resolved" for item in revision_request.items)
        ):
            ok("Designer revised upload resolves request and preserves earlier version")
        else:
            fail("revised upload", {
                "status": revised.status_code,
                "submission_status": submission.status,
                "versions": len(versions),
                "request_status": revision_request.status if revision_request else None,
            })

        pm_detail = admin.get(f"/projects/{fx['project_id']}")
        if (
            pm_detail.status_code == 200
            and "initial.png" in pm_detail.text
            and "revision-v2.png" in pm_detail.text
            and "Revision response" in pm_detail.text
            and "/uploads/" not in pm_detail.text
        ):
            ok("PM sees version history and revision-linked response without raw uploads")
        else:
            fail("PM revision history", {"status": pm_detail.status_code, "uploads": "/uploads/" in pm_detail.text})

        # Separate submission to prove reject action without disturbing revised state.
        second = upload(other, fx["quest_id"], "other.png", b"other")
        from app.database import SessionLocal
        from app.models import DesignSubmission
        db = SessionLocal()
        try:
            other_submission = (
                db.query(DesignSubmission)
                .filter(
                    DesignSubmission.project_id == fx["project_id"],
                    DesignSubmission.designer_user_id == fx["user_ids"][2],
                )
                .first()
            )
        finally:
            db.close()
        reject = admin.post(
            f"/projects/{fx['project_id']}/design-quests/{fx['quest_id']}/submissions/{other_submission.id}/reject",
            data={"reason": "Not aligned"},
            follow_redirects=False,
        )
        _submission, _versions, _revisions = get_state(fx["project_id"])
        db = SessionLocal()
        try:
            rejected = db.query(DesignSubmission).filter(DesignSubmission.id == other_submission.id).first()
            rejected_status = rejected.status if rejected else None
        finally:
            db.close()
        if second.status_code in (302, 303) and reject.status_code in (302, 303) and rejected_status == "rejected":
            ok("PM can reject a separate submission")
        else:
            fail("reject", {"upload": second.status_code, "reject": reject.status_code, "status": rejected_status})
    finally:
        cleanup_fixture(fx)

    print("\n── 4. i18n parity ──")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    required = [
        "design_quest.shortlist_button",
        "design_quest.request_revision_button",
        "design_quest.revision_response_label",
        "designer.revision_requested_title",
    ]
    missing = [key for key in required if key not in en or key not in zh]
    if set(en) == set(zh) and not missing and len(en) >= 881:
        ok(f"i18n parity preserved with Build 06 keys ({len(en)}/{len(zh)})")
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
