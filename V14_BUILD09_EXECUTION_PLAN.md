# v1.4 Build 09 Execution Plan - Release Hardening

## Status

Execution plan and implementation scope for the final v1.4 Planning Sandbox
release-hardening build.

Predecessor: v1.4 Build 08 - Save Workflow As Template.

Successor: none inside v1.4; future sandbox expansion starts after v1.4.0 is
released and reviewed.

Canonical design references:
- `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md` v1.4-09 row.
- `V14_PLANNING_SANDBOX_IMPLEMENTATION_PLAN.md` section "v1.4 Build 09 -
  Release Hardening".

## Purpose

Close the Planning Sandbox version as v1.4.0. This build proves the full
sandbox loop works as a PM workflow, not just as isolated CRUD pieces:
template -> sandbox graph -> edit -> schedule -> no live mutation before Apply
-> Apply -> live phases -> save reusable template.

## Scope

In:

1. Version bump to v1.4.0.
2. Release documentation roll-up:
   - `VERSION.md`
   - `CHANGELOG.md`
   - `USER_GUIDE.md`
   - `MASTERPLAN.md`
3. AI tools registry roll-up for the sandbox surface:
   - planned/deferred template listing,
   - planned/deferred template application,
   - planned/deferred sandbox apply,
   - planned/deferred schedule explanation,
   - planned/deferred sandbox edit proposals.
4. Add `test_v14_build09.py` release-proof scenario contract runner.
5. Refresh older release-proof tests only where version bump tolerance is
   needed.

Out:

- No schema changes.
- No new product feature.
- No sandbox UI redesign.
- No AI handler implementation.
- No behavior changes to Apply, templates, node editing, or schedule math.

## Architecture Review

1. Problem solved: release hardening proves v1.4 can ship as a coherent PM
   Planning Sandbox workflow.
2. Tables affected: no schema changes; tests exercise existing sandbox,
   template, phase, and apply-event tables.
3. Real column vs notes: no new columns needed; release evidence belongs in
   docs and regression tests.
4. Service layer: no new service layer write path; tests use existing CRUD
   services.
5. Change log: no runtime project change is part of this build, but docs
   record release history.
6. Rollback: version/docs/test-only changes can be reverted without data
   migration.

## Feature Design Review

1. Real problem: before release, PMs need confidence that the full sandbox loop
   works across realistic template families.
2. Repeated use: every PM starts future projects from these workflows.
3. Structured data: the release proof exercises existing graph/template/phase
   structures.
4. Notes fallback: no, release correctness cannot live in prose alone.
5. Intake burden: scenario tests reduce manual QA burden.
6. AI role: AI tool surface remains planned/deferred and confirmation-only.
7. Display payoff: release docs explain the PM workflow clearly.
8. Migration impact: none.
9. Minimal schema: zero schema change.
10. Minimal UI change: zero UI change.
11. Deferred: real AI sandbox handlers, template editing/deletion, publishing,
    and richer workflow analytics.

## Backend Honesty Mapping

| Visible/Release Surface | Source Of Truth | Write Path | Derived Rule | Permission | Test |
|---|---|---|---|---|---|
| Runtime version | `app/version.py` | constants only | navbar/help reads current version | all users | `test_v14_build09.py` |
| Release docs | `VERSION.md`, `CHANGELOG.md`, `USER_GUIDE.md`, `MASTERPLAN.md` | docs only | preserve older release markers | n/a | release-proof assertions |
| System templates | `planning_templates` seeded rows | migration 010 seed | exactly six active system templates | all authenticated view | seed invariant |
| Module library | `planning_module_library` seeded rows | migration 007 seed | at least 24 active modules | all authenticated view | seed invariant |
| Schedule estimate | `compute_sandbox_schedule` | read-only service | recompute from sandbox graph | all project viewers | scenario runner |
| No live mutation before Apply | `project_phases` count | no write until Apply | create/edit/save template do not write phases | PM/admin only | scenario runner |
| Apply result | `project_phases` + `planning_apply_events` | `apply_sandbox_to_project` | one phase per scheduled node, audited apply event | PM/admin only | scenario runner |
| Saved user template | template tables | `save_sandbox_as_template` | copied graph reusable by picker | PM/admin only | scenario runner |
| AI sandbox surface | `AI_TOOLS_REGISTRY.md` | docs only | planned/deferred; no handler | confirmation required later | registry assertion |

## Test Plan

Add `test_v14_build09.py` covering:

1. Runtime version and release-doc markers for v1.4.0.
2. v1.2.1 and v1.3.0 release markers remain preserved.
3. AI registry includes the v1.4 sandbox tool surface but no chat handler.
4. Migration/seed invariants:
   - migrations 007, 009, 010 exist,
   - exactly six active system templates,
   - at least 24 active planning modules.
5. Scenario contract runner:
   - for each of the six system templates,
   - create a project,
   - create sandbox from template,
   - edit the first node,
   - persist a position,
   - save a reusable user template,
   - assert no `project_phases` rows exist before Apply,
   - apply sandbox,
   - assert project phases match scheduled nodes,
   - assert one apply event exists,
   - assert timeline history exposes a plan-applied event.
6. i18n parity remains exact.
7. Roll-up inventory includes `test_v14_build01.py` through
   `test_v14_build09.py`.

Regression sweep:
- `python3 test_v14_build09.py`
- `python3 test_v14_build08.py`
- `python3 test_v14_build07.py`
- `python3 test_v14_build06.py`
- `python3 test_v14_build05.py`
- `python3 test_v14_build04.py`
- `python3 test_v14_build03.py`
- `python3 test_v14_build02.py`
- `python3 test_v14_build01.py`
- `python3 test_v13_build10.py`
- `python3 test_build_v121.py`
- `git diff --check`

## Acceptance Criteria

- Runtime reports v1.4.0.
- Docs explain v1.4.0 and preserve earlier release proof.
- Scenario contract runner passes across all six system templates.
- No live `project_phases` mutation happens before Apply.
- Sandbox AI surface is documented but not silently wired.
- All v1.4 build regressions and v1.3/v1.2.1 baselines pass.
