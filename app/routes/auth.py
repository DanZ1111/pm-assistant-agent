import os
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserSession, InvitePin
from app.dependencies import get_current_user
from app.i18n import i18n_context

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
    return templates.TemplateResponse(request, "auth/login.html", {
        "error": None,
        **i18n_context(request),
    })


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
            "error": "Invalid username or password.",
            **i18n_context(request),
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
    return templates.TemplateResponse(request, "auth/register.html", {
        "error": None,
        **i18n_context(request),
    })


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
    invite_pin_raw = (invite_pin or "").strip().upper()
    # Forgiving normalization: strip all non-alphanumeric chars so PMs/viewers
    # can paste "PM-X7KP2Q", "PMX7KP2Q", "pm-x7kp2q", etc. and still match.
    pin_normalized = "".join(c for c in invite_pin_raw if c.isalnum())

    def err(msg):
        return templates.TemplateResponse(request, "auth/register.html", {
            "error": msg,
            **i18n_context(request),
        })

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
    if not pin_normalized:
        return err("Invite PIN is required. Ask your administrator for one.")

    # Match the PIN by stripping non-alphanumerics on both sides too,
    # in case stored format ever differs (defensive).
    candidates = (
        db.query(InvitePin)
        .filter(InvitePin.used_by_user_id == None)  # noqa: E711
        .all()
    )
    pin_row = None
    for c in candidates:
        if "".join(ch for ch in (c.pin or "").upper() if ch.isalnum()) == pin_normalized:
            pin_row = c
            break
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


# ── Emergency admin reset ──────────────────────────────────────────────────
# Enabled only when EMERGENCY_RESET_TOKEN env var is set.
# Without the env var the route returns 404 (looks like it doesn't exist).
# Use this when you're locked out of the admin account and can't access the
# Railway shell. Set EMERGENCY_RESET_TOKEN to a long random string, visit
# /auth/emergency-reset, paste the token, and choose new credentials.
# REMOVE the env var after recovery for security.

def _emergency_token() -> str | None:
    tok = os.environ.get("EMERGENCY_RESET_TOKEN")
    return tok.strip() if tok and tok.strip() else None


@router.get("/auth/emergency-reset", response_class=HTMLResponse)
def emergency_reset_form(request: Request):
    if _emergency_token() is None:
        raise HTTPException(status_code=404, detail="Not found")
    return templates.TemplateResponse(request, "auth/emergency_reset.html", {
        "error": None,
        **i18n_context(request),
    })


@router.post("/auth/emergency-reset")
def emergency_reset_submit(
    request: Request,
    reset_token: str = Form(""),
    new_username: str = Form(""),
    new_password: str = Form(""),
    confirm_password: str = Form(""),
    db: Session = Depends(get_db),
):
    expected = _emergency_token()
    if expected is None:
        raise HTTPException(status_code=404, detail="Not found")

    def err(msg: str):
        return templates.TemplateResponse(request, "auth/emergency_reset.html", {
            "error": msg,
            **i18n_context(request),
        })

    # Constant-time token comparison
    if not secrets.compare_digest(reset_token.strip(), expected):
        return err("Invalid reset token.")

    new_username = new_username.strip().lower()
    if len(new_username) < 3:
        return err("Username must be at least 3 characters.")
    if len(new_password) < 8:
        return err("Password must be at least 8 characters.")
    if new_password != confirm_password:
        return err("Passwords do not match.")

    # If the desired username is taken by a non-admin user, refuse — let the
    # operator pick a different username rather than silently demoting someone.
    existing = db.query(User).filter(User.username == new_username).first()
    if existing and existing.role != "admin":
        return err(f"Username '{new_username}' is already taken by a non-admin user. Pick a different username.")

    # Find any existing admin and update it; otherwise create one
    admin = db.query(User).filter(User.role == "admin").first()
    if admin:
        admin.username = new_username
        admin.display_name = admin.display_name or new_username
        admin.hashed_password = pwd_ctx.hash(new_password)
    else:
        admin = User(
            username=new_username,
            display_name=new_username,
            hashed_password=pwd_ctx.hash(new_password),
            role="admin",
        )
        db.add(admin)
        db.flush()

    # Invalidate any existing sessions for this user — forces fresh login
    db.query(UserSession).filter(UserSession.user_id == admin.id).delete()
    db.commit()

    return RedirectResponse(url="/auth/login?reset=1", status_code=303)
