# QA Build 08 Execution Plan — Disruption Library + Medium Journey

## Status

Execution plan for the eighth QA Build.

Predecessor: QA Build 07 — Sandbox UI mutation: add module from palette (`162501b`).

Successor: QA Build 09 — Full Marine Knife journey (20+ steps).

Canonical roadmap: [QA_ROADMAP.md](QA_ROADMAP.md).

Plan-first commit so Codex can review the scope before any implementation lands.

## Purpose

First taste of "AI PM reacts to a real-world disruption." This build
materializes the user's framing from 2026-06-09:

> "PM opens with a couple of ideas... pushes through phases, mixing
> manual edits with AI intake... sometimes the factory did something
> wrong so we need to add another round of prototyping... the factory
> decides it will delay/raise the price because Trump or the Chinese
> government suddenly exploded... PM decides to add one more variant
> but just a different color..."

QA-08 introduces **composable disruption helpers** (`lib/disruptions.py`)
that bundle realistic real-world events into single calls, and ships
the **first medium journey** (~10 steps) that mixes:
- normal PM actions (create project, finish phases),
- mocked AI confirmation flows (from QA-05),
- and 2 real-world disruptions (factory cost rise + supplier delay).

If any one of those features breaks, OR if they fail to compose, the
journey fails at the exact step where composition broke.

## Scope

In:

1. New module `scenario_contracts/lib/disruptions.py`:
   - `factory_raises_cost_by_pct(db, project_id, pct, reason)` —
     bumps `target_factory_cost` via `crud.update_project`; writes
     a change-log row with the reason.
   - `supplier_delays_phase(db, phase_id, days, reason)` — moves
     `planned_end_date` by N days via `crud.update_phase(reason=...)`.
     Reuses the existing actions.adjust_due_date path.
   - `prototype_round_added(db, project_id, name, after_phase_name, duration_days)`
     — inserts a new phase via `crud.add_phase` between two existing
     phases; bumps `phase_order` on later phases.
   - `variant_color_only(db, project_id, variant_name)` — creates a
     variant whose ONLY non-default difference is the variant_name
     (no cost overrides). Sanity-locks the variant_pricing_isolation
     contract inside a journey.
   - `geopolitical_event(db, project_id, factory_pct, delay_phase_id, delay_days, reason)`
     — bundles factory-cost-rise + supplier-delay into one "Trump
     tariff" / "China holiday" composite disruption.
2. Extend `scenario_contracts/lib/actions.py` with 2 new actions:
   - `update_project(db, project_id, data, changed_by="user")` —
     wraps `crud.update_project`. Needed by `factory_raises_cost_by_pct`.
   - `add_phase(db, project_id, data)` — wraps `crud.add_phase`.
     Needed by `prototype_round_added`.
3. New medium journey `scenario_contracts/journeys/journey_pm_with_disruptions.py`:
   - 10 steps, deterministic, mixes manual PM actions + mocked AI
     dispatch + 2 disruptions + 1 color variant.
   - Tags: `journey`, `deterministic`, `ai_mocked`, `disruption`.
   - MATURITY: `candidate` (earns `stable` after 10 consecutive
     green runs per the roadmap stable-credibility rule).
4. `test_qa_build08.py` regression that:
   - Locks the plan + disruption library surface.
   - Runs the journey end-to-end.
   - Verifies each disruption helper exists and has the right signature.
   - Verifies the discipline boundary — `run()` may use `actions.*` AND
     `disruptions.*` (the boundary is widened in this build; locked in
     the test).

Out:

- HTTP / browser steps (this is a DB+dispatch journey).
- Live LLM (never).
- New runner extensions (uses the journey runner from QA-04 as-is).
- Full Marine Knife journey (QA-09 — 20+ steps).
- Coverage assistant (QA-10).
- Sandbox UI mutation (QA-07b/c — Codex domain).
- `app/*` modifications.
- Version bump.

## Architecture Review

1. **Problem solved.** Contract scenarios catch atomic regressions.
   Journeys catch integration regressions. QA-08 layers on
   **disruptions** — composable real-world events — so journeys can
   express "AI PM reacts to X" without re-implementing X each time.
   The disruption helpers are reusable across QA-09's full journey.
2. **Tables touched.** `users`, `projects`, `project_phases`,
   `project_variants`, `project_blockers`, `project_journal_entries`,
   `project_changes`, `phase_plan_changes`. All per-scenario in-memory
   SQLite.
3. **Service layer.** Every disruption wraps existing public
   `app.crud.*` functions. The dispatch flow (for AI proposals) goes
   through `app.ai.tools.dispatch`. No ORM bypass anywhere.
4. **Change log.** Each disruption triggers `write_change()` inside
   the service helper it wraps. The journey asserts the cumulative
   `project_changes` count grows correctly across steps.
5. **Rollback.** Delete `lib/disruptions.py`, the new journey file,
   the 2 new actions, and `test_qa_build08.py`. Existing scenarios,
   journeys, and the runner are unchanged.

## Backend Honesty Mapping

| Step | Source of truth | Write path | Predicted state |
|---|---|---|---|
| 1. PM creates project | `crud.create_project` | `actions.create_project_for_pm` | 1 project + 8 default phases (`PHASE_TEMPLATES["single"]`) + 1 event_note change-log row |
| 2. AI proposes journal entry (unconfirmed → confirmed) | `app.ai.tools.dispatch` + `CONFIRMATION_TOOLS` guard | `actions.ai_dispatch` | unconfirmed → `confirmation_required` + 0 journal rows; confirmed → 1 journal row + 1 event_note change-log row |
| 3. Factory raises cost (geopolitical disruption) | `crud.update_project` | `disruptions.factory_raises_cost_by_pct` | `projects.target_factory_cost` changed by the pct; 1 change-log row containing the reason |
| 4. PM finishes Design | `crud.finish_phase` + `recalculate_stage_and_delay` | `actions.finish_phase` | Design `status=done`; Engineering Review `status=in_progress`; `project.current_stage` updates |
| 5. AI proposes Engineering Review delay (supplier said +10 days) | `dispatch("adjust_phase_plan")` | `actions.ai_dispatch` confirmed | phase `planned_end_date` moved; 1 `phase_plan_changes` row + 1 change-log row with reason |
| 6. Prototype Round 2 inserted | `crud.add_phase` | `disruptions.prototype_round_added` | phase count grows to 9; new phase has expected name + phase_type |
| 7. PM finishes Engineering Review | `crud.finish_phase` | `actions.finish_phase` | Eng Review `done`; next eligible phase advances; `current_stage` updates |
| 8. PM adds color-only variant | `crud.create_variant` | `disruptions.variant_color_only` | 1 variant row with the new name; **project costs UNCHANGED** (cross-checks the `variant_pricing_isolation` contract inside a journey) |
| 9. AI proposes blocker on Mass Production | `dispatch("create_blocker")` confirmed | `actions.ai_dispatch` | 1 active blocker linked to the phase; 1 blocker_opened change-log row |
| 10. Final state snapshot | cumulative reads | `actions.snapshot_table_count` | total counts match: 1 project, 9 phases, 1 variant, 1 active blocker, 1 journal entry, cumulative project_changes count ≥ 8 |

## Locked Implementation Decisions

1. **Disruptions live in their own module.** `lib/disruptions.py`,
   separate from `actions.py`. Disruptions are compositions; actions
   are single CRUD calls. Keep them visually distinct in scenario
   code.
2. **Discipline boundary widens.** `run()` may call `actions.*` AND
   `disruptions.*`. `check()` still uses `assertions.*` only.
   `test_qa_build08.py` locks this widened boundary explicitly so a
   future test can't accidentally introduce a third "compound action"
   namespace without updating the contract.
3. **No new runner extension.** The journey runner from QA-04 walks
   `STEPS=[Step(name, do, check)]`. Disruption calls go inside
   step's `do_*` functions like any other action. No runner change
   needed.
4. **AI dispatch uses the role-pass path.** Per QA-05, viewer dispatch
   is `forbidden`. Journey runs as the PM and asserts the
   confirmation-required + confirmed paths. No viewer test here
   (separately covered in QA-05 contracts).
5. **Color-only variant cross-checks QA-02's `variant_pricing_isolation`
   contract inside a journey.** If a future commit breaks variant
   isolation, both the QA-02 contract scenario AND this journey
   step 8 will fail — double-guard.
6. **MATURITY = "candidate".** First disruption-mixed journey. Earns
   `stable` after 10 consecutive green runs.
7. **No `release_gate` tag.** Journeys are exploratory by default per
   the roadmap; they earn promotion to release-gate set in QA-10's
   release-gate promotion rule.

## Discipline boundary (User lock 9, widened)

The journey scenario:
- `setup(db)` — creates pm user, returns world.
- `do_*(world, db, http)` — uses `actions.*` AND `disruptions.*`.
- `check_*(db, world)` — uses only `assertions.*`.

`test_qa_build08.py` regex-checks each step body to enforce the
boundary.

## Critical files to reference (read-only during implementation)

- [app/crud.py:513-553](app/crud.py#L513-L553) — `update_project`
  (target field for factory cost rise)
- [app/crud.py:646-674](app/crud.py#L646-L674) — `add_phase` (target
  for prototype round added)
- [scenario_contracts/lib/journey.py](scenario_contracts/lib/journey.py)
  — `Step(name, do, check)` shape (no changes here; journey reuses
  the QA-04 runner)
- [scenario_contracts/journeys/journey_basic_pm_lifecycle.py](scenario_contracts/journeys/journey_basic_pm_lifecycle.py)
  — pattern reference for `STEPS` shape and do_/check_ split
- [scenario_contracts/lib/actions.py:182-194](scenario_contracts/lib/actions.py#L182-L194)
  — `ai_dispatch` from QA-05; reused for AI-proposes steps

## Files Added (new)

- `scenario_contracts/lib/disruptions.py`
- `scenario_contracts/journeys/journey_pm_with_disruptions.py`
- `test_qa_build08.py`
- `QA_BUILD08_EXECUTION_PLAN.md` (this file)

## Files Modified (additive only)

- `scenario_contracts/lib/actions.py` — add `update_project`, `add_phase`
- `QA_ROADMAP.md` — mark QA-08 as shipped (after implementation
  commit)

## Test Plan

Run:

```bash
# 1. The medium journey passes all 10 steps
python3 -m scenario_contracts.lib.runner scenario_contracts/journeys/journey_pm_with_disruptions.py
# Expect: exit 0; "10 steps OK"; PASS: 1

# 2. QA-08 regression
python3 test_qa_build08.py
# Expect: PASSED: N / FAILED: 0

# 3. Existing regressions unchanged
python3 test_qa_build07.py        # 16/16 PASS
python3 test_qa_build06.py        # 26/26 PASS
python3 test_qa_build05.py        # 23/23 PASS
python3 test_qa_build04.py        # 13/13 PASS (mini-journey)
python3 test_qa_build03.py        # 21/21 PASS
python3 test_qa_build02.py        # 24/24 PASS
python3 test_qa_build01.py        # 24/24 PASS
python3 test_v14_build09.py       # 15/15 PASS
python3 test_build_v121.py        # 19/19 PASS

# 4. release_gate set unchanged (journey is candidate, not release_gate)
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ --tag release_gate
# Expect: still 16 PASS — QA-08's journey is NOT in the release-gate set
```

`test_qa_build08.py` must cover:

- Plan file exists and locks the 5 disruption helpers + medium-journey scope.
- `lib/disruptions.py` exposes all 5 helpers.
- 2 new actions (`update_project`, `add_phase`) present with the expected signatures.
- Journey loads with: `journey` + `ai_mocked` + `disruption` tags + `MATURITY="candidate"` + exactly 10 steps.
- Journey runs end-to-end as PASS via subprocess.
- Discipline boundary holds: each step's do_* uses only `actions.*` / `fixtures.*` / `disruptions.*`; check_* uses only `assertions.*`.
- A deliberately-broken step (injected via temp fixture) is reported with `step N (name)` detail (proves the runner correctly attributes journey failures even with disruptions in the mix).
- `lib/runner.py` LOC budget unchanged.
- `app/*` is untouched.

## Acceptance Criteria

- Medium journey passes all 10 steps.
- `test_qa_build08.py` exits 0.
- All earlier QA + v1.4 + v1.2.1 regressions stay green.
- `--tag release_gate` aggregation unchanged (still 16; journey is
  candidate, not gate).
- No `app/*` modification.
- `lib/runner.py` stays under 300 LOC.

## What QA Build 08 is NOT

- Not adding the full Marine Knife journey (QA-09; 20+ steps, multiple
  ideas, sandbox apply via dispatch, and all 5 disruption types
  exercised).
- Not adding browser-driven UI steps (Codex domain).
- Not adding live LLM tests (never).
- Not introducing the coverage assistant (QA-10).
- Not changing the runner, the journey shape, or any existing
  scenarios.
- Not bumping the product version.

## Open questions

None blocking. If any disruption's `crud.update_project` /
`crud.add_phase` call writes a `project_changes` row with a slightly
different wording than predicted, the assertion adapts during
implementation — same normal contract-discovery loop as QA-05's
"Linked {serial_number}" find and QA-04's auto-seed-8-phases find.
