"""Project Journal routes — Build 14.

Permission matrix:
- View: admin + PM only (viewer cannot see the section AT ALL)
- Create: admin (any project) + PM (own projects only)
- Edit: admin (any entry) + PM (only their OWN entries on projects they can edit)
- Delete: admin only
- Summarize: admin (any) + PM (own projects)

All routes redirect to /projects/{id}#journal on success or error
(error info passed via ?journal_error=... query param).
"""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
import app.crud as crud
from app.dependencies import (
    get_current_user, require_auth, can_edit_project,
    can_view_journal, _RedirectException,
)
from app.ai.parser import summarize_journal_entry
from app.models import ProjectJournalEntry

router = APIRouter()


def _back(project_id: int, error: str | None = None, entry_id: int | None = None) -> RedirectResponse:
    url = f"/projects/{project_id}#journal"
    if error:
        params = [f"journal_error={error}"]
        if entry_id:
            params.append(f"entry_id={entry_id}")
        url = f"/projects/{project_id}?{'&'.join(params)}#journal"
    return RedirectResponse(url=url, status_code=303)


# ── Create ───────────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/journal")
def journal_create(
    request: Request,
    project_id: int,
    entry_text: str = Form(""),
    entry_type: str = Form("general"),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    if not can_view_journal(current_user):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)

    project = crud.get_project(db, project_id)
    if not project or not can_edit_project(current_user, project):
        return _back(project_id, error="not_authorized")

    entry_text = entry_text.strip()
    if not entry_text:
        return _back(project_id, error="empty_entry")

    crud.create_journal_entry(
        db, project_id, entry_text, entry_type, author_user_id=current_user.id
    )
    return _back(project_id)


# ── Edit (PM: own entries only; admin: any) ─────────────────────────────────

@router.post("/projects/{project_id}/journal/{entry_id}/edit")
def journal_edit(
    request: Request,
    project_id: int,
    entry_id: int,
    entry_text: str = Form(""),
    entry_type: str = Form("general"),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    if not can_view_journal(current_user):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)

    project = crud.get_project(db, project_id)
    if not project or not can_edit_project(current_user, project):
        return _back(project_id, error="not_authorized")

    entry = db.query(ProjectJournalEntry).filter(ProjectJournalEntry.id == entry_id).first()
    if not entry or entry.project_id != project_id:
        return _back(project_id, error="entry_not_found")

    # PM may edit ONLY their own entries. Admin bypasses author check.
    if current_user.role != "admin" and entry.author_user_id != current_user.id:
        return _back(project_id, error="not_your_entry", entry_id=entry_id)

    crud.update_journal_entry(
        db, entry_id, entry_text, entry_type, edited_by_user_id=current_user.id
    )
    return _back(project_id)


# ── Delete (admin only) ──────────────────────────────────────────────────────

@router.post("/projects/{project_id}/journal/{entry_id}/delete")
def journal_delete(
    request: Request,
    project_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    if current_user.role != "admin":
        return _back(project_id, error="delete_admin_only")

    crud.delete_journal_entry(db, entry_id)
    return _back(project_id)


# ── Summarize via AI ─────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/journal/{entry_id}/summarize")
def journal_summarize(
    request: Request,
    project_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    if not can_view_journal(current_user):
        return RedirectResponse(url=f"/projects/{project_id}", status_code=303)

    project = crud.get_project(db, project_id)
    if not project or not can_edit_project(current_user, project):
        return _back(project_id, error="not_authorized")

    entry = db.query(ProjectJournalEntry).filter(ProjectJournalEntry.id == entry_id).first()
    if not entry or entry.project_id != project_id:
        return _back(project_id, error="entry_not_found")

    result = summarize_journal_entry(entry.entry_text or "")
    if "_error" in result:
        # Preserve existing title/summary; surface error to user
        return _back(project_id, error="summarize_failed", entry_id=entry_id)

    crud.apply_ai_summary(db, entry_id, result["title"], result["summary"])
    return _back(project_id)
