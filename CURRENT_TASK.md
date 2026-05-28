# CURRENT_TASK.md

## Task
Build 21 — Bottom AI Chat + Side Panel + Conversation History

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder. If anything here disagrees with git, trust git.

## Current state
Build 20 is shipped (latest commit). Working tree is clean. No Build 21 work started.

Roadmap scope (MASTERPLAN.md table row 1540, size: L):
- Fixed-position bottom chat input on every authenticated page.
- Input grows vertically as user types (ChatGPT-style). Files/images drag-droppable into the same box.
- Submit → right-side panel slides open with response.
- Panel has: Ask/Intake mode toggle, Project/Global scope toggle, conversation history, archive button.
- `ai_conversations` table (already exists from Build 13) stores grouping.
- Wires `create_journal_entry` as the v1.1 working Intake tool (the one real handler from Build 20).

No detailed Build 21 section exists in MASTERPLAN.md yet — write one in plan mode before coding (it's a Large build).

## Remaining work
1. Plan-mode pass first: write a Build 21 detailed section in MASTERPLAN.md before coding (this is the largest remaining build).
2. Implement the bottom chat UI + side panel + chat persistence.
3. Wire dispatch from Build 20's `app/ai/tools.py` into the chat flow.
4. Tests + docs + version bump.
5. Commit only after user explicitly asks.

## Constraints
- Build 20's dispatcher is the single source of AI-tool truth — do not reimplement permission logic elsewhere.
- Only `create_journal_entry` actually mutates DB via chat in v1.1. Other tools should show a "not yet wired" message gracefully in the UI.
- Do not push to origin without explicit user instruction.
- If unsure, read the code instead of trusting this file.

## Next step
Enter plan mode to draft the Build 21 detail section in MASTERPLAN.md. Build 21 is "size: L" — expect more sub-pieces than the recent S/M builds.
