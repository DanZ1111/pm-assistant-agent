# CURRENT_TASK.md

## Task
Build 27 — Confirmed daily PM actions + Global read-only search (`v1.2.0-build27`)

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder.

## Current state
Build 26 shipped and was pushed as `7d3a180`. Codex is implementing the Build 27 milestone from `BUILD26_CODEX_PLAN.md`: generalize the existing Idea proposal-card lifecycle for all assistant writes, add editable reviewed values with server-side revalidation, wire the daily PM handlers through audited CRUD services, and make Global scope truthful with read-only project search and role-filtered context.

No schema migration. Build 28 remains separate: assistant file and image intake.

## Safety choices
- Every AI mutation, including journal capture and file comments, waits for a proposal-card confirmation. The confirm endpoint re-checks auth, project access, relationships, allowlists, and reviewed args before dispatch.
- Read-only `search_projects` and `get_project_context` execute immediately and return only accessible, role-filtered data.
- Viewers remain read-only for mutations.
- `current_stage`, `delayed`, and `needs_info` remain derived.

## Verification so far
- Build 26 baseline before Build 27: `test_build26.py` 19/19 and all Build 20-25 regressions passing.
- `python3 test_build27.py` — 29/29 passing after the final proposal-card and read-only result refinement.
- Static checks: `python3 -m compileall -q app`, JSON parse and EN/Chinese parity at 534/534, `node --check app/static/js/main.js`, Python test-file compilation, and `git diff --check` passing.
- Regressions: `test_build20.py` 24/24, `test_build21.py` 20/20, `test_build22.py` 15/15, `test_build23.py` 24/24, `test_build24.py` 11/11, `test_build25.py` 15/15 after widening its staged-v1.2 assertion, and `test_build26.py` 19/19.
- `test_ai_e2e.py` — 10 passed, 7 skipped external-AI checks, 0 failed.
- Headless Playwright geometry smoke passed at desktop `1600x1000` and mobile `390x844`; visually inspected refined screenshots are under `/tmp/pm-tracker-build27-*-refined.png`.

## Remaining
- Await user review and explicit commit / push instruction.

## Do not do yet
- Do not implement Build 28.
- Do not commit or push unless the user explicitly asks.
