"""Build 23 — Chinese i18n.

Loads translation bundles from app/i18n/{en,zh}.json at import time. Exposes
`t(key, **kwargs)` as a Jinja2 `pass_context` global plus `get_locale(request,
current_user)` for routes/middleware.

Locale resolution (priority order):
  1. Authenticated user's `users.language` (the durable preference).
  2. `lang` cookie (logged-out fallback or just-switched anonymous user).
  3. Default `"en"`.

Fail-safe by design — a missing key returns the literal key string instead of
raising. A page must never 500 because of i18n.
"""
from __future__ import annotations

import json
import os
from typing import Any

from jinja2 import pass_context

SUPPORTED_LOCALES = ("en", "zh")
DEFAULT_LOCALE = "en"
LANG_COOKIE = "lang"

# Bundles live next to this file (app/i18n/en.json, app/i18n/zh.json).
_BUNDLE_DIR = os.path.dirname(__file__)

TRANSLATIONS: dict[str, dict[str, str]] = {}


def _load_bundles() -> None:
    """Read every locale bundle into TRANSLATIONS. Silent on missing files
    (returns empty dict for that locale) so dev environments work even if
    a bundle was deleted by accident — pages will fall back to English or
    to the literal key."""
    for locale in SUPPORTED_LOCALES:
        path = os.path.join(_BUNDLE_DIR, f"{locale}.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                TRANSLATIONS[locale] = json.load(f)
        except FileNotFoundError:
            TRANSLATIONS[locale] = {}
        except json.JSONDecodeError:
            import sys as _sys
            _sys.stderr.write(f"[i18n] Failed to parse {path}; using empty bundle.\n")
            TRANSLATIONS[locale] = {}


_load_bundles()


def get_locale(request, current_user) -> str:
    """Resolve which locale to use for this request.

    Order: authenticated user pref → cookie → default. Never raises.
    """
    if current_user is not None:
        lang = getattr(current_user, "language", None)
        if lang in SUPPORTED_LOCALES:
            return lang
    cookie = None
    try:
        cookie = request.cookies.get(LANG_COOKIE)
    except Exception:
        cookie = None
    if cookie in SUPPORTED_LOCALES:
        return cookie
    return DEFAULT_LOCALE


def i18n_context(request, current_user=None) -> dict[str, str]:
    """Small helper for TemplateResponse contexts."""
    return {"locale": get_locale(request, current_user)}


def _resolve_locale_from_ctx(ctx) -> str:
    """Pull locale out of the Jinja render context. Reads `request` and
    `current_user` which every TemplateResponse already exposes (request via
    FastAPI's Jinja2Templates auto-injection; current_user via the existing
    route-context convention). Never raises."""
    try:
        # Some test contexts pass a plain dict with an explicit 'locale' key.
        if hasattr(ctx, "get"):
            explicit = ctx.get("locale")
            if explicit in SUPPORTED_LOCALES:
                return explicit
            request = ctx.get("request")
            current_user = ctx.get("current_user")
        else:
            request = None
            current_user = None

        if current_user is not None:
            lang = getattr(current_user, "language", None)
            if lang in SUPPORTED_LOCALES:
                return lang
        if request is not None:
            cookie = None
            try:
                cookie = request.cookies.get(LANG_COOKIE)
            except Exception:
                cookie = None
            if cookie in SUPPORTED_LOCALES:
                return cookie
    except Exception:
        pass
    return DEFAULT_LOCALE


@pass_context
def t(ctx, key: str, **kwargs: Any) -> str:
    """Jinja2 global. Look up `key` in current locale's bundle, falling back
    to the English bundle, then to the literal key string. Fail-safe: never
    raises (a missing key surfaces as the literal key so devs see what's
    untranslated).

    Locale is resolved from the render context — `current_user.language`
    wins, then `lang` cookie on request, then `"en"`. Routes that pass an
    explicit `locale` in their context override this.

    If kwargs are supplied, the resolved string is `.format(**kwargs)`-applied
    — supports inline values like `t('alert.days_late', days=5)`. If the
    format itself errors, the unformatted string is returned (still no crash).
    """
    locale = _resolve_locale_from_ctx(ctx)

    val = TRANSLATIONS.get(locale, {}).get(key)
    if val is None:
        val = TRANSLATIONS.get(DEFAULT_LOCALE, {}).get(key)
    if val is None:
        return key  # surfaces missing keys to dev
    if kwargs:
        try:
            return val.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return val
    return val


@pass_context
def current_locale(ctx) -> str:
    """Jinja helper used by shared chrome such as the language switcher."""
    return _resolve_locale_from_ctx(ctx)


def reload_bundles() -> None:
    """For tests or hot-reload scenarios."""
    TRANSLATIONS.clear()
    _load_bundles()
