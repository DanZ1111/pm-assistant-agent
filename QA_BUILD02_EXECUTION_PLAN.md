# QA Build 02 Execution Plan — First 5 Hard Contract Scenarios

## Status

Execution plan for the second QA Build.

Predecessor: QA Build 01 — Runner skeleton + golden tests (`850380a`, local).

Successor: QA Build 03 — Playwright UI Layer.

Canonical plan: `/Users/Mordred5687/.claude/plans/can-you-still-find-nested-cook.md`.

## Purpose

Lock the five load-bearing PM-workflow contracts as deterministic, runnable
scenarios. These five together form the v1.x release gate.

Every scenario obeys User locks 7 (5 metadata fields), 8 (setup/run/check),
and 9 (run uses only actions.*, check uses only assertions.*).

## Scope

In:

1. Five scenarios under `scenario_contracts/contracts/`:
   - `pm_project_ownership.py` — PMs see only their projects in My Projects;
     admin sees all; viewer sees none.
   - `viewer_permission_boundaries.py` — viewer's `can_edit_project`,
     `can_view_costs`, `can_view_journal`, `can_view_sensitive_fields`
     all return False.
   - `variant_pricing_isolation.py` — creating/editing variant pricing
     does not mutate project-level cost fields.
   - `timeline_delay_reason_audit.py` — adjusting a phase's planned_end_date
     with a reason writes a `phase_plan_changes` row + a `project_changes`
     row whose summary surfaces the reason.
   - `sandbox_apply_invariant.py` — before Apply, `project_phases` is empty
     for a fresh project; after Apply, phases match the sandbox graph,
     a `planning_apply_events` row exists, and a `plan_applied` change-log
     row exists.
2. Extend `scenario_contracts/lib/actions.py` with:
   - `create_project_for_pm`
   - `create_variant`
   - `create_sandbox_from_template`
   - `apply_sandbox`
3. Extend `scenario_contracts/lib/assertions.py` with:
   - `assert_project_visible_to_user`
   - `assert_project_not_visible_to_user`
   - `assert_permission`
   - `assert_phase_field`
   - `assert_no_rows`
4. Extend `scenario_contracts/lib/fixtures.py` with:
   - `create_user` overload to allow `role="viewer"` and `role="admin"`
     (already supported; verify and document).
   - `create_project_with_costs` — wraps existing helper plus initial
     `target_factory_cost` + `target_msrp`.
5. Add `test_qa_build02.py` regression that runs all 5 scenarios via the
   runner and asserts each behaves exactly as designed.

Out:

- No Playwright (QA-03).
- No AI mocking (QA-04).
- No new permissions or auth changes.
- No app/* source modifications.
- No version bump.
- No new migrations.

## Architecture Review

1. Problem solved: each of these 5 contracts has been re-validated by hand
   in every v1.x release for months. Turning them into runnable scenarios
   gives a deterministic release gate the team can re-run on every commit.
2. Tables touched (by setup/run): `users`, `projects`, `project_phases`,
   `project_variants`, `planning_sandboxes`, `planning_sandbox_nodes`,
   `planning_apply_events`, `project_changes`, `phase_plan_changes`. All in
   the per-scenario in-memory SQLite — never the real DB.
3. Real column vs notes: every assertion targets a real column or a service
   helper return value. No "notes contains" string-grep brittleness.
4. Service layer: actions.* calls only public `app.crud.*` and
   `app.dependencies.*`. No direct ORM mutation in run().
5. Change log: each mutating action calls into the real `write_change()`
   path inside the service helper. Scenarios assert the resulting change-log
   rows.
6. Rollback: deleting `scenario_contracts/contracts/*.py` removes the
   contracts; library extensions are purely additive.

## Backend Honesty Mapping

| Visible behavior | Source of truth | Write path | Derived rule | Permission | Test |
|---|---|---|---|---|---|
| PM "My Projects" list | `projects.product_manager` | `crud.create_project` | `crud.get_projects_for_user(user)` filters by lower-case match against `username` and `display_name` | viewer always empty | `pm_project_ownership` |
| Admin "All Projects" list | all `projects` rows | n/a | `get_projects_for_user(admin)` returns `get_projects(db)` | admin sees all | `pm_project_ownership` |
| Viewer mutation refusal | `app.dependencies.can_edit_project` | n/a | role check at route layer | viewer always False | `viewer_permission_boundaries` |
| Viewer cost/factory/journal hiding | `app.dependencies.can_view_costs / can_view_journal / can_view_sensitive_fields` | n/a | role check | viewer always False | `viewer_permission_boundaries` |
| Variant cost isolation | `project_variants.target_factory_cost / target_msrp` | `crud.create_variant` | variant costs are independent columns | scoped to project | `variant_pricing_isolation` |
| Phase due-date adjustment audit | `phase_plan_changes` + `project_changes` | `crud.update_phase(reason=...)` | every planned_*_date shift writes a `phase_plan_changes` row | `can_edit_project` | `timeline_delay_reason_audit` |
| Sandbox draft isolation | `planning_sandbox_nodes` only; `project_phases` untouched | sandbox CRUD helpers | sandbox edits do not call `update_phase` | `can_edit_project` + sandbox is `draft` | `sandbox_apply_invariant` |
| Apply audit | `planning_apply_events` + `project_changes('plan_applied')` | `crud.apply_sandbox_to_project` | one event row + one change-log row per Apply | `can_edit_project` + draft sandbox + preconditions | `sandbox_apply_invariant` |

## Locked Implementation Decisions

1. **Discipline boundary holds.** `run()` calls only `actions.*`; `check()`
   calls only `assertions.*`. No exceptions for any of the 5 scenarios.
2. **Permission assertions are static.** `viewer_permission_boundaries`
   has an effectively empty `run()` — the contract is about static helpers,
   not state changes. The scenario shape still requires `run()` to be
   defined.
3. **No must_not_mutate in QA-02.** The helper's `created_at == updated_at`
   check is unreliable due to microsecond skew at row creation. Use
   `assert_db_field` with the original expected value instead.
4. **MATURITY of all 5 scenarios is `stable`.** They represent committed
   product contracts.
5. **TAGS include `release_gate` for all 5.** They are the first batch of
   actual release gates.
6. **No QA-02b split.** All 5 scenarios fit within QA-02's discipline
   boundary; `sandbox_apply_invariant.py` is the largest at ~70 LOC.

## Files Added (new)

- `scenario_contracts/contracts/pm_project_ownership.py`
- `scenario_contracts/contracts/viewer_permission_boundaries.py`
- `scenario_contracts/contracts/variant_pricing_isolation.py`
- `scenario_contracts/contracts/timeline_delay_reason_audit.py`
- `scenario_contracts/contracts/sandbox_apply_invariant.py`
- `test_qa_build02.py`
- `QA_BUILD02_EXECUTION_PLAN.md` (this file)

## Files Modified (additive)

- `scenario_contracts/lib/actions.py` — add 4 actions
- `scenario_contracts/lib/assertions.py` — add 5 assertions
- `scenario_contracts/lib/fixtures.py` — add `create_project_with_costs`

## Test Plan

Run:

```bash
# 1. Each scenario individually
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/pm_project_ownership.py
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/viewer_permission_boundaries.py
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/variant_pricing_isolation.py
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/timeline_delay_reason_audit.py
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/sandbox_apply_invariant.py
# Expect: each exits 0 with PASS: 1

# 2. release_gate tag filter
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ --tag release_gate
# Expect: 6 scenarios (golden_pass + 5 QA-02), all pass

# 3. QA-02 regression
python3 test_qa_build02.py
# Expect: PASSED: N / FAILED: 0

# 4. Existing regressions unchanged
python3 test_qa_build01.py        # 24/24 PASS
python3 test_v14_build09.py       # 15/15 PASS
python3 test_build_v121.py        # 19/19 PASS
```

`test_qa_build02.py` must cover:

- Plan file exists and locks the 5 scenarios.
- All 5 scenarios load and declare the 5 required metadata fields.
- Each of the 5 scenarios runs as PASS via the runner subprocess.
- Directory mode with `--tag release_gate` aggregates all 6 release gates.
- Discipline boundary spot-check: `run()` body of each scenario contains
  `actions.` but not `db.add(`, `db.commit(`, or `from app.crud`.
- Discipline boundary spot-check: `check()` body of each scenario contains
  `assertions.` but not raw `assert ` statements.

## Acceptance Criteria

- All 5 scenarios pass via the runner.
- `--tag release_gate` aggregates all 6 release gates (`golden_pass` + the 5).
- `test_qa_build02.py` exits 0.
- Existing QA-01, v1.4 Build 09, and v1.2.1 regressions remain green.
- No `app/*` file is modified.
- `app/version.py` stays at `1.4.0`.
- `lib/runner.py` LOC budget unchanged (no new growth from QA-02).

## What QA Build 02 is NOT

- Not introducing Playwright (QA-03).
- Not introducing AI mocking (QA-04).
- Not adding live LLM tests.
- Not changing release-gate behavior — these scenarios are gates but the
  gate enforcement itself ships in QA-09 (TBD).
- Not bumping the product version.
