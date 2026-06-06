from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
import app.crud as crud
from app.dependencies import get_current_user, require_admin, _RedirectException

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/admin/database", response_class=HTMLResponse)
def database_inspector(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_admin(current_user)
    except _RedirectException as e:
        return e.response
    table_stats = crud.get_table_stats(db)
    field_usage = crud.get_field_usage(db)
    missing_critical = crud.get_missing_critical_summary(db)

    from app.models import ProjectChange, Project
    recent_changes = (
        db.query(ProjectChange)
        .order_by(ProjectChange.changed_at.desc())
        .limit(50)
        .all()
    )
    # attach project names
    project_names = {p.id: p.name for p in db.query(Project).all()}
    changes_with_names = [
        {"change": c, "project_name": project_names.get(c.project_id, "Unknown")}
        for c in recent_changes
    ]

    return templates.TemplateResponse(request, "admin_db.html", {
        "table_stats": table_stats,
        "field_usage": field_usage,
        "missing_critical": missing_critical,
        "recent_changes": changes_with_names,
        "current_user": current_user,
    })


@router.get("/admin/modules", response_class=HTMLResponse)
def planning_modules_inspector(request: Request, db: Session = Depends(get_db)):
    """v1.4 Build 01 — read-only planning module/template inventory."""
    current_user = get_current_user(request, db)
    try:
        require_admin(current_user)
    except _RedirectException as e:
        return e.response

    modules = crud.list_planning_modules(db, active_only=False)
    templates_rows = crud.list_planning_templates(db, active_only=False)
    template_counts = crud.get_planning_template_counts(db)

    return templates.TemplateResponse(request, "admin_modules.html", {
        "current_user": current_user,
        "modules": modules,
        "planning_templates": templates_rows,
        "template_counts": template_counts,
    })
