# QA Build 03 Execution Plan — Playwright UI Layer

## Status

Execution plan for the third QA Build.

Predecessor: QA Build 02 — First 5 hard contract scenarios (`a886fce`, local).

Successor: QA Build 04 — Mocked AI Intake Contracts.

Canonical plan: `/Users/Mordred5687/.claude/plans/can-you-still-find-nested-cook.md`.

## Purpose

Add the browser-test path to the scenario runner so future UI regressions
in v1.3 Project Detail, v1.4 Planning Sandbox, and any future UI surface
can be locked as deterministic contracts.

QA-03 ships only the **infrastructure + read-only smoke proofs**. Browser-
driven mutation flows (apply sandbox via the UI, click Adjust Due Date in
the Timeline Command Center) are deferred to a later QA build so each
mutation gets its own dev-DB cleanup story rather than risking a half-done
shared-DB pattern in this one.

## Scope

In:

1. Add `scenario_contracts/lib/browser.py`:
   - `is_playwright_available()` — import probe
   - `is_dev_server_reachable(base_url)` — quick HEAD/GET against base
   - `BrowserContext` — context manager that yields a Playwright Page
     pre-logged-in as a given role (admin / pm / viewer)
   - `capture_failure_artifacts(page, name)` — write screenshot + trace
2. Extend `scenario_contracts/lib/actions.py` with UI variants:
   - `open_url(page, path)`
   - `click(page, selector)`
   - `fill_input(page, selector, value)`
   - `wait_for_load(page)`
3. Extend `scenario_contracts/lib/assertions.py` with browser variants:
   - `assert_ui_shows(page, selector)` — element exists and is visible
   - `assert_ui_does_not_show(page, selector)` — absent or hidden
   - `assert_url_path(page, expected_path)` — `page.url` ends with path
4. Extend `scenario_contracts/lib/runner.py`:
   - Detect `ui` tag on a scenario; if present, require Playwright +
     reachable dev server; otherwise SKIP cleanly with structured reason
   - Introspect `run` signature; pass `page` kwarg when scenario declares
     it (backward-compatible — existing DB-only scenarios untouched)
   - On scenario failure with `page`, call
     `capture_failure_artifacts` to drop a screenshot under
     `scenario_contracts/reports/`
5. Add 2 read-only UI smoke scenarios:
   - `ui_login_smoke.py` — admin can log in and reach `/projects`
   - `ui_sandbox_canvas_smoke.py` — admin opens an existing project's
     `/projects/{id}/sandbox`; canvas + module palette markers render
6. Update `golden_ui_fail.py` to be a real (intentional) UI failure
   instead of the QA-01 placeholder. It must FAIL the runner (exit 1)
   to prove the UI failure pipeline catches real regressions.
7. Add `test_qa_build03.py` regression.

Out:

- No mutation flows in browser (deferred to QA-03b / later builds).
- No new fixture creation against the dev DB.
- No AI mocking (QA-04).
- No app/* source modifications.
- No version bump.
- No assumptions about dev DB contents beyond "at least one project
  exists" — scenarios DISCOVER project IDs via the projects index.

## Architecture Review

1. Problem solved: the QA runner has no browser path. v1.3 UI rescue and
   v1.4 Sandbox UI bugs can ship undetected because every existing
   scenario is server-side only.
2. Tables touched: none. QA-03 scenarios are read-only against the dev
   server's existing DB. No setup/teardown writes.
3. Real column vs notes: UI assertions target real CSS selectors with
   semantic meaning (`.timeline-phase-strip`, `.planning-sandbox-canvas`,
   `.module-palette`). Not text-grep brittleness.
4. Service layer: UI actions hit real HTTP routes; the route handlers
   call the real service helpers. End-to-end coverage.
5. Change log: QA-03 scenarios don't mutate, so no `write_change()`
   rows are produced. QA-03b/QA-04 will exercise mutation flows.
6. Rollback: delete `scenario_contracts/lib/browser.py`, the UI scenario
   files, and the runner extension. Existing scenarios remain intact.

## Backend Honesty Mapping

| Visible behavior | Source of truth | Write path | Derived rule | Permission | Test |
|---|---|---|---|---|---|
| Admin login | `POST /auth/login` with form fields | n/a (auth route) | success returns 303 redirect | admin credentials known | `ui_login_smoke` |
| `/projects` list page | server-rendered Jinja template | n/a | server queries `crud.get_projects(...)` | admin sees all | `ui_login_smoke` |
| Sandbox canvas markers | `app/templates/planning_sandbox.html` | n/a | server renders Cytoscape host element + module palette region | `can_edit_project` | `ui_sandbox_canvas_smoke` |
| Failure screenshot | Playwright `page.screenshot()` | `lib/browser.capture_failure_artifacts` | written under `scenario_contracts/reports/screenshots/` | runner CLI | `golden_ui_fail` |
| UI scenario SKIP when Playwright missing | `lib/browser.is_playwright_available()` | n/a | runner falls through with clear `detail` | n/a | `test_qa_build03` mocks `is_playwright_available` |
| UI scenario SKIP when dev server down | `lib/browser.is_dev_server_reachable()` | n/a | runner falls through with clear `detail` | n/a | `test_qa_build03` |

## Locked Implementation Decisions

1. **Dev server is external.** Runner does not start the server. If
   unreachable, UI scenarios SKIP with `dev_server_unreachable` reason.
2. **Read-only smoke only in QA-03.** No DB writes from browser flows.
3. **Login is via admin credentials only.** PM / viewer login is
   QA-03b. (Reduces fixture-permutation surface in this build.)
4. **`BASE_URL` env override.** Defaults to `http://localhost:8000`.
5. **`TEST_ADMIN_USERNAME` / `TEST_ADMIN_PASSWORD` env overrides.**
   Defaults match `test_v13_ui_r*.py` (`admin` / `show me the money`).
6. **Headless by default.** `QA_BROWSER_HEADED=1` switches to headed
   for local debugging.
7. **Screenshot on failure only.** Don't capture on every step — too
   noisy for the reports folder.
8. **Signature inspection for `page` kwarg.** Existing scenarios that
   don't declare `page` continue to work; UI scenarios declare it.
9. **Trace API is opt-in.** Set `QA_BROWSER_TRACE=1` to record a
   trace zip on failure. Off by default to keep `reports/` small.
10. **`ui` tag is now an OPT-IN, not SKIP.** QA-01's "skip ui scenarios"
    behavior is replaced with "run if browser available; skip otherwise."

## UX / runner behavior contract

- `python3 -m scenario_contracts.lib.runner contracts/ui_login_smoke.py`
  → runs the scenario against the live dev server.
- If Playwright is uninstalled → exit 0, SKIP, reason
  `playwright_not_installed`.
- If dev server unreachable → exit 0, SKIP, reason `dev_server_unreachable`.
- On UI assertion failure → exit 1, FAIL, screenshot saved.
- Existing DB-only scenarios behave exactly as before.

## Files Added (new)

- `scenario_contracts/lib/browser.py`
- `scenario_contracts/contracts/ui_login_smoke.py`
- `scenario_contracts/contracts/ui_sandbox_canvas_smoke.py`
- `test_qa_build03.py`
- `QA_BUILD03_EXECUTION_PLAN.md` (this file)

## Files Modified (additive)

- `scenario_contracts/lib/runner.py` — UI scenario detection + page kwarg
- `scenario_contracts/lib/actions.py` — UI action helpers
- `scenario_contracts/lib/assertions.py` — UI assertion helpers
- `scenario_contracts/contracts/golden_ui_fail.py` — flip to real (intentional) UI failure
- `scenario_contracts/README.md` — document UI scenario shape

## Test Plan

Pre-conditions:
- `python run.py` running (dev server on localhost:8000)
- `playwright install chromium` already done

Run:

```bash
# 1. New UI scenarios pass against the live dev server
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ui_login_smoke.py
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ui_sandbox_canvas_smoke.py
# Expect: exit 0, PASS

# 2. golden_ui_fail must fail intentionally to prove the UI failure path
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/golden_ui_fail.py
# Expect: exit 1, FAIL, screenshot in reports/

# 3. Directory mode aggregates correctly
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/
# Expect: 2 UI PASS + 5 QA-02 PASS + golden_pass PASS = 8 PASS;
# golden_db_fail + golden_ui_fail = 2 FAIL;
# golden_invalid_shape + golden_missing_metadata = 2 INVALID

# 4. QA-03 regression
python3 test_qa_build03.py
# Expect: PASSED: N / FAILED: 0

# 5. Existing regressions unchanged
python3 test_qa_build02.py     # 24/24 PASS
python3 test_qa_build01.py     # PASS (directory-mode test updated)
python3 test_v14_build09.py    # 15/15 PASS
python3 test_build_v121.py     # 19/19 PASS
```

`test_qa_build03.py` must cover:

- Plan file exists.
- `lib/browser.py` exposes `is_playwright_available`,
  `is_dev_server_reachable`, `BrowserContext`,
  `capture_failure_artifacts`.
- UI actions exist and accept a `page` argument.
- UI assertions exist and accept a `page` argument.
- Runner introspects `page` kwarg and only passes it to UI scenarios.
- `ui_login_smoke` runs as PASS when dev server reachable.
- `ui_sandbox_canvas_smoke` runs as PASS when dev server reachable.
- `golden_ui_fail` runs as FAIL with a captured screenshot file.
- All scenarios SKIP cleanly when Playwright is unavailable (simulate by
  monkey-patching `is_playwright_available` to return False).
- All scenarios SKIP cleanly when dev server unreachable (simulate by
  setting `BASE_URL` to an unreachable host).
- Discipline boundary still holds for new UI scenarios.
- `app/*` is untouched; `app/version.py` stays at `1.4.0`.

## Acceptance Criteria

- 2 UI scenarios pass against a live dev server.
- `golden_ui_fail` produces a real failure with a screenshot artifact.
- UI scenarios SKIP cleanly when Playwright unavailable.
- UI scenarios SKIP cleanly when dev server unreachable.
- All earlier regressions remain green.
- No `app/*` file modified.
- `lib/runner.py` LOC stays under 300.

## What QA Build 03 is NOT

- Not creating any new fixtures in the dev DB.
- Not exercising browser-driven mutation (defer to QA-03b).
- Not testing AI flows (QA-04).
- Not auto-promoting scenarios into the release gate set without human
  review (release-gate inclusion is a human decision per Codex's plan).
