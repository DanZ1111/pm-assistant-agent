# QA Build 06 Execution Plan — Tier 1 Contract Gaps

## Status

Execution plan for the sixth QA Build.

Predecessor: QA Build 05 — Mocked AI library + 4 confirmation-required contracts (`d24cfec`).

Successor: QA Build 07 — Sandbox UI mutation flows (browser-driven).

Canonical roadmap: [QA_ROADMAP.md](QA_ROADMAP.md).

Plan-first commit: this file lands before any code so Codex can review the scope and locked decisions.

## Purpose

Close the bug-class safety net for the mutation contracts we have
actually shipped bugs in. The most important is **project delete on
Railway** — the Marine bug — which a single regression-test scenario
will catch in CI before it ever ships again.

These 5 scenarios encode load-bearing contracts:
1. Project delete with AI-intake FK references (the Marine bug).
2. Delete-permission boundary (admin / PM-if-not-started / viewer).
3. Project create idempotency under repeated POST.
4. Phase finish auto-advance + stage/delay recalc.
5. Blocker lifecycle (create → update → resolve).

## Scope

In:

1. Extend `scenario_contracts/lib/actions.py` with:
   - `delete_project(db, project_id)` — wraps `crud.delete_project`.
   - `create_project_with_idempotency(db, data, token, user_id, prototype_rounds="single")` — wraps the atomic helper.
   - `mint_creation_token(db, user_id)` — wraps `crud.mint_creation_token`.
   - `update_blocker(db, blocker_id, data, user_id=None)` — wraps `crud.update_blocker`.
2. Extend `scenario_contracts/lib/fixtures.py` with:
   - `seed_ai_conversation(db, project_id)` — directly insert one
     `AIConversation` row plus one `AIMessage` row, mirroring what
     the AI intake flow produces. Used by the Marine-bug scenario.
   - `seed_creation_token(db, user_id, project_id=None, claimed=False)`
     — directly insert a `project_creation_tokens` row to simulate
     an unclaimed or stale token.
3. Extend `scenario_contracts/lib/assertions.py` with:
   - `assert_no_row` (alias if missing; we may already have it via
     `assert_no_rows` / `assert_row_count(expected=0)`).
   - Reuse existing `assert_permission` for `can_delete_project`.
4. Five contract scenarios under `scenario_contracts/contracts/`:
   - `project_delete_ai_intake_cleanup.py` — Marine-bug regression.
   - `project_delete_permission_boundary.py` — admin / PM-eligible /
     PM-blocked-by-started-phase / viewer.
   - `project_create_idempotency.py` — first POST creates; repeat POST
     returns "duplicate"; invalid token returns "invalid".
   - `finish_phase_advancement.py` — Design done → Engineering Review
     in_progress → current_stage updates → delay recalculates.
   - `blocker_lifecycle.py` — create (severity=low) → update (severity=high) → resolve.
5. `test_qa_build06.py` regression.

Out:

- HTTP-level coverage of the create-project POST (deferred to a later
  build that uses TestClient).
- Excel batch intake idempotency (`create_projects_batch_with_idempotency`)
  — deferred to QA-06b unless the basic idempotency contract reveals
  the same surface.
- Pure-function tests for `derive_current_stage` and `calculate_delay`
  as standalone scenarios — they are exercised inside
  `finish_phase_advancement.py` instead.
- AI intake create-project (`POST /ai/intake/extract`) — QA-05b.
- No new migrations.
- No `app/*` modifications.
- No version bump.

## Architecture Review

1. **Problem solved.** The Marine bug shipped (`b8a9687`) because no
   automated test exercised "delete a project that has AIConversation
   + ProjectCreationToken rows under SQLite with FK enforcement on."
   QA-06's first scenario locks that regression class. The other 4
   close adjacent gaps in the same blast radius: who can delete, who
   can create idempotently, what finishing a phase actually does to
   derived state, and the blocker write/edit/resolve audit trail.
2. **Tables touched.** `users`, `projects`, `project_phases`,
   `project_blockers`, `project_changes`, `ai_conversations`,
   `ai_messages`, `project_creation_tokens`,
   `phase_plan_changes`. All per-scenario in-memory SQLite with FK
   enforcement (already enabled via [app/database.py](app/database.py)
   `PRAGMA foreign_keys = ON`).
3. **Service layer.** Every action wraps a public
   `app.crud.*` function. No ORM bypass.
4. **Change log.** Each mutating action triggers `write_change()`
   inside the service helper. Scenarios assert the `project_changes`
   rows.
5. **Rollback.** Delete the 5 new contract files, the new actions,
   and the new fixtures. The runner, executors, journey shape, and
   existing contracts are unchanged.

## Backend Honesty Mapping

| Scenario | Source of truth | Write path | Predicted state | Permission | Test |
|---|---|---|---|---|---|
| `project_delete_ai_intake_cleanup` | `crud.delete_project` + explicit cleanup of `ai_conversations` + `project_creation_tokens` before ORM cascade | `actions.delete_project` | project + 8 phases + 1 ai_conversation + 1 token row exists pre-delete; post-delete all rows for that project_id are gone; no FK violation raised | n/a (action runs under SQLite FK enforcement) | `project_delete_ai_intake_cleanup.py` |
| `project_delete_permission_boundary` | `app.dependencies.can_delete_project` | n/a (pure permission check) | admin can delete any project; PM can delete if `every phase has status=not_started AND actual_start_date IS NULL`; PM blocked once any phase is started; viewer never | role check static | `project_delete_permission_boundary.py` |
| `project_create_idempotency` | `crud.create_project_with_idempotency` + `project_creation_tokens.claimed_at` | `actions.create_project_with_idempotency` | first POST → IdempotencyResult("created"); second POST with same token → IdempotencyResult("duplicate", project_id=N); empty/wrong token → IdempotencyResult("invalid") | n/a (test runs as PM/admin) | `project_create_idempotency.py` |
| `finish_phase_advancement` | `crud.finish_phase` + `crud.recalculate_stage_and_delay` + `derive_current_stage` + `calculate_delay` | `actions.finish_phase` | Design `status=done` with `actual_end_date=today` and `actual_start_date` filled; Engineering Review `status=in_progress` with `actual_start_date=today`; project.current_stage reflects the new in-progress phase; project.estimated_launch_date set | n/a (PM action) | `finish_phase_advancement.py` |
| `blocker_lifecycle` | `crud.create_blocker` → `crud.update_blocker` → `crud.resolve_blocker` | `actions.create_blocker` / `update_blocker` / `resolve_blocker` | After create: 1 active blocker severity=low + 1 `project_changes` "blocker_opened" row; after update: severity=high + 1 "blocker_updated" row; after resolve: 0 active blockers + 1 "blocker_resolved" (or equivalent) row | PM action | `blocker_lifecycle.py` |

## Locked Implementation Decisions

1. **`project_delete_ai_intake_cleanup` is the only scenario that seeds
   raw FK-referencing rows.** Other delete scenarios run on
   crud-created projects only. This isolates the "Marine bug regression"
   contract.
2. **SQLite FK enforcement is the test surface.** The Marine bug was
   invisible on dev SQLite until `app/database.py`'s
   `PRAGMA foreign_keys = ON` event listener landed. Scenarios rely on
   that listener being active in every `build_db()`. If a future commit
   removes the listener, the Marine-bug scenario STOPS catching
   regressions silently — locked as an explicit assertion in
   `test_qa_build06.py`.
3. **Idempotency contract uses real token lifecycle.** Scenario calls
   `actions.mint_creation_token`, then
   `actions.create_project_with_idempotency` twice with the same token.
   No in-test shortcuts.
4. **`finish_phase_advancement` exercises both derived helpers.** The
   `check()` asserts `project.current_stage` (`derive_current_stage`
   output) and `project.estimated_launch_date` (`calculate_delay`
   output). No separate pure-function scenarios — folded in.
5. **Blocker scenario is one journey-shaped contract in 3 sub-steps.**
   Not a journey (not a `STEPS=[...]` list); a single
   `setup/run/check` where `run()` does create + update + resolve and
   `check()` validates the cumulative project_changes count + final
   state.
6. **MATURITY = "stable", TAGS include "release_gate"** for all 5.
   Same precedent as QA-02 / QA-05.

## Discipline boundary (User lock 9)

All 5 scenarios:
- `setup(db)` — creates admin + pm + viewer + project + phases as
  needed (uses `fixtures.*` only).
- `run(world, db, http)` — calls `actions.*` (delete_project,
  create_project_with_idempotency, finish_phase, create_blocker,
  update_blocker, resolve_blocker) and `actions.snapshot_*` for
  per-path state capture.
- `check(db, world)` — uses only `assertions.*`.

## Critical files to reference (read-only during implementation)

- [app/crud.py:572-616](app/crud.py#L572-L616) — `delete_project` (the
  Marine fix; cleans ai_conversations + project_creation_tokens before
  ORM delete)
- [app/crud.py:324-334](app/crud.py#L324-L334) — `create_project`
  (auto-seeds 8 phases via PHASE_TEMPLATES["single"])
- [app/crud.py:344-363](app/crud.py#L344-L363) — `mint_creation_token`
- [app/crud.py:467-511](app/crud.py#L467-L511) —
  `create_project_with_idempotency`
- [app/crud.py:773-827](app/crud.py#L773-L827) — `finish_phase`
- [app/crud.py:201-214](app/crud.py#L201-L214) —
  `recalculate_stage_and_delay`
- [app/crud.py:3355-3504](app/crud.py#L3355-L3504) — `create_blocker`,
  `update_blocker`, `resolve_blocker`
- [app/dependencies.py:58-84](app/dependencies.py#L58-L84) —
  `can_delete_project`
- [app/database.py](app/database.py) — SQLite FK enforcement event
  listener

## Files Added (new)

- `scenario_contracts/contracts/project_delete_ai_intake_cleanup.py`
- `scenario_contracts/contracts/project_delete_permission_boundary.py`
- `scenario_contracts/contracts/project_create_idempotency.py`
- `scenario_contracts/contracts/finish_phase_advancement.py`
- `scenario_contracts/contracts/blocker_lifecycle.py`
- `test_qa_build06.py`
- `QA_BUILD06_EXECUTION_PLAN.md` (this file)

## Files Modified (additive only)

- `scenario_contracts/lib/actions.py` — add 4 actions
- `scenario_contracts/lib/fixtures.py` — add 2 fixtures
- `QA_ROADMAP.md` — mark QA-06 as shipped (after implementation
  commit)

## Test Plan

Run:

```bash
# 1. Each scenario individually
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/project_delete_ai_intake_cleanup.py
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/project_delete_permission_boundary.py
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/project_create_idempotency.py
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/finish_phase_advancement.py
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/blocker_lifecycle.py
# Expect: each exits 0 with PASS: 1

# 2. release_gate tag filter aggregates 15 PASS
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ --tag release_gate
# Expect: 15 PASS (golden_pass + 5 QA-02 + 4 QA-05 + 5 QA-06)

# 3. QA-06 regression
python3 test_qa_build06.py
# Expect: PASSED: N / FAILED: 0

# 4. Existing regressions unchanged
python3 test_qa_build05.py        # 23/23 PASS
python3 test_qa_build04.py        # 13/13 PASS
python3 test_qa_build03.py        # 21/21 PASS
python3 test_qa_build02.py        # 24/24 PASS
python3 test_qa_build01.py        # 24/24 PASS
python3 test_v14_build09.py       # 15/15 PASS
python3 test_build_v121.py        # 19/19 PASS
```

`test_qa_build06.py` must cover:

- Plan file exists and locks the 5 scenarios + Marine-bug intent.
- 4 new actions present (`delete_project`, `create_project_with_idempotency`,
  `mint_creation_token`, `update_blocker`).
- 2 new fixtures present (`seed_ai_conversation`,
  `seed_creation_token`).
- Each of the 5 scenarios declares 5 metadata + 3 functions +
  `release_gate` tag + `MATURITY="stable"`.
- Each runs as PASS via subprocess.
- Discipline boundary: every `run()` uses only `actions.*` /
  `fixtures.*`; every `check()` uses only `assertions.*`.
- SQLite FK enforcement is still wired in `app/database.py` (locks
  the precondition for the Marine-bug scenario being meaningful).
- `lib/runner.py` LOC budget unchanged.
- `app/*` is untouched; `app/version.py` stays at `1.4.0`.

## Acceptance Criteria

- All 5 Tier 1 contract scenarios PASS.
- `--tag release_gate` aggregates 15 PASS (golden_pass + 5 QA-02 +
  4 QA-05 + 5 QA-06).
- `test_qa_build06.py` exits 0.
- All earlier QA + v1.4 + v1.2.1 regressions stay green.
- No `app/*` modification.

## What QA Build 06 is NOT

- Not exercising the HTTP `POST /create-project` route (deferred to
  QA that introduces TestClient).
- Not testing the AI-intake create-project flow (QA-05b).
- Not testing Excel batch intake (deferred to QA-06b).
- Not splitting `derive_current_stage` / `calculate_delay` into their
  own scenarios (folded into `finish_phase_advancement`).
- Not changing the runner, the journey shape, or any existing
  scenarios.
- Not bumping the product version.

## Open questions

None blocking. The blocker resolve-status write (`crud.resolve_blocker`)
writes a `project_changes` row with `change_type` we will verify
during implementation; if the type name differs from what we assume
(e.g. `"blocker_resolved"` vs `"blocker_updated"`), the assertion
adapts — this is normal contract discovery, not a planning gap.
