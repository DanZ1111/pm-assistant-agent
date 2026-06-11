# QA Build 05 Execution Plan — Mocked AI Library + Confirmation-Required Contracts

## Status

Execution plan for the fifth QA Build.

Predecessor: QA Build 04 — Journey runner skeleton + first mini-journey (`a273f74`).

Successor: QA Build 06 — Tier 1 contract gaps (project create/delete, finish_phase, blocker create/edit/resolve).

Canonical roadmap: [QA_ROADMAP.md](QA_ROADMAP.md).

This plan is committed BEFORE the implementation lands so Codex (or future-Claude) can review the scope, locked decisions, and Backend Honesty Mapping before any code is written.

## Purpose

Close the CLAUDE.md non-negotiable:

> *"AI never writes directly to the database without user confirmation."*

Right now nothing in the QA suite locks this. A single line removed from
`CONFIRMATION_TOOLS` would silently allow AI to write to the DB without
user confirmation, with zero test failures. This build adds the guard:
4 contract scenarios, one per critical intake path, each covering
unconfirmed / confirmed / viewer in a single file.

QA-05 also extracts the `_FakeOpenAIClient` pattern from
[test_build21.py](test_build21.py) into `scenario_contracts/lib/fake_ai.py`
so QA-08+ journey scenarios can inject AI proposals deterministically. The
library lands now even though QA-05 contracts don't use it (they exercise
`dispatch` directly).

## Two findings from exploration that shape this plan

1. **"3 AI intake surfaces" is a misconception.** The codebase actually has
   2 routes, not 3:
   - `POST /ai/chat` — polymorphic over both *global* (no `project_id`)
     and *project-scoped* (`project_id=N`) chat via request body params.
     Used by both the sidebar `#aiSidePanel` and the bottom chat bar.
     See [app/routes/ai_chat.py:320-502](app/routes/ai_chat.py#L320-L502).
   - `POST /ai/intake/extract` + `POST /ai/intake/extract-file` — the
     "AI-assisted create project" intake panel; single-use, no
     conversation. See [app/routes/intake.py](app/routes/intake.py).
   - The "timeline planner chat" the user described does not exist as a
     separate route. Project-scoped chat goes through `/ai/chat` with
     `project_id` set.

2. **The non-negotiable lives at dispatch level, not HTTP level.** The
   `CONFIRMATION_TOOLS` guard at [app/ai/tools.py:664-665](app/ai/tools.py#L664-L665)
   is the single point where the contract is enforced. Testing
   `app.ai.tools.dispatch(...)` directly locks the contract without
   dragging FastAPI TestClient + auth-override scaffolding into the QA
   stack. The HTTP layer is a thin serialization wrapper; covering it
   adds value (it catches route-level regressions) but is a separable
   concern.

## Scope

In:

1. New module `scenario_contracts/lib/fake_ai.py` — lift the 7 classes
   from [test_build21.py:36-86](test_build21.py#L36-L86):
   `_FakeFunction`, `_FakeToolCall`, `_FakeMessage`, `_FakeChoice`,
   `_FakeResponse`, `_FakeCompletions`, `_FakeChat`, `FakeOpenAIClient`.
   Public API: `FakeOpenAIClient()` exposing `.chat.completions.queue_text(content)`
   and `.queue_tool_call(name, args_dict, follow_text="")`. Includes
   `install(client)` helper that monkey-patches `app.routes.ai_chat._client`
   for HTTP-level tests later.
2. Extend `scenario_contracts/lib/actions.py` with one new action:
   - `ai_dispatch(db, tool_name, args, user, confirmed=False)` — wraps
     `app.ai.tools.dispatch`. Returns the result dict.
3. Extend `scenario_contracts/lib/assertions.py` with two new assertions:
   - `assert_dispatch_required_confirmation(result, tool_name)` —
     asserts result is a dict with `error == "confirmation_required"`
     and `tool == tool_name`.
   - `assert_dispatch_succeeded(result)` — asserts result has no
     `error` key and an `ok` flag (or whatever positive shape dispatch
     returns).
4. Four contract scenarios under `scenario_contracts/contracts/`, each
   covering unconfirmed / confirmed / viewer paths in a single file:
   - `ai_proposes_idea.py` — `create_idea` + `link_idea_to_project`
   - `ai_proposes_journal.py` — `create_journal_entry`
   - `ai_proposes_due_date_shift.py` — `adjust_phase_plan`
   - `ai_proposes_blocker.py` — `create_blocker`
5. `test_qa_build05.py` regression that asserts the surface, behavior,
   and discipline boundary.

Out:

- HTTP-level scenarios through `POST /ai/chat` + confirm/cancel routes
  (deferred to QA-05b).
- The `/ai/intake/extract` panel surface (QA-05b).
- Pending-proposal storage in `ai_messages.metadata_json.tool_calls[i].result`
  (only relevant once we go HTTP-level).
- Multi-step "AI proposes → user edits args → user confirms with edited args"
  flow via `_merge_reviewed_args` (QA-05b).
- FastAPI TestClient + auth override scaffolding (lands when QA-05b
  needs it).
- Live LLM (never).
- No `app/*` source modifications.
- No version bump.
- No new migrations.

## Architecture Review

1. **Problem solved.** The CLAUDE.md non-negotiable has no automated
   guard. A removed entry from `CONFIRMATION_TOOLS`, a dispatch path
   that skips the `confirmed` check, or a viewer who slips through
   would all ship silently. This build locks the 4 critical intake
   paths.
2. **Tables touched (per scenario).** `users`, `projects`,
   `project_phases`, `project_blockers`, `project_journal_entries`,
   `ideas`, `project_ideas`, `project_changes`,
   `phase_plan_changes`. All in the per-scenario in-memory SQLite.
   Never the real DB. Never the live `/ai/chat` route.
3. **Real column vs notes.** Every "no DB write" assertion targets
   actual table row counts via `snapshot_table_count` before and
   after dispatch. Every "confirmation_required" assertion targets
   the actual return-value shape of `dispatch`.
4. **Service layer.** Goes through `app.ai.tools.dispatch` — the
   real service-layer entry point that the HTTP route also calls.
   We bypass HTTP serialization, not business logic.
5. **Change log.** Confirmed writes trigger the real `write_change()`
   path inside each `_handle_*` function. Scenarios assert the
   `project_changes` rows.
6. **Rollback.** Delete `scenario_contracts/lib/fake_ai.py`, the 4
   new contract files, and the action/assertion additions. The
   runner, executors, journey shape, and existing contracts are
   unchanged.

## Backend Honesty Mapping

| Scenario | Source of truth | Write path | Predicted state | Permission | Test |
|---|---|---|---|---|---|
| `ai_proposes_idea` | `CONFIRMATION_TOOLS` membership + `_HANDLERS["create_idea"]` + `_HANDLERS["link_idea_to_project"]` | `app.ai.tools.dispatch` | unconfirmed → `confirmation_required`, 0 rows in `ideas` / `project_ideas`; confirmed → 1 idea row, 1 link row, 1 `project_changes` audit row | admin/pm allowed; viewer denied | `ai_proposes_idea.py` + `test_qa_build05` |
| `ai_proposes_journal` | `_HANDLERS["create_journal_entry"]` | `dispatch` | unconfirmed → no `project_journal_entries` row; confirmed → 1 entry + 1 `project_changes` "event_note" row containing the entry snippet | admin/pm allowed; viewer denied | `ai_proposes_journal.py` |
| `ai_proposes_due_date_shift` | `_HANDLERS["adjust_phase_plan"]` | `dispatch` | unconfirmed → `project_phases.planned_end_date` unchanged + 0 `phase_plan_changes` rows; confirmed → planned_end_date moved + 1 `phase_plan_changes` row + 1 `project_changes` row with reason | admin/pm allowed; viewer denied | `ai_proposes_due_date_shift.py` |
| `ai_proposes_blocker` | `_HANDLERS["create_blocker"]` | `dispatch` | unconfirmed → 0 `project_blockers` rows; confirmed → 1 blocker (`status=active`) + 1 `project_changes` "blocker_opened" row | admin/pm allowed; viewer denied | `ai_proposes_blocker.py` |

## Locked Implementation Decisions

1. **Dispatch-level only in QA-05.** No HTTP, no TestClient, no auth
   override. The CLAUDE.md non-negotiable is enforced at
   `app.ai.tools.dispatch`; that's where we test it.
2. **3-path coverage in each scenario.** Every scenario covers
   unconfirmed / confirmed / viewer in a single contract file, not
   three. The runner reports a single PASS/FAIL per scenario, but
   the body asserts all three paths internally — so a regression in
   any one is caught.
3. **Snapshot-before / snapshot-after for "no write" half.** Use the
   existing `actions.snapshot_table_count` (from QA-02) to capture
   row counts before dispatch, then `assertions.assert_equal` to
   verify no change. Same discipline as `sandbox_apply_invariant`.
4. **Fake AI library extracted but not wired to scenarios.** QA-05
   contracts call `dispatch` directly; the fake client doesn't
   participate. The library lands now because QA-08+ journey
   scenarios will need it.
5. **MATURITY = "stable", TAGS include "release_gate".** These 4
   scenarios encode product non-negotiables. Same precedent as
   QA-02's 5 release-gate contracts.
6. **No new permission helpers.** Viewer denial is whatever
   `dispatch` already does for viewer-role users. If `dispatch`
   doesn't currently check role, the scenario will surface that as
   a failure — which is itself a finding worth shipping.

## Discipline boundary (User lock 9)

All 4 scenarios:
- `setup(db)` — creates admin + pm + viewer + a project + phases as
  needed (uses `fixtures.*` only)
- `run(world, db, http)` — calls `actions.ai_dispatch(...)` for each
  of the 3 paths; uses `actions.snapshot_table_count` for pre/post
  counts
- `check(db, world)` — uses only `assertions.*`
  (`assert_dispatch_required_confirmation`, `assert_dispatch_succeeded`,
  `assert_equal`, `assert_row_count`, `assert_history_contains`,
  `assert_no_rows`)

## Critical files to reference (read-only during implementation)

- [test_build21.py:36-86](test_build21.py#L36-L86) — source of the
  FakeOpenAIClient classes to lift
- [test_build21.py:82-86](test_build21.py#L82-L86) — injection pattern
  (`app.routes.ai_chat._client = FAKE`)
- [app/ai/tools.py:486-496](app/ai/tools.py#L486-L496) —
  `CONFIRMATION_TOOLS` set
- [app/ai/tools.py:664-665](app/ai/tools.py#L664-L665) — the guard
  line we're locking
- [app/ai/tools.py:1081-1104](app/ai/tools.py#L1081-L1104) — `_HANDLERS`
  dict; we need handler signatures for `create_idea`,
  `link_idea_to_project`, `create_journal_entry`, `adjust_phase_plan`,
  `create_blocker`
- [app/routes/ai_chat.py:35-42](app/routes/ai_chat.py#L35-L42) —
  module-level `_client` (the monkey-patch target for QA-05b)
- [app/crud.py](app/crud.py) — `create_journal_entry`,
  `create_blocker`, `update_phase`, `create_idea` are what
  `_HANDLERS` ultimately calls; we already wrap them as `actions.*`
  in earlier builds, so the existing actions remain valid

## Files Added (new)

- `scenario_contracts/lib/fake_ai.py`
- `scenario_contracts/contracts/ai_proposes_idea.py`
- `scenario_contracts/contracts/ai_proposes_journal.py`
- `scenario_contracts/contracts/ai_proposes_due_date_shift.py`
- `scenario_contracts/contracts/ai_proposes_blocker.py`
- `test_qa_build05.py`
- `QA_BUILD05_EXECUTION_PLAN.md` (this file)

## Files Modified (additive only)

- `scenario_contracts/lib/actions.py` — add `ai_dispatch`
- `scenario_contracts/lib/assertions.py` — add two dispatch assertions
- `QA_ROADMAP.md` — mark QA-05 as shipped (after implementation
  commit)

## Test Plan

Run:

```bash
# 1. Each scenario individually
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ai_proposes_idea.py
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ai_proposes_journal.py
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ai_proposes_due_date_shift.py
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ai_proposes_blocker.py
# Expect: each exits 0 with PASS: 1

# 2. release_gate tag filter aggregates all 10 gates
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ --tag release_gate
# Expect: 10 PASS (golden_pass + 5 QA-02 + 4 QA-05)

# 3. QA-05 regression
python3 test_qa_build05.py
# Expect: PASSED: N / FAILED: 0

# 4. Existing regressions unchanged
python3 test_qa_build04.py        # 13/13 PASS (incl. mini-journey)
python3 test_qa_build03.py        # 21/21 PASS (UI smoke)
python3 test_qa_build02.py        # 24/24 PASS
python3 test_qa_build01.py        # 24/24 PASS
python3 test_v14_build09.py       # 15/15 PASS
python3 test_build_v121.py        # 19/19 PASS
```

`test_qa_build05.py` must cover:

- `QA_BUILD05_EXECUTION_PLAN.md` exists and locks the 4 scenarios +
  dispatch-level decision.
- `lib/fake_ai.py` exposes `FakeOpenAIClient`, `_FakeChat`,
  `_FakeCompletions` with `queue_text` and `queue_tool_call`.
- `actions.ai_dispatch` exists and accepts
  `(db, tool_name, args, user, confirmed)`.
- `assertions.assert_dispatch_required_confirmation` and
  `assert_dispatch_succeeded` exist.
- All 4 scenarios declare 5 metadata + 3 functions + `release_gate`
  tag + `MATURITY="stable"`.
- Each of the 4 scenarios runs as PASS via subprocess.
- Discipline boundary: every `run()` calls only `actions.*` (no
  `app.ai.*` direct import), every `check()` calls only
  `assertions.*` (no bare assert).
- `lib/runner.py` LOC budget unchanged (no growth from QA-05;
  everything is additive to library + scenarios).
- `app/*` is untouched; `app/version.py` stays at `1.4.0`.

## Acceptance Criteria

- All 4 AI confirmation-required scenarios PASS.
- `--tag release_gate` aggregates 10 PASS (golden_pass + 5 QA-02 +
  4 QA-05).
- `test_qa_build05.py` exits 0.
- All earlier QA + v1.4 + v1.2.1 regressions stay green.
- No `app/*` modification.
- `fake_ai.py` is importable and has the queue API even though
  QA-05 scenarios don't use it (foundation for QA-08+).

## What QA Build 05 is NOT

- Not introducing HTTP-level AI scenarios (QA-05b).
- Not introducing live LLM (never).
- Not introducing the `/ai/intake/extract` panel surface (QA-05b).
- Not testing the `_merge_reviewed_args` edit-then-confirm flow
  (QA-05b).
- Not testing pending-proposal storage in
  `ai_messages.metadata_json` (QA-05b).
- Not changing the runner, the journey shape, or any existing
  scenarios.
- Not bumping the product version.

## Open questions

None blocking. The "3 surfaces" → "2 routes" finding is an
observation, not a question — QA-05b will handle both routes, and
the user doesn't need to make a decision here.

Viewer-denial behavior in `dispatch` is the only place that could
surprise us; if `dispatch` doesn't currently enforce role, the
scenarios will detect it as a regression-class finding, which is
itself useful.
