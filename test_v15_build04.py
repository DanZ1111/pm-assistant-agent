"""v1.5 Build 04 — Designer Portal quest view and guarded references.

Run: python3 test_v15_build04.py
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
    from app.models import Project

    project = Project(
        name=name,
        product_manager=pm_username,
        factory="Hidden Factory",
        target_msrp_text="$70-100",
        target_factory_cost_text="under 120 RMB",
        status="active",
    )
    db.add(project)
    db.flush()
    return project


def create_file(db, project_id, filename):
    from app.models import ProjectFile
    import app.crud as crud

    os.makedirs(crud.UPLOAD_DIR, exist_ok=True)
    disk_path = os.path.join(crud.UPLOAD_DIR, filename)
    with open(disk_path, "wb") as fh:
        fh.write(b"designer reference bytes")

    pf = ProjectFile(
        project_id=project_id,
        filename=filename,
        original_filename="safe-reference.png",
        file_path=f"uploads/{filename}",
        file_type="image",
        file_category="reference",
        file_size=os.path.getsize(disk_path),
    )
    db.add(pf)
    db.flush()
    return pf, disk_path


def setup_fixture():
    from app.database import Base, SessionLocal, engine
    from app import migrations
    import app.crud as crud

    Base.metadata.create_all(bind=engine)
    migrations.run_pending(engine)

    db = SessionLocal()
    disk_paths = []
    try:
        admin = create_user(db, f"v15_b04_admin_{RUN_TAG}", "admin")
        designer_a = create_user(db, f"v15_b04_designer_a_{RUN_TAG}", "designer", "Designer A")
        designer_b = create_user(db, f"v15_b04_designer_b_{RUN_TAG}", "designer", "Designer B")
        manager = create_user(db, f"v15_b04_manager_{RUN_TAG}", "designer_manager", "Design Manager")
        viewer = create_user(db, f"v15_b04_viewer_{RUN_TAG}", "viewer", "Viewer")
        create_session(db, designer_a, f"v15-b04-a-{RUN_TAG}")
        create_session(db, designer_b, f"v15-b04-b-{RUN_TAG}")
        create_session(db, manager, f"v15-b04-m-{RUN_TAG}")
        create_session(db, viewer, f"v15-b04-v-{RUN_TAG}")
        db.commit()

        project_all = create_project(db, f"Visible Quest Project {RUN_TAG}", admin.username)
        db.commit()
        visible = crud.create_design_quest_draft(
            db,
            project_all.id,
            admin.id,
            title="Open handle rendering quest",
            brief="Create two visual directions for a compact outdoor handle.",
            must_keep="Slim practical handle",
            must_avoid="Fantasy styling",
            soft_deadline=date(2026, 8, 1),
            visibility="all_active_designers",
        )
        pf, disk_path = create_file(db, project_all.id, f"v15-b04-ref-{RUN_TAG}.png")
        disk_paths.append(disk_path)
        db.commit()
        crud.link_design_quest_reference(db, visible.id, pf.id, admin.id, label="Safe reference")
        crud.publish_design_quest(db, visible.id, admin.id)

        project_draft = create_project(db, f"Draft Quest Project {RUN_TAG}", admin.username)
        db.commit()
        draft = crud.create_design_quest_draft(
            db,
            project_draft.id,
            admin.id,
            title="Hidden draft quest",
            brief="Designers must not see drafts.",
            visibility="all_active_designers",
        )

        project_assigned = create_project(db, f"Assigned Quest Project {RUN_TAG}", admin.username)
        db.commit()
        assigned = crud.create_design_quest_draft(
            db,
            project_assigned.id,
            admin.id,
            title="Assigned-only quest",
            brief="Only Designer A should see this quest.",
            visibility="assigned_designers_only",
        )
        crud.assign_designers_to_quest(db, assigned.id, [designer_a.id], admin.id)
        crud.publish_design_quest(db, assigned.id, admin.id)

        return {
            "project_ids": [project_all.id, project_draft.id, project_assigned.id],
            "user_ids": [admin.id, designer_a.id, designer_b.id, manager.id, viewer.id],
            "designer_a_token": f"v15-b04-a-{RUN_TAG}",
            "designer_b_token": f"v15-b04-b-{RUN_TAG}",
            "manager_token": f"v15-b04-m-{RUN_TAG}",
            "viewer_token": f"v15-b04-v-{RUN_TAG}",
            "visible_quest_id": visible.id,
            "draft_quest_id": draft.id,
            "assigned_quest_id": assigned.id,
            "reference_id": visible.references[0].id,
            "disk_paths": disk_paths,
        }
    finally:
        db.close()


def cleanup_fixture(fx):
    from app.database import SessionLocal
    from app.models import Project, User, UserSession

    db = SessionLocal()
    try:
        if fx.get("user_ids"):
            db.query(UserSession).filter(UserSession.user_id.in_(fx["user_ids"])).delete(synchronize_session=False)
        for project_id in fx.get("project_ids", []):
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
    for path in fx.get("disk_paths", []):
        if os.path.exists(path):
            os.remove(path)


def client_with_token(app, token):
    client = TestClient(app)
    client.cookies.set("pm_session", token)
    return client


def main():
    print("\n── 1. Source locks ──")
    plan = read("V15_BUILD04_DESIGNER_QUEST_VIEW_PLAN.md")
    route = read("app/routes/designer.py")
    dashboard = read("app/templates/designer/dashboard.html")
    detail = read("app/templates/designer/quest_detail.html")
    models = read("app/models.py")
    contains_all(
        "Build 04 plan locks read-only Designer Portal quest view scope",
        plan,
        [
            "read-only for designers",
            "guarded reference download route",
            "no designer submission upload",
            "no raw `/uploads` links",
        ],
    )
    contains_all(
        "Designer routes/templates expose dashboard, detail, and guarded references",
        route + dashboard + detail,
        [
            '@router.get("/designer/quests/{quest_id}"',
            '@router.get("/designer/quests/{quest_id}/references/{reference_id}/download"',
            "list_design_quests_for_designer",
            "shape_design_quest_for_designer",
            "data-designer-quest-list",
            "data-designer-quest-detail",
        ],
    )
    if "DesignSubmission" not in models and "submission" not in route.lower() and "submission" not in detail.lower():
        ok("Build 04 adds no submission model, route, or UI")
    else:
        fail("submission scope leak", "submission marker found")

    print("\n── 2. i18n parity ──")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    required = [
        "designer.available_quests",
        "designer.open_quest",
        "designer.back_to_dashboard",
        "designer.quest_brief_label",
        "designer.download_reference",
        "designer.no_references",
    ]
    missing = [key for key in required if key not in en or key not in zh]
    if set(en) == set(zh) and not missing and len(en) == 854:
        ok("i18n parity locked at 854/854 with Build 04 keys")
    else:
        fail("i18n parity/count", {"en": len(en), "zh": len(zh), "missing": missing, "diff": sorted(set(en) ^ set(zh))[:8]})

    print("\n── 3. Designer Portal quest access ──")
    from app.main import app

    fx = setup_fixture()
    try:
        designer_a = client_with_token(app, fx["designer_a_token"])
        designer_b = client_with_token(app, fx["designer_b_token"])
        manager = client_with_token(app, fx["manager_token"])
        viewer = client_with_token(app, fx["viewer_token"])

        dash_a = designer_a.get("/designer")
        if (
            dash_a.status_code == 200
            and "Open handle rendering quest" in dash_a.text
            and "Assigned-only quest" in dash_a.text
            and "Hidden draft quest" not in dash_a.text
            and "/projects/" not in dash_a.text
        ):
            ok("Designer dashboard lists visible quests, hides drafts, and has no PM project links")
        else:
            fail("designer A dashboard", {"status": dash_a.status_code, "body": dash_a.text[:400]})

        dash_b = designer_b.get("/designer")
        if (
            dash_b.status_code == 200
            and "Open handle rendering quest" in dash_b.text
            and "Assigned-only quest" not in dash_b.text
        ):
            ok("Assigned-only quest is hidden from unassigned designer")
        else:
            fail("designer B dashboard", {"status": dash_b.status_code, "has_assigned": "Assigned-only quest" in dash_b.text})

        manager_dash = manager.get("/designer")
        if manager_dash.status_code == 200 and "Assigned-only quest" in manager_dash.text:
            ok("Designer manager can inspect published portal quests")
        else:
            fail("manager dashboard", manager_dash.status_code)

        detail_a = designer_a.get(f"/designer/quests/{fx['visible_quest_id']}")
        forbidden_terms = ["Hidden Factory", "$70-100", "under 120 RMB", "Timeline", "Journal", "/uploads/", "/projects/"]
        if (
            detail_a.status_code == 200
            and "Create two visual directions" in detail_a.text
            and "Slim practical handle" in detail_a.text
            and "Safe reference" in detail_a.text
            and not any(term in detail_a.text for term in forbidden_terms)
            and f"/designer/quests/{fx['visible_quest_id']}/references/{fx['reference_id']}/download" in detail_a.text
        ):
            ok("Quest detail shows safe brief/reference fields without internal data or raw upload links")
        else:
            fail("designer quest detail", {"status": detail_a.status_code, "forbidden": [t for t in forbidden_terms if t in detail_a.text]})

        assigned_by_b = designer_b.get(f"/designer/quests/{fx['assigned_quest_id']}", follow_redirects=False)
        if assigned_by_b.status_code in (302, 303) and assigned_by_b.headers.get("location") == "/designer":
            ok("Unassigned designer cannot open assigned-only quest detail")
        else:
            fail("assigned quest detail boundary", {"status": assigned_by_b.status_code, "location": assigned_by_b.headers.get("location")})

        download = designer_a.get(
            f"/designer/quests/{fx['visible_quest_id']}/references/{fx['reference_id']}/download"
        )
        if download.status_code == 200 and download.content == b"designer reference bytes":
            ok("Visible designer can download reference through guarded route")
        else:
            fail("guarded reference download", {"status": download.status_code, "content": download.content[:40]})

        blocked_download = designer_b.get(
            f"/designer/quests/{fx['assigned_quest_id']}/references/{fx['reference_id']}/download"
        )
        if blocked_download.status_code == 404:
            ok("Guarded reference route rejects invisible quest/reference combination")
        else:
            fail("blocked reference download", blocked_download.status_code)

        pm_boundary = designer_a.get(f"/projects/{fx['project_ids'][0]}", follow_redirects=False)
        if pm_boundary.status_code in (302, 303) and pm_boundary.headers.get("location") == "/designer":
            ok("Designer remains blocked from PM project detail")
        else:
            fail("designer PM boundary", {"status": pm_boundary.status_code, "location": pm_boundary.headers.get("location")})

        viewer_designer = viewer.get("/designer", follow_redirects=False)
        if viewer_designer.status_code in (302, 303) and viewer_designer.headers.get("location") == "/projects":
            ok("Viewer is not allowed into Designer Portal")
        else:
            fail("viewer designer portal boundary", {"status": viewer_designer.status_code, "location": viewer_designer.headers.get("location")})
    finally:
        cleanup_fixture(fx)

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
