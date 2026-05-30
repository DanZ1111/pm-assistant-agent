from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
import app.crud as crud
from app.crud import IDEA_TYPES, IDEA_SOURCES
from app.dependencies import get_current_user, require_auth, _RedirectException
from app.i18n import i18n_context

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ── Board / list ─────────────────────────────────────────────────────────────

@router.get("/ideas", response_class=HTMLResponse)
def ideas_board(
    request: Request,
    source: str = None,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    grouped = crud.get_ideas_grouped(db, source_filter=source)
    return templates.TemplateResponse(request, "ideas_board.html", {
        "current_user": current_user,
        "grouped": grouped,
        "idea_types": IDEA_TYPES,
        "idea_sources": IDEA_SOURCES,
        "current_source": source or "",
        **i18n_context(request, current_user),
    })


# ── Create ───────────────────────────────────────────────────────────────────

@router.get("/ideas/new", response_class=HTMLResponse)
def idea_new_form(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    return templates.TemplateResponse(request, "idea_form.html", {
        "current_user": current_user,
        "idea": None,
        "is_edit": False,
        "error": None,
        "idea_types": IDEA_TYPES,
        "idea_sources": IDEA_SOURCES,
        **i18n_context(request, current_user),
    })


@router.post("/ideas/new")
def idea_new_submit(
    request: Request,
    name: str = Form(""),
    description: str = Form(""),
    idea_type: str = Form("other"),
    source: str = Form("other"),
    source_detail: str = Form(""),
    contributor: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    name = name.strip()
    if not name:
        return templates.TemplateResponse(request, "idea_form.html", {
            "current_user": current_user,
            "idea": None,
            "is_edit": False,
            "error": "Idea name is required.",
            "idea_types": IDEA_TYPES,
            "idea_sources": IDEA_SOURCES,
            **i18n_context(request, current_user),
        })

    data = {
        "name": name,
        "description": description,
        "idea_type": idea_type,
        "source": source,
        "source_detail": source_detail,
        "contributor": contributor or current_user.display_name or current_user.username,
        "notes": notes,
    }
    idea = crud.create_idea(db, data, contributor_user_id=current_user.id)
    return RedirectResponse(url=f"/ideas?highlight={idea.id}", status_code=303)


# ── Edit (PM and Admin only) ─────────────────────────────────────────────────

@router.get("/ideas/{idea_id}/edit", response_class=HTMLResponse)
def idea_edit_form(request: Request, idea_id: int, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    if current_user.role == "viewer":
        return RedirectResponse(url="/ideas", status_code=303)

    idea = crud.get_idea(db, idea_id)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")

    return templates.TemplateResponse(request, "idea_form.html", {
        "current_user": current_user,
        "idea": idea,
        "is_edit": True,
        "error": None,
        "idea_types": IDEA_TYPES,
        "idea_sources": IDEA_SOURCES,
        **i18n_context(request, current_user),
    })


@router.post("/ideas/{idea_id}/edit")
def idea_edit_submit(
    request: Request,
    idea_id: int,
    name: str = Form(""),
    description: str = Form(""),
    idea_type: str = Form("other"),
    source: str = Form("other"),
    source_detail: str = Form(""),
    contributor: str = Form(""),
    notes: str = Form(""),
    status: str = Form("open"),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    if current_user.role == "viewer":
        return RedirectResponse(url="/ideas", status_code=303)

    data = {
        "name": name,
        "description": description,
        "idea_type": idea_type,
        "source": source,
        "source_detail": source_detail,
        "contributor": contributor,
        "notes": notes,
        "status": status,
    }
    crud.update_idea(db, idea_id, data)
    return RedirectResponse(url=f"/ideas?highlight={idea_id}", status_code=303)


# ── Delete (Admin only) ──────────────────────────────────────────────────────

@router.post("/ideas/{idea_id}/delete")
def idea_delete(request: Request, idea_id: int, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    if current_user.role != "admin":
        return RedirectResponse(url="/ideas", status_code=303)

    crud.delete_idea(db, idea_id)
    return RedirectResponse(url="/ideas", status_code=303)
