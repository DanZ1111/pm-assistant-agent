"""Build 16 — variant + component (packaging/accessory) routes.

Kept in its own module so app/routes/projects.py doesn't sprawl further.
All mutating routes go through can_edit_project; delete routes are
admin-only (variants and components carry cost data — accidental deletion
loses operational history).
"""
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
import app.crud as crud
from app.dependencies import (
    get_current_user, require_auth, require_admin,
    can_edit_project, _RedirectException,
)

router = APIRouter()


def _back(project_id: int, anchor: str = "variants") -> RedirectResponse:
    return RedirectResponse(url=f"/projects/{project_id}#{anchor}", status_code=303)


def _auth_edit(request: Request, project_id: int, db: Session):
    """Returns (current_user, project) on success, or a RedirectResponse on failure."""
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return None, e.response
    project = crud.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not can_edit_project(current_user, project):
        return None, RedirectResponse(url=f"/projects/{project_id}", status_code=303)
    return (current_user, project), None


# ---------------- Variants ----------------

@router.post("/projects/{project_id}/variants")
def variant_create(
    request: Request,
    project_id: int,
    variant_name: str = Form(...),
    sku: str = Form(""),
    status: str = Form("evaluating"),
    is_primary: str = Form(""),
    target_factory_cost: str = Form(""),
    actual_factory_cost: str = Form(""),
    target_msrp: str = Form(""),
    material_summary: str = Form(""),
    size_color_summary: str = Form(""),
    packaging_summary: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    ctx, redirect = _auth_edit(request, project_id, db)
    if redirect: return redirect
    if not variant_name.strip():
        return _back(project_id)
    crud.create_variant(db, project_id, {
        "variant_name": variant_name, "sku": sku, "status": status,
        "is_primary": bool(is_primary),
        "target_factory_cost": target_factory_cost,
        "actual_factory_cost": actual_factory_cost,
        "target_msrp": target_msrp,
        "material_summary": material_summary,
        "size_color_summary": size_color_summary,
        "packaging_summary": packaging_summary,
        "notes": notes,
    })
    return _back(project_id)


@router.post("/projects/{project_id}/variants/{variant_id}/edit")
def variant_edit(
    request: Request,
    project_id: int,
    variant_id: int,
    variant_name: str = Form(...),
    sku: str = Form(""),
    status: str = Form("evaluating"),
    is_primary: str = Form(""),
    target_factory_cost: str = Form(""),
    actual_factory_cost: str = Form(""),
    target_msrp: str = Form(""),
    material_summary: str = Form(""),
    size_color_summary: str = Form(""),
    packaging_summary: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    ctx, redirect = _auth_edit(request, project_id, db)
    if redirect: return redirect
    v = crud.get_variant(db, variant_id)
    if not v or v.project_id != project_id:
        return _back(project_id)
    crud.update_variant(db, variant_id, {
        "variant_name": variant_name, "sku": sku, "status": status,
        "is_primary": bool(is_primary),
        "target_factory_cost": target_factory_cost,
        "actual_factory_cost": actual_factory_cost,
        "target_msrp": target_msrp,
        "material_summary": material_summary,
        "size_color_summary": size_color_summary,
        "packaging_summary": packaging_summary,
        "notes": notes,
    })
    return _back(project_id)


@router.post("/projects/{project_id}/variants/{variant_id}/delete")
def variant_delete(
    request: Request,
    project_id: int,
    variant_id: int,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
        require_admin(current_user)
    except _RedirectException as e:
        return e.response
    v = crud.get_variant(db, variant_id)
    if v and v.project_id == project_id:
        crud.delete_variant(db, variant_id)
    return _back(project_id)


@router.post("/projects/{project_id}/variants/{variant_id}/set-primary")
def variant_set_primary(
    request: Request,
    project_id: int,
    variant_id: int,
    db: Session = Depends(get_db),
):
    ctx, redirect = _auth_edit(request, project_id, db)
    if redirect: return redirect
    crud.set_primary_variant(db, project_id, variant_id)
    return _back(project_id)


# ---------------- Components (packaging / accessories) ----------------

@router.post("/projects/{project_id}/components")
def component_create(
    request: Request,
    project_id: int,
    name: str = Form(...),
    component_type: str = Form("accessory"),
    variant_id: str = Form(""),
    target_cost: str = Form(""),
    actual_cost: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    ctx, redirect = _auth_edit(request, project_id, db)
    if redirect: return redirect
    if not name.strip():
        return _back(project_id, "packaging")
    crud.create_variant_component(db, project_id, {
        "name": name, "component_type": component_type, "variant_id": variant_id,
        "target_cost": target_cost, "actual_cost": actual_cost, "notes": notes,
    })
    return _back(project_id, "packaging")


@router.post("/projects/{project_id}/components/{component_id}/edit")
def component_edit(
    request: Request,
    project_id: int,
    component_id: int,
    name: str = Form(...),
    component_type: str = Form("accessory"),
    variant_id: str = Form(""),
    target_cost: str = Form(""),
    actual_cost: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    ctx, redirect = _auth_edit(request, project_id, db)
    if redirect: return redirect
    c = crud.get_component(db, component_id)
    if not c or c.project_id != project_id:
        return _back(project_id, "packaging")
    crud.update_variant_component(db, component_id, {
        "name": name, "component_type": component_type, "variant_id": variant_id,
        "target_cost": target_cost, "actual_cost": actual_cost, "notes": notes,
    })
    return _back(project_id, "packaging")


@router.post("/projects/{project_id}/components/{component_id}/delete")
def component_delete(
    request: Request,
    project_id: int,
    component_id: int,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
        require_admin(current_user)
    except _RedirectException as e:
        return e.response
    c = crud.get_component(db, component_id)
    if c and c.project_id == project_id:
        crud.delete_variant_component(db, component_id)
    return _back(project_id, "packaging")
