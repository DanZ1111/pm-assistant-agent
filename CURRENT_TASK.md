# CURRENT_TASK.md

## Task
Build 23 — Chinese i18n

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder. If anything here disagrees with git, trust git.

## Current state
Build 23 implementation is complete and tested, but not committed. Do not push or commit unless the user explicitly asks.

Implemented:
- `app/i18n/` package with `en.json` + `zh.json` bundles (520 keys each), `t(...)`, `current_locale(...)`, `get_locale(...)`, and `i18n_context(...)`.
- `POST /lang/set` route with cookie persistence, logged-in `users.language` persistence, invalid-lang fallback, and local-only redirect target.
- Navbar language switcher visible to logged-in and logged-out users.
- Locale context added to user-facing TemplateResponse routes: auth, projects, intake, calendar, ideas, thesis preview.
- Broad UI translation sweep across primary Build 23 scope: nav, auth pages, projects list, My Projects, Create/Edit Project, AI-assisted create panel, project detail, Project Journal, Variants, Packaging, Quotation, Profit Model placeholder, Rendering History, Prototype Photos, Calendar, Ideas, bottom chat labels/tooltips, status/badge/empty-state copy.
- Docs/version updated for v1.1.0-build23.
- Generated `__pycache__` folders removed after testing.

Out of scope remains:
- Help modal body.
- Admin-only pages.
- AI prompts.
- Changelog/version-history prose.
- Legacy `app/templates/intake.html` artifact.

## Tests run
- `python3 -m compileall app` — PASS
- Jinja template compile smoke — 24 templates compiled
- `python3 test_build23.py` — 24 PASS / 0 FAIL
- `python3 test_build18.py` — 17 PASS / 0 FAIL
- `python3 test_build19.py` — 15 PASS / 0 FAIL
- `python3 test_build20.py` — 23 PASS / 0 FAIL
- `python3 test_build21.py` — 20 PASS / 0 FAIL
- `python3 test_build22.py` — 15 PASS / 0 FAIL
- `python3 test_ai_e2e.py` — 10 PASS / 7 SKIP / 0 FAIL (SKIPs are expected AI-call failures until server has valid OpenAI config)
- Extra Chinese-mode smoke: `/projects`, `/my-projects`, `/projects/new`, `/projects/new?tab=ai`, `/calendar`, `/ideas`, `/ideas/new`, and latest `/projects/{id}` all returned 200 with no obvious raw translation keys.

## Remaining work
1. User/native-speaker review of `app/i18n/zh.json` wording.
2. Optional full historical test sweep if desired.
3. Commit only after user explicitly asks.
