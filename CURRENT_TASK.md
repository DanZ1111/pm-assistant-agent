# CURRENT_TASK.md

## Task
Build 26 — Professional assistant workspace + project-aware Idea capture (`v1.2.0-build26`)

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder.

## Current state
Codex implemented the Build 26 milestone from `BUILD26_CODEX_PLAN.md`. The app now has a compact assistant dock, resizable desktop split workspace, mobile full-screen assistant pane, panel composer, segmented Ask / Capture and This Project / Global controls, immutable conversation scope, role-filtered active-project prompt context, manual Create & Link Idea, and Idea-specific confirm/cancel cards for create/link/update actions.

No schema migration. Build 27 remains separate: generalized proposal cards, the broader daily PM tool set, and Global read-only search.

## Safety choices
- AI Idea writes do not apply silently. The model creates a pending review card; the confirm endpoint re-checks auth and permissions before dispatch.
- Viewers are read-only for Good Ideas mutations across manual and AI paths.
- `current_stage`, `delayed`, and `needs_info` remain derived.

## Verification so far
- `python3 test_build26.py` — 19/19 passing.
- Static checks: JSON bundle parity, `python3 -m compileall -q app`, `node --check app/static/js/main.js`, and `git diff --check` passing.
- Regressions: `test_build20.py` 23/23, `test_build21.py` 20/20, `test_build22.py` 15/15, `test_build23.py` 24/24, `test_build24.py` 11/11, `test_build25.py` 15/15.
- `test_ai_e2e.py` — 10 passed, 7 skipped external-AI checks, 0 failed.
- Headless Playwright geometry smoke passed at desktop `1600x1000` and mobile `390x844`; screenshots are under `/tmp/pm-tracker-build26/`.
- Refined screenshots were visually inspected after the expanded-nav compacting pass. Build 26 is commit-ready.

## Remaining
Await user review and explicit commit / push instruction.

## Do not do yet
- Do not implement Build 27 or Build 28.
- Do not commit or push unless the user explicitly asks.
