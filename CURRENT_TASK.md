# CURRENT_TASK.md

## Task
Write `test_ai_e2e.py` — comprehensive AI end-to-end test (cross-cuts Builds 5/6/7/11/14/15/20/21/22)

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder. If anything here disagrees with git, trust git.

## Current state
Build 22 is shipped (latest commit). Working tree is clean. No `test_ai_e2e.py` written yet.

This is a deliberate inter-build task — not numbered. It produces a single standalone test file that exercises every AI surface with real OpenAI calls. The test must skip gracefully (not fail) when the server's `OPENAI_API_KEY` is invalid, so it's safe to run any time without breaking CI.

## Scope (per agreed plan)
One file: `test_ai_e2e.py` at project root. Hits these endpoints with live OpenAI calls:
1. POST `/ai/intake/extract` — text intake (project + idea classification both)
2. POST `/ai/intake/extract-file` — file intake (PDF + image)
3. POST `/ai/help/ask` — Help Q&A + viewer refusal
4. POST `/journal/{id}/summarize` — Journal AI summary
5. POST `/projects/{id}/thesis/extract` — Business plan thesis extraction
6. POST `/ai/chat` — Bottom chat with tool invocation (`create_journal_entry` round-trip)

Skip behavior: if any endpoint surface returns "AI error" / "extraction failed" / 401, mark that case as SKIPPED with a clear note. Other structural assertions (permission guard, routing, schema) still run regardless of key validity.

## Remaining work
1. Read the routes above to confirm exact paths and form fields.
2. Write the test file with skip-on-error semantics.
3. Run it (it'll likely skip most cases until the user fixes their OpenAI env).
4. Commit as its own commit: `Add test_ai_e2e.py — comprehensive AI e2e test (skips when OPENAI_API_KEY is invalid)`.
5. After commit, CURRENT_TASK.md rotates to Build 23 — Chinese i18n (L).

## Constraints
- Do not modify any AI logic itself. The test only exercises existing endpoints.
- Skip-on-error is mandatory — the test must pass in a no-key environment.
- Do not push to origin without explicit user instruction.
- If unsure, read the code instead of trusting this file.

## Next step
Read `app/routes/journal.py`, `app/routes/projects.py` (thesis extract route), and confirm endpoint paths. Then write `test_ai_e2e.py`.
