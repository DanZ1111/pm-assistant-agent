# QA Build 04 Execution Plan — Journey Runner Skeleton + Mini-Journey

## Status

Execution plan for the fourth QA Build.

Predecessor: QA Build 03 — Playwright UI Layer (`79cce10`).

Successor: QA Build 05 — Mocked AI library.

Canonical roadmap: [QA_ROADMAP.md](QA_ROADMAP.md).

## Purpose

Introduce the **journey** test class. A journey is a multi-step
narrative: setup, then a sequence of `Step(name, do, check)` tuples
where each step predicts what the system should look like after the
action runs. The runner walks the steps, captures the actual reaction,
compares to predicted, and reports any divergence with the failing step
name.

QA-04 ships the **shape** + a deterministic mini-journey (6 steps, no
AI, no UI mutation). Prove the multi-step pattern works before adding
AI or disruptions on top of it. Larger journeys with AI proposals,
realistic disruptions, and UI-driven mutation come in QA-05..QA-09 per
the roadmap.

## Scope

In:

1. New module `scenario_contracts/lib/journey.py`:
   - `Step(name, do, check)` dataclass.
2. Extend `scenario_contracts/lib/runner.py`:
   - Detect journey-shaped scenarios (have `setup` and `STEPS`; no `run`/`check`).
   - Walk `STEPS`: for each step, call `do(world, db, http)` then
     `check(db, world)`.
   - On failure, report `step N (name)` in the detail field.
   - Backward compatible with contract scenarios.
3. Extend `scenario_contracts/lib/actions.py` with 4 new actions:
   - `finish_phase` — wraps `crud.finish_phase`
   - `create_blocker` — wraps `crud.create_blocker`
   - `resolve_blocker` — wraps `crud.resolve_blocker`
   - `create_journal_entry` — wraps `crud.create_journal_entry`
4. Extend `scenario_contracts/lib/assertions.py` with 1 new assertion:
   - `assert_active_blocker_count(db, project_id, expected)` — counts
     `project_blockers` rows where `status='active'` for the project.
5. First journey: `scenario_contracts/journeys/journey_basic_pm_lifecycle.py`:
   - 6 steps, deterministic, DB-only.
   - PM creates project → seeds 3 phases → finishes Design phase →
     adjusts Sample due date with reason → creates blocker on Production →
     resolves the blocker.
   - Each step has a do_* function and a check_* function with at
     least one assertion that pins the predicted state.
6. New `scenario_contracts/journeys/` directory with its own
   `__init__.py`. Journeys are discoverable separately from contracts
   so the runner can be invoked against either or both.
7. Update runner to accept paths to journey files / directories.
8. `test_qa_build04.py` regression that asserts:
   - Plan file exists.
   - `lib/journey.py` exposes `Step`.
   - Runner detects `STEPS=[...]` and runs the journey shape.
   - The mini-journey passes all 6 steps.
   - Each step's check_* function uses only `assertions.*`.
   - Each step's do_* function uses only `actions.*` and
     `fixtures.*`.
   - Failure in a step reports the step name in the detail field.
9. `QA_BUILD04_EXECUTION_PLAN.md` (this file).

Out:

- No mocked AI (QA-05).
- No real LLM (never).
- No browser steps in this journey (QA-07).
- No disruption library (QA-08).
- No `app/*` changes.
- No version bump.

## Architecture Review

1. Problem solved: contract scenarios are atomic. They don't catch
   integration bugs — "X works, Y works, but X followed by Y breaks Z."
   Journeys are the test class that catches those. QA-04 introduces the
   shape so future builds can layer AI and disruptions on top.
2. Tables touched (by the mini-journey): `users`, `projects`,
   `project_phases`, `project_blockers`, `project_changes`,
   `phase_plan_changes`. All in the per-scenario in-memory SQLite.
3. Real column vs notes: every step's assertion targets a real column
   or service helper return value. No string-grep brittleness.
4. Service layer: every action wraps an `app.crud.*` function. The
   runner does not bypass the service layer.
5. Change log: each mutating action triggers `write_change()` inside
   the service helper it wraps. The journey asserts the change-log
   rows where appropriate.
6. Rollback: delete `journeys/journey_basic_pm_lifecycle.py`,
   `lib/journey.py`, and the runner extension; existing contracts and
   UI scenarios are unaffected.

## Backend Honesty Mapping

| Step | Source of truth | Write path | Predicted state | Test |
|---|---|---|---|---|
| 1. PM creates project | `projects` row | `crud.create_project` | 1 project row; `product_manager=alice` | step 1 check |
| 2. 3 phases seeded | `project_phases` rows | `fixtures.seed_phases` | 3 phase rows for project; all `status=not_started` | step 2 check |
| 3. PM finishes Design | `project_phases.status`, `actual_end_date`, `actual_start_date` | `crud.finish_phase` | Design `status=done` with `actual_end_date=today`; Sample `status=in_progress` (auto-advanced by finish_phase) | step 3 check |
| 4. PM adjusts Sample due date | `project_phases.planned_end_date` + `phase_plan_changes` + `project_changes` | `crud.update_phase(reason=...)` | Sample `planned_end_date` updated; `phase_plan_changes` row with reason; `project_changes` summary contains reason | step 4 check |
| 5. PM creates blocker on Production | `project_blockers` row | `crud.create_blocker` | 1 active blocker on Production phase | step 5 check |
| 6. PM resolves the blocker | `project_blockers.status` | `crud.resolve_blocker` | 0 active blockers; blocker `status=resolved` | step 6 check |

## Locked Implementation Decisions

1. **Backward compatibility.** Contract scenarios (`setup/run/check`)
   continue to work unchanged. Journey scenarios declare `STEPS=[...]`
   and a `setup`. The runner detects shape via attribute presence.
2. **Step shape.** `Step(name: str, do: Callable, check: Callable)`.
   `do(world, db, http) -> None`; `check(db, world) -> None`. Both
   participate in the same discipline boundary (User lock 9): `do`
   calls only `actions.*` and `fixtures.*` (in setup-like usage when
   adding to world); `check` calls only `assertions.*`.
3. **Failure reporting.** On any step failure (assertion or unexpected
   exception), the result `detail` field is prefixed with
   `step N (name): <reason>` so journey reports are scannable.
4. **Discoverability.** Journeys live in
   `scenario_contracts/journeys/` so they can be tagged separately
   from contracts. The runner accepts a path to either contracts/ or
   journeys/ or a specific file.
5. **MATURITY semantics.** Journeys start as `candidate`. They earn
   `stable` only after 10 consecutive green runs (locked in QA-10).
6. **Tag semantics.** Journeys MUST include `journey` tag. Optional
   layered tags: `marathon` (long), `ai_mocked` (uses fake AI),
   `disruption` (includes simulated real-world disruption).
7. **No DB writes across steps via the shared session.** Each step
   uses the same `db` session opened by the runner. `do` may commit;
   `check` reads. No new transactions per step.

## Files Added (new)

- `scenario_contracts/lib/journey.py`
- `scenario_contracts/journeys/__init__.py`
- `scenario_contracts/journeys/journey_basic_pm_lifecycle.py`
- `test_qa_build04.py`
- `QA_BUILD04_EXECUTION_PLAN.md` (this file)

## Files Modified (additive)

- `scenario_contracts/lib/runner.py` — journey detection + step walker
- `scenario_contracts/lib/actions.py` — 4 new actions
- `scenario_contracts/lib/assertions.py` — 1 new assertion
- `scenario_contracts/README.md` — document the journey shape

## Test Plan

Run:

```bash
# 1. The mini-journey passes all 6 steps
python3 -m scenario_contracts.lib.runner scenario_contracts/journeys/journey_basic_pm_lifecycle.py
# Expect: exit 0; "step 6 (PM resolves the blocker)" shown as last step OK;
# PASS: 1

# 2. QA-04 regression
python3 test_qa_build04.py
# Expect: PASSED: N / FAILED: 0

# 3. All earlier regressions still green
python3 test_qa_build03.py     # 21/21 PASS
python3 test_qa_build02.py     # 24/24 PASS
python3 test_qa_build01.py     # 24/24 PASS
python3 test_v14_build09.py    # 15/15 PASS
python3 test_build_v121.py     # 19/19 PASS

# 4. Directory mode over contracts/ unchanged (journey lives elsewhere)
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/
# Expect: same aggregation as before QA-04
```

`test_qa_build04.py` must cover:

- Plan file exists and locks the journey shape.
- `lib/journey.py` exposes `Step` with the right fields.
- Runner detects `STEPS=[...]` and runs the journey.
- The mini-journey scenario declares ID/TITLE/TAGS/MATURITY/WHY_IT_MATTERS,
  has setup, has STEPS as a list of Step objects.
- The mini-journey passes all 6 steps as PASS.
- Discipline boundary: every do_* uses only actions.*/fixtures.*; every
  check_* uses only assertions.*.
- An intentionally-broken step (injected via a test fixture) is
  reported as `step N (name) failed: <reason>` — proves the failure
  path identifies the failing step.
- `lib/runner.py` stays under 300 LOC (target: ≤ 320 after journey
  extension; if higher, split into helper module).
- `app/*` untouched.

## Acceptance Criteria

- Journey mini-journey passes all 6 steps.
- Runner reports which step failed when a step fails.
- Existing contract and UI scenarios behave unchanged.
- All earlier QA regressions remain green.
- No `app/*` file modified.
- `app/version.py` stays at `1.4.0`.

## What QA Build 04 is NOT

- Not introducing mocked AI (QA-05).
- Not introducing disruption helpers (QA-08).
- Not introducing browser-driven mutation steps (QA-07).
- Not running journeys as release gates yet — `MATURITY="candidate"`
  until QA-10 defines the promotion rule.
