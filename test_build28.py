"""Build 28 — assistant PDF, DOCX, and image intake."""
import io
import json
import os
import sys
import time
import uuid

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app.crud as crud
from app.ai.attachments import (
    PENDING_TTL_SECONDS, PENDING_UPLOAD_DIR, AttachmentError,
    cleanup_stale_pending_attachments, create_pending_attachment,
    discard_pending_attachment, get_pending_attachment,
)
from app.ai.tools import TOOL_PERMISSIONS, TOOL_SCHEMAS, dispatch
from app.database import SessionLocal
from app.models import ProjectChange, ProjectFile, User

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


def make_png():
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00"
        b"\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def make_docx(text):
    from docx import Document
    document = Document()
    document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_pdf():
    from pypdf import PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def latest_ai_file_change(db, project_id):
    return (
        db.query(ProjectChange)
        .filter(
            ProjectChange.project_id == project_id,
            ProjectChange.change_type == "file_upload",
            ProjectChange.changed_by == "ai",
            ProjectChange.source_type == "ai_chat",
        )
        .order_by(ProjectChange.id.desc())
        .first()
    )


def upload_attachment(session, name, content, content_type):
    return session.post(
        f"{BASE}/ai/chat/attachments",
        files={"file": (name, io.BytesIO(content), content_type)},
        timeout=5,
    )


def main():
    db = SessionLocal()
    admin = db.query(User).filter(User.username == ADMIN).first()
    pm = db.query(User).filter(User.username == PM_USER).first()
    viewer = db.query(User).filter(User.username == VIEWER_USER).first()
    admin_http = login(ADMIN, ADMIN_PWD)
    pm_http = login(PM_USER, PM_PWD)
    viewer_http = login(VIEWER_USER, VIEWER_PWD)
    if not all((admin, pm, viewer, admin_http, pm_http, viewer_http)):
        fail("setup", "missing test users or local app is not running")
        return done(db)

    suffix = uuid.uuid4().hex[:8]
    project = crud.create_project(db, {
        "name": f"Build28 Attachment {suffix}",
        "product_manager": PM_USER,
        "project_thesis": "A" * 100,
    })
    pid = project.id
    ok(f"Created PM-owned Build 28 project #{pid}")

    print("\n── Schema + local pending service ──")
    names = {schema["function"]["name"] for schema in TOOL_SCHEMAS}
    if len(TOOL_SCHEMAS) == 20 and names == set(TOOL_PERMISSIONS) and "save_pending_attachment" in names:
        ok("20 schemas include confirmed save_pending_attachment with permission parity")
    else:
        fail("schema parity", f"count={len(TOOL_SCHEMAS)} diff={names ^ set(TOOL_PERMISSIONS)}")

    docx_text = f"Build28 local DOCX extraction {suffix}"
    docx_pending = create_pending_attachment(
        make_docx(docx_text), "brief.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        admin.id,
    )
    docx_meta = get_pending_attachment(docx_pending["attachment_id"], admin.id)
    if docx_text in docx_meta.get("extracted_text", ""):
        ok("DOCX text is extracted locally into pending discussion metadata")
    else:
        fail("DOCX extraction", str(docx_meta))
    pdf_pending = create_pending_attachment(
        make_pdf(), "reference.pdf", "application/pdf", admin.id,
    )
    if pdf_pending.get("file_type") == "pdf":
        ok("PDF bytes are accepted for pending assistant discussion")
    else:
        fail("PDF pending input", str(pdf_pending))

    try:
        create_pending_attachment(b"bad", "script.exe", "application/octet-stream", admin.id)
        fail("unsupported type", "EXE upload was accepted")
    except AttachmentError as exc:
        if exc.code == "unsupported_attachment_type":
            ok("Unsupported pending attachment extension is rejected")
        else:
            fail("unsupported type", exc.code)
    try:
        create_pending_attachment(b"x" * (10 * 1024 * 1024 + 1), "huge.pdf", "application/pdf", admin.id)
        fail("size limit", "oversized upload was accepted")
    except AttachmentError as exc:
        if exc.code == "attachment_too_large":
            ok("Pending attachment size limit rejects files over 10 MB")
        else:
            fail("size limit", exc.code)

    stale = create_pending_attachment(make_png(), "stale.png", "image/png", admin.id)
    stale_meta_path = PENDING_UPLOAD_DIR / f"{stale['attachment_id']}.json"
    stale_meta = json.loads(stale_meta_path.read_text())
    stale_meta["created_ts"] = time.time() - PENDING_TTL_SECONDS - 2
    stale_meta_path.write_text(json.dumps(stale_meta))
    if cleanup_stale_pending_attachments() >= 1 and not stale_meta_path.exists():
        ok("Request-time cleanup removes stale pending bytes and sidecars")
    else:
        fail("stale cleanup", "stale metadata still exists")

    print("\n── HTTP upload permissions + non-public pending bytes ──")
    viewer_response = upload_attachment(viewer_http, "viewer.png", make_png(), "image/png")
    if viewer_response.status_code == 403 and viewer_response.json().get("error") == "forbidden":
        ok("Viewer cannot upload assistant attachments")
    else:
        fail("viewer upload", f"{viewer_response.status_code}: {viewer_response.text[:200]}")
    bad_response = upload_attachment(pm_http, "notes.txt", b"hello", "text/plain")
    if bad_response.status_code == 400 and bad_response.json().get("error") == "unsupported_attachment_type":
        ok("HTTP upload rejects unsupported file types")
    else:
        fail("HTTP unsupported", f"{bad_response.status_code}: {bad_response.text[:200]}")
    upload_response = upload_attachment(pm_http, "reference.png", make_png(), "image/png")
    upload_data = upload_response.json()
    attachment_id = (upload_data.get("attachment") or {}).get("attachment_id")
    if upload_response.status_code == 200 and attachment_id:
        ok("PM can upload a pending image attachment")
    else:
        fail("PM image upload", f"{upload_response.status_code}: {upload_response.text[:200]}")
        return done(db)
    if not (os.path.join(crud.UPLOAD_DIR, f"{attachment_id}.png") and os.path.exists(os.path.join(crud.UPLOAD_DIR, f"{attachment_id}.png"))):
        ok("Pending image bytes are not written into public project uploads")
    else:
        fail("pending public storage", "pending image leaked into app/uploads")
    public_probe = requests.get(f"{BASE}/uploads/{attachment_id}.png", timeout=5)
    if public_probe.status_code == 404:
        ok("Pending image cannot be fetched through mounted /uploads")
    else:
        fail("pending public URL", f"status={public_probe.status_code}")

    print("\n── Project discussion proposal + cancel cleanup ──")
    chat = pm_http.post(
        f"{BASE}/ai/chat",
        json={
            "message": "Discuss this reference image.",
            "mode": "intake", "scope": "project", "project_id": pid,
            "attachment_ids": [attachment_id],
        },
        timeout=10,
    )
    chat_data = chat.json()
    proposals = [
        item for item in chat_data.get("tool_calls") or []
        if item.get("name") == "save_pending_attachment"
    ]
    if chat.status_code == 200 and proposals and proposals[0]["result"].get("error") == "confirmation_required":
        ok("Project-scoped attachment discussion creates a save proposal without writing")
    else:
        fail("project save proposal", f"{chat.status_code}: {chat.text[:500]}")
        return done(db)
    if db.query(ProjectFile).filter(ProjectFile.project_id == pid, ProjectFile.original_filename == "reference.png").count() == 0:
        ok("Pending save proposal does not silently create a project_files row")
    else:
        fail("silent file save", "project_files row exists before confirmation")
    proposal_id = proposals[0]["result"]["proposal_id"]
    cancel = pm_http.post(
        f"{BASE}/ai/chat/{chat_data['conversation_id']}/proposals/{proposal_id}/cancel",
        timeout=5,
    )
    if cancel.status_code == 200:
        try:
            get_pending_attachment(attachment_id, pm.id)
            fail("cancel cleanup", "pending bytes remain after cancel")
        except AttachmentError:
            ok("Cancelling a save proposal cleans pending bytes")
    else:
        fail("cancel proposal", f"{cancel.status_code}: {cancel.text[:200]}")

    print("\n── Confirmed persistence + audit ──")
    confirmed_upload = upload_attachment(pm_http, "factory-feedback.png", make_png(), "image/png").json()
    confirmed_id = confirmed_upload["attachment"]["attachment_id"]
    args = {
        "project_id": pid, "attachment_id": confirmed_id,
        "file_category": "factory_feedback", "source_note": "Factory sample reference",
    }
    pending = dispatch("save_pending_attachment", args, db, pm)
    before = db.query(ProjectFile).filter(ProjectFile.project_id == pid).count()
    saved = dispatch("save_pending_attachment", args, db, pm, confirmed=True)
    after = db.query(ProjectFile).filter(ProjectFile.project_id == pid).count()
    project_file = db.query(ProjectFile).filter(ProjectFile.id == saved.get("file_id")).first()
    if pending.get("error") == "confirmation_required" and saved.get("ok") and after == before + 1:
        ok("Confirmed save moves original bytes into project_files exactly once")
    else:
        fail("confirmed persistence", f"pending={pending} saved={saved} counts={before}/{after}")
    disk_path = os.path.join(crud.UPLOAD_DIR, project_file.filename) if project_file else ""
    if project_file and open(disk_path, "rb").read() == make_png():
        ok("Confirmed persistence preserves original attachment bytes")
    else:
        fail("preserve bytes", str(project_file))
    if latest_ai_file_change(db, pid):
        ok("Confirmed attachment save writes ai_chat file-upload audit")
    else:
        fail("attachment audit", "missing changed_by=ai source_type=ai_chat file_upload")
    try:
        get_pending_attachment(confirmed_id, pm.id)
        fail("confirmed pending cleanup", "pending sidecar remains after persistence")
    except AttachmentError:
        ok("Confirmed persistence cleans pending sidecar")

    denied = dispatch("save_pending_attachment", {
        "project_id": pid, "attachment_id": docx_pending["attachment_id"],
    }, db, viewer, confirmed=True)
    if denied.get("error") == "forbidden":
        ok("Viewer cannot confirm assistant attachment persistence")
    else:
        fail("viewer persistence", str(denied))

    print("\n── Global discussion + workspace markup ──")
    global_upload = upload_attachment(admin_http, "global.png", make_png(), "image/png").json()
    global_id = global_upload["attachment"]["attachment_id"]
    global_chat = admin_http.post(
        f"{BASE}/ai/chat",
        json={
            "message": "Discuss this global reference without filing it.",
            "mode": "intake", "scope": "global", "attachment_ids": [global_id],
        },
        timeout=10,
    ).json()
    if not any(item.get("name") == "save_pending_attachment" for item in global_chat.get("tool_calls") or []):
        ok("Global attachment discussion does not auto-target a project save")
    else:
        fail("global auto save", str(global_chat))
    page = pm_http.get(f"{BASE}/projects/{pid}", timeout=5).text
    if 'data-chat-attachment-button' in page and 'accept=".pdf,.docx,.png,.jpg,.jpeg,.webp,.gif"' in page:
        ok("PM workspace renders PDF, DOCX, and image attachment controls")
    else:
        fail("PM attachment markup", "attachment controls missing")
    viewer_page = viewer_http.get(f"{BASE}/projects/{pid}", timeout=5).text
    if 'data-chat-attachment-button' not in viewer_page:
        ok("Viewer workspace hides attachment controls")
    else:
        fail("viewer markup", "viewer attachment controls visible")

    for pending_id, owner_id in (
        (docx_pending["attachment_id"], admin.id),
        (pdf_pending["attachment_id"], admin.id),
        (global_id, admin.id),
    ):
        try:
            discard_pending_attachment(pending_id, owner_id)
        except AttachmentError:
            pass

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
