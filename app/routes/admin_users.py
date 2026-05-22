import secrets
import string

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, InvitePin
from app.dependencies import get_current_user, require_admin, _RedirectException

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


PIN_PREFIXES = {"pm": "PM", "viewer": "VW", "admin": "AD"}


def _generate_pin(role: str) -> str:
    """Generate a role-prefixed PIN like PM-X7KP2Q or VW-X7KP2Q."""
    alphabet = string.ascii_uppercase + string.digits
    # Exclude ambiguous chars (0, O, I, 1)
    alphabet = "".join(c for c in alphabet if c not in "0O1I")
    body = "".join(secrets.choice(alphabet) for _ in range(6))
    prefix = PIN_PREFIXES.get(role, "VW")
    return f"{prefix}-{body}"


@router.get("/admin/users", response_class=HTMLResponse)
def users_list(request: Request, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_admin(current_user)
    except _RedirectException as e:
        return e.response

    users = db.query(User).order_by(User.created_at).all()
    unused_pins = (
        db.query(InvitePin)
        .filter(InvitePin.used_by_user_id == None)  # noqa: E711
        .order_by(InvitePin.created_at.desc())
        .all()
    )
    new_pin = request.query_params.get("new_pin")
    new_pin_role = request.query_params.get("new_pin_role")

    return templates.TemplateResponse(request, "admin/users.html", {
        "current_user": current_user,
        "users": users,
        "unused_pins": unused_pins,
        "new_pin": new_pin,
        "new_pin_role": new_pin_role,
    })


@router.post("/admin/users/generate-pin")
def generate_pin(
    request: Request,
    role: str = Form("viewer"),
    db: Session = Depends(get_db),
):
    current_user = get_current_user(request, db)
    try:
        require_admin(current_user)
    except _RedirectException as e:
        return e.response

    if role not in ("pm", "viewer"):
        role = "viewer"

    pin = _generate_pin(role)
    # Ensure uniqueness (retry on collision — astronomically rare)
    while db.query(InvitePin).filter(InvitePin.pin == pin).first():
        pin = _generate_pin(role)

    db.add(InvitePin(pin=pin, role=role, created_by_user_id=current_user.id))
    db.commit()

    return RedirectResponse(
        url=f"/admin/users?new_pin={pin}&new_pin_role={role}",
        status_code=303,
    )


@router.post("/admin/users/{user_id}/deactivate")
def deactivate_user(request: Request, user_id: int, db: Session = Depends(get_db)):
    current_user = get_current_user(request, db)
    try:
        require_admin(current_user)
    except _RedirectException as e:
        return e.response

    user = db.query(User).filter(User.id == user_id).first()
    if user and user.id != current_user.id:  # cannot deactivate yourself
        from app.models import UserSession
        db.query(UserSession).filter(UserSession.user_id == user.id).delete()
        db.delete(user)
        db.commit()

    return RedirectResponse(url="/admin/users", status_code=303)
