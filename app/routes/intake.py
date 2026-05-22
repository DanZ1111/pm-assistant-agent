import os
import types
import uuid
from datetime import date
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project
import app.crud as crud
from app.ai.parser import extract_project_fields, extract_from_pdf, extract_from_image
from app.ai.matching import find_best_match, MATCH_THRESHOLD
from app.routes.files import detect_file_type
from app.dependencies import get_current_user, require_auth, can_use_ai_intake, _RedirectException

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = crud.UPLOAD_DIR

SUPPORTED_INTAKE_TYPES = {"image", "pdf"}


def _parse_float(val: str) -> float | None:
    if not val or not val.strip():
        return None
    try:
        return float(val.strip().replace(",", ""))
    except ValueError:
        return None


def _parse_date(val: str) -> date | None:
    if not val or not val.strip():
        return None
    try:
        return date.fromisoformat(val.strip())
    except ValueError:
        return None


def _find_match(extracted: dict, db: Session):
    """Return (matched_project, score) if above threshold, else (None, 0.0)."""
    candidate = extracted.get("name", "")
    if not candidate:
        return None, 0.0
    projects = db.query(Project).filter(Project.status != "archived").all()
    project, score = find_best_match(candidate, projects)
    if score >= MATCH_THRESHOLD:
        return project, round(score, 2)
    return None, 0.0


def _health_from_dict(extracted: dict):
    proj_ns = types.SimpleNamespace(
        brand=extracted.get("brand"),
        product_manager=extracted.get("product_manager"),
        engineer=extracted.get("engineer"),
        factory=extracted.get("factory"),
        target_factory_cost=extracted.get("target_factory_cost"),
        target_msrp=extracted.get("target_msrp"),
        planned_launch_date=extracted.get("planned_launch_date"),
        project_thesis=extracted.get("project_thesis"),
        sku=extracted.get("sku"),
        product_type=extracted.get("product_type"),
    )
    return crud.get_project_health(proj_ns, [], [])


@router.get("/ai/intake", response_class=HTMLResponse)
def intake_form(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response
    if not can_use_ai_intake(current_user):
        return RedirectResponse(url="/projects", status_code=303)

    return templates.TemplateResponse(request, "intake.html", {
        "proposed": None,
        "raw_text": "",
        "health": None,
        "error": None,
        "uploaded_filename": "",
        "uploaded_original_filename": "",
        "uploaded_file_type": "",
        "uploaded_file_category": "",
        "uploaded_ai_summary": "",
        "matched_project": None,
        "match_score": 0.0,
        "current_user": current_user,
    })


@router.post("/ai/intake/extract", response_class=HTMLResponse)
async def intake_extract(
    request: Request,
    raw_text: str = Form(""),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response
    if not can_use_ai_intake(current_user):
        return RedirectResponse(url="/projects", status_code=303)
    if not raw_text.strip():
        return templates.TemplateResponse(request, "intake.html", {
            "proposed": None, "raw_text": raw_text, "health": None,
            "error": "Please enter some text to extract from.",
            "uploaded_filename": "", "uploaded_original_filename": "",
            "uploaded_file_type": "", "uploaded_file_category": "", "uploaded_ai_summary": "",
        })

    extracted = extract_project_fields(raw_text)

    if "_error" in extracted:
        return templates.TemplateResponse(request, "intake.html", {
            "proposed": None, "raw_text": raw_text, "health": None,
            "error": f"AI extraction failed: {extracted['_error']}",
            "uploaded_filename": "", "uploaded_original_filename": "",
            "uploaded_file_type": "", "uploaded_file_category": "", "uploaded_ai_summary": "",
        })

    health = _health_from_dict(extracted)
    crud.save_ai_message(db, None, "user", raw_text, None)
    crud.save_ai_message(db, None, "assistant", str(extracted), {"extracted_fields": extracted})

    matched_project, match_score = _find_match(extracted, db)

    return templates.TemplateResponse(request, "intake.html", {
        "proposed": extracted, "raw_text": raw_text, "health": health, "error": None,
        "uploaded_filename": "", "uploaded_original_filename": "",
        "uploaded_file_type": "", "uploaded_file_category": "", "uploaded_ai_summary": "",
        "matched_project": matched_project, "match_score": match_score,
    })


@router.post("/ai/intake/extract-file", response_class=HTMLResponse)
async def intake_extract_file(
    request: Request,
    file: UploadFile = File(...),
    file_category: str = Form("reference"),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response
    if not can_use_ai_intake(current_user):
        return RedirectResponse(url="/projects", status_code=303)
    if not file or not file.filename:
        return templates.TemplateResponse(request, "intake.html", {
            "proposed": None, "raw_text": "", "health": None,
            "error": "No file selected.",
            "uploaded_filename": "", "uploaded_original_filename": "",
            "uploaded_file_type": "", "uploaded_file_category": "", "uploaded_ai_summary": "",
        })

    file_type = detect_file_type(file.filename, file.content_type or "")

    if file_type not in SUPPORTED_INTAKE_TYPES:
        return templates.TemplateResponse(request, "intake.html", {
            "proposed": None, "raw_text": "", "health": None,
            "error": f"Unsupported file type '{file_type}'. Upload a PDF or image (PNG, JPG, WEBP).",
            "uploaded_filename": "", "uploaded_original_filename": "",
            "uploaded_file_type": "", "uploaded_file_category": "", "uploaded_ai_summary": "",
        })

    # Save to UPLOAD_DIR immediately (same pattern as files.py)
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    disk_path = os.path.join(UPLOAD_DIR, unique_name)
    content = await file.read()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(disk_path, "wb") as f_out:
        f_out.write(content)

    # Extract fields + summary from the file
    ai_summary = ""
    raw_text_from_file = ""

    if file_type == "pdf":
        result = extract_from_pdf(disk_path)
        if "_error" in result:
            os.remove(disk_path)
            return templates.TemplateResponse(request, "intake.html", {
                "proposed": None, "raw_text": "", "health": None,
                "error": f"PDF extraction failed: {result['_error']}",
                "uploaded_filename": "", "uploaded_original_filename": "",
                "uploaded_file_type": "", "uploaded_file_category": "", "uploaded_ai_summary": "",
            })
        extracted = result["extracted"]
        raw_text_from_file = result.get("raw_text", "")
        ai_summary = raw_text_from_file[:500] if raw_text_from_file else ""

    else:  # image
        result = extract_from_image(disk_path)
        if "_error" in result:
            os.remove(disk_path)
            return templates.TemplateResponse(request, "intake.html", {
                "proposed": None, "raw_text": "", "health": None,
                "error": f"Image analysis failed: {result['_error']}",
                "uploaded_filename": "", "uploaded_original_filename": "",
                "uploaded_file_type": "", "uploaded_file_category": "", "uploaded_ai_summary": "",
            })
        extracted = result["extracted"]
        ai_summary = result.get("ai_summary", "")

    health = _health_from_dict(extracted)

    crud.save_ai_message(db, None, "user", f"[File upload: {file.filename}]", None)
    crud.save_ai_message(db, None, "assistant", str(extracted),
                         {"extracted_fields": extracted, "ai_summary": ai_summary, "file_type": file_type})

    matched_project, match_score = _find_match(extracted, db)

    return templates.TemplateResponse(request, "intake.html", {
        "proposed": extracted,
        "raw_text": raw_text_from_file,
        "health": health,
        "error": None,
        "uploaded_filename": unique_name,
        "uploaded_original_filename": file.filename,
        "uploaded_file_type": file_type,
        "uploaded_file_category": file_category,
        "uploaded_ai_summary": ai_summary,
        "matched_project": matched_project,
        "match_score": match_score,
    })


@router.post("/ai/intake/confirm")
def intake_confirm(
    request: Request,
    raw_text: str = Form(""),
    name: str = Form(""),
    brand: str = Form(""),
    sku: str = Form(""),
    product_type: str = Form(""),
    product_manager: str = Form(""),
    engineer: str = Form(""),
    factory: str = Form(""),
    target_factory_cost: str = Form(""),
    target_msrp: str = Form(""),
    planned_launch_date: str = Form(""),
    project_thesis: str = Form(""),
    prototype_rounds: str = Form("single"),
    uploaded_filename: str = Form(""),
    uploaded_original_filename: str = Form(""),
    uploaded_file_type: str = Form(""),
    uploaded_file_category: str = Form("reference"),
    uploaded_ai_summary: str = Form(""),
    project_id: str = Form(""),
    action: str = Form("create"),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response
    if not can_use_ai_intake(current_user):
        return RedirectResponse(url="/projects", status_code=303)

    name = name.strip()
    if not name:
        return templates.TemplateResponse(request, "intake.html", {
            "proposed": None, "raw_text": raw_text, "health": None,
            "error": "Project name is required to confirm.",
            "uploaded_filename": uploaded_filename,
            "uploaded_original_filename": uploaded_original_filename,
            "uploaded_file_type": uploaded_file_type,
            "uploaded_file_category": uploaded_file_category,
            "uploaded_ai_summary": uploaded_ai_summary,
            "matched_project": None, "match_score": 0.0,
        })

    data = {
        "name": name,
        "brand": brand.strip() or None,
        "sku": sku.strip() or None,
        "product_type": product_type.strip() or None,
        "product_manager": product_manager.strip() or None,
        "engineer": engineer.strip() or None,
        "factory": factory.strip() or None,
        "target_factory_cost": _parse_float(target_factory_cost),
        "target_msrp": _parse_float(target_msrp),
        "planned_launch_date": _parse_date(planned_launch_date),
        "project_thesis": project_thesis.strip() or None,
        "status": "active",
    }

    # ── Update existing project ──────────────────────────────────────────────
    if action == "update" and project_id.isdigit():
        pid = int(project_id)
        update_data = {k: v for k, v in data.items() if v is not None and k != "status"}
        project = crud.update_project(db, pid, update_data, changed_by="ai")
        if not project:
            return templates.TemplateResponse(request, "intake.html", {
                "proposed": None, "raw_text": raw_text, "health": None,
                "error": f"Project {pid} not found.",
                "uploaded_filename": "", "uploaded_original_filename": "",
                "uploaded_file_type": "", "uploaded_file_category": "", "uploaded_ai_summary": "",
                "matched_project": None, "match_score": 0.0,
            })
        crud.write_change(
            db, project.id, "event_note", changed_by="ai",
            summary="Project updated via AI intake.",
            source_type="ai_chat",
        )
        db.commit()
        crud.save_ai_message(db, project.id, "user", raw_text or "(update)", None)
        crud.save_ai_message(db, project.id, "assistant",
            f"Updated project '{project.name}' via AI intake.",
            {"source": "intake_update", "fields_updated": list(update_data.keys())})
        return RedirectResponse(url=f"/projects/{project.id}", status_code=303)

    # ── Create new project ───────────────────────────────────────────────────
    project = crud.create_project(db, data, prototype_rounds=prototype_rounds)

    # Attach uploaded file to the new project if one was provided
    if uploaded_filename and uploaded_original_filename:
        disk_path = os.path.join(UPLOAD_DIR, uploaded_filename)
        if os.path.exists(disk_path):
            file_size = os.path.getsize(disk_path)
            crud.upload_file(
                db,
                project_id=project.id,
                filename=uploaded_filename,
                original_filename=uploaded_original_filename,
                file_path=f"uploads/{uploaded_filename}",
                file_type=uploaded_file_type or "other",
                file_category=uploaded_file_category or "reference",
                file_size=file_size,
                source_note="Uploaded via AI intake",
                ai_summary=uploaded_ai_summary or None,
            )

    crud.save_ai_message(db, project.id, "user", raw_text or "(file upload)", None)
    crud.save_ai_message(
        db, project.id, "assistant",
        f"Created project '{name}' from AI intake.",
        {"source": "intake_confirm", "fields_set": [k for k, v in data.items() if v is not None]},
    )

    crud.write_change(
        db, project.id, "event_note",
        changed_by="ai",
        summary="Project created via AI intake.",
        source_type="ai_chat",
    )
    db.commit()

    return RedirectResponse(url=f"/projects/{project.id}", status_code=303)
