import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserSession, InvitePin
from app.dependencies import get_current_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_DAYS = 7
COOKIE_NAME = "pm_session"


def _create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(days=SESSION_DAYS)
    db.add(UserSession(token=token, user_id=user.id, expires_at=expires))
    user.last_login = datetime.utcnow()
    db.commit()
    return token


def _set_session_cookie(response, token: str):
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
    )


# ── Login ─────────────────────────────────────────────────────────────────────

@router.get("/auth/login", response_class=HTMLResponse)
def login_form(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if user:
        return RedirectResponse(url="/projects", status_code=303)
    return templates.TemplateResponse(request, "auth/login.html", {"error": None})


@router.post("/auth/login")
def login_submit(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db),
):
    username = username.strip().lower()
    user = db.query(User).filter(User.username == username).first()

    if not user or not pwd_ctx.verify(password, user.hashed_password):
        return templates.TemplateResponse(request, "auth/login.html", {
            "error": "Invalid username or password."
        })

    token = _create_session(db, user)
    response = RedirectResponse(url="/projects", status_code=303)
    _set_session_cookie(response, token)
    return response


# ── Logout ────────────────────────────────────────────────────────────────────

@router.post("/auth/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.query(UserSession).filter(UserSession.token == token).delete()
        db.commit()
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


# ── Register ──────────────────────────────────────────────────────────────────

@router.get("/auth/register", response_class=HTMLResponse)
def register_form(request: Request):
    return templates.TemplateResponse(request, "auth/register.html", {"error": None})


@router.post("/auth/register")
def register_submit(
    request: Request,
    username: str = Form(""),
    display_name: str = Form(""),
    password: str = Form(""),
    confirm_password: str = Form(""),
    invite_pin: str = Form(""),
    db: Session = Depends(get_db),
):
    username = username.strip().lower()
    invite_pin = invite_pin.strip().upper()

    def err(msg):
        return templates.TemplateResponse(request, "auth/register.html", {"error": msg})

    if not username:
        return err("Username is required.")
    if len(username) < 3:
        return err("Username must be at least 3 characters.")
    if not password:
        return err("Password is required.")
    if len(password) < 8:
        return err("Password must be at least 8 characters.")
    if password != confirm_password:
        return err("Passwords do not match.")
    if not invite_pin:
        return err("Invite PIN is required. Ask your administrator for one.")

    # Validate PIN
    pin_row = db.query(InvitePin).filter(
        InvitePin.pin == invite_pin,
        InvitePin.used_by_user_id == None,  # noqa: E711
    ).first()
    if not pin_row:
        return err("Invalid or already-used invite PIN.")

    # Check username not taken
    if db.query(User).filter(User.username == username).first():
        return err(f"Username '{username}' is already taken.")

    hashed = pwd_ctx.hash(password)
    user = User(
        username=username,
        display_name=display_name.strip() or username,
        hashed_password=hashed,
        role=pin_row.role,
    )
    db.add(user)
    db.flush()

    pin_row.used_by_user_id = user.id
    pin_row.used_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url="/auth/login?registered=1", status_code=303)
