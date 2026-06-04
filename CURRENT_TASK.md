# CURRENT_TASK.md

## Task
v1.3 Build 05 — Variant Command Cards execution plan drafted for review. Build 03 and Build 04 remain implemented/tested but uncommitted.

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
1. **Review/commit v1.3 Build 03 + Build 04** — current working tree contains both implemented builds.
2. **Review v1.3 Build 05 execution plan** — `V13_BUILD05_EXECUTION_PLAN.md`.
3. **Revise/commit the Build 05 plan** after Claude/ChatGPT review.
4. **Implement v1.3 Build 05** only after the execution plan is approved.

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

## v1.3 Build 03 planning

- Added `V13_BUILD03_EXECUTION_PLAN.md`.
- Revised per Claude review: Inspired By is locked as an internal Product Concept chip-row, Product Concept gets primary `id="product-concept"` plus a hidden `#thesis` compatibility anchor, exact EN/ZH i18n strings are specified, and Build 02 Pulse wording must change from Product Thesis to Product Concept.

## v1.3 Build 03 verification

- `env BASE_URL=http://localhost:8001 python3 test_v13_build03.py` — 20/20 passed.
- `env BASE_URL=http://localhost:8001 python3 test_v13_build01.py` — 16/16 passed.
- `env BASE_URL=http://localhost:8001 python3 test_v13_build02.py` — 11/11 passed.
- `python3 test_build_v121.py` — 19/19 passed.

## v1.3 Build 04 planning

- Added `V13_BUILD04_EXECUTION_PLAN.md`.
- Plan locks Renderings as a standalone Overview section after Product Concept and before Variants.
- Source of truth is existing `project_files` rows already loaded as `renderings` and `prototype_photos`.
- Latest visual rule: newest image rendering first by `ProjectFile.uploaded_at`, newest image prototype photo second by `uploaded_at`, newest non-image rendering/prototype by `uploaded_at` as document fallback, otherwise empty state.
- Revised per Claude review: preview image maxes out at section-safe dimensions, non-image fallback is a defined file card, mixed rendering/prototype test must prove the rendering wins while the prototype link still appears, mobile width gets a real no-overflow assertion, and lightbox integration is explicitly deferred.
- No schema, service, new route, AI behavior, pinning workflow, or Designer Portal backend.

## v1.3 Build 04 implementation

- Added `latest_overview_visual` derived context on project detail; no new query/service/schema.
- Added standalone `#renderings-overview` section after Product Concept, before Variants.
- Section displays newest rendering image by `uploaded_at`, falls back to newest prototype image, then newest non-image rendering/prototype document card.
- Added safe CSS sizing so large uploaded visuals cannot dominate the page.
- Added EN/ZH i18n keys and `test_v13_build04.py`.
- Designer Portal is a disabled placeholder only; no lightbox integration.

## v1.3 Build 04 verification

- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build04.py` — 20/20 passed.
- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build03.py` — 20/20 passed.
- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build02.py` — 11/11 passed.
- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build01.py` — 16/16 passed.
- `python3 test_build_v121.py` — 19/19 passed.
- Screenshots generated under ignored `test_artifacts/`.

## v1.3 Build 05 planning

- Added `V13_BUILD05_EXECUTION_PLAN.md`.
- Plan locks Build 05 as a Variants display refactor: expandable command cards using existing `project_variants` and `project_variant_components`.
- Existing add/edit/set-primary/delete routes and CRUD services stay unchanged.
- Packaging & Accessories remains the management section; variant cards summarize project-wide and variant-specific components.
- No schema, migration, AI behavior, real profit model, variant thumbnail model, or drag/drop ordering.
