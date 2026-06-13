# QA Build 09 Execution Plan — Full Marine Knife Journey (20 steps)

## Status

Execution plan for the ninth QA Build.

Predecessor: QA Build 08 — Disruption library + medium journey (`d0e491c`).

Successor: QA Build 10 — Coverage assistant + release-gate promotion + `run_qa_loop.sh`.

Canonical roadmap: [QA_ROADMAP.md](QA_ROADMAP.md).

Plan-first commit so Codex can review the scope before any implementation lands.

## Purpose

The **end-state journey** the user described on 2026-06-09:

> "It launches from adding a couple ideas, then link them together
> and create a plan, then it sort of creates a project timeline
> template using the sandbox we just developed, and then push
> through each phase of creation, it sometimes uses the manual
> edits, but mostly using AI intake... sometimes it will add in
> some sudden situations for example the factory did something
> wrong... the factory decides it will delay/raise the price
> because Trump or the Chinese government suddenly exploded...
> AI pm needs to change the plan in different ways. And suddenly
> it decided to add one more variants but just a different color
> not the entire thing."

QA-09 materializes this in a single 20-step deterministic journey
that integrates **everything** the QA system shipped to date:
- runner + journey shape (QA-01, QA-04)
- contract scenarios used as cross-checks inside steps (QA-02, QA-06)
- mocked AI dispatch (QA-05)
- disruption library (QA-08)
- ideas + project linking (new, QA-09)

If the QA system's own integration breaks — e.g. if disruptions stop
composing with AI dispatch, or if sandbox apply via the journey
contract diverges from the QA-02 contract — this journey fails at the
exact composition that broke.

## Scope

In:

1. Extend `scenario_contracts/lib/actions.py` with 2 new actions:
   - `create_idea(db, data, contributor_user_id=None)` — wraps
     `crud.create_idea`. Used in steps 1-2.
   - `link_idea_to_project(db, project_id, idea_id, user_id=None, note=None)`
     — wraps `crud.link_idea_to_project`. Used in step 3.
2. New full-lifecycle journey
   `scenario_contracts/journeys/journey_marine_knife_full_lifecycle.py`:
   - **20 steps**, deterministic, mixes:
     - normal PM actions
     - mocked AI dispatch (4 different AI proposals)
     - all 5 disruption types from QA-08
     - 2 color-only variants (to test cumulative behavior)
     - sandbox apply via service-layer (replaces auto-seeded phases)
   - Tags: `journey`, `deterministic`, `ai_mocked`, `disruption`,
     `marathon`, `marine_knife`.
   - MATURITY: `candidate`. Earns `stable` after 10 consecutive green
     runs per the roadmap rule.
3. `test_qa_build09.py` regression that:
   - Locks the plan + 20-step shape + journey tag set.
   - Verifies the 2 new actions present + signatures.
   - Runs the journey end-to-end (must produce "20 steps OK").
   - Verifies discipline boundary holds across all 40 do_/check_
     functions.

Out:

- HTTP / browser steps (DB + dispatch journey).
- Coverage assistant (QA-10).
- New runner extensions.
- Live LLM (never).
- `app/*` modifications.
- Version bump.

## Architecture Review

1. **Problem solved.** QA-01..QA-08 each lock a slice. QA-09 proves
   the slices **compose** under realistic PM-workday pressure. The
   medium journey from QA-08 was 10 steps and 2 disruptions; this is
   20 steps and all 5 disruption types plus ideas + sandbox apply.
2. **Tables touched.** `users`, `projects`, `ideas`, `project_ideas`,
   `project_phases`, `project_variants`, `project_blockers`,
   `project_journal_entries`, `project_changes`, `phase_plan_changes`,
   `planning_sandboxes`, `planning_sandbox_nodes`,
   `planning_apply_events`. All in per-scenario in-memory SQLite.
3. **Service layer.** Every step wraps `app.crud.*` or
   `app.ai.tools.dispatch` via the existing action/disruption helpers.
   No raw ORM mutation. No `app.*` imports inside scenario code.
4. **Change log.** Cumulative `project_changes` count grows
   monotonically across the journey. The final-snapshot step asserts
   the count is ≥ 18 (lower bound — defensive against future
   write_change additions).
5. **Rollback.** Delete the new journey + 2 new actions + the new
   test. Existing scenarios, journeys, library, and runner unchanged.

## The 20 Steps

| # | Step | Helper(s) | Predicted state delta |
|---|---|---|---|
| 1 | PM creates 2 ideas (electronic switch + ergonomic grip) | `actions.create_idea` × 2 | `ideas` count = 2 |
| 2 | PM creates Marine Knife project (auto-seeds 8 default phases + 1 event_note) | `actions.create_project_for_pm` | `projects` = 1; `project_phases` = 8; `project_changes` ≥ 1 |
| 3 | PM links both ideas to the project | `actions.link_idea_to_project` × 2 | `project_ideas` = 2 (for this project); 2 audit rows |
| 4 | PM creates a sandbox from `simple_oem_knife` template | `actions.create_sandbox_from_template` | `planning_sandboxes` = 1; `planning_sandbox_nodes` ≥ 6 (template node count) |
| 5 | PM applies the sandbox → replaces auto-seeded phases with template-derived phases | `actions.apply_sandbox` | `project_phases` count = sandbox node count; `planning_apply_events` = 1; `project_changes` += 1 (`plan_applied`) |
| 6 | PM finishes first applied phase | `actions.finish_phase` | first phase `status='done'`; next phase `status='in_progress'` |
| 7 | Factory raises cost 18% (Trump-tariff disruption) | `disruptions.factory_raises_cost_by_pct` | `projects.target_factory_cost` × 1.18 |
| 8 | PM finishes second phase | `actions.finish_phase` | second phase `status='done'` |
| 9 | Supplier delays third phase +12 days (disruption) | `disruptions.supplier_delays_phase` | third phase `planned_end_date` shifted; 1 `phase_plan_changes` row |
| 10 | AI proposes journal entry about delay → confirmed | `actions.ai_dispatch` × 2 (unconfirmed + confirmed) | unconfirmed → `confirmation_required`; confirmed → 1 journal entry row |
| 11 | PM finishes third phase | `actions.finish_phase` | third phase `status='done'` |
| 12 | Prototype Round 2 added mid-stream (factory-mistake disruption) | `disruptions.prototype_round_added` | phase count += 1 |
| 13 | PM finishes fourth phase | `actions.finish_phase` | fourth phase `status='done'` |
| 14 | Geopolitical event (composite cost rise + phase delay) | `disruptions.geopolitical_event` | factory cost rises again; another phase delayed |
| 15 | PM adds first color-only variant ("Matte Black") | `disruptions.variant_color_only` | `project_variants` = 1; project costs UNCHANGED |
| 16 | AI proposes a blocker on the remaining phase → confirmed | `actions.ai_dispatch` × 2 | 1 active blocker linked to that phase |
| 17 | PM resolves the blocker | `actions.resolve_blocker` | 0 active blockers; blocker `status='resolved'` |
| 18 | AI proposes a second journal entry → confirmed | `actions.ai_dispatch` × 2 | 2 journal entries total |
| 19 | PM adds second color-only variant ("Forest Green") | `disruptions.variant_color_only` | `project_variants` = 2 |
| 20 | Final state snapshot — cumulative integration validation | `actions.snapshot_table_count` × N | 1 project, ≥6 phases (template-applied + 1 prototype), 2 variants, 0 active blockers, 2 journal entries, ≥18 `project_changes`, 2 ideas linked, 1 sandbox in `applied` status, 1 `planning_apply_events` row |

## Locked Implementation Decisions

1. **No release_gate tag.** Marathon journeys are exploratory until
   promotion via QA-10's stable-credibility rule.
2. **`marathon` tag included.** Distinguishes long journeys (20+ steps)
   from shorter ones; future loop runners can filter by it (e.g.
   "smoke loop excludes marathons").
3. **`marine_knife` tag included.** Marks this as the specific Marine
   Knife product story so future variations (`marine_knife_v2`,
   `marine_knife_recall_scenario`, etc.) sit alongside.
4. **Sandbox apply replaces auto-seeded phases.** Step 5 asserts the
   post-apply `project_phases` count equals the sandbox's node count
   — locks the QA-02 `sandbox_apply_invariant` contract inside a
   journey.
5. **Two color-only variants in different steps.** Step 15 and step 19.
   Verifies cumulative behavior — the second variant's existence
   doesn't break project-cost invariance after step 14's geopolitical
   event also changed costs.
6. **Step 10's AI journal mid-disruption.** The AI proposal happens
   AFTER the supplier delay (step 9). Tests that AI dispatch composes
   with a freshly-mutated phase state.
7. **Step 14's geopolitical_event reuses the same phase as step 9's
   supplier delay.** Tests that a phase delayed once can be delayed
   again — `phase_plan_changes` accumulates multiple rows per phase.
8. **Final snapshot uses ≥ bounds for cumulative counts.** Project
   changes count is monotonic-grow with normal operation; defensive
   against future `write_change` additions in the service layer.
9. **MATURITY = "candidate".** First marathon journey; earns `stable`
   only after 10 consecutive green runs (QA-10 will introduce the
   loop runner that measures this).

## Discipline boundary

Same widened boundary from QA-08:
- `do_*(world, db, http)` uses `actions.*` AND `disruptions.*` only.
- `check_*(db, world)` uses `assertions.*` only.
- No raw `app.*` imports anywhere in scenario code.

`test_qa_build09.py` regex-checks all 40 functions to enforce.

## Critical files to reference (read-only during implementation)

- [app/crud.py:2475-2499](app/crud.py#L2475-L2499) — `create_idea`
  (target for `actions.create_idea`)
- [app/crud.py:2592-2630](app/crud.py#L2592-L2630) — `link_idea_to_project`
  (target for `actions.link_idea_to_project`)
- [scenario_contracts/journeys/journey_pm_with_disruptions.py](scenario_contracts/journeys/journey_pm_with_disruptions.py)
  — pattern reference (do_/check_ split, snapshot per path)
- [scenario_contracts/lib/disruptions.py](scenario_contracts/lib/disruptions.py)
  — 5 disruption helpers (all reused unchanged in QA-09)
- [scenario_contracts/contracts/sandbox_apply_invariant.py](scenario_contracts/contracts/sandbox_apply_invariant.py)
  — QA-02 contract that step 5 cross-checks (sandbox draft → apply
  → audit row)

## Files Added (new)

- `scenario_contracts/journeys/journey_marine_knife_full_lifecycle.py`
- `test_qa_build09.py`
- `QA_BUILD09_EXECUTION_PLAN.md` (this file)

## Files Modified (additive only)

- `scenario_contracts/lib/actions.py` — `create_idea`, `link_idea_to_project`
- `QA_ROADMAP.md` — mark QA-09 as shipped (after implementation
  commit)

## Test Plan

Run:

```bash
# 1. The marathon journey passes all 20 steps
python3 -m scenario_contracts.lib.runner scenario_contracts/journeys/journey_marine_knife_full_lifecycle.py
# Expect: exit 0; "20 steps OK"; PASS: 1

# 2. QA-09 regression
python3 test_qa_build09.py
# Expect: PASSED: N / FAILED: 0

# 3. Existing regressions still green
python3 test_qa_build08.py  # 19/19 PASS (medium journey)
python3 test_qa_build07.py  # 16/16 PASS
python3 test_qa_build06.py  # 26/26 PASS
python3 test_qa_build05.py  # 23/23 PASS
python3 test_qa_build04.py  # 13/13 PASS (mini-journey)
python3 test_qa_build03.py  # 21/21 PASS
python3 test_qa_build02.py  # 24/24 PASS
python3 test_qa_build01.py  # 24/24 PASS
python3 test_v14_build09.py # 15/15 PASS
python3 test_build_v121.py  # 19/19 PASS

# 4. release_gate set unchanged
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ --tag release_gate
# Expect: 16 PASS — QA-09's journey is candidate, not release_gate
```

`test_qa_build09.py` must cover:

- Plan file exists and locks the 20-step shape + Marine Knife intent.
- `actions.create_idea`, `actions.link_idea_to_project` present with
  the expected signatures.
- Journey loads with: `journey` + `ai_mocked` + `disruption` +
  `marathon` + `marine_knife` tags + `MATURITY="candidate"` + exactly
  20 steps.
- Journey runs end-to-end as PASS via subprocess.
- Discipline boundary holds across all 40 do_/check_ functions.
- `lib/runner.py` LOC budget unchanged.
- `app/*` is untouched.

## Acceptance Criteria

- Marathon journey passes all 20 steps.
- `test_qa_build09.py` exits 0.
- All earlier QA + v1.4 + v1.2.1 regressions stay green.
- `--tag release_gate` aggregation unchanged (still 16; journey is
  candidate).
- No `app/*` modification.

## What QA Build 09 is NOT

- Not introducing the coverage assistant (QA-10).
- Not introducing the loop runner (`run_qa_loop.sh`) (QA-10).
- Not introducing the release-gate promotion rule (QA-10).
- Not adding browser-driven UI steps (Codex domain).
- Not bumping the product version.
- Not changing the runner, the journey shape, or any existing
  scenarios.

## Open questions

None blocking. If the simple_oem_knife template's node count
changes in a future v1.4 seed update, the post-apply phase-count
assertion uses `>= N` rather than `== N` to absorb that — the
contract is "Apply replaces phases with the sandbox graph", not
"the simple_oem_knife template has exactly 6 nodes."
