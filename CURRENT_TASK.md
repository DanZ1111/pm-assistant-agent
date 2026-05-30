# CURRENT_TASK.md

## Task
Build 25 — Beauty Department isolated deployment (code side complete; awaiting user Railway provisioning)

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder. If anything here disagrees with git, trust git.

## Current state
Build 25's code-side deliverable is complete and verified (commit pending). The Railway provisioning side is on the user.

Code-side (done by Claude):
- `DEPLOYMENT.md` — canonical Railway runbook at project root.
- `app/version.py` bumped to `1.1.0-build25`.
- `VERSION.md` + `CHANGELOG.md` + `MASTERPLAN.md` updated.
- `test_build25.py` written; all 15 assertions pass.
- `test_build24.py` loosened to tolerate post-release version bumps (so adding Build 25 doesn't invalidate the v1.1.0-release-proof test). Still 11/11.

User-action (pending):
- Provision a second Railway service per `DEPLOYMENT.md` for Beauty dept.
- Set env vars: `INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_PASSWORD`, `OPENAI_API_KEY` (Beauty's own), `SECRET_KEY` (unique), `DISABLE_RELOAD=1`. `DATABASE_URL` is auto-set by the attached PostgreSQL plugin.
- Configure custom domain (subdomain pattern: `pm.tracker.example.com`, `beauty.tracker.example.com`).
- Run the 5-step verification checklist in `DEPLOYMENT.md`.
- Delete bootstrap env vars (`INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_PASSWORD`) after first admin login.

## Verification status
- `python3 test_build25.py` — 15/15 PASS.
- Regression: `test_build24.py` 11/11, `test_build23.py` 24/24, `test_ai_e2e.py` 10P/7S/0F.

## Out of scope (deferred to v1.2 if Beauty's needs grow)
- Native-speaker review of `app/i18n/zh.json` wording.
- Full Profit Model implementation (placeholder only in v1.1).
- Row-level multi-tenancy (`Organization` table + `org_id` everywhere). Justified if 4th dept arrives or cross-dept features are needed.
- AI prompt translation, Help modal body translation, `/admin/*` page translation.
- 15 stubbed AI tools getting real handlers (only `create_journal_entry` wired in v1.1).
- Auto-provisioning script for Railway (the runbook is manual; could automate with Railway CLI in a future build).

## Next step
Wait for user to authorize push of Build 25 commit. Then user proceeds with Railway provisioning per `DEPLOYMENT.md`.
