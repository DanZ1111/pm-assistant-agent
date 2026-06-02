"""Build 27 — confirmed daily PM actions + Global read-only search."""
import os
import sys
import uuid
from datetime import date

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app.crud as crud
from app.ai.tools import TOOL_PERMISSIONS, TOOL_SCHEMAS, dispatch
from app.database import SessionLocal
from app.models import (
    ProjectChange, ProjectFile, ProjectJournalEntry, ProjectVariant,
    ProjectVariantComponent, User,
)
from app.routes.ai_chat import _decorate_confirmation_result

BASE = "http://localhost:8000"
PASS, FAIL = [], []
ADMIN, ADMIN_PWD = "admin", "show me the money"
PM_USER = "testpm_b8"
VIEWER_USER = "testviewer_b8"


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


def expect_pending(db, user, tool, args):
    result = dispatch(tool, args, db, user)
    if result.get("error") == "confirmation_required":
        ok(f"{tool} waits for confirmation")
        return True
    fail(f"{tool} proposal", str(result))
    return False


def latest_ai_change(db, project_id):
    return (
        db.query(ProjectChange)
        .filter(
            ProjectChange.project_id == project_id,
            ProjectChange.changed_by == "ai",
            ProjectChange.source_type == "ai_chat",
        )
        .order_by(ProjectChange.id.desc())
        .first()
    )


def main():
    db = SessionLocal()
    admin = db.query(User).filter(User.username == ADMIN).first()
    pm = db.query(User).filter(User.username == PM_USER).first()
    viewer = db.query(User).filter(User.username == VIEWER_USER).first()
    admin_http = login(ADMIN, ADMIN_PWD)
    if not all((admin, pm, viewer, admin_http)):
        fail("setup", "missing test users or local app is not running")
        return done(db)

    suffix = uuid.uuid4().hex[:8]
    project = crud.create_project(db, {
        "name": f"Build27 Marine {suffix}",
        "product_manager": PM_USER,
        "brand": "Build27 Brand",
        "factory": "Hidden Build27 Factory",
        "project_thesis": "A" * 100,
    })
    other = crud.create_project(db, {
        "name": f"Build27 Other {suffix}",
        "product_manager": "someone_else",
    })
    pid = project.id
    ok(f"Created Build 27 test projects #{pid} and #{other.id}")

    print("\n── Schema + read-only Global tools ──")
    names = {schema["function"]["name"] for schema in TOOL_SCHEMAS}
    if len(TOOL_SCHEMAS) == 20 and names == set(TOOL_PERMISSIONS):
        ok("20 schemas have exact permission-rule parity")
    else:
        fail("schema parity", f"count={len(TOOL_SCHEMAS)} diff={names ^ set(TOOL_PERMISSIONS)}")
    search = dispatch("search_projects", {"query": suffix}, db, viewer)
    if search.get("ok") and search.get("read_only") and search.get("count") == 2 and all("factory" not in item for item in search["projects"]):
        ok("Global viewer search returns matching role-filtered projects")
    else:
        fail("Global viewer search", str(search))
    context = dispatch("get_project_context", {"project_id": pid}, db, viewer)
    if context.get("ok") and context.get("read_only") and "factory" not in context["project"] and "recent_journal" not in context["project"]:
        ok("Viewer project context omits sensitive fields and journal")
    else:
        fail("viewer context", str(context))

    print("\n── Confirmed daily PM handlers ──")
    journal_args = {"project_id": pid, "entry_text": "Build27 journal capture", "entry_type": "decision"}
    expect_pending(db, pm, "create_journal_entry", journal_args)
    journal = dispatch("create_journal_entry", journal_args, db, pm, confirmed=True)
    if journal.get("ok") and latest_ai_change(db, pid):
        ok("Confirmed journal capture writes an ai_chat audit row")
    else:
        fail("journal confirm", str(journal))

    variant_args = {"project_id": pid, "variant_name": "Build27 Primary", "status": "evaluating", "sku": "B27-A"}
    expect_pending(db, pm, "create_variant", variant_args)
    variant_result = dispatch("create_variant", variant_args, db, pm, confirmed=True)
    variant = db.query(ProjectVariant).filter(ProjectVariant.id == variant_result.get("variant_id")).first()
    if variant and latest_ai_change(db, pid):
        ok("Confirmed create_variant uses stored status values and audited CRUD")
    else:
        fail("create_variant", str(variant_result))

    update_variant_args = {"variant_id": variant.id, "fields": {"material_summary": "X-30 steel"}}
    expect_pending(db, pm, "update_variant", update_variant_args)
    updated_variant = dispatch("update_variant", update_variant_args, db, pm, confirmed=True)
    db.refresh(variant)
    if updated_variant.get("ok") and variant.material_summary == "X-30 steel":
        ok("Confirmed update_variant edits allowlisted fields")
    else:
        fail("update_variant", str(updated_variant))

    primary_args = {"project_id": pid, "variant_id": variant.id}
    expect_pending(db, pm, "set_primary_variant", primary_args)
    primary = dispatch("set_primary_variant", primary_args, db, pm, confirmed=True)
    db.refresh(variant)
    if primary.get("ok") and variant.is_primary:
        ok("Confirmed set_primary_variant applies through service layer")
    else:
        fail("set_primary_variant", str(primary))

    component_args = {
        "project_id": pid, "variant_id": variant.id, "component_type": "packaging",
        "name": "Gift box", "target_cost": 2.5,
    }
    expect_pending(db, pm, "create_variant_component", component_args)
    component_result = dispatch("create_variant_component", component_args, db, pm, confirmed=True)
    component = db.query(ProjectVariantComponent).filter(
        ProjectVariantComponent.id == component_result.get("component_id")
    ).first()
    if component and component.target_cost == 2.5:
        ok("Confirmed create_variant_component uses stored cost fields")
    else:
        fail("create component", str(component_result))

    update_component_args = {"component_id": component.id, "fields": {"notes": "Matte black finish"}}
    expect_pending(db, pm, "update_variant_component", update_component_args)
    updated_component = dispatch("update_variant_component", update_component_args, db, pm, confirmed=True)
    db.refresh(component)
    if updated_component.get("ok") and component.notes == "Matte black finish":
        ok("Confirmed update_variant_component edits allowlisted fields")
    else:
        fail("update component", str(updated_component))

    pf = ProjectFile(
        project_id=pid, filename=f"build27-{suffix}.png", original_filename="build27.png",
        file_path=f"/tmp/build27-{suffix}.png", file_type="image", file_category="rendering",
    )
    db.add(pf)
    db.commit()
    file_args = {"project_id": pid, "file_id": pf.id, "comment": "Use the second rendering"}
    expect_pending(db, pm, "update_file_comment", file_args)
    file_result = dispatch("update_file_comment", file_args, db, pm, confirmed=True)
    db.refresh(pf)
    if file_result.get("ok") and pf.source_note == "Use the second rendering":
        ok("Confirmed update_file_comment writes through audited CRUD")
    else:
        fail("file comment", str(file_result))

    field_args = {"project_id": pid, "field_name": "target_msrp", "new_value": "89.50"}
    expect_pending(db, pm, "update_project_field", field_args)
    field_result = dispatch("update_project_field", field_args, db, pm, confirmed=True)
    db.refresh(project)
    if field_result.get("ok") and project.target_msrp == 89.5:
        ok("Confirmed sensitive project-field proposal converts and saves reviewed value")
    else:
        fail("project field", str(field_result))
    rejected = dispatch(
        "update_project_field",
        {"project_id": pid, "field_name": "current_stage", "new_value": "Launch"},
        db, pm, confirmed=True,
    )
    if rejected.get("error") == "field_not_allowlisted":
        ok("Derived current_stage remains non-writable")
    else:
        fail("derived field guard", str(rejected))

    first_phase = project.phases[0]
    phase_args = {
        "project_id": pid, "phase_id": first_phase.id,
        "planned_end_date": "2026-07-15", "reason": "Supplier timing update",
    }
    expect_pending(db, pm, "adjust_phase_plan", phase_args)
    phase_result = dispatch("adjust_phase_plan", phase_args, db, pm, confirmed=True)
    db.refresh(first_phase)
    if phase_result.get("ok") and first_phase.planned_end_date == date(2026, 7, 15):
        ok("Confirmed adjust_phase_plan preserves reasoned timeline workflow")
    else:
        fail("adjust phase", str(phase_result))
    finish_args = {"project_id": pid, "phase_id": first_phase.id}
    expect_pending(db, pm, "finish_phase", finish_args)
    finish_result = dispatch("finish_phase", finish_args, db, pm, confirmed=True)
    db.refresh(first_phase)
    if finish_result.get("ok") and first_phase.status == "done":
        ok("Confirmed Finish Phase advances through existing service")
    else:
        fail("finish phase", str(finish_result))

    denied = dispatch("create_variant", {"project_id": other.id, "variant_name": "Denied"}, db, pm)
    if denied.get("error") == "forbidden":
        ok("PM cannot mutate a project they do not own")
    else:
        fail("PM ownership guard", str(denied))

    print("\n── Editable HTTP proposal lifecycle ──")
    decorated = _decorate_confirmation_result(
        "create_journal_entry", journal_args,
        {"ok": False, "error": "confirmation_required"}, db,
    )
    if decorated.get("editable_args") == journal_args and decorated.get("target_project", {}).get("id") == pid:
        ok("Proposal decoration includes editable args and target project")
    else:
        fail("proposal decoration", str(decorated))
    conv = crud.create_ai_conversation(db, admin.id, project_id=pid)
    proposal_id = decorated["proposal_id"]
    crud.save_ai_message(db, pid, "assistant", "Review this.", {
        "conversation_id": conv.id,
        "tool_calls": [{"name": "create_journal_entry", "args": journal_args, "result": decorated}],
    })
    response = admin_http.post(
        f"{BASE}/ai/chat/{conv.id}/proposals/{proposal_id}/confirm",
        json={"action": "confirm", "args": {"entry_text": "Reviewed journal wording"}},
        timeout=5,
    )
    saved = db.query(ProjectJournalEntry).filter(
        ProjectJournalEntry.entry_text == "Reviewed journal wording"
    ).first()
    if response.status_code == 200 and saved:
        ok("HTTP confirmation applies editable reviewed values")
    else:
        fail("editable HTTP confirm", f"{response.status_code}: {response.text[:200]}")
    repeat = admin_http.post(
        f"{BASE}/ai/chat/{conv.id}/proposals/{proposal_id}/confirm",
        json={"action": "confirm"}, timeout=5,
    )
    if repeat.status_code == 409 and repeat.json().get("error") == "proposal_already_resolved":
        ok("Double-confirm remains rejected")
    else:
        fail("double confirm", f"{repeat.status_code}: {repeat.text[:200]}")

    return done(db)


def done(db):
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
