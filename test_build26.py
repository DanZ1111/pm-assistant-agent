"""Build 26 — professional assistant workspace + project-aware Idea capture."""
import os
import sys
import uuid

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.ai.tools import TOOL_PERMISSIONS, TOOL_SCHEMAS, dispatch
from app.database import SessionLocal
from app.models import Idea, ProjectChange, ProjectIdea, User
import app.crud as crud
from app.routes.ai_chat import build_project_context, _decorate_confirmation_result

BASE = "http://localhost:8000"
PASS, FAIL = [], []
ADMIN, ADMIN_PWD = "admin", "show me the money"
PM_USER, PM_PWD = "testpm_b8", "pmpassword8!"
VIEWER_USER, VIEWER_PWD = "testviewer_b8", "viewerpass8!"


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, reason):
    FAIL.append((name, reason))
    print(f"  ✗  {name}: {reason}")


def login(username, password):
    session = requests.Session()
    response = session.post(
        f"{BASE}/auth/login",
        data={"username": username, "password": password},
        allow_redirects=False,
        timeout=5,
    )
    return session if response.status_code in (302, 303) else None


def main():
    db = SessionLocal()
    admin = db.query(User).filter(User.username == ADMIN).first()
    pm = db.query(User).filter(User.username == PM_USER).first()
    viewer = db.query(User).filter(User.username == VIEWER_USER).first()
    if not all((admin, pm, viewer)):
        fail("setup", "missing Build 8 test users")
        return _done(db)

    admin_http = login(ADMIN, ADMIN_PWD)
    pm_http = login(PM_USER, PM_PWD)
    viewer_http = login(VIEWER_USER, VIEWER_PWD)
    if not all((admin_http, pm_http, viewer_http)):
        fail("setup", "HTTP login failed; is python run.py running?")
        return _done(db)
    ok("Admin, PM, and viewer test users are available")

    suffix = uuid.uuid4().hex[:8]
    project = crud.create_project(
        db,
        {
            "name": f"Build26 Workspace {suffix}",
            "product_manager": PM_USER,
            "factory": "Sensitive Test Factory",
            "target_factory_cost": 12.5,
            "target_msrp": 79.0,
            "project_thesis": "A" * 100,
        },
    )
    pid = project.id
    ok(f"Created PM-owned Build 26 project #{pid}")

    print("\n── Schema + i18n ──")
    schema_names = {schema["function"]["name"] for schema in TOOL_SCHEMAS}
    if len(TOOL_SCHEMAS) == 20 and schema_names == set(TOOL_PERMISSIONS):
        ok("20 AI schemas have matching permission rules")
    else:
        fail("schema registry", f"schemas={len(TOOL_SCHEMAS)} diff={schema_names ^ set(TOOL_PERMISSIONS)}")
    if {"create_idea", "link_idea_to_project", "update_idea"} <= schema_names:
        ok("Build 26 Idea tool schemas are registered")
    else:
        fail("Idea schemas", str(schema_names))
    from app.i18n import TRANSLATIONS
    if set(TRANSLATIONS["en"]) == set(TRANSLATIONS["zh"]):
        ok(f"English / Chinese bundles have exact parity ({len(TRANSLATIONS['en'])} keys)")
    else:
        fail("i18n parity", "bundle keys differ")

    print("\n── Role-filtered project context ──")
    pm_context = build_project_context(db, pid, pm)
    viewer_context = build_project_context(db, pid, viewer)
    if pm_context.get("factory") == "Sensitive Test Factory":
        ok("PM project prompt context includes permitted sensitive fields")
    else:
        fail("PM prompt context", str(pm_context))
    if "factory" not in viewer_context and "target_factory_cost" not in viewer_context:
        ok("Viewer project prompt context omits sensitive fields")
    else:
        fail("viewer prompt context", str(viewer_context))

    print("\n── Confirmation-guarded Idea tools ──")
    idea_name = f"Canton Ceramic Handle {suffix}"
    args = {"project_id": pid, "name": idea_name, "source": "tradeshow"}
    before_count = db.query(Idea).filter(Idea.name == idea_name).count()
    pending = dispatch("create_idea", args, db, pm)
    after_count = db.query(Idea).filter(Idea.name == idea_name).count()
    if pending.get("error") == "confirmation_required" and before_count == after_count:
        ok("create_idea returns confirmation_required without writing")
    else:
        fail("create_idea preview", f"pending={pending} counts={before_count}/{after_count}")

    created = dispatch("create_idea", args, db, pm, confirmed=True)
    idea = db.query(Idea).filter(Idea.id == created.get("idea_id")).first()
    linked = db.query(ProjectIdea).filter(
        ProjectIdea.project_id == pid, ProjectIdea.idea_id == created.get("idea_id")
    ).first()
    if created.get("ok") and idea and linked:
        ok("Confirmed create_idea creates and links Inspired By in one action")
    else:
        fail("confirmed create_idea", str(created))
    change = db.query(ProjectChange).filter(
        ProjectChange.project_id == pid,
        ProjectChange.changed_by == "ai",
        ProjectChange.source_type == "ai_chat",
    ).order_by(ProjectChange.id.desc()).first()
    if change and "Linked IDEA-" in (change.summary or ""):
        ok("Confirmed AI Idea linkage writes an ai_chat change-log row")
    else:
        fail("AI linkage audit", str(change.summary if change else None))

    denied = dispatch("create_idea", {"name": "Viewer write"}, db, viewer, confirmed=True)
    if denied.get("error") == "forbidden":
        ok("Viewer cannot create Ideas through AI tools")
    else:
        fail("viewer AI write", str(denied))

    update_pending = dispatch(
        "update_idea", {"idea_id": idea.id, "fields": {"source_detail": "Canton Fair"}}, db, pm
    )
    update_done = dispatch(
        "update_idea",
        {"idea_id": idea.id, "fields": {"source_detail": "Canton Fair"}},
        db,
        pm,
        confirmed=True,
    )
    db.refresh(idea)
    if update_pending.get("error") == "confirmation_required" and update_done.get("ok") and idea.source_detail == "Canton Fair":
        ok("update_idea is guarded and applies allowlisted follow-up detail after confirmation")
    else:
        fail("update_idea", f"pending={update_pending} done={update_done} detail={idea.source_detail}")

    duplicate = _decorate_confirmation_result(
        "create_idea",
        {"project_id": pid, "name": idea_name},
        {"ok": False, "error": "confirmation_required"},
        db,
    )
    if duplicate.get("duplicate", {}).get("idea_id") == idea.id:
        ok("Duplicate Idea proposal identifies the existing match")
    else:
        fail("duplicate detection", str(duplicate))

    print("\n── HTTP proposal lifecycle ──")
    conv = crud.create_ai_conversation(db, admin.id, project_id=pid)
    proposal_id = uuid.uuid4().hex
    crud.save_ai_message(
        db,
        pid,
        "assistant",
        "Please confirm.",
        {
            "conversation_id": conv.id,
            "tool_calls": [{
                "name": "create_idea",
                "args": {"project_id": pid, "name": f"Proposal Idea {suffix}"},
                "result": {
                    "ok": False,
                    "error": "confirmation_required",
                    "proposal_id": proposal_id,
                    "summary": "Create and link this Idea?",
                },
            }],
        },
    )
    response = admin_http.post(
        f"{BASE}/ai/chat/{conv.id}/proposals/{proposal_id}/confirm",
        json={"action": "confirm"},
        timeout=5,
    )
    if response.status_code == 200 and response.json().get("ok"):
        ok("HTTP proposal confirmation applies a pending Idea action")
    else:
        fail("proposal confirm", f"{response.status_code}: {response.text[:300]}")
    repeat = admin_http.post(
        f"{BASE}/ai/chat/{conv.id}/proposals/{proposal_id}/confirm",
        json={"action": "confirm"},
        timeout=5,
    )
    if repeat.status_code == 409 and repeat.json().get("error") == "proposal_already_resolved":
        ok("Double-confirmed proposal is rejected")
    else:
        fail("double confirm", f"{repeat.status_code}: {repeat.text[:200]}")

    scope = admin_http.post(
        f"{BASE}/ai/chat",
        json={
            "message": "switch scope",
            "conversation_id": conv.id,
            "scope": "global",
            "mode": "ask",
        },
        timeout=5,
    )
    if scope.status_code == 409 and scope.json().get("error") == "scope_change_requires_new_conversation":
        ok("Server rejects silent Project-to-Global scope changes")
    else:
        fail("scope immutability", f"{scope.status_code}: {scope.text[:200]}")

    print("\n── Manual Create & Link + workspace markup ──")
    manual_name = f"Manual Linked Idea {suffix}"
    response = pm_http.post(
        f"{BASE}/projects/{pid}/ideas/create-and-link",
        data={"name": manual_name, "idea_type": "feature", "source": "team"},
        allow_redirects=False,
        timeout=5,
    )
    manual_idea = db.query(Idea).filter(Idea.name == manual_name).first()
    if response.status_code == 303 and manual_idea and db.query(ProjectIdea).filter(
        ProjectIdea.project_id == pid, ProjectIdea.idea_id == manual_idea.id
    ).first():
        ok("Manual Create & Link route creates a linked Idea")
    else:
        fail("manual create link", f"status={response.status_code} idea={manual_idea}")

    page = pm_http.get(f"{BASE}/projects/{pid}", timeout=5).text
    required_markup = [
        'id="bottomChatBar"',
        'id="aiSidePanel"',
        'id="panelChatForm"',
        'id="aiPanelResizeHandle"',
        'data-chat-mode="intake"',
        'data-chat-scope="project"',
        'id="createLinkIdeaModal"',
        f'data-project-id="{pid}"',
    ]
    missing = [needle for needle in required_markup if needle not in page]
    if not missing:
        ok("Project detail renders split-workspace and Create & Link markup")
    else:
        fail("workspace markup", f"missing={missing}")

    viewer_board = viewer_http.get(f"{BASE}/ideas", timeout=5).text
    if 'href="/ideas/new"' not in viewer_board:
        ok("Viewer Good Ideas board hides New Idea action")
    else:
        fail("viewer board", "New Idea action is visible")

    return _done(db)


def _done(db):
    db.close()
    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    for name, reason in FAIL:
        print(f"  ✗ {name}: {reason}")
    print("=" * 60)
    return not FAIL


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
