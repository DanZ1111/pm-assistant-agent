from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import date

from app.database import get_db
from app.models import Project
import app.crud as crud
from app.dependencies import (
    get_current_user, require_auth, require_admin,
    can_edit_project, can_view_sensitive_fields, _RedirectException
)

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
    needs_attention = [e for e in active_enriched if e["delay"] or e["health"]["needs_info"]]
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
    })


# ---------------------------------------------------------------------------
# Create Project
# ---------------------------------------------------------------------------

@router.get("/projects/new", response_class=HTMLResponse)
def project_new_form(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response
    if current_user.role == "viewer":
        return RedirectResponse(url="/projects", status_code=303)

    return templates.TemplateResponse(request, "project_form.html", {
        "project": None,
        "is_edit": False,
        "error": None,
        "current_user": current_user,
    })


@router.post("/projects/new")
def project_new_submit(
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
        "target_factory_cost": parse_float(target_factory_cost),
        "target_msrp": parse_float(target_msrp),
        "planned_launch_date": parse_date(planned_launch_date),
        "project_thesis": project_thesis.strip() or None,
    }
    project = crud.create_project(db, data, prototype_rounds=prototype_rounds)
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
    can_sensitive = can_view_sensitive_fields(current_user)
    linked_ideas = crud.get_ideas_for_project(db, project_id)
    linked_idea_ids = {li["idea"].id for li in linked_ideas}
    available_ideas = [i for i in crud.get_all_open_ideas(db) if i.id not in linked_idea_ids]

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
        "can_sensitive": can_sensitive,
        "linked_ideas": linked_ideas,
        "available_ideas": available_ideas,
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
        "target_factory_cost": parse_float(target_factory_cost),
        "target_msrp": parse_float(target_msrp),
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
    current_user = get_current_user(request, db)
    try:
        require_admin(current_user)
    except _RedirectException as e:
        return e.response

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
            "status": status,
            "planned_start_date": parse_date(planned_start_date),
            "planned_end_date": parse_date(planned_end_date),
            "actual_start_date": parse_date(actual_start_date),
            "actual_end_date": parse_date(actual_end_date),
            "owner": owner.strip() or None,
            "notes": notes.strip() or None,
        }
        crud.update_phase(db, phase_id, data)
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
