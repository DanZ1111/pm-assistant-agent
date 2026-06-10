# QA Build 01 Execution Plan — PM Scenario Contract Runner Skeleton + Golden Tests

## Status

Execution plan for the first QA Build in the PM Scenario Contract series.

Predecessor: v1.4.0 release hardening shipped at `2143a5e`.

Successor: QA Build 02 — First 5 Hard Contract Scenarios.

Canonical plan: `/Users/Mordred5687/.claude/plans/can-you-still-find-nested-cook.md` (PM Scenario Contract System, approved 2026-06-10 with 10 user locks).

## Purpose

Build a small, trustworthy deterministic scenario runner so AI-authored or
human-authored PM workflow scenarios can be executed against the app and
gate releases without inventing a parser DSL that itself needs debugging.

QA-01 ships only the runner skeleton plus golden tests that prove the runner
behaves correctly (pass behaves as pass, fail behaves as fail, malformed
scenarios are rejected cleanly). No real PM scenarios ship in QA-01.

## Scope

In:

1. Create `scenario_contracts/` Python package with:
   - `scenario_contracts/__init__.py`
   - `scenario_contracts/lib/__init__.py`
   - `scenario_contracts/lib/runner.py` — load + validate + execute one scenario file or a directory
   - `scenario_contracts/lib/fixtures.py` — extracted from `test_v14_build09.py:34-95`:
     `build_db()`, `create_user()`, `create_project()`, plus new `seed_phases()`
   - `scenario_contracts/lib/actions.py` — placeholders + 1 real action (`adjust_due_date_via_crud`) so the golden_pass scenario has something to exercise
   - `scenario_contracts/lib/assertions.py` — `assert_db_field()`, `assert_history_contains()`, `must_not_mutate()`
   - `scenario_contracts/lib/reporter.py` — write markdown + JSON summary per run
2. Create `scenario_contracts/contracts/__init__.py` (empty).
3. Create 5 golden scenarios under `scenario_contracts/contracts/`:
   - `golden_pass.py` — known pass
   - `golden_db_fail.py` — pass `setup` and `run`, fail `check` with structured diff
   - `golden_ui_fail.py` — flagged but skipped in QA-01 (no Playwright path yet); proves the runner can correctly skip UI scenarios when Playwright is unavailable
   - `golden_invalid_shape.py` — missing `check()` function; runner must reject before executing
   - `golden_missing_metadata.py` — missing `WHY_IT_MATTERS`; runner must reject before executing
4. Each scenario declares exactly: `ID`, `TITLE`, `TAGS`, `MATURITY`,
   `WHY_IT_MATTERS` (User lock 7), and `setup(db)`, `run(world, http)`,
   `check(db, world)` (User lock 8). Runner enforces both.
5. Discipline boundary inside scenarios (User lock 9):
   - `setup()` may seed fixtures directly.
   - `run()` may only call `actions.*`.
   - `check()` may only call `assertions.*`.
6. Add `scenario_contracts/README.md` documenting the scenario shape and how
   to add one.
7. Add `scenario_contracts/reports/` to `.gitignore`.
8. Add `test_qa_build01.py` at repo root that runs all 5 goldens and asserts
   each behaves as designed.

Out:

- No real PM scenarios (QA-02).
- No Playwright execution path (QA-03; golden_ui_fail is a placeholder).
- No AI mocking (QA-04).
- No AI scenario authoring (QA-05).
- No live LLM (QA-06).
- No pytest. Self-contained `python3 test_qa_build01.py` only.
- No YAML.
- No version bump. QA series is infrastructure; `app/version.py` stays at 1.4.0.

## Architecture Review

1. Problem solved: ad-hoc per-build `test_*.py` scripts have grown to 60 files
   and ~19k lines. There is no shared library of fixtures or PM actions, no
   way to exercise the full PM workflow as a contract, and no path for AI to
   draft scenarios that the team can adopt as release gates. The existing
   pattern works but doesn't scale.
2. Tables affected: none. QA-01 reads `app/migrations.py` and instantiates
   `app/models.py` rows in a temporary SQLite DB. No schema changes.
3. Real column vs notes: the runner emits markdown/JSON reports to disk
   (`scenario_contracts/reports/`), gitignored. No DB persistence.
4. Service layer: the runner imports `app.crud` directly when scenarios call
   `actions.*`. It does not bypass service helpers.
5. Change log: no `write_change()` from the runner itself. Scenarios that
   exercise mutation paths trigger `write_change()` via the real service
   helpers they call.
6. Rollback: delete `scenario_contracts/` and `test_qa_build01.py`. No schema
   to revert. No code outside the new package is modified.

## Backend Honesty Mapping

| Visible behavior | Source of truth | Write path | Derived rule | Permission | Test |
|---|---|---|---|---|---|
| Scenario `PASS / FAIL` count | runner stdout + `reports/*.md` | `reporter.write_report()` | counted from `setup/run/check` exception capture | runner is CLI-only (no auth) | `test_qa_build01.py` |
| Metadata validation | each scenario module attributes | `runner._validate_metadata()` | reject if any of `ID/TITLE/TAGS/MATURITY/WHY_IT_MATTERS` missing | runner is CLI-only | `golden_missing_metadata.py` |
| Shape validation | scenario module callables | `runner._validate_shape()` | reject if any of `setup/run/check` not callable | runner is CLI-only | `golden_invalid_shape.py` |
| Discipline boundary | scenario file authoring (linter-style, not runtime) | documented in `README.md` and `Locked Decisions` | enforced by code review, not by runner | n/a | `README.md` review |
| Exit codes | runner CLI | runner main | `0` pass / `1` assertion fail / `2` config error | runner is CLI-only | `test_qa_build01.py` runs CLI subprocesses |

## Locked Implementation Decisions

1. **Runner stays small.** `lib/runner.py` target <300 LOC. If approaching
   that, split scope into QA-01b before adding features (User lock 4).
2. **Five required metadata fields.** Runner reads `ID`, `TITLE`, `TAGS`,
   `MATURITY`, `WHY_IT_MATTERS` from scenario module attributes; missing any
   → exit code 2 (User lock 7).
3. **Three required functions.** `setup(db)`, `run(world, http)`,
   `check(db, world)` must all be callable; missing any → exit code 2
   (User lock 8).
4. **MATURITY enum.** `stable` / `candidate` / `experimental`. Runner accepts
   any of those three strings; rejects anything else.
5. **TAGS list.** Must be a Python `list[str]`. Used for filtering (e.g.
   `--tag release_gate`).
6. **DB strategy.** Each scenario gets a fresh in-memory SQLite via
   `fixtures.build_db()`. Migrations run via `migrations.run_pending(engine)`.
   No cross-scenario state.
7. **HTTP strategy in QA-01.** `run(world, http)` receives `http=None`
   because QA-01 has no real HTTP layer yet. `actions.*` in QA-01 call
   service helpers directly. QA-03 introduces a real HTTP/Playwright path.
8. **Exit codes.** `0` = all scenarios passed. `1` = at least one assertion
   failed. `2` = at least one scenario was malformed (config error).
9. **Reports.** Each run writes `reports/run_<timestamp>.md` and
   `reports/run_<timestamp>.json`. Both gitignored.
10. **No global state in the runner.** Each scenario gets its own `tempdir`,
    `engine`, `Session`. Tested by golden_pass + golden_db_fail running back
    to back without interference.

## Files Added (new)

- `scenario_contracts/__init__.py`
- `scenario_contracts/README.md`
- `scenario_contracts/lib/__init__.py`
- `scenario_contracts/lib/runner.py`
- `scenario_contracts/lib/fixtures.py`
- `scenario_contracts/lib/actions.py`
- `scenario_contracts/lib/assertions.py`
- `scenario_contracts/lib/reporter.py`
- `scenario_contracts/contracts/__init__.py`
- `scenario_contracts/contracts/golden_pass.py`
- `scenario_contracts/contracts/golden_db_fail.py`
- `scenario_contracts/contracts/golden_ui_fail.py`
- `scenario_contracts/contracts/golden_invalid_shape.py`
- `scenario_contracts/contracts/golden_missing_metadata.py`
- `test_qa_build01.py`
- `QA_BUILD01_EXECUTION_PLAN.md` (this file)

## Files Modified

- `.gitignore` — add `scenario_contracts/reports/`

## Test Plan

Run:

```bash
# 1. Per-scenario CLI behavior
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/golden_pass.py
# Expect: exit 0, report written, "PASS: 1 / FAIL: 0"

python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/golden_db_fail.py
# Expect: exit 1, "FAIL: 1", structured diff in stdout and report

python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/golden_invalid_shape.py
# Expect: exit 2, "INVALID: missing check()"

python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/golden_missing_metadata.py
# Expect: exit 2, "INVALID: missing WHY_IT_MATTERS"

# 2. Directory mode
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/
# Expect: runs all 5 goldens; exits with the worst observed code (2);
# prints a summary table

# 3. QA-01 regression
python3 test_qa_build01.py
# Expect: PASSED: N / FAILED: 0

# 4. Existing regressions unchanged
python3 test_v14_build09.py
# Expect: 15/15 PASS
python3 test_build_v121.py
# Expect: PASSED: 19 / FAILED: 0
```

`test_qa_build01.py` must cover:

- Plan file exists and locks the 10 user locks.
- `scenario_contracts/` package importable.
- All 5 scenarios load and have the 5 required metadata fields + 3 required
  functions.
- Running `golden_pass.py` via the runner exits 0.
- Running `golden_db_fail.py` via the runner exits 1 and emits a structured
  diff.
- Running `golden_invalid_shape.py` via the runner exits 2 with a clean
  config-error message.
- Running `golden_missing_metadata.py` via the runner exits 2 with a clean
  config-error message.
- Directory mode runs all 5 scenarios.
- Reports directory exists and is gitignored.
- `lib/runner.py` is under 300 LOC.

## Acceptance Criteria

- All 5 goldens behave exactly as designed (pass passes, fail fails with
  clear reason, malformed rejects cleanly, ui_fail skips cleanly when
  Playwright is unavailable).
- `python3 test_qa_build01.py` exits 0 with all assertions passed.
- `lib/runner.py` stays under 300 LOC.
- No live dev server required.
- No existing `test_*.py` file is modified.
- No `app/` code is modified.
- `app/version.py` stays at 1.4.0.

## What QA Build 01 is NOT

- Not implementing real PM scenarios (QA-02).
- Not adding Playwright execution (QA-03).
- Not mocking AI (QA-04).
- Not introducing AI-assisted scenario authoring (QA-05).
- Not auto-promoting AI-drafted scenarios into release gates (never).
- Not bumping the product version.
- Not changing any `app/*` source file.
