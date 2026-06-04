import os
import uuid
from fastapi import APIRouter, Depends, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date, datetime

from app.database import get_db
from app.models import Project
import app.crud as crud
from app.ai.parser import extract_thesis_and_inspirations
from app.ai.matching import find_best_match, MATCH_THRESHOLD
from app.dependencies import (
    get_current_user, require_auth, require_admin,
    can_edit_project, can_delete_project,
    can_view_sensitive_fields, can_view_journal, can_view_costs,
    can_use_ai_intake,
    _RedirectException
)
from app.i18n import i18n_context

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def parse_date(val: str) -> date | None:
    if not val or not val.strip():
        return None
    try:
        return date.fromisoformat(val.strip())
    except ValueError:
        return None


def parse_float(val: str) -> float | None:
    if not val or not val.strip():
        return None
    try:
        return float(val.strip().replace(",", ""))
    except ValueError:
        return None


# Build 15 — map an uploaded business-plan file extension to the dispatch
# key the parser uses. The generic project_files.file_type column groups
# .doc + .docx as "word" already; for extraction we need finer granularity
# so we resolve from extension here.
_BUSINESS_PLAN_TYPES = {
    "pdf": "pdf",
    "docx": "docx",
    "doc": "doc",
    "png": "image", "jpg": "image", "jpeg": "image", "webp": "image", "gif": "image",
}


def _resolve_business_plan_type(filename: str) -> str | None:
    if not filename or "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].lower()
    return _BUSINESS_PLAN_TYPES.get(ext)


def _pick_latest_overview_visual(renderings: list, prototype_photos: list):
    """Build 04: choose the Overview visual from existing ProjectFile lists.

    Lists are already newest-first by ProjectFile.uploaded_at. "Latest" is
    upload time only; comments or other engagement do not affect ordering.
    """
    for f in renderings:
        if f.file_type == "image":
            return f
    for f in prototype_photos:
        if f.file_type == "image":
            return f
    candidates = list(renderings) + list(prototype_photos)
    return sorted(
        candidates,
        key=lambda f: f.uploaded_at or datetime.min,
        reverse=True,
    )[0] if candidates else None


def _save_uploaded_business_plan(
    db: Session, project_id: int, upload: UploadFile, content: bytes,
) -> tuple:
    """Save the uploaded business plan to disk + DB. Returns (ProjectFile, dispatch_type)."""
    ext = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
    unique_name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    os.makedirs(crud.UPLOAD_DIR, exist_ok=True)
    disk_path = os.path.join(crud.UPLOAD_DIR, unique_name)
    with open(disk_path, "wb") as fh:
        fh.write(content)

    # generic file_type for the file row (matches files.py convention)
    if ext == "pdf":
        file_type = "pdf"
    elif ext in ("doc", "docx"):
        file_type = "word"
    elif ext in ("png", "jpg", "jpeg", "webp", "gif"):
        file_type = "image"
    else:
        file_type = "other"

    pf = crud.upload_file(
        db,
        project_id=project_id,
        filename=unique_name,
        original_filename=upload.filename,
        file_path=f"uploads/{unique_name}",
        file_type=file_type,
        file_category="business_plan",
        file_size=len(content),
    )
    return pf, _resolve_business_plan_type(upload.filename)


# ---------------------------------------------------------------------------
# All Projects
# ---------------------------------------------------------------------------

@router.get("/projects", response_class=HTMLResponse)
def projects_list(
    request: Request,
    status: str = "all",
    brand: str = None,
    search: str = None,
    delayed: str = None,
    needs_info: str = None,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    enriched = crud.get_projects_enriched(db, status=status, brand=brand, search=search)

    if delayed:
        enriched = [e for e in enriched if e["delay"]]
    elif needs_info:
        enriched = [e for e in enriched if e["health"]["needs_info"]]

    if delayed:
        current_filter = "delayed"
    elif needs_info:
        current_filter = "needs_info"
    else:
        current_filter = status

    brands = crud.get_all_brands(db)
    all_projects = crud.get_projects(db)
    active_enriched = crud.get_projects_enriched(db, status="active")
    counts = {
        "all": len(all_projects),
        "active": sum(1 for p in all_projects if p.status == "active"),
        "delayed": sum(1 for e in active_enriched if e["delay"]),
        "needs_info": sum(1 for e in active_enriched if e["health"]["needs_info"]),
        "completed": sum(1 for p in all_projects if p.status == "completed"),
        "archived": sum(1 for p in all_projects if p.status == "archived"),
    }
    # Build 19 — banner is delay-only (Needs-Info still surfaces via card badge + filter tab)
    needs_attention = [e for e in active_enriched if e["delay"]]
    phases_due = crud.get_phases_due_this_week(db)

    return templates.TemplateResponse(request, "projects_list.html", {
        "enriched": enriched,
        "brands": brands,
        "counts": counts,
        "needs_attention": needs_attention,
        "phases_due": phases_due,
        "current_status": status,
        "current_filter": current_filter,
        "current_brand": brand or "",
        "search": search or "",
        "current_user": current_user,
        **i18n_context(request, current_user),
    })


# ---------------------------------------------------------------------------
# Build 19 — My Projects (admin + pm only; viewer redirected)
# ---------------------------------------------------------------------------

@router.get("/my-projects", response_class=HTMLResponse)
def my_projects(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response
    if current_user.role not in ("admin", "pm"):
        return RedirectResponse(url="/projects", status_code=303)

    projects = crud.get_projects_for_user(db, current_user)
    # Compute per-project delay + current_stage helpers (lightweight; reuse get_projects_enriched-style).
    rows = []
    for p in projects:
        delay = crud.calculate_delay(p, p.phases)
        rows.append({"project": p, "delay": delay})

    return templates.TemplateResponse(request, "my_projects.html", {
        "rows": rows,
        "current_user": current_user,
        "today": date.today(),
        **i18n_context(request, current_user),
    })


# ---------------------------------------------------------------------------
# Create Project
# ---------------------------------------------------------------------------

@router.get("/projects/new", response_class=HTMLResponse)
def project_new_form(request: Request, tab: str = "manual", db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response
    if current_user.role == "viewer":
        return RedirectResponse(url="/projects", status_code=303)

    # Build 22 — tab=ai opens the AI-Assisted panel; default is Manual Form.
    initial_tab = "ai" if tab == "ai" else "manual"

    # Build 30A — mint a one-shot idempotency token for the Manual Form's POST.
    # Embedded as a hidden input; claim-by-UPDATE on POST prevents duplicate
    # rows when a slow submit gets clicked multiple times.
    submission_token = crud.mint_creation_token(db, current_user.id)

    return templates.TemplateResponse(request, "project_form.html", {
        "project": None,
        "is_edit": False,
        "error": None,
        "current_user": current_user,
        "initial_tab": initial_tab,
        "submission_token": submission_token,
        # Defaults so the AI intake panel renders state-1 (input form)
        "proposed": None,
        "raw_text": "",
        "health": None,
        "uploaded_filename": "",
        "uploaded_original_filename": "",
        "uploaded_file_type": "",
        "uploaded_file_category": "",
        "uploaded_ai_summary": "",
        "matched_project": None,
        "match_score": 0.0,
        "classification": None,
        "idea_fields": None,
        **i18n_context(request, current_user),
    })


@router.post("/projects/new")
async def project_new_submit(
    request: Request,
    name: str = Form(...),
    brand: str = Form(""),
    sku: str = Form(""),
    product_type: str = Form(""),
    project_owner: str = Form(""),
    product_manager: str = Form(""),
    engineer: str = Form(""),
    factory: str = Form(""),
    target_factory_cost: str = Form(""),
    target_msrp: str = Form(""),
    planned_launch_date: str = Form(""),
    project_thesis: str = Form(""),
    prototype_rounds: str = Form("single"),
    submission_token: str = Form(""),
    business_plan: UploadFile = File(None),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response
    if current_user.role == "viewer":
        return RedirectResponse(url="/projects", status_code=303)

    name = name.strip()
    if not name:
        return templates.TemplateResponse(request, "project_form.html", {
            "project": None, "is_edit": False,
            "error": "Project name is required.",
            "current_user": current_user,
            "submission_token": submission_token,
            **i18n_context(request, current_user),
        })

    # Build 30A — default blank PM to the creator's username; normalize
    # display-name typed into the PM field to a canonical username when
    # exactly one user matches (ambiguous typed-in names fall through as-is).
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
        "project_owner": project_owner.strip() or None,
        "product_manager": pm_value or None,
        "engineer": engineer.strip() or None,
        "factory": factory.strip() or None,
        "target_factory_cost_text": target_factory_cost.strip() or None,
        "target_factory_cost": crud.parse_simple_usd_price(target_factory_cost),
        "target_msrp_text": target_msrp.strip() or None,
        "target_msrp": crud.parse_simple_usd_price(target_msrp),
        "planned_launch_date": parse_date(planned_launch_date),
        "project_thesis": project_thesis.strip() or None,
    }

    # Build 30A — claim the idempotency token atomically with the project
    # insert. A racing POST (slow submit + double-click) sees rowcount=0
    # and gets redirected to the original project instead of duplicating.
    result = crud.create_project_with_idempotency(
        db, data, prototype_rounds, submission_token, current_user.id,
    )
    if result.status == "duplicate":
        return RedirectResponse(url=f"/projects/{result.project_id}", status_code=303)
    if result.status == "invalid":
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired submission token. Please reload the New Project page and try again.",
        )
    project = result.project

    # Build 15 — optional business plan upload + thesis extraction
    if business_plan is not None and business_plan.filename:
        content = await business_plan.read()
        if content:
            pf, dispatch_type = _save_uploaded_business_plan(db, project.id, business_plan, content)
            if dispatch_type is None:
                payload = {"_error": "Unsupported business plan file type. Use PDF, DOCX, DOC, or image."}
            else:
                payload = extract_thesis_and_inspirations(
                    os.path.join(crud.UPLOAD_DIR, pf.filename), dispatch_type,
                )
            extraction = crud.save_thesis_extraction(db, project.id, pf, payload)
            return RedirectResponse(
                url=f"/projects/{project.id}/thesis/preview?extraction_id={extraction.id}",
                status_code=303,
            )

    return RedirectResponse(url=f"/projects/{project.id}", status_code=303)


# ---------------------------------------------------------------------------
# Project Detail
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_detail(request: Request, project_id: int, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    phases = project.phases
    files = project.files
    health = crud.get_project_health(project, phases, files)
    delay = crud.calculate_delay(project, phases)
    changes = sorted(project.changes, key=lambda c: c.changed_at, reverse=True)[:30]
    can_edit = can_edit_project(current_user, project)
    can_delete = can_delete_project(current_user, project)
    can_sensitive = can_view_sensitive_fields(current_user)
    linked_ideas = crud.get_ideas_for_project(db, project_id)
    linked_idea_ids = {li["idea"].id for li in linked_ideas}
    available_ideas = [i for i in crud.get_all_open_ideas(db) if i.id not in linked_idea_ids]

    # v1.1 Build 14: Journal section. Viewer cannot see it at all — only
    # load entries if the user is allowed to view them, so the section
    # never appears even by template accident.
    can_journal = can_view_journal(current_user)
    journal_entries = (
        crud.get_journal_entries_for_project(db, project_id) if can_journal else []
    )
    journal_error = request.query_params.get("journal_error")
    journal_error_entry_id = request.query_params.get("entry_id")

    # Build 15 — latest attached business plan (used for Re-extract button)
    business_plan_file = crud.get_latest_business_plan_file(db, project_id)
    thesis_error = request.query_params.get("thesis_error")

    # Build 16 — variants, packaging/accessory components, quotation files
    variants = crud.get_variants_for_project(db, project_id)
    primary_variant = next((v for v in variants if v.is_primary), None)
    components = crud.get_components_for_project(db, project_id)
    quotation_files = crud.get_quotation_files_for_project(db, project_id)
    can_costs = can_view_costs(current_user)

    # v1.3 Build 05 — group components by variant_id for variant command
    # cards. Project-wide components (variant_id IS NULL) live in [None];
    # variant-specific components live in [v.id]. Single O(C) pass over
    # the already-loaded components list — no new DB query.
    components_by_variant = {None: []}
    for v in variants:
        components_by_variant[v.id] = []
    for c in components:
        components_by_variant.setdefault(c.variant_id, []).append(c)

    # Build 18 — Rendering History + Prototype Photos
    renderings = crud.get_files_by_category(db, project_id, "rendering")
    prototype_photos = crud.get_files_by_category(db, project_id, "prototype_photo")
    latest_overview_visual = _pick_latest_overview_visual(renderings, prototype_photos)

    # Build 17 — Timeline 2.0: plan-change history per phase + error flash
    plan_changes_by_phase = crud.get_plan_changes_by_project(db, project_id)
    timeline_error = request.query_params.get("timeline_error")
    # Find the current "in_progress" phase (for Finish Phase button decoration)
    current_phase = next((p for p in phases if p.status == "in_progress"), None)
    if not current_phase:
        current_phase = next(
            (p for p in sorted(phases, key=lambda x: x.phase_order)
             if p.status not in ("done", "skipped")),
            None,
        )

    # v1.3 Build 06 — Timeline Command Center state.
    # Per V13_BUILD06_EXECUTION_PLAN.md "Backend Honesty Mapping" — derive
    # display-only state from existing phase data in one O(N) pass. No new
    # DB query, no schema change. Blocker and AI Nudge stay placeholders
    # until Build 07.
    today_date = date.today()
    sorted_phases = sorted(phases, key=lambda p: p.phase_order)
    current_id = current_phase.id if current_phase else None
    current_order = current_phase.phase_order if current_phase else None
    phase_strip = []
    for p in sorted_phases:
        if p.status == "done":
            state = "done"
        elif p.status == "skipped":
            state = "skipped"
        elif current_id is not None and p.id == current_id:
            state = "current"
        elif current_order is not None and p.phase_order == current_order + 1:
            state = "next"
        else:
            state = "later"
        phase_strip.append({"phase": p, "state": state})

    # days_left + pressure derivation (Locks 4 & 5 in the plan)
    days_left = None
    days_overdue = None
    pressure_dots = 0
    if current_phase and current_phase.planned_end_date:
        delta = (current_phase.planned_end_date - today_date).days
        if delta < 0:
            days_overdue = -delta
            pressure_dots = 3
        else:
            days_left = delta
            if delta <= 3:
                pressure_dots = 2
            elif delta <= 7:
                pressure_dots = 1

    # health_band (Lock 3): derived from delay + current_phase scheduling
    if delay is None:
        if current_phase and not current_phase.planned_end_date and current_phase.status == "not_started":
            health_band = "not_scheduled"
        else:
            health_band = "on_track"
    elif delay.get("days_late", 0) <= 3:
        health_band = "at_risk"
    else:
        health_band = "delayed"

    command_center_state = {
        "phase_strip": phase_strip,
        "days_left": days_left,
        "days_overdue": days_overdue,
        "pressure_dots": pressure_dots,
        "health_band": health_band,
        "today": today_date,
    }

    return templates.TemplateResponse(request, "project_detail.html", {
        "project": project,
        "phases": phases,
        "files": files,
        "health": health,
        "delay": delay,
        "changes": changes,
        "today": date.today(),
        "current_user": current_user,
        "can_edit": can_edit,
        "can_delete": can_delete,
        "can_sensitive": can_sensitive,
        "linked_ideas": linked_ideas,
        "available_ideas": available_ideas,
        "can_view_journal": can_journal,
        "journal_entries": journal_entries,
        "journal_error": journal_error,
        "journal_error_entry_id": journal_error_entry_id,
        "business_plan_file": business_plan_file,
        "thesis_error": thesis_error,
        "variants": variants,
        "primary_variant": primary_variant,
        "components": components,
        "components_by_variant": components_by_variant,
        "quotation_files": quotation_files,
        "can_view_costs": can_costs,
        "plan_changes_by_phase": plan_changes_by_phase,
        "timeline_error": timeline_error,
        "current_phase": current_phase,
        "command_center_state": command_center_state,
        "can_use_ai_intake_user": can_use_ai_intake(current_user),
        "renderings": renderings,
        "prototype_photos": prototype_photos,
        "latest_overview_visual": latest_overview_visual,
        # Build 21 — for bottom chat scope toggle
        "current_project_id": project.id,
        "current_project_name": project.name,
        **i18n_context(request, current_user),
    })


# ---------------------------------------------------------------------------
# Edit Project
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/edit", response_class=HTMLResponse)
def project_edit_form(request: Request, project_id: int, db: Session = Depends(get_db)):
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

    return templates.TemplateResponse(request, "project_form.html", {
        "project": project,
        "is_edit": True,
        "error": None,
        "current_user": current_user,
        **i18n_context(request, current_user),
    })


@router.post("/projects/{project_id}/edit")
def project_edit_submit(
    request: Request,
    project_id: int,
    name: str = Form(...),
    brand: str = Form(""),
    sku: str = Form(""),
    product_type: str = Form(""),
    project_owner: str = Form(""),
    product_manager: str = Form(""),
    engineer: str = Form(""),
    factory: str = Form(""),
    target_factory_cost: str = Form(""),
    target_msrp: str = Form(""),
    planned_launch_date: str = Form(""),
    project_thesis: str = Form(""),
    status: str = Form("active"),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    project = crud.get_project(db, project_id)
    if not project or not can_edit_project(current_user, project):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)

    name = name.strip()
    if not name:
        return templates.TemplateResponse(request, "project_form.html", {
            "project": project, "is_edit": True,
            "error": "Project name is required.",
            "current_user": current_user,
            **i18n_context(request, current_user),
        })

    data = {
        "name": name,
        "brand": brand.strip() or None,
        "sku": sku.strip() or None,
        "product_type": product_type.strip() or None,
        "project_owner": project_owner.strip() or None,
        "product_manager": product_manager.strip() or None,
        "engineer": engineer.strip() or None,
        "factory": factory.strip() or None,
        "target_factory_cost_text": target_factory_cost.strip() or None,
        "target_factory_cost": crud.parse_simple_usd_price(target_factory_cost),
        "target_msrp_text": target_msrp.strip() or None,
        "target_msrp": crud.parse_simple_usd_price(target_msrp),
        "planned_launch_date": parse_date(planned_launch_date),
        "project_thesis": project_thesis.strip() or None,
        "status": status,
    }
    crud.update_project(db, project_id, data)
    return RedirectResponse(url=f"/projects/{project_id}", status_code=303)


# ---------------------------------------------------------------------------
# Archive / Delete
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/archive")
def project_archive(request: Request, project_id: int, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    project = crud.get_project(db, project_id)
    if project and can_edit_project(current_user, project):
        crud.archive_project(db, project_id)
    return RedirectResponse(url="/projects", status_code=303)


@router.post("/projects/{project_id}/delete")
def project_delete(request: Request, project_id: int, db: Session = Depends(get_db)):
    """Build 30C — permission expanded from admin-only to admin + PM-of-untouched-draft.

    PM scope: PM is the project's product_manager AND every phase is still
    `not_started` with no actual_start_date. Once any phase advances, the
    project leaves draft state and PM must use Archive instead.
    """
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not can_delete_project(current_user, project):
        # Mirrors the pre-30C admin-only behavior for unauthorized callers:
        # 403 rather than a silent redirect, so PMs see why their POST failed
        # if they hit the route directly after a phase advance.
        raise HTTPException(
            status_code=403,
            detail="Cannot delete this project. Admin can delete any project; "
                   "PM can delete only their own projects that have no advanced phases. "
                   "If work has started, use Archive instead.",
        )

    crud.delete_project(db, project_id)
    return RedirectResponse(url="/projects", status_code=303)


# ---------------------------------------------------------------------------
# Phase CRUD
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/phases")
def phase_add(
    request: Request,
    project_id: int,
    phase_name: str = Form(...),
    phase_type: str = Form(""),
    planned_start_date: str = Form(""),
    planned_end_date: str = Form(""),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    project = crud.get_project(db, project_id)
    if project and can_edit_project(current_user, project):
        data = {
            "phase_name": phase_name.strip(),
            "phase_type": phase_type.strip() or None,
            "planned_start_date": parse_date(planned_start_date),
            "planned_end_date": parse_date(planned_end_date),
        }
        crud.add_phase(db, project_id, data)
    return RedirectResponse(url=f"/projects/{project_id}#timeline", status_code=303)


@router.post("/projects/{project_id}/phases/{phase_id}/edit")
def phase_edit(
    request: Request,
    project_id: int,
    phase_id: int,
    phase_name: str = Form(...),
    phase_type: str = Form(""),
    status: str = Form("not_started"),
    planned_start_date: str = Form(""),
    planned_end_date: str = Form(""),
    actual_start_date: str = Form(""),
    actual_end_date: str = Form(""),
    owner: str = Form(""),
    notes: str = Form(""),
    plan_change_reason: str = Form(""),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    project = crud.get_project(db, project_id)
    if project and can_edit_project(current_user, project):
        # Build 17 — if user is changing a plan date, require a reason
        existing = crud.get_phase(db, phase_id)
        if existing:
            new_pstart = parse_date(planned_start_date)
            new_pend = parse_date(planned_end_date)
            plan_changed = (
                (existing.planned_start_date != new_pstart) or
                (existing.planned_end_date != new_pend)
            )
            if plan_changed and not plan_change_reason.strip():
                return RedirectResponse(
                    url=f"/projects/{project_id}?timeline_error=reason_required#timeline",
                    status_code=303,
                )
        data = {
            "phase_name": phase_name.strip(),
            "phase_type": phase_type.strip() or None,
            "status": status,
            "planned_start_date": parse_date(planned_start_date),
            "planned_end_date": parse_date(planned_end_date),
            "actual_start_date": parse_date(actual_start_date),
            "actual_end_date": parse_date(actual_end_date),
            "owner": owner.strip() or None,
            "notes": notes.strip() or None,
        }
        crud.update_phase(
            db, phase_id, data,
            changed_by=current_user.role,
            reason=plan_change_reason,
            changed_by_user_id=current_user.id,
        )
    return RedirectResponse(url=f"/projects/{project_id}#timeline", status_code=303)


@router.post("/projects/{project_id}/phases/{phase_id}/finish")
def phase_finish(
    request: Request,
    project_id: int,
    phase_id: int,
    db: Session = Depends(get_db),
):
    """Build 17 — one-click 'mark phase done + advance next phase'."""
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    project = crud.get_project(db, project_id)
    if project and can_edit_project(current_user, project):
        crud.finish_phase(
            db, phase_id,
            changed_by=current_user.role,
            changed_by_user_id=current_user.id,
        )
    return RedirectResponse(url=f"/projects/{project_id}#timeline", status_code=303)


@router.post("/projects/{project_id}/phases/{phase_id}/delete")
def phase_delete(request: Request, project_id: int, phase_id: int, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    project = crud.get_project(db, project_id)
    if project and can_edit_project(current_user, project):
        crud.delete_phase(db, phase_id)
    return RedirectResponse(url=f"/projects/{project_id}#timeline", status_code=303)


# ---------------------------------------------------------------------------
# Project ↔ Idea linking
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/ideas/link")
def project_link_idea(
    request: Request,
    project_id: int,
    idea_id: int = Form(...),
    note: str = Form(""),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    project = crud.get_project(db, project_id)
    if project and can_edit_project(current_user, project):
        crud.link_idea_to_project(db, project_id, idea_id, current_user.id, note)
    return RedirectResponse(url=f"/projects/{project_id}#inspired-by", status_code=303)


@router.post("/projects/{project_id}/ideas/create-and-link")
def project_create_and_link_idea(
    request: Request,
    project_id: int,
    name: str = Form(""),
    description: str = Form(""),
    idea_type: str = Form("other"),
    source: str = Form("other"),
    source_detail: str = Form(""),
    contributor: str = Form(""),
    notes: str = Form(""),
    link_note: str = Form(""),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    project = crud.get_project(db, project_id)
    if not project or not can_edit_project(current_user, project):
        return RedirectResponse(url=f"/projects/{project_id}#inspired-by", status_code=303)
    name = name.strip()
    if not name:
        return RedirectResponse(url=f"/projects/{project_id}?idea_error=name_required#inspired-by", status_code=303)
    crud.create_and_link_idea(
        db,
        project_id=project_id,
        data={
            "name": name,
            "description": description,
            "idea_type": idea_type,
            "source": source,
            "source_detail": source_detail,
            "contributor": contributor or current_user.display_name or current_user.username,
            "notes": notes,
        },
        contributor_user_id=current_user.id,
        note=link_note,
    )
    return RedirectResponse(url=f"/projects/{project_id}#inspired-by", status_code=303)


@router.post("/projects/{project_id}/ideas/{idea_id}/unlink")
def project_unlink_idea(
    request: Request,
    project_id: int,
    idea_id: int,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    project = crud.get_project(db, project_id)
    if project and can_edit_project(current_user, project):
        crud.unlink_idea_from_project(db, project_id, idea_id)
    return RedirectResponse(url=f"/projects/{project_id}#inspired-by", status_code=303)


# ---------------------------------------------------------------------------
# Build 15 — Business Plan Thesis Extraction (preview-confirm)
# AI extraction is a one-time POST action. The preview page is a pure GET
# render of saved data — refreshing it must NEVER re-trigger the AI call.
# ---------------------------------------------------------------------------

@router.post("/projects/{project_id}/thesis/extract-upload")
async def thesis_extract_upload(
    request: Request,
    project_id: int,
    business_plan: UploadFile = File(...),
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

    if not business_plan or not business_plan.filename:
        return RedirectResponse(
            url=f"/projects/{project_id}?thesis_error=no_file",
            status_code=303,
        )

    content = await business_plan.read()
    if not content:
        return RedirectResponse(
            url=f"/projects/{project_id}?thesis_error=empty_file",
            status_code=303,
        )

    pf, dispatch_type = _save_uploaded_business_plan(db, project_id, business_plan, content)
    if dispatch_type is None:
        payload = {"_error": "Unsupported business plan file type. Use PDF, DOCX, DOC, or image."}
    else:
        payload = extract_thesis_and_inspirations(
            os.path.join(crud.UPLOAD_DIR, pf.filename), dispatch_type,
        )

    extraction = crud.save_thesis_extraction(db, project_id, pf, payload)
    return RedirectResponse(
        url=f"/projects/{project_id}/thesis/preview?extraction_id={extraction.id}",
        status_code=303,
    )


@router.get("/projects/{project_id}/thesis/preview", response_class=HTMLResponse)
def thesis_preview(
    request: Request,
    project_id: int,
    extraction_id: int,
    db: Session = Depends(get_db),
):
    """Pure GET render of a saved extraction. Refreshing this page does NOT
    re-trigger AI — the result was persisted on the upload POST."""
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

    extraction = crud.get_thesis_extraction(db, extraction_id, project_id)
    if not extraction:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)

    meta = extraction.metadata_json or {}
    error = meta.get("_error")
    thesis_text = meta.get("thesis") or ""
    raw_inspirations = meta.get("inspirations") or []

    # Compute fuzzy matches against current open ideas (cheap, no AI)
    open_ideas = crud.get_all_open_ideas(db)
    inspirations_with_matches = []
    for insp in raw_inspirations:
        match, score = find_best_match(insp.get("name", ""), open_ideas)
        inspirations_with_matches.append({
            "data": insp,
            "matched_idea": match if score >= MATCH_THRESHOLD else None,
            "match_score": round(score, 2) if score else 0.0,
        })

    return templates.TemplateResponse(request, "thesis_preview.html", {
        "project": project,
        "extraction": extraction,
        "extraction_id": extraction_id,
        "source_filename": meta.get("source_filename"),
        "duration_seconds": meta.get("duration_seconds"),
        "thesis_text": thesis_text,
        "inspirations_with_matches": inspirations_with_matches,
        "error": error,
        "current_user": current_user,
        **i18n_context(request, current_user),
    })


@router.post("/projects/{project_id}/thesis/confirm")
async def thesis_confirm(
    request: Request,
    project_id: int,
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

    form = await request.form()
    extraction_id = int(form.get("extraction_id") or 0)
    if not extraction_id or not crud.get_thesis_extraction(db, extraction_id, project_id):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)

    new_thesis = (form.get("project_thesis") or "").strip()

    # Reassemble inspirations from posted form fields. Indices are 0..N-1.
    inspirations = []
    idx = 0
    while True:
        action_key = f"inspiration_action_{idx}"
        if action_key not in form:
            break
        inspirations.append({
            "action": form.get(action_key) or "skip",
            "idea_id": form.get(f"inspiration_idea_id_{idx}") or None,
            "name": form.get(f"inspiration_name_{idx}") or "",
            "description": form.get(f"inspiration_description_{idx}") or "",
            "idea_type": form.get(f"inspiration_idea_type_{idx}") or "other",
            "source": form.get(f"inspiration_source_{idx}") or "other",
            "source_detail": form.get(f"inspiration_source_detail_{idx}") or "",
        })
        idx += 1

    crud.apply_thesis_extraction(
        db, project_id, extraction_id, new_thesis, inspirations, current_user,
    )
    return RedirectResponse(url=f"/projects/{project_id}#thesis", status_code=303)


@router.post("/projects/{project_id}/thesis/inline-edit")
def thesis_inline_edit(
    request: Request,
    project_id: int,
    project_thesis: str = Form(""),
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

    new = (project_thesis or "").strip()
    if not new:
        return RedirectResponse(
            url=f"/projects/{project_id}?thesis_error=empty",
            status_code=303,
        )
    crud.update_project(db, project_id, {"project_thesis": new}, changed_by=current_user.role)
    return RedirectResponse(url=f"/projects/{project_id}#thesis", status_code=303)
