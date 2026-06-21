import os
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DesignQuest, DesignQuestReference
import app.crud as crud
from app.dependencies import (
    _RedirectException,
    get_current_user,
    require_designer_portal_user,
)
from app.i18n import i18n_context

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _parse_optional_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid_soft_deadline") from exc


@router.get("/designer", response_class=HTMLResponse)
def designer_dashboard(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_designer_portal_user(current_user)
    except _RedirectException as e:
        return e.response

    quests = crud.list_design_quests_for_designer(db, current_user.id)

    return templates.TemplateResponse(request, "designer/dashboard.html", {
        "current_user": current_user,
        "quests": quests,
        **i18n_context(request, current_user),
    })


@router.get("/designer/tutorial", response_class=HTMLResponse)
def designer_tutorial(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_designer_portal_user(current_user)
    except _RedirectException as e:
        return e.response
    return templates.TemplateResponse(request, "designer/tutorial.html", {
        "current_user": current_user,
        **i18n_context(request, current_user),
    })


@router.get("/designer/manager", response_class=HTMLResponse)
def designer_manager_dashboard(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_designer_portal_user(current_user)
    except _RedirectException as e:
        return e.response
    if current_user.role != "designer_manager":
        return RedirectResponse(url="/designer", status_code=303)
    operations = crud.list_designer_manager_operations(db, current_user.id)
    return templates.TemplateResponse(request, "designer/manager.html", {
        "current_user": current_user,
        "operations": operations,
        "manager_error": request.query_params.get("manager_error"),
        "manager_result": request.query_params.get("manager_result"),
        **i18n_context(request, current_user),
    })


@router.post("/designer/manager/quests/{quest_id}/assign")
def designer_manager_assign(
    request: Request,
    quest_id: int,
    designer_user_id: int = Form(...),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_designer_portal_user(current_user)
    except _RedirectException as e:
        return e.response
    try:
        crud.manager_assign_designer_to_quest(db, quest_id, designer_user_id, current_user.id)
    except (PermissionError, ValueError) as exc:
        return RedirectResponse(url=f"/designer/manager?manager_error={str(exc)}", status_code=303)
    return RedirectResponse(url="/designer/manager?manager_result=assigned", status_code=303)


@router.post("/designer/manager/quests/create")
def designer_manager_create_quest(
    request: Request,
    project_id: int = Form(...),
    title: str = Form(...),
    brief: str = Form(...),
    must_keep: str = Form(""),
    must_avoid: str = Form(""),
    soft_deadline: str = Form(""),
    visibility: str = Form("all_active_designers"),
    is_timeline_blocking: bool = Form(False),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_designer_portal_user(current_user)
        crud.create_design_quest_draft(
            db,
            project_id=project_id,
            user_id=current_user.id,
            title=title,
            brief=brief,
            must_keep=must_keep,
            must_avoid=must_avoid,
            soft_deadline=_parse_optional_date(soft_deadline),
            visibility=visibility,
            is_timeline_blocking=is_timeline_blocking,
            allow_designer_manager=True,
        )
    except (PermissionError, ValueError) as exc:
        return RedirectResponse(url=f"/designer/manager?manager_error={str(exc)}", status_code=303)
    except _RedirectException as exc:
        return exc.response
    return RedirectResponse(url="/designer/manager?manager_result=quest_created", status_code=303)


@router.post("/designer/manager/quests/{quest_id}/publish")
def designer_manager_publish_quest(
    request: Request,
    quest_id: int,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_designer_portal_user(current_user)
        crud.publish_design_quest(
            db,
            quest_id,
            current_user.id,
            allow_designer_manager=True,
        )
    except (PermissionError, ValueError) as exc:
        return RedirectResponse(url=f"/designer/manager?manager_error={str(exc)}", status_code=303)
    except _RedirectException as exc:
        return exc.response
    return RedirectResponse(url="/designer/manager?manager_result=quest_published", status_code=303)


@router.post("/designer/manager/submissions/{submission_id}/reopen")
def designer_manager_reopen_submission(
    request: Request,
    submission_id: int,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_designer_portal_user(current_user)
    except _RedirectException as e:
        return e.response
    try:
        crud.manager_reopen_design_submission(db, submission_id, current_user.id)
    except (PermissionError, ValueError) as exc:
        return RedirectResponse(url=f"/designer/manager?manager_error={str(exc)}", status_code=303)
    return RedirectResponse(url="/designer/manager?manager_result=reopened", status_code=303)


@router.get("/designer/quests/{quest_id}", response_class=HTMLResponse)
def designer_quest_detail(request: Request, quest_id: int, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_designer_portal_user(current_user)
    except _RedirectException as e:
        return e.response

    quest = db.query(DesignQuest).filter(DesignQuest.id == quest_id).first()
    if not quest or not crud.can_designer_view_quest(current_user, quest):
        return RedirectResponse(url="/designer", status_code=303)
    safe_quest = crud.shape_design_quest_for_designer(quest, current_user)
    submissions = [
        crud.shape_design_submission_for_designer(submission, current_user)
        for submission in crud.list_design_submissions_for_designer(db, current_user.id, quest_id=quest_id)
    ]
    open_revision_request = next(
        (
            revision_request
            for submission in submissions
            for revision_request in submission.get("open_revision_requests", [])
        ),
        None,
    )

    return templates.TemplateResponse(request, "designer/quest_detail.html", {
        "current_user": current_user,
        "safe_quest": safe_quest,
        "submissions": submissions,
        "open_revision_request": open_revision_request,
        "submission_error": request.query_params.get("submission_error"),
        "submission_uploaded": request.query_params.get("submission_uploaded"),
        **i18n_context(request, current_user),
    })


@router.post("/designer/quests/{quest_id}/submissions/upload")
async def designer_submission_upload(
    request: Request,
    quest_id: int,
    title: str = Form(""),
    designer_note: str = Form(""),
    revision_request_id: int | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_designer_portal_user(current_user)
    except _RedirectException as e:
        return e.response

    try:
        content = await file.read(crud.DESIGN_SUBMISSION_MAX_BYTES + 1)
        crud.create_or_append_design_submission_version(
            db,
            quest_id=quest_id,
            designer_user_id=current_user.id,
            original_filename=file.filename or "",
            content=content,
            designer_note=designer_note,
            title=title,
            revision_request_id=revision_request_id,
        )
    except (PermissionError, ValueError) as exc:
        return RedirectResponse(
            url=f"/designer/quests/{quest_id}?submission_error={str(exc)}",
            status_code=303,
        )
    return RedirectResponse(url=f"/designer/quests/{quest_id}?submission_uploaded=1", status_code=303)


@router.get("/designer/quests/{quest_id}/references/{reference_id}/download")
def designer_reference_download(
    request: Request,
    quest_id: int,
    reference_id: int,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_designer_portal_user(current_user)
    except _RedirectException as e:
        return e.response

    quest = db.query(DesignQuest).filter(DesignQuest.id == quest_id).first()
    if not quest or not crud.can_designer_view_quest(current_user, quest):
        raise HTTPException(status_code=404, detail="Reference not found")
    reference = (
        db.query(DesignQuestReference)
        .filter(
            DesignQuestReference.id == reference_id,
            DesignQuestReference.quest_id == quest_id,
            DesignQuestReference.visibility == "designer_visible",
        )
        .first()
    )
    if not reference or not reference.project_file:
        raise HTTPException(status_code=404, detail="Reference not found")

    project_file = reference.project_file
    disk_path = os.path.join(crud.UPLOAD_DIR, project_file.filename)
    if not os.path.exists(disk_path):
        raise HTTPException(status_code=404, detail="Reference file missing")
    return FileResponse(disk_path, filename=project_file.original_filename or project_file.filename)


@router.get("/designer/quests/{quest_id}/submissions/{submission_id}/versions/{version_id}/download")
def designer_submission_version_download(
    request: Request,
    quest_id: int,
    submission_id: int,
    version_id: int,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_designer_portal_user(current_user)
    except _RedirectException as e:
        return e.response

    try:
        version = crud.get_design_submission_version_for_download(db, version_id, current_user)
    except PermissionError:
        raise HTTPException(status_code=404, detail="Submission not found")
    if version.quest_id != quest_id or version.submission_id != submission_id:
        raise HTTPException(status_code=404, detail="Submission not found")
    disk_path = os.path.join(crud.UPLOAD_DIR, version.filename)
    if not os.path.exists(disk_path):
        raise HTTPException(status_code=404, detail="Submission file missing")
    return FileResponse(disk_path, filename=version.original_filename or version.filename)
