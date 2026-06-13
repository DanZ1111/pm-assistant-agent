# v1.5 Build 10 Plan — Release Hardening

## Status

Implementation plan for v1.5 Build 10 after Build 09 Designer Manager
Operations is committed.

Parent plan:

- `V15_MASTERPLAN.md`

Canonical PRD:

- `V15_DESIGNER_PORTAL_PRD.md`

## Purpose

Ship v1.5 as an internal Designer Portal MVP with version/docs updates and
release-proof regression coverage.

Build 10 does not add new product workflow capability.

## Scope

In:

1. Bump runtime/docs to `v1.5.0`.
2. Add v1.5 release notes to `VERSION.md` and `CHANGELOG.md`.
3. Document v1.5 AI tool surface as intentionally deferred/no write handlers.
4. Add a release-proof `test_v15_build10.py` covering:
   - version constants/docs,
   - committed v1.5 plan/build artifacts,
   - migrations 011-015,
   - i18n parity,
   - permission boundaries,
   - designer portal happy-path workflow tests remain present.
5. Run Build 10 test plus representative v1.5 regressions.

Out:

- no new schema,
- no new routes,
- no new UI,
- no AI write handlers,
- no scenario promotion unless already covered by existing acceptance files,
- no push to origin.

## Feature Design Review

1. Real problem: v1.5 needs a clear release boundary and proof it did not
   weaken permissions.
2. Repeated: every major release needs version/docs/test hardening.
3. Structured data: no new workflow data is required.
4. Notes fallback: release notes and tests are the right artifact.
5. Intake burden: none for PMs/designers.
6. AI role: document deferred AI writes only.
7. Display payoff: app version and docs match shipped behavior.
8. Migration impact: none.
9. Minimal schema: no schema change.
10. Minimal UI change: no UI change beyond existing version text.
11. Deferred: AI handlers, rewards, design library, external sharing.

## Architecture Review

1. Problem solved: release proof and documentation alignment.
2. Tables/services affected: none.
3. Real column vs notes: no new column.
4. Service layer: no service mutation.
5. Change log: docs-only release entry; no runtime change-log row.
6. Rollback: revert docs/version/test files.

## Backend Honesty Mapping

| Visible Field / Action | Source Of Truth | Write Path | Derived Rule | Permission Rule | Test |
|---|---|---|---|---|---|
| Runtime version | `app/version.py` | constants update | navbar/help reads runtime constants | all users | Build 10 version test |
| Release docs | `VERSION.md`, `CHANGELOG.md` | docs update | v1.5 release notes list shipped builds | n/a | Build 10 docs test |
| AI boundary | `AI_TOOLS_REGISTRY.md` and release docs | docs update | no v1.5 AI write handlers | n/a | Build 10 AI boundary test |
| Permissions | route tests from v1.5 suite | no new write path | designer roles remain portal-only | role-based | Build 10 regression references |

## Testing Plan

Create:

- `test_v15_build10.py`

Required assertions:

1. Runtime version is `1.5.0` and docs agree.
2. Changelog has a `v1.5.0` release entry.
3. v1.5 plan and test artifacts for Builds 01-10 exist.
4. Migrations 011-015 are present.
5. i18n EN/ZH parity is exact.
6. AI tools registry documents Designer Portal write handlers as deferred.
7. No v1.5 AI write handler markers exist in `app/ai/tools.py`.
8. Designer-manager/project permission boundary tests are present.
9. Release-proof tests reference the full PM/designer workflow.

Verification target:

- `python3 test_v15_build10.py`
- `python3 test_v15_build09.py`
- `python3 test_v15_build08.py`
- `python3 test_v15_build07.py`
- `python3 test_build_v121.py`
- `git diff --check`
