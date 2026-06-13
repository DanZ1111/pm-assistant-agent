"""v1.5 Build 05 — Designer submissions and immutable versions.

Run: python3 test_v15_build05.py
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
        f"sqlite:///{Path(tmp.name) / 'v15_build05.db'}",
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
        admin = create_user(db, f"v15_b05_admin_{RUN_TAG}", "admin")
        designer_a = create_user(db, f"v15_b05_designer_a_{RUN_TAG}", "designer", "Designer A")
        designer_b = create_user(db, f"v15_b05_designer_b_{RUN_TAG}", "designer", "Designer B")
        manager = create_user(db, f"v15_b05_manager_{RUN_TAG}", "designer_manager", "Design Manager")
        create_session(db, admin, f"v15-b05-admin-{RUN_TAG}")
        create_session(db, designer_a, f"v15-b05-a-{RUN_TAG}")
        create_session(db, designer_b, f"v15-b05-b-{RUN_TAG}")
        create_session(db, manager, f"v15-b05-m-{RUN_TAG}")
        db.commit()

        project = create_project(db, f"Submission Project {RUN_TAG}", admin.username)
        db.commit()
        quest = crud.create_design_quest_draft(
            db,
            project.id,
            admin.id,
            title="Handle rendering submissions",
            brief="Upload visual directions for PM review.",
            visibility="all_active_designers",
            soft_deadline=date(2026, 9, 1),
        )
        crud.publish_design_quest(db, quest.id, admin.id)

        return {
            "project_id": project.id,
            "quest_id": quest.id,
            "user_ids": [admin.id, designer_a.id, designer_b.id, manager.id],
            "admin_token": f"v15-b05-admin-{RUN_TAG}",
            "designer_a_token": f"v15-b05-a-{RUN_TAG}",
            "designer_b_token": f"v15-b05-b-{RUN_TAG}",
            "manager_token": f"v15-b05-m-{RUN_TAG}",
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


def upload(client, quest_id, filename, content, title="Direction A", note="first direction"):
    return client.post(
        f"/designer/quests/{quest_id}/submissions/upload",
        data={"title": title, "designer_note": note},
        files={"file": (filename, content, "image/png")},
        follow_redirects=False,
    )


def submission_state(project_id):
    from app.database import SessionLocal
    from app.models import DesignSubmission

    db = SessionLocal()
    try:
        submission = (
            db.query(DesignSubmission)
            .filter(DesignSubmission.project_id == project_id)
            .first()
        )
        if not submission:
            return None, []
        versions = list(submission.versions)
        return submission, versions
    finally:
        db.close()


def main():
    print("\n── 1. Source locks ──")
    plan = read("V15_BUILD05_SUBMISSIONS_VERSIONS_PLAN.md")
    models = read("app/models.py")
    migrations_py = read("app/migrations.py")
    crud_py = read("app/crud.py")
    designer_route = read("app/routes/designer.py")
    projects_route = read("app/routes/projects.py")
    designer_detail = read("app/templates/designer/quest_detail.html")
    project_detail = read("app/templates/project_detail.html")
    ai_tools = read("app/ai/tools.py")

    contains_all(
        "Build 05 plan locks submissions/version scope",
        plan,
        [
            "DesignSubmission",
            "DesignSubmissionVersion",
            "no shortlist/reject/request-revision actions",
            "no final selection",
            "no raw `/uploads` links",
        ],
    )
    contains_all(
        "Models, migration, services, routes, and templates are present",
        models + migrations_py + crud_py + designer_route + projects_route + designer_detail + project_detail,
        [
            "class DesignSubmission",
            "class DesignSubmissionVersion",
            "012_v1_5_create_design_submissions",
            "create_or_append_design_submission_version",
            '@router.post("/designer/quests/{quest_id}/submissions/upload"',
            "data-designer-submission-workspace",
            "data-design-submission-grid",
        ],
    )
    if "no shortlist/reject/request-revision actions" in plan and "no final selection" in plan:
        ok("Build 05 plan locks no revision/final-selection scope")
    else:
        fail("Build 05 plan scope lock", "revision/final-selection deferral missing")

    print("\n── 2. Fresh DB schema proof ──")
    tmp, engine, _Session = build_db()
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        expected = {"design_submissions", "design_submission_versions"}
        if expected.issubset(tables):
            ok("Design submission tables exist on a fresh DB")
        else:
            fail("design submission tables", sorted(expected - tables))
        index_names = set()
        for table in expected:
            index_names.update(idx["name"] for idx in insp.get_indexes(table))
        required_indexes = {
            "uq_design_submissions_active_designer",
            "ix_design_submissions_quest_status",
            "ix_design_submissions_designer_status",
            "ix_design_submission_versions_submission",
            "ix_design_submission_versions_quest",
        }
        if required_indexes.issubset(index_names):
            ok("Design submission indexes exist")
        else:
            fail("design submission indexes", sorted(required_indexes - index_names))
    finally:
        tmp.cleanup()

    print("\n── 3. Upload/version behavior ──")
    from app.main import app
    import app.crud as crud

    fx = setup_fixture()
    try:
        designer_a = client_with_token(app, fx["designer_a_token"])
        designer_b = client_with_token(app, fx["designer_b_token"])
        manager = client_with_token(app, fx["manager_token"])
        admin = client_with_token(app, fx["admin_token"])

        first = upload(designer_a, fx["quest_id"], "direction-a.png", b"version-one", title="Direction A")
        submission, versions = submission_state(fx["project_id"])
        if first.status_code in (302, 303) and submission and len(versions) == 1 and versions[0].version_number == 1:
            ok("First designer upload creates one submission and version 1")
        else:
            fail("first upload", {"status": first.status_code, "submission": bool(submission), "versions": len(versions)})

        second = upload(designer_a, fx["quest_id"], "direction-a-v2.webp", b"version-two", title="Direction A v2", note="refined")
        submission, versions = submission_state(fx["project_id"])
        if (
            second.status_code in (302, 303)
            and submission
            and len(versions) == 2
            and [v.version_number for v in versions] == [1, 2]
            and versions[0].original_filename == "direction-a.png"
        ):
            ok("Second upload preserves version 1 and appends version 2")
        else:
            fail("version preservation", {"status": second.status_code, "versions": [(v.version_number, v.original_filename) for v in versions]})

        invalid = upload(designer_a, fx["quest_id"], "bad.exe", b"bad")
        huge_error = None
        huge_db = __import__("app.database", fromlist=["SessionLocal"]).SessionLocal()
        try:
            crud.create_or_append_design_submission_version(
                huge_db,
                quest_id=fx["quest_id"],
                designer_user_id=fx["user_ids"][1],
                original_filename="huge.png",
                content=b"x" * (crud.DESIGN_SUBMISSION_MAX_BYTES + 1),
            )
        except ValueError as exc:
            huge_error = str(exc)
        finally:
            huge_db.close()
        if invalid.status_code in (302, 303) and "submission_invalid_file_type" in invalid.headers.get("location", "") and huge_error == "submission_file_too_large":
            ok("Invalid extension and oversize uploads are rejected")
        else:
            fail("upload validation", {"invalid": invalid.headers.get("location"), "huge": huge_error})

        detail_a = designer_a.get(f"/designer/quests/{fx['quest_id']}")
        latest = versions[-1]
        if (
            detail_a.status_code == 200
            and "Direction A v2" in detail_a.text
            and "direction-a.png" in detail_a.text
            and "direction-a-v2.webp" in detail_a.text
            and "/uploads/" not in detail_a.text
        ):
            ok("Designer detail shows own version history without raw upload links")
        else:
            fail("designer detail submissions", {"status": detail_a.status_code, "uploads": "/uploads/" in detail_a.text})

        detail_b = designer_b.get(f"/designer/quests/{fx['quest_id']}")
        if detail_b.status_code == 200 and "Direction A v2" not in detail_b.text and "direction-a.png" not in detail_b.text:
            ok("Other designer cannot see private submission history")
        else:
            fail("other designer privacy", {"status": detail_b.status_code, "has_private": "Direction A v2" in detail_b.text})

        download_a = designer_a.get(
            f"/designer/quests/{fx['quest_id']}/submissions/{submission.id}/versions/{versions[0].id}/download"
        )
        blocked_b = designer_b.get(
            f"/designer/quests/{fx['quest_id']}/submissions/{submission.id}/versions/{versions[0].id}/download"
        )
        if download_a.status_code == 200 and download_a.content == b"version-one" and blocked_b.status_code == 404:
            ok("Guarded designer download allows owner and blocks other designer")
        else:
            fail("designer guarded download", {"owner": download_a.status_code, "other": blocked_b.status_code})

        manager_download = manager.get(
            f"/designer/quests/{fx['quest_id']}/submissions/{submission.id}/versions/{latest.id}/download"
        )
        if manager_download.status_code == 200 and manager_download.content == b"version-two":
            ok("Designer manager can inspect portal submission downloads")
        else:
            fail("designer manager download", manager_download.status_code)

        pm_detail = admin.get(f"/projects/{fx['project_id']}#renderings-overview")
        pm_download = admin.get(
            f"/projects/{fx['project_id']}/design-quests/{fx['quest_id']}/submissions/{submission.id}/versions/{latest.id}/download"
        )
        if (
            pm_detail.status_code == 200
            and "Incoming submissions" in pm_detail.text
            and "Designer A" in pm_detail.text
            and "direction-a-v2.webp" in pm_detail.text
            and "/uploads/" not in pm_detail.text
            and pm_download.status_code == 200
            and pm_download.content == b"version-two"
        ):
            ok("PM page shows incoming submissions and guarded latest-version download")
        else:
            fail("PM submission grid/download", {"detail": pm_detail.status_code, "download": pm_download.status_code, "uploads": "/uploads/" in pm_detail.text})
    finally:
        cleanup_fixture(fx)

    print("\n── 4. i18n parity ──")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    required = [
        "designer.submissions_title",
        "designer.upload_submission",
        "designer.latest_version",
        "design_quest.incoming_submissions",
        "design_quest.download_latest",
    ]
    missing = [key for key in required if key not in en or key not in zh]
    if set(en) == set(zh) and not missing and len(en) >= 871:
        ok(f"i18n parity preserved with Build 05 keys ({len(en)}/{len(zh)})")
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
