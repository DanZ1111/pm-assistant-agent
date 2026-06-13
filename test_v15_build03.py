"""v1.5 Build 03 — PM Renderings & Design quest panel.

Requires the app running at BASE_URL (default http://localhost:8000).

Run: python3 test_v15_build03.py
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = Path(__file__).resolve().parent
ADMIN = os.environ.get("TEST_ADMIN_USERNAME", "admin")
ADMIN_PWD = os.environ.get("TEST_ADMIN_PASSWORD", "show me the money")
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


def admin_login(client):
    response = client.post(
        "/auth/login",
        data={"username": ADMIN, "password": ADMIN_PWD},
        follow_redirects=False,
    )
    return response


def fixture_records():
    from app.database import SessionLocal
    from app.models import Project, ProjectFile, User, UserSession

    db = SessionLocal()
    try:
        project = Project(
            name=f"V15 Build03 Project {RUN_TAG}",
            product_manager="admin",
            status="active",
        )
        db.add(project)
        db.flush()
        pf = ProjectFile(
            project_id=project.id,
            filename=f"v15-build03-{RUN_TAG}.png",
            original_filename="designer-reference.png",
            file_path=f"uploads/v15-build03-{RUN_TAG}.png",
            file_type="image",
            file_category="reference",
            file_size=5555,
        )
        designer = User(
            username=f"v15_b03_designer_{RUN_TAG}",
            display_name="V15 B03 Designer",
            hashed_password="not-used",
            role="designer",
        )
        db.add_all([pf, designer])
        db.flush()
        token = f"v15-b03-{RUN_TAG}"
        db.add(UserSession(
            token=token,
            user_id=designer.id,
            created_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(hours=1),
        ))
        db.commit()
        return project.id, pf.id, designer.id, token
    finally:
        db.close()


def cleanup(project_id, designer_id):
    from app.database import SessionLocal
    from app.models import Project, User, UserSession

    db = SessionLocal()
    try:
        db.query(UserSession).filter(UserSession.user_id == designer_id).delete(synchronize_session=False)
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            db.delete(project)
        designer = db.query(User).filter(User.id == designer_id).first()
        if designer:
            db.delete(designer)
        db.commit()
    finally:
        db.close()


def get_quest(project_id):
    from app.database import SessionLocal
    from app.models import DesignQuest

    db = SessionLocal()
    try:
        return db.query(DesignQuest).filter(DesignQuest.project_id == project_id).order_by(DesignQuest.id.desc()).first()
    finally:
        db.close()


def count_references(quest_id):
    from app.database import SessionLocal
    from app.models import DesignQuestReference

    db = SessionLocal()
    try:
        return db.query(DesignQuestReference).filter(DesignQuestReference.quest_id == quest_id).count()
    finally:
        db.close()


def main():
    print("\n── 1. Source locks ──")
    plan = read("V15_BUILD03_PM_RENDERINGS_DESIGN_QUEST_PLAN.md")
    routes = read("app/routes/projects.py")
    template = read("app/templates/project_detail.html")
    css = read("app/static/css/styles.css")
    contains_all(
        "Build 03 plan locks PM-only Renderings & Design scope",
        plan,
        [
            "PM Workspace only",
            "no Designer Portal quest dashboard/detail pages",
            "no designer upload/submissions",
            "no guarded designer file route yet",
        ],
    )
    contains_all(
        "PM design quest routes call Build 02 service helpers",
        routes,
        [
            '@router.post("/projects/{project_id}/design-quest/create")',
            "create_design_quest_draft",
            "publish_design_quest",
            "close_design_quest",
            "link_design_quest_reference",
        ],
    )
    contains_all(
        "Project detail renders Active Design Quest panel",
        template + css,
        [
            "design-quest-panel",
            "design_quest.active_title",
            "design_quest.create_button",
            "design_quest.preview_title",
        ],
    )
    if "renderings-designer-placeholder" not in template and "Designer Portal future" not in template:
        ok("Old renderings Designer Portal placeholder is removed from project detail")
    else:
        fail("placeholder removal", "old placeholder marker still renders")

    print("\n── 2. i18n parity ──")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    required_keys = [
        "section.renderings_design",
        "design_quest.active_title",
        "design_quest.create_button",
        "design_quest.publish_button",
        "design_quest.close_button",
        "design_quest.preview_title",
        "design_quest.visibility_all_active_designers",
        "design_quest.visibility_assigned_designers_only",
    ]
    missing = [key for key in required_keys if key not in en or key not in zh]
    if set(en) == set(zh) and not missing and len(en) == 842:
        ok("i18n parity locked at 842/842 with Build 03 keys")
    else:
        fail("i18n parity/count", {"en": len(en), "zh": len(zh), "missing": missing, "diff": sorted(set(en) ^ set(zh))[:8]})

    print("\n── 3. PM quest lifecycle via TestClient ──")
    from app.main import app
    from app.database import Base, engine
    from app import migrations

    Base.metadata.create_all(bind=engine)
    migrations.run_pending(engine)

    client = TestClient(app)
    health = client.get("/healthz")
    if health.status_code == 200:
        ok("In-process app responds before PM design quest flow")
    else:
        fail("test app health", health.status_code)
        return summary()

    login = admin_login(client)
    if login.status_code in (302, 303) and client.cookies.get("pm_session"):
        ok("Admin login works for PM design quest flow")
    else:
        fail("admin login", login.status_code)
        return summary()

    project_id, file_id, designer_id, designer_token = fixture_records()
    try:
        detail = client.get(f"/projects/{project_id}")
        if detail.status_code == 200 and "Renderings &amp; Design" in detail.text and "Create Draft Quest" in detail.text:
            ok("Project detail shows Renderings & Design quest creation panel")
        else:
            fail("initial project detail panel", {"status": detail.status_code, "has_panel": "Create Draft Quest" in detail.text})

        create = client.post(
            f"/projects/{project_id}/design-quest/create",
            data={
                "title": "Outdoor handle rendering",
                "brief": "Create handle direction renderings for a compact outdoor folding knife.",
                "must_keep": "Slim handle and practical pocket carry.",
                "must_avoid": "Overbuilt fantasy knife language.",
                "soft_deadline": "2026-07-15",
                "visibility": "all_active_designers",
                "is_timeline_blocking": "true",
            },
            follow_redirects=False,
        )
        quest = get_quest(project_id)
        if create.status_code in (302, 303) and quest and quest.status == "draft":
            ok("Create draft route creates draft design quest")
        else:
            fail("create draft route", {"status": create.status_code, "quest": getattr(quest, "status", None)})

        detail = client.get(f"/projects/{project_id}")
        if detail.status_code == 200 and "Outdoor handle rendering" in detail.text and "Publish Quest" in detail.text:
            ok("Project detail shows active draft quest and publish action")
        else:
            fail("draft quest panel", {"status": detail.status_code, "has_title": "Outdoor handle rendering" in detail.text})

        add_ref = client.post(
            f"/projects/{project_id}/design-quest/{quest.id}/references",
            data={"project_file_id": str(file_id), "label": "Reference board"},
            follow_redirects=False,
        )
        if add_ref.status_code in (302, 303) and count_references(quest.id) == 1:
            ok("Reference route links same-project file")
        else:
            fail("reference add route", {"status": add_ref.status_code, "count": count_references(quest.id)})

        from app.database import SessionLocal
        from app.models import DesignQuest
        import app.crud as crud
        db = SessionLocal()
        try:
            fresh_quest = db.query(DesignQuest).filter(DesignQuest.id == quest.id).first()
            preview = crud.shape_design_quest_for_pm_preview(fresh_quest)
            preview_text = json.dumps(preview, default=str)
        finally:
            db.close()
        if "Reference board" in preview_text and "/uploads/" not in preview_text and "file_path" not in preview_text:
            ok("PM designer-safe preview omits raw upload URLs and file_path")
        else:
            fail("designer-safe preview", preview)

        publish = client.post(
            f"/projects/{project_id}/design-quest/{quest.id}/publish",
            follow_redirects=False,
        )
        quest = get_quest(project_id)
        if publish.status_code in (302, 303) and quest.status == "open":
            ok("Publish route opens draft quest")
        else:
            fail("publish route", {"status": publish.status_code, "quest": getattr(quest, "status", None)})

        designer_client = TestClient(app)
        designer_client.cookies.set("pm_session", designer_token)
        designer_project = designer_client.get(f"/projects/{project_id}", follow_redirects=False)
        if designer_project.status_code in (302, 303) and designer_project.headers.get("location") == "/designer":
            ok("Designer role remains blocked from PM project detail")
        else:
            fail("designer PM route boundary", {"status": designer_project.status_code, "location": designer_project.headers.get("location")})

        close = client.post(
            f"/projects/{project_id}/design-quest/{quest.id}/close",
            data={"reason": "Build 03 test cleanup"},
            follow_redirects=False,
        )
        quest = get_quest(project_id)
        if close.status_code in (302, 303) and quest.status == "closed":
            ok("Close route closes active quest")
        else:
            fail("close route", {"status": close.status_code, "quest": getattr(quest, "status", None)})
    finally:
        cleanup(project_id, designer_id)

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
