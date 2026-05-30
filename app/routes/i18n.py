"""Build 23 — language switcher endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.i18n import SUPPORTED_LOCALES, LANG_COOKIE, DEFAULT_LOCALE

router = APIRouter()

# Same shape as the auth session cookie. 1-year persistence so users don't
# have to re-pick every browser session.
_LANG_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


@router.post("/lang/set")
def set_language(
    request: Request,
    lang: str = Form(...),
    next: str = Form("/projects"),
    db: Session = Depends(get_db),
):
    """Switch UI language. Accepts a `lang` form field; if it's not in
    SUPPORTED_LOCALES we silently fall back to the default — no error page.

    Side effects:
      - Always sets the `lang` cookie (samesite=lax, max_age=1y).
      - If the user is authenticated, also persists to `users.language` so the
        preference survives even after the cookie expires or is cleared.
    """
    if lang not in SUPPORTED_LOCALES:
        lang = DEFAULT_LOCALE

    # Sanitize the `next` redirect target — only allow relative paths to our
    # own app. Refuse external URLs and protocol-relative URLs.
    if not next.startswith("/") or next.startswith("//"):
        next = "/projects"

    response = RedirectResponse(url=next, status_code=303)
    response.set_cookie(
        key=LANG_COOKIE,
        value=lang,
        max_age=_LANG_COOKIE_MAX_AGE,
        samesite="lax",
    )

    # Persist to DB for authenticated users so the preference is durable
    # across browsers / cookie clears.
    current_user = get_current_user(request, db)
    if current_user is not None and getattr(current_user, "language", None) != lang:
        current_user.language = lang
        db.commit()

    return response
