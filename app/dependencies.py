"""
Shared auth dependencies and permission helpers.
"""
from datetime import datetime
from fastapi import Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.models import User, UserSession

# ── Session lookup ────────────────────────────────────────────────────────────

def get_current_user(request: Request, db: Session) -> User | None:
    """Read pm_session cookie, look up session in DB, return User or None."""
    token = request.cookies.get("pm_session")
    if not token:
        return None
    session = (
        db.query(UserSession)
        .filter(UserSession.token == token, UserSession.expires_at > datetime.utcnow())
        .first()
    )
    if not session:
        return None
    return session.user


def require_auth(user: User | None) -> User:
    """Return user or raise a redirect to login."""
    if not user:
        raise _redirect("/auth/login")
    return user


def require_admin(user: User | None) -> User:
    """Return user or raise a redirect. Also enforces admin role."""
    u = require_auth(user)
    if u.role != "admin":
        raise _redirect("/projects")
    return u


# ── Permission helpers ────────────────────────────────────────────────────────

DESIGNER_ROLES = ("designer", "designer_manager")


def is_designer_role(user: User | None) -> bool:
    return bool(user) and user.role in DESIGNER_ROLES


def is_designer_manager(user: User | None) -> bool:
    return bool(user) and user.role == "designer_manager"


def auth_landing_path(user: User | None) -> str:
    return "/designer" if is_designer_role(user) else "/projects"


def require_designer_portal_user(user: User | None) -> User:
    u = require_auth(user)
    if u.role not in ("admin", "designer", "designer_manager"):
        raise _redirect("/projects")
    return u

def can_edit_project(user: User, project) -> bool:
    """Admin can edit anything. PM can edit projects where they are the assigned PM."""
    if user.role == "admin":
        return True
    if user.role == "pm":
        pm_field = (project.product_manager or "").lower().strip()
        if not pm_field:
            return False
        return (pm_field == user.username.lower() or
                pm_field == (user.display_name or "").lower().strip())
    return False


def can_delete_project(user: User | None, project) -> bool:
    """Build 30C — who can hard-delete a project.

    Admin: always (matches existing admin-only delete behavior, preserved).
    PM: only if they own the project AND no phase has started yet.
        "No phase has started" = every phase still has status='not_started'
        AND actual_start_date IS NULL. This is "until first phase advance":
        once anyone marks real work as started, the project is no longer
        a deletable draft — switch to archive instead.
    Viewer: never.
    """
    if user is None:
        return False
    if user.role == "admin":
        return True
    if user.role != "pm":
        return False
    if not can_edit_project(user, project):
        return False
    # Conservative draft check: every phase must be untouched.
    phases = getattr(project, "phases", None) or []
    for phase in phases:
        if phase.status != "not_started":
            return False
        if phase.actual_start_date is not None:
            return False
    return True


def can_view_sensitive_fields(user: User) -> bool:
    """Factory and engineer are visible only to admin and pm."""
    return user.role in ("admin", "pm")


def can_use_ai_intake(user: User) -> bool:
    return user.role in ("admin", "pm")


def can_view_costs(user: User | None) -> bool:
    """Build 16: viewers see variants/components but not the cost columns.
    Same rule as factory/engineer visibility — admin + PM only."""
    return bool(user) and user.role in ("admin", "pm")


def can_view_journal(user: User | None) -> bool:
    """Project Journal contains product reasoning, factory discussions, cost
    discoveries, abandoned directions — strictly internal. Viewers cannot see."""
    return bool(user) and user.role in ("admin", "pm")


# ── AI Permission Guard ───────────────────────────────────────────────────────

# Topics that are forbidden for everyone (raw secrets / system internals)
_ALWAYS_FORBIDDEN = [
    ".env", "api key", "api_key", "openai_api_key", "openai key",
    "database_url", "database url", "secret_key", "secret key",
    "password hash", "hashed_password", "session token", "session cookie",
    "cookie value", "pm_session", "system prompt", "what model",
    "which model", "model name", "gpt-5", "tool call", "internal tool",
    "source code", "database credential", "connection string",
]

# Topics forbidden for viewers (supply-chain / sensitive project data)
_VIEWER_FORBIDDEN = [
    "factory", "supplier", "manufacturer", "engineer", "engineering",
    "quotation", "factory cost", "unit cost", "target cost",
    "which factory", "who is engineer", "which supplier",
    # v1.1 Build 14: Project Journal is admin/PM only — viewer AI must not
    # surface journal content even indirectly
    "journal", "internal note", "project update", "journal entry",
    # v1.1 Build 15: Business plan / thesis extraction sources can contain
    # margin/pricing strategy — viewers must not be able to AI-summarize them
    "business plan", "thesis extraction", "margin target", "pricing strategy",
    # v1.1 Build 16: Variant + packaging + quotation costs are sensitive
    "variant cost", "actual cost", "quotation", "packaging cost", "component cost",
]


def is_forbidden_ai_question(user: User | None, message: str) -> bool:
    """Return True if the message asks for role-inappropriate information."""
    msg = message.lower()

    for topic in _ALWAYS_FORBIDDEN:
        if topic in msg:
            return True

    if user is None or user.role == "viewer":
        for topic in _VIEWER_FORBIDDEN:
            if topic in msg:
                return True

    return False


def sanitize_project_for_user(project, user: User | None) -> dict:
    """Return a role-filtered plain dict of project fields — never raw DB object."""
    base = {
        "name": project.name,
        "brand": project.brand,
        "sku": project.sku,
        "product_type": project.product_type,
        "status": project.status,
        "current_stage": project.current_stage,
        "project_thesis": project.project_thesis,
        "planned_launch_date": str(project.planned_launch_date) if project.planned_launch_date else None,
        "product_manager": project.product_manager,
    }

    if user and user.role in ("admin", "pm"):
        base.update({
            "engineer": project.engineer,
            "factory": project.factory,
            "target_factory_cost": project.target_factory_cost_display,
            "target_msrp": project.target_msrp_display,
            "project_owner": project.project_owner,
        })

    return base


# ── Internal helpers ──────────────────────────────────────────────────────────

class _RedirectException(Exception):
    def __init__(self, url: str):
        self.url = url
        self.response = RedirectResponse(url=url, status_code=303)


def _redirect(url: str) -> _RedirectException:
    return _RedirectException(url)
