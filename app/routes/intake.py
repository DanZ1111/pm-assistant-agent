import os
import types
import uuid
from datetime import date
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Project
import app.crud as crud
from app.ai.parser import (
    extract_project_fields, extract_from_pdf, extract_from_image,
    extract_intake, extract_batch_from_workbook_text,
)
from app.ai.excel_parser import extract_from_workbook
from app.ai.matching import find_best_match, MATCH_THRESHOLD
from app.crud import IDEA_TYPES, IDEA_SOURCES
from app.routes.files import detect_file_type
from app.dependencies import get_current_user, require_auth, can_use_ai_intake, _RedirectException
from app.i18n import i18n_context

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

UPLOAD_DIR = crud.UPLOAD_DIR

SUPPORTED_INTAKE_TYPES = {"image", "pdf", "excel", "csv"}


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


def _ai_panel_response(request, current_user, db=None, **overrides):
    """Build 22 — render the AI-Assisted panel inside /projects/new with
    the AI tab active. Fills in safe defaults for any intake context key
    the caller doesn't supply.

    Build 30A — when a `db` Session is supplied, also mint a fresh
    submission_token so the rendered preview form can POST idempotently.
    """
    submission_token = ""
    if db is not None and current_user is not None:
        submission_token = crud.mint_creation_token(db, current_user.id)
    ctx = {
        # project_form.html scaffolding
        "project": None,
        "is_edit": False,
        "initial_tab": "ai",
        "current_user": current_user,
        "submission_token": submission_token,
        # AI intake panel defaults
        "proposed": None,
        "proposed_batch": None,  # Build 30B — populated on Excel/CSV batch extract
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
        "classification": None,
        "idea_fields": None,
        "idea_types": IDEA_TYPES,
        "idea_sources": IDEA_SOURCES,
        **i18n_context(request, current_user),
    }
    ctx.update(overrides)
    return templates.TemplateResponse(request, "project_form.html", ctx)


@router.get("/ai/intake")
def intake_form_redirect():
    """Build 22 — legacy URL preserved as a 303 redirect to the AI tab on
    the consolidated Create Project page. Bookmarks and old tests still work.
    """
    return RedirectResponse(url="/projects/new?tab=ai", status_code=303)


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
        return _ai_panel_response(request, current_user, db=db,
            raw_text=raw_text,
            error="Please enter some text to extract from.")

    # Dual-mode classification: project vs idea
    result = extract_intake(raw_text)
    if "_error" in result:
        return _ai_panel_response(request, current_user, db=db,
            raw_text=raw_text,
            error=f"AI extraction failed: {result['_error']}")

    classification = result["classification"]
    project_fields = result["project_fields"] or {}
    idea_fields = result["idea_fields"] or {}

    crud.save_ai_message(db, None, "user", raw_text, None)
    crud.save_ai_message(db, None, "assistant", str(result),
                         {"classification": classification,
                          "project_fields": project_fields,
                          "idea_fields": idea_fields})

    # When classified as project, run health + match. When idea, skip.
    health = None
    matched_project = None
    match_score = 0.0
    if classification == "project":
        health = _health_from_dict(project_fields)
        matched_project, match_score = _find_match(project_fields, db)

    # `proposed` is the project_fields dict (for backward compat with template),
    # idea_fields is passed separately
    return _ai_panel_response(request, current_user, db=db,
        proposed=project_fields, raw_text=raw_text, health=health,
        matched_project=matched_project, match_score=match_score,
        classification=classification, idea_fields=idea_fields)


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
        return _ai_panel_response(request, current_user, db=db, error="No file selected.")

    file_type = detect_file_type(file.filename, file.content_type or "")

    if file_type not in SUPPORTED_INTAKE_TYPES:
        return _ai_panel_response(request, current_user, db=db,
            error=f"Unsupported file type '{file_type}'. Upload a PDF, image, Excel (.xlsx/.xlsm/.xls), or CSV.")

    # Save to UPLOAD_DIR immediately (same pattern as files.py)
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    disk_path = os.path.join(UPLOAD_DIR, unique_name)
    content = await file.read()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(disk_path, "wb") as f_out:
        f_out.write(content)

    # ── Build 30B — Excel / CSV batch path ────────────────────────────────
    if file_type in ("excel", "csv"):
        wb_result = extract_from_workbook(disk_path)
        if "_error" in wb_result:
            os.remove(disk_path)
            return _ai_panel_response(request, current_user, db=db,
                error=f"Workbook parsing failed: {wb_result['_error']}")
        ai_result = extract_batch_from_workbook_text(wb_result["workbook_text"])
        if "_error" in ai_result:
            os.remove(disk_path)
            return _ai_panel_response(request, current_user, db=db,
                error=f"Batch extraction failed: {ai_result['_error']}")
        projects_raw = ai_result.get("projects", [])
        # Match each candidate row against existing projects so the review
        # table can show "matches: Existing Project X (87% similarity)"
        # and default that row's action to Skip.
        proposed_batch = []
        for row in projects_raw:
            match, score = _find_match(row, db)
            proposed_batch.append({
                "fields": row,
                "match_project_id": match.id if match else None,
                "match_project_name": match.name if match else None,
                "match_score": score,
            })
        crud.save_ai_message(db, None, "user", f"[Workbook upload: {file.filename}]", None)
        crud.save_ai_message(db, None, "assistant",
            f"Extracted {len(proposed_batch)} project candidate(s) from {file.filename}.",
            {"workbook_filename": file.filename, "project_count": len(proposed_batch),
             "kind": wb_result.get("kind")})
        return _ai_panel_response(request, current_user, db=db,
            proposed_batch=proposed_batch,
            uploaded_filename=unique_name,
            uploaded_original_filename=file.filename,
            uploaded_file_type=file_type,
            uploaded_file_category=file_category,
            classification="project",
        )

    # ── PDF / image single-project path (unchanged) ──────────────────────
    ai_summary = ""
    raw_text_from_file = ""

    if file_type == "pdf":
        result = extract_from_pdf(disk_path)
        if "_error" in result:
            os.remove(disk_path)
            return _ai_panel_response(request, current_user, db=db,
                error=f"PDF extraction failed: {result['_error']}")
        extracted = result["extracted"]
        raw_text_from_file = result.get("raw_text", "")
        ai_summary = raw_text_from_file[:500] if raw_text_from_file else ""

    else:  # image
        result = extract_from_image(disk_path)
        if "_error" in result:
            os.remove(disk_path)
            return _ai_panel_response(request, current_user, db=db,
                error=f"Image analysis failed: {result['_error']}")
        extracted = result["extracted"]
        ai_summary = result.get("ai_summary", "")

    health = _health_from_dict(extracted)

    crud.save_ai_message(db, None, "user", f"[File upload: {file.filename}]", None)
    crud.save_ai_message(db, None, "assistant", str(extracted),
                         {"extracted_fields": extracted, "ai_summary": ai_summary, "file_type": file_type})

    matched_project, match_score = _find_match(extracted, db)

    return _ai_panel_response(request, current_user, db=db,
        proposed=extracted,
        raw_text=raw_text_from_file,
        health=health,
        uploaded_filename=unique_name,
        uploaded_original_filename=file.filename,
        uploaded_file_type=file_type,
        uploaded_file_category=file_category,
        uploaded_ai_summary=ai_summary,
        matched_project=matched_project,
        match_score=match_score,
        classification="project",  # file extractions are always project-classified
    )


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
    submission_token: str = Form(""),
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
        return _ai_panel_response(request, current_user, db=db,
            raw_text=raw_text,
            error="Project name is required to confirm.",
            uploaded_filename=uploaded_filename,
            uploaded_original_filename=uploaded_original_filename,
            uploaded_file_type=uploaded_file_type,
            uploaded_file_category=uploaded_file_category,
            uploaded_ai_summary=uploaded_ai_summary)

    # Build 30A — default blank PM to the AI-intake submitter; normalize
    # display-name typed into the PM field when unambiguous.
    pm_value = (product_manager or "").strip()
    if not pm_value:
        pm_value = current_user.username
    else:
        canonical = crud.normalize_pm_value(db, pm_value)
        if canonical:
            pm_value = canonical

    data = {
        "name": name,
        "brand": brand.strip() or None,
        "sku": sku.strip() or None,
        "product_type": product_type.strip() or None,
        "product_manager": pm_value or None,
        "engineer": engineer.strip() or None,
        "factory": factory.strip() or None,
        "target_factory_cost_text": target_factory_cost.strip() or None,
        "target_factory_cost": crud.parse_simple_usd_price(target_factory_cost),
        "target_msrp_text": target_msrp.strip() or None,
        "target_msrp": crud.parse_simple_usd_price(target_msrp),
        "planned_launch_date": _parse_date(planned_launch_date),
        "project_thesis": project_thesis.strip() or None,
        "status": "active",
    }

    # ── Update existing project ──────────────────────────────────────────────
    # Update path is naturally idempotent (no new row inserted), so the
    # submission token only gates the CREATE path below.
    if action == "update" and project_id.isdigit():
        pid = int(project_id)
        update_data = {k: v for k, v in data.items() if v is not None and k != "status"}
        project = crud.update_project(db, pid, update_data, changed_by="ai")
        if not project:
            return _ai_panel_response(request, current_user, db=db,
                raw_text=raw_text,
                error=f"Project {pid} not found.")
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

    # ── Create new project (Build 30A: token-gated) ─────────────────────────
    result = crud.create_project_with_idempotency(
        db, data, prototype_rounds, submission_token, current_user.id,
    )
    if result.status == "duplicate":
        return RedirectResponse(url=f"/projects/{result.project_id}", status_code=303)
    if result.status == "invalid":
        return _ai_panel_response(request, current_user, db=db,
            raw_text=raw_text,
            error="This intake session expired. Please reload the page and try again.")
    project = result.project

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


# ── Idea confirmation (dual-mode intake) ─────────────────────────────────────

@router.post("/ai/intake/confirm-idea")
def intake_confirm_idea(
    request: Request,
    raw_text: str = Form(""),
    name: str = Form(""),
    description: str = Form(""),
    idea_type: str = Form("other"),
    source: str = Form("other"),
    source_detail: str = Form(""),
    contributor: str = Form(""),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response
    if not can_use_ai_intake(current_user):
        return RedirectResponse(url="/ideas", status_code=303)
    name = name.strip()
    if not name:
        return _ai_panel_response(request, current_user, db=db,
            raw_text=raw_text,
            error="Idea name is required to confirm.",
            classification="idea")

    data = {
        "name": name,
        "description": description,
        "idea_type": idea_type,
        "source": source,
        "source_detail": source_detail,
        "contributor": contributor or (current_user.display_name or current_user.username),
    }
    idea = crud.create_idea(db, data, contributor_user_id=current_user.id)
    crud.save_ai_message(db, None, "user", raw_text or "(idea intake)", None)
    crud.save_ai_message(
        db, None, "assistant",
        f"Created idea '{idea.serial_number}: {idea.name}' from AI intake.",
        {"source": "intake_confirm_idea", "idea_id": idea.id},
    )
    return RedirectResponse(url=f"/ideas?highlight={idea.id}", status_code=303)


# ---------------------------------------------------------------------------
# Build 30B — Excel batch confirm
# ---------------------------------------------------------------------------

@router.post("/ai/intake/confirm-batch")
async def intake_confirm_batch(
    request: Request,
    submission_token: str = Form(""),
    prototype_rounds: str = Form("single"),
    db: Session = Depends(get_db),
):
    """Build 30B — commit N reviewed Excel rows in one atomic batch.

    Form encoding: the review table posts arrays of parallel fields, indexed
    by row order (row_action[], row_name[], row_brand[], ...). Rows whose
    row_action is "skip" are dropped server-side; "create" and
    "create_anyway" rows pass through; "update_existing" routes to
    update_project() with the matched project's id.

    Single submission_token covers the whole batch — a double-click on Save
    Batch redirects to /my-projects (the prior batch's resulting page)
    rather than re-inserting.
    """
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response
    if not can_use_ai_intake(current_user):
        return RedirectResponse(url="/projects", status_code=303)

    form = await request.form()

    def _list(field: str) -> list[str]:
        # form.getlist returns [] when the field is absent; values are str
        # (or UploadFile if multipart — not the case here).
        return [v if isinstance(v, str) else "" for v in form.getlist(field)]

    actions = _list("row_action")
    names = _list("row_name")
    brands = _list("row_brand")
    skus = _list("row_sku")
    product_types = _list("row_product_type")
    pms = _list("row_product_manager")
    engineers = _list("row_engineer")
    factories = _list("row_factory")
    target_costs = _list("row_target_factory_cost")
    target_msrps = _list("row_target_msrp")
    launch_dates = _list("row_planned_launch_date")
    thesises = _list("row_project_thesis")
    match_ids = _list("row_match_project_id")

    n = len(actions)
    if n == 0:
        return _ai_panel_response(request, current_user, db=db,
            error="No rows submitted. Please re-upload the workbook.")

    # Default-pad shorter parallel arrays to n
    def _pad(arr): return arr + [""] * (n - len(arr)) if len(arr) < n else arr
    names = _pad(names); brands = _pad(brands); skus = _pad(skus)
    product_types = _pad(product_types); pms = _pad(pms); engineers = _pad(engineers)
    factories = _pad(factories); target_costs = _pad(target_costs)
    target_msrps = _pad(target_msrps); launch_dates = _pad(launch_dates)
    thesises = _pad(thesises); match_ids = _pad(match_ids)

    # Build per-row create payloads (skipping rows the user marked "skip")
    rows_to_create: list[dict] = []
    updates_done = 0
    skipped_explicit = 0
    skipped_reasons: list[str] = []

    for i in range(n):
        action = (actions[i] or "skip").strip().lower()
        if action == "skip":
            skipped_explicit += 1
            continue
        # PM default + display_name normalization (Build 30A pattern)
        pm_value = (pms[i] or "").strip()
        if not pm_value:
            pm_value = current_user.username
        else:
            canonical = crud.normalize_pm_value(db, pm_value)
            if canonical:
                pm_value = canonical
        data = {
            "name": (names[i] or "").strip() or None,
            "brand": (brands[i] or "").strip() or None,
            "sku": (skus[i] or "").strip() or None,
            "product_type": (product_types[i] or "").strip() or None,
            "product_manager": pm_value or None,
            "engineer": (engineers[i] or "").strip() or None,
            "factory": (factories[i] or "").strip() or None,
            "target_factory_cost_text": (target_costs[i] or "").strip() or None,
            "target_factory_cost": crud.parse_simple_usd_price(target_costs[i]),
            "target_msrp_text": (target_msrps[i] or "").strip() or None,
            "target_msrp": crud.parse_simple_usd_price(target_msrps[i]),
            "planned_launch_date": _parse_date(launch_dates[i]),
            "project_thesis": (thesises[i] or "").strip() or None,
            "status": "active",
        }
        if action == "update_existing" and match_ids[i].isdigit():
            pid = int(match_ids[i])
            update_data = {k: v for k, v in data.items() if v is not None and k != "status"}
            project = crud.update_project(db, pid, update_data, changed_by="ai")
            if project:
                updates_done += 1
            continue
        # "create" or "create_anyway" — both flow through batch create
        rows_to_create.append(data)

    result = crud.create_projects_batch_with_idempotency(
        db, rows_to_create, prototype_rounds, submission_token, current_user.id,
    )
    if result.status == "invalid":
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired submission token. Please re-upload the workbook and try again.",
        )
    if result.status == "duplicate":
        return RedirectResponse(url=f"/my-projects?imported=0&duplicate=1", status_code=303)

    created_n = len(result.projects)
    skipped_n = len(result.skipped) + skipped_explicit
    summary = (
        f"Batch import: {created_n} created"
        + (f", {updates_done} updated" if updates_done else "")
        + (f", {skipped_n} skipped" if skipped_n else "")
        + "."
    )
    for project in result.projects:
        crud.save_ai_message(db, project.id, "user", "[Batch import row]", None)
        crud.save_ai_message(db, project.id, "assistant", summary,
            {"source": "intake_batch_confirm"})
    return RedirectResponse(
        url=f"/my-projects?imported={created_n}&updated={updates_done}&skipped={skipped_n}",
        status_code=303,
    )
