# CURRENT_TASK.md

## Task
Build 26 — AI Side Panel UX polish + Idea tools wiring (plan written, awaiting Codex review)

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder. If anything here disagrees with git, trust git.

## Current state
Build 25's code is fully shipped (commit `af96b46` on `main`, plus follow-up CSS polish `dfb454a`). The Railway provisioning for the Beauty Department instance is on the user — out of code scope.

Build 26 is **plan only** right now. The plan lives in `BUILD26_PLAN.md` at project root. It addresses six AI-side-panel UX issues plus wires the `create_idea` + `link_idea_to_project` + minimal `update_idea` tools (schemas already exist; only handlers stubbed). No schema change.

## Who's doing what

- **Claude** (this session): wrote the plan, committed it. Will not write code until Codex has reviewed.
- **Codex** (next): please open `BUILD26_PLAN.md`, read it, then add your review at the bottom under `## Codex Review`. Either +1 the plan, edit sections directly with rationale, or list blocking concerns. Once you're done, the user will decide whether to start implementation as-is or with your amendments.
- **User**: triggers Codex, then says "go" (or "go with Codex's amendments") to start implementation.

## Files Codex should read first

In this order, to avoid wasted context:
1. `BUILD26_PLAN.md` — the proposal
2. `app/templates/components/bottom_chat.html` — both the bottom bar and the side panel live in this single file
3. `app/static/js/main.js` lines ~212-352 — open/close/archive/send logic
4. `app/ai/tools.py` lines 265-408 — `create_idea` + `link_idea_to_project` schemas, permission rules, dispatcher
5. `app/ai/prompts.py` lines 124-150 — `CHAT_INTAKE_SYSTEM_PROMPT`
6. `app/routes/ai_chat.py` lines 73-181 — POST `/ai/chat` handler

## Out of scope for this build
See `BUILD26_PLAN.md` § "Out of scope". Tl;dr: not wiring the other 12 stubbed AI tools, not row-level multi-tenancy, not modal popups, not native-speaker zh review.

## Next step
Awaiting Codex review of `BUILD26_PLAN.md`. Implementation paused.
