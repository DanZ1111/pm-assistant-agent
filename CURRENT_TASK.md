# CURRENT_TASK.md

## Task
Build 22 — AI-Assisted Create Project (remove AI Intake from nav)

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder. If anything here disagrees with git, trust git.

## Current state
Build 21 is shipped (latest commit). Working tree is clean. No Build 22 work started.

Roadmap scope (MASTERPLAN.md table row 1541, size: M): the Create Project page gets two tabs — Manual Form / AI-Assisted. AI-Assisted is the new home for the unified text+file intake. The `/ai/intake` link is removed from the navbar but the route stays and redirects to the Create Project AI tab.

No detailed Build 22 section exists in MASTERPLAN.md yet — write one in plan mode before coding.

## Remaining work
1. Plan-mode pass: write a Build 22 detailed section in MASTERPLAN.md.
2. Move the existing `/ai/intake` UI into a tab on `/projects/new` (Manual / AI-Assisted).
3. Remove the AI Intake link from `base.html` navbar; keep the route as a 303 redirect to `/projects/new?tab=ai`.
4. Tests + docs + version bump.
5. Commit only after user explicitly asks.

## Constraints
- Don't break existing `/ai/intake` POST flows used by HTMX — they should continue working from the new tab location.
- Don't change the AI intake logic (parser, prompts) — just move where the UI lives.
- Do not push to origin without explicit user instruction.
- If unsure, read the code instead of trusting this file.

## Next step
Enter plan mode to draft the Build 22 detail section. The intake page already has working POST endpoints in `app/routes/intake.py`; the work is mostly UI relocation + a small redirect.
