# CURRENT_TASK.md

## Task
v1.3 Build 02 — Project Pulse v1 (rules-based) implemented and tested. Awaiting review/commit direction.

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth.

## What just shipped (v1.2.1)

Release-hardening rollup of 7 patches that landed on the v1.2.0 line:

| # | Patch | Commit |
|---|---|---|
| 1 | Chinese IME composer fix v2 | `7d56198` |
| 2 | Railway nixpacks Python-only | `2bd82bf` |
| 3 | PM-facing price strings | `1465265` |
| 4 | Project detail layout refactor | `36a787e` |
| 5 | Build 30A — project creation safety | `cab8884` |
| 6 | Build 30B — Excel batch intake | `1d811b9` |
| 7 | Build 30C — PM draft delete | `b0f6ad3` |

Plus the v1.2.1 release-hardening commit itself (test_build_v121, docs rollup, version bump).

## Verification at ship time
- `python3 test_build_v121.py` — 19/19 (release-proof regression covering version source, docs strings, USER_GUIDE coverage, regression-file inventory, i18n parity, and 7 behavior locks).
- Regression: `test_build14`, `test_build16-30c` all green. `test_ai_e2e.py` 15P/2S/0F baseline preserved.
- Browser: navbar Help button shows `v1.2.1`, footer shows `PM Product Tracker v1.2.1`, Help modal shows the new build name.
- i18n parity: 538/538.

## v1.2 patch series — empty queue
`## Unreleased` in CHANGELOG is now empty. The next patch can either:
- Land directly on `v1.2.1` and join a fresh Unreleased queue, OR
- Trigger a v1.3.0 minor release if it's a real new feature (e.g., the deferred Native-speaker zh review, Profit Model implementation, etc.)

## Known v1.2.1 outstanding items (admin-only, no code)
- **One-time cleanup of the original 6 admin-linked duplicates** from the Build 30A backstory incident. Build 30A prevented new ones; this cleanup is for the existing rows. Either delete 5 (keep the last) via admin UI, or reassign their PM to the real PM and let her use the Build 30C delete capability.

## Deferred to future v1.3
- Native-speaker Chinese review of strings added in Builds 26-30C.
- AI prompt translation, Help modal body translation, `/admin/*` page translation.
- Full Profit Model implementation (placeholder still ships).
- Row-level multi-tenancy (`Organization` table + `org_id` everywhere). Deployment-level isolation (Build 25) remains the answer for ≤3 departments.
- Bulk delete from the projects list / soft-delete with undo window.
- Auto-provisioning script for Railway (the DEPLOYMENT.md runbook is still manual).
- Pruning the now-historical "Claude Review Request" block at the end of `BUILD26_CODEX_PLAN.md`.

## Next step

Wait for user direction. Suggested directions:
1. **Review v1.3 Build 02** — Overview now starts with rules-based Project Pulse v1.
2. **Commit v1.3 Build 02** — changes are template/CSS/i18n/test/docs only; no schema, route, service, or AI mutation changes.
3. **Plan v1.3 Build 03** — create and review/commit `V13_BUILD03_EXECUTION_PLAN.md` before any Build 03 code.

## v1.3 process update

Starting with v1.3 Build 03, every build gets a short build-specific execution plan before coding. The execution plan should be committed/reviewed first and include exact files/components, source-of-truth fields, permissions, i18n labels, tests, deferrals, and rollback/safety notes.

## v1.3 Build 01 verification

- `env BASE_URL=http://localhost:8001 python3 test_v13_build01.py` — 16/16 passed.
- `python3 test_build_v121.py` — 19/19 passed.
- Screenshots generated during test under ignored `test_artifacts/`.

## v1.3 Build 02 verification

- `env BASE_URL=http://localhost:8001 python3 test_v13_build02.py` — 11/11 passed.
- `env BASE_URL=http://localhost:8001 python3 test_v13_build01.py` — 16/16 passed.
- `python3 test_build_v121.py` — 19/19 passed.
