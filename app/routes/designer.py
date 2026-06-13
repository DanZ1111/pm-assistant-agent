from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
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

    return templates.TemplateResponse(request, "designer/dashboard.html", {
        "current_user": current_user,
        **i18n_context(request, current_user),
    })
