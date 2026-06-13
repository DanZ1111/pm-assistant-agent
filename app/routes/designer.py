import os

from fastapi import APIRouter, Depends, HTTPException, Request
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

    return templates.TemplateResponse(request, "designer/quest_detail.html", {
        "current_user": current_user,
        "safe_quest": safe_quest,
        **i18n_context(request, current_user),
    })


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
