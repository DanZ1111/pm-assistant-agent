import os
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ProjectFile
import app.crud as crud
from app.dependencies import get_current_user, require_auth, can_edit_project, _RedirectException

router = APIRouter()

UPLOAD_DIR = crud.UPLOAD_DIR

FILE_TYPE_MAP = {
    # images
    "png": "image", "jpg": "image", "jpeg": "image",
    "gif": "image", "webp": "image", "svg": "image", "bmp": "image",
    # documents
    "pdf": "pdf",
    "doc": "word", "docx": "word",
    "xls": "excel", "xlsx": "excel",
}


def detect_file_type(filename: str, content_type: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in FILE_TYPE_MAP:
        return FILE_TYPE_MAP[ext]
    ct = (content_type or "").lower()
    if "image" in ct:
        return "image"
    if "pdf" in ct:
        return "pdf"
    if "word" in ct or "document" in ct:
        return "word"
    if "excel" in ct or "spreadsheet" in ct:
        return "excel"
    return "other"


@router.post("/projects/{project_id}/files")
async def file_upload(
    request: Request,
    project_id: int,
    file: UploadFile = File(...),
    file_category: str = Form("other"),
    source_note: str = Form(""),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not can_edit_project(current_user, project):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    file_type = detect_file_type(file.filename, file.content_type or "")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    disk_path = os.path.join(UPLOAD_DIR, unique_name)

    content = await file.read()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(disk_path, "wb") as f:
        f.write(content)

    crud.upload_file(
        db,
        project_id=project_id,
        filename=unique_name,
        original_filename=file.filename,
        file_path=f"uploads/{unique_name}",
        file_type=file_type,
        file_category=file_category,
        file_size=len(content),
        source_note=source_note.strip() or None,
    )

    return RedirectResponse(url=f"/projects/{project_id}#files", status_code=303)


@router.get("/projects/{project_id}/files/{file_id}/download")
def file_download(request: Request, project_id: int, file_id: int, db: Session = Depends(get_db)):
    """Build 16 — guarded download route. Used by Quotation section so
    viewers can't grab files whose category requires PM+. For non-quotation
    files this just redirects to the existing /uploads/<name> static URL."""
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response
    pf = db.query(ProjectFile).filter(
        ProjectFile.id == file_id, ProjectFile.project_id == project_id,
    ).first()
    if not pf:
        raise HTTPException(status_code=404, detail="File not found")
    if pf.file_category == "quotation" and current_user.role not in ("admin", "pm"):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)
    disk_path = os.path.join(UPLOAD_DIR, pf.filename)
    if not os.path.exists(disk_path):
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(disk_path, filename=pf.original_filename or pf.filename)


@router.post("/projects/{project_id}/files/{file_id}/delete")
def file_delete(request: Request, project_id: int, file_id: int, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response
    project = crud.get_project(db, project_id)
    if not project or not can_edit_project(current_user, project):
        return RedirectResponse(url=f"/projects/{project_id}#files", status_code=303)
    deleted = crud.delete_file(db, file_id, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")
    return RedirectResponse(url=f"/projects/{project_id}#files", status_code=303)
