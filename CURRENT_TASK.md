# CURRENT_TASK.md

## Task
Build 28 — Assistant file and image intake (`v1.2.0-build28`)

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder.

## Current state
Build 27 was committed locally as `4e0c0aa` and has not been pushed. Codex is implementing Build 28 from `BUILD26_CODEX_PLAN.md`: add pending PDF, DOCX, and image discussion inputs to the assistant workspace, keep bytes outside public uploads until confirmation, and persist confirmed saves through the normal audited project-file path.

No schema migration. Build 29 remains separate: v1.2.0 release hardening.

## Safety choices
- Pending attachment bytes live in ignored `app/pending_uploads/`, outside mounted `/uploads`.
- Confirmed save uses the normal file service with `changed_by="ai"` and `source_type="ai_chat"`.
- Request-time stale cleanup removes pending inputs after 24 hours; no worker or migration.
- Viewers remain read-only and cannot upload assistant attachments.

## Verification so far
- Build 27 committed baseline: `test_build27.py` 29/29, Build 20-26 regressions passing, static checks passing, `test_ai_e2e.py` 10 passed / 7 external-AI skips / 0 failed.
- `python3 test_build28.py` — 23/23 passing after bounded-read hardening.
- Static checks: `python3 -m compileall -q app`, Python test-file compilation, JSON parse and EN/Chinese parity at 537/537, `node --check app/static/js/main.js`, and `git diff --check` passing.
- Regressions: `test_build20.py` 24/24, `test_build21.py` 20/20, `test_build22.py` 15/15, `test_build23.py` 24/24, `test_build24.py` 11/11, `test_build25.py` 15/15, `test_build26.py` 19/19, and `test_build27.py` 29/29.
- `test_ai_e2e.py` — 10 passed, 7 skipped external-AI checks, 0 failed.
- Browser interaction smoke passed for desktop dock, expanded desktop split panel, and refined mobile full-screen composer. Screenshots: `/tmp/pm-tracker-build28-desktop-dock.png`, `/tmp/pm-tracker-build28-desktop-expanded.png`, and `/tmp/pm-tracker-build28-mobile-refined.png`.

## Remaining
- Await user review and explicit commit / push instruction.

## Do not do yet
- Do not implement Build 29.
- Do not commit or push unless the user explicitly asks.
