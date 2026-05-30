from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
import app.crud as crud
from app.dependencies import get_current_user, require_auth, _RedirectException
from app.i18n import i18n_context

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


@router.get("/calendar", response_class=HTMLResponse)
def calendar_view(
    request: Request,
    year: int = None,
    month: int = None,
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_auth(current_user)
    except _RedirectException as e:
        return e.response

    today = date.today()
    year = year or today.year
    month = month if (month and 1 <= month <= 12) else today.month

    months_data = crud.get_calendar_data(db, year)
    min_year, max_year = crud.get_calendar_year_range(db)

    return templates.TemplateResponse(request, "calendar.html", {
        "current_user": current_user,
        "year": year,
        "selected_month": month,
        "today": today,
        "months_data": months_data,
        "month_names": MONTH_NAMES,
        "min_year": min_year,
        "max_year": max_year,
        **i18n_context(request, current_user),
    })
