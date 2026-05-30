# CURRENT_TASK.md

## Task
Build 25 — Beauty Department isolated deployment (post-v1.1.0)

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder. If anything here disagrees with git, trust git.

## Current state
v1.1.0 is RELEASED. Build 24 was the final release bump (commit pending — see below).

Last in-flight detail (just resolved by Claude): Codex implemented Build 24 fully (`app/version.py` → `1.1.0`, VERSION/CHANGELOG/USER_GUIDE/MASTERPLAN updated, `test_build24.py` added). Codex ran out of tokens before the final commit + push. Claude verified the work (test_build24 11/11; full v1.1 regression suite still green) and is committing Build 24 now. Push to origin is pending user authorization.

Build 25 is queued up but NOT started. It's the Beauty-dept isolated deployment per `~/.claude/plans/can-you-still-find-nested-cook.md` (architectural decision recorded: Option 4 — separate deployment per dept, same image, different DB + env vars).

## Remaining work (Build 25)
1. **Wait for user to confirm push of Build 24** before any new work.
2. Answer 4 open questions before starting Build 25:
   - Hosting platform (Railway? Docker? local?)
   - URL scheme (subdomain? path? separate domain?)
   - Beauty starts empty, or copy any shared lookup data?
   - Shared OpenAI key, or its own?
3. Provision second Railway service (same git repo).
4. Different `DATABASE_URL`, `OPENAI_API_KEY`, `INITIAL_ADMIN_USERNAME`/`PASSWORD` per service.
5. Write `DEPLOYMENT.md` runbook for spinning up a new department instance.
6. Bump `app/version.py` to `1.1.1` (or `1.1.0-build25` — user's call).
7. Verify both instances are truly isolated (browser test, regression test against each).
8. Commit + ask user before push.

## Known stale tests (pre-existing, NOT Build 24 regressions)
- `test_build8.py` — Playwright selectors look for old English nav labels and the now-removed AI Intake link. Broken since Build 22 (nav cleanup) + Build 23 (i18n). Functional coverage still provided by test_build11+.
- `test_build12.py` — 8/9; "Phase edit buttons not found" Playwright timing issue. Pre-existing.

These are documented out-of-scope. Decision: address only if Build 25 changes anything they would assert.

## Out of scope (deferred to v1.2)
- Native-speaker review of `app/i18n/zh.json` wording.
- Full Profit Model implementation (placeholder only in v1.1).
- Row-level multi-tenancy (Organization table + `org_id` everywhere). Only justified if 4th dept arrives or cross-dept features needed.
- AI prompt translation, Help modal body translation, `/admin/*` page translation.
- 15 stubbed AI tools getting real handlers (only `create_journal_entry` wired in v1.1).

## Next step
Wait for user to authorize push of Build 24. Then revisit the 4 Build 25 open questions and start implementation.
