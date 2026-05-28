# CURRENT_TASK.md

## Task
Build 20 — AI Tools Architecture + Permission Guard update

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder. If anything here disagrees with git, trust git.

## Current state
Build 19 is shipped (latest commit). Working tree is clean. No Build 20 work started.

Roadmap scope (MASTERPLAN.md table row 1539): create `app/ai/tools.py` with JSON schemas for all 14 tools. Only `create_journal_entry` is actually wired in v1.1; the rest are schemas with TODO handlers. Update `AI_TOOLS_REGISTRY.md`. Extend `is_forbidden_ai_question` and `sanitize_project_for_user` to filter journal entries, business plans, quotations, variant costs, and packaging costs for viewers.

No detailed Build 20 section exists in MASTERPLAN.md yet — write one when starting (matches the Build 12-16 pattern).

## Remaining work
1. Plan-mode pass first: write a Build 20 detailed section in MASTERPLAN.md before coding.
2. Implement the 14 JSON tool schemas + only-`create_journal_entry`-handler wiring.
3. Extend the AI Permission Guard (`is_forbidden_ai_question`, `sanitize_project_for_user`).
4. Tests + docs + version bump.
5. Commit only after user explicitly asks.

## Constraints
- Only `create_journal_entry` gets a real handler in v1.1 — others are JSON schema stubs.
- Do not push to origin without explicit user instruction.
- If unsure, read the code instead of trusting this file.

## Next step
Read `MASTERPLAN.md` table row 1539, then enter plan mode to draft the Build 20 detail section (FDR-style 11 questions, affected files, AI tool registry implications, schema review).
