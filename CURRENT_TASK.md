# CURRENT_TASK.md

## Task
Build 30A — Project creation safety (idempotency + PM ownership). Implementation complete in working tree. **Awaiting user authorization to commit + push.**

Build 30B (Excel batch intake) and Build 30C (PM draft delete) remain deferred per user direction.

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder.

## What changed in Build 30A

### Bug fixes
- **Bug A** — `POST /projects/new` and `POST /ai/intake/confirm` had no server-side idempotency. PM double-clicking Submit during slow request produced N duplicate rows. Now: one-shot `submission_token` minted on GET, claimed atomically with the project insert via UPDATE-rowcount. Racing POSTs redirect to the originally-created project.
- **Bug B** — Blank `product_manager` form field → NULL → PM's My Projects empty (admin sees all). Now: defaults to `current_user.username` on create. Typed display_names normalized to canonical username when unambiguous. `get_projects_for_user()` matches by username OR display_name.

### Files modified
- `app/models.py` — `ProjectCreationToken` model added.
- `app/migrations.py` — migration `004_v1_2_add_project_creation_tokens` (additive table + index, idempotent).
- `app/crud.py` — `_build_project_in_session()` extracted, `create_project()` preserved as wrapper, new `create_project_with_idempotency()`, new `normalize_pm_value()`, new `mint_creation_token()`, `get_projects_for_user()` extended to match display_name.
- `app/routes/projects.py` — GET mints token; POST consumes it, defaults blank PM, normalizes display_name.
- `app/routes/intake.py` — `_ai_panel_response()` now mints fresh tokens; POST `/ai/intake/confirm` consumes them and applies the same PM defaulting + normalization.
- `app/templates/project_form.html` — hidden `submission_token` input + `data-idempotent` attr + inline spinner script.
- `app/templates/components/ai_intake_panel.html` — same hidden token treatment for the AI confirm form.
- NEW: `test_build30.py` (23 assertions).
- `CHANGELOG.md` — Build 30A entry added to `## Unreleased`.
- `MASTERPLAN.md` — Build 30A detail section.

No version bump. Stays on `v1.2.0` consistent with the other four shipped unreleased patches (IME v2 `7d56198`, nixpacks `2bd82bf`, price strings `1465265`, layout refactor `36a787e`). Future `v1.2.1` release-hardening will roll them up.

## Verification

- `python3 test_build30.py` — **23/23** including a 5-parallel-POST stress test that proves exactly 1 row gets created from concurrent submissions sharing one token.
- Migration 004 applied cleanly on the dev DB. Idempotent — safe to re-run.
- Manual smoke (browser, dev server):
  1. Log in as PM. New Project. Click Submit 6 times rapidly. → exactly 1 project, browser lands on its detail page.
  2. Leave PM field blank → project's product_manager is the PM's username → /my-projects includes it.
  3. Type the PM's display name in PM field → normalized to their username.
  4. Same flow via the AI Assisted tab.

## One-time admin cleanup (separate from this build, no code)

The 6 admin-linked duplicates from the original incident need a manual admin cleanup. SQL or admin UI either works:

```sql
SELECT id, name, product_manager, created_at FROM projects
WHERE product_manager IS NULL OR product_manager = 'admin'
ORDER BY created_at DESC LIMIT 20;
-- Pick the 5 you want to delete and run:
DELETE FROM project_changes WHERE project_id IN (?, ?, ?, ?, ?);
DELETE FROM project_phases WHERE project_id IN (?, ?, ?, ?, ?);
DELETE FROM project_files WHERE project_id IN (?, ?, ?, ?, ?);
DELETE FROM ai_messages WHERE project_id IN (?, ?, ?, ?, ?);
DELETE FROM projects WHERE id IN (?, ?, ?, ?, ?);
-- For the survivor, reassign PM via the edit UI to the real PM's username.
```

After cleanup + the Build 30A fix, the same incident cannot recur (server-side token blocks duplicates, blank PM defaults to creator's username).

## What's NOT in this build

- Excel batch intake → **Build 30B**.
- PM draft delete → **Build 30C** (needs explicit policy decision from user: 48h vs "until first phase advance" vs other).
- v1.2.1 release-proof regression — happens when the unreleased patches accumulate enough.

## Next step

Awaiting user authorization to commit + push Build 30A. Manual browser smoke encouraged before push (the 6-click scenario in particular). After Build 30A lands, the natural next moves are:

1. **Admin one-time cleanup** of the 6 existing duplicates (manual, SQL or UI).
2. **Build 30B planning** — Excel batch intake spec, with the 12 ambiguities from the original mega-plan resolved.
3. **Build 30C policy decision** — PM delete window: 48h vs "until first phase advance" vs other.
