# QA Build 11 Execution Plan — PM Acceptance Journey Layer

## Status

Execution plan for QA Build 11. Plan-first commit so Codex sees the
scope before any code lands.

Predecessor: QA Build 10 — Coverage assistant + suite/loop runners (`53ac9c4`).

Successor: TBD — the next acceptance journey, or a UI testability
patch if QA-11's audit surfaces blockers.

Canonical roadmap: [QA_ROADMAP.md](QA_ROADMAP.md).

## Purpose: stop treating QA as engineering coverage

QA-01 through QA-10 shipped a complete QA system as infrastructure:
runner, library, journey shape, mocked AI, disruption helpers,
suite/loop runners, promotion rule. But the **scenarios** written on
top are mostly engineering-driven — they assert DB state after
specific CRUD calls.

The user's pushback (2026-06-13): if the QA system only catches what
per-build `test.py` files catch, it's not worth what was built. The
real bugs PMs hit are:

- **Summary not updating** after a field edit
- **Timeline Command Center** showing stale state
- **AI writing to the wrong entity** (Combo Pack vs project-level)
- **Variant page out of sync with Overview**
- **10 steps in, PM has no idea what to do next**
- **Viewer seeing fields they shouldn't**

These are **PM workflow / UI mismatch / comprehension** bugs. The
existing scenarios don't catch them because they only check DB rows,
not what the PM sees on the page.

QA-11 adds a new scenario tier — **PM Acceptance Journeys** — that
tests "could a real PM use the system to ship a real project?" by
checking four kinds of truth, not just one:

1. **DB truth** (already covered)
2. **UI truth** (new in QA-11)
3. **History/audit truth** (new in QA-11)
4. **PM comprehension** (new in QA-11)

## Scope

In:

1. New scenario tier: `scenario_contracts/acceptance/` — parallel to
   `contracts/` and `journeys/`. Uses the existing journey executor
   with the `ui` tag for browser steps.
2. New library module:
   `scenario_contracts/lib/pm_views.py` — PM-facing assertions:
   `assert_overview_shows`, `assert_timeline_command_center_shows`,
   `assert_variant_page_shows`, `assert_history_explains`,
   `assert_overview_and_variant_consistent`,
   `assert_viewer_does_not_see`.
3. First acceptance journey:
   `acceptance/football_knife_asd_lifecycle.py` — ~12-15 steps.
   Realistic ASD scenario: football-themed folding knife sold both
   standalone and as a Combo Pack with packaging upgrade; coating
   supplier delays sample; PM keeps stakeholders aligned through
   cost rises and blockers.
4. `SCENARIO_AUTHORING_GUIDE.md` at repo root — locks the new
   authoring rules for every future scenario draft (Codex, Claude,
   me, or human).
5. `STABLE_CREDIBILITY.md` updated with the acceptance tier.
6. `test_qa_build11.py` — locks all of the above.

Out:

- Coverage matrix tooling (deferred — engineering-tooling-first
  detour, not load-bearing for the actual goal).
- QA_CONTEXT_PACK.md generator (deferred).
- `scripts/suggest.py` prompt formatter (deferred).
- Auto-LLM scenario generation (never — Lock 5 stands).
- `app/*` changes (UI testability gaps reported separately if found,
  patched in a follow-up the user approves).
- Version bump.

## User-locked rules (all 9 from the approved plan)

1. The acceptance journey MUST NOT be DB-only. Every load-bearing step
   checks UI truth, history truth, or PM comprehension.
2. PM comprehension assertions are concrete: visible current phase,
   active blocker, reason text, next action, visible state.
3. At least one cross-page consistency check — Variant detail vs
   Overview (variant cost vs project cost).
4. Viewer privacy checks hit the actual page, not just the permission
   helper.
5. Realistic product data: ASD Football Folder, Single Knife, Combo
   Pack, coating supplier delay, packaging cost change.
6. No coverage matrix / context pack / prompt formatter in this build.
7. No auto-LLM scenario generation.
8. **Stable selectors only.** No fragile `text=...` or class-name
   grep. If the UI doesn't expose stable `data-*` attributes for an
   assertion I need, I do NOT add a workaround — I add an entry to
   `UI_TESTABILITY_GAPS.md` and propose a follow-up `app/*` patch.
9. Success criterion is not "more tests exist." The bar: this
   journey catches at least one class of bug that normal per-build
   `test.py` would miss.

## Architecture Review

1. **Problem solved.** The QA system has been engineering-driven so
   far. This build introduces the user-facing tier that catches
   workflow / UI mismatch / comprehension / privacy bugs.
2. **Tables touched (by the journey).** `users`, `projects`,
   `project_phases`, `project_variants`, `project_blockers`,
   `project_changes`, `phase_plan_changes`. Soft-archive at end via
   `projects.status = 'archived'`.
3. **Service layer.** Goes through `app.crud.*` for mutations + real
   HTTP routes via Playwright for the UI-facing actions. No ORM
   bypass.
4. **Change log.** Each mutating action triggers `write_change()` in
   the service helper. Acceptance journey asserts both DB rows AND
   that the **page can communicate** the change to the PM.
5. **Rollback.** Delete `acceptance/`, `lib/pm_views.py`,
   `SCENARIO_AUTHORING_GUIDE.md`, the test, and the
   `STABLE_CREDIBILITY.md` tier addition. Existing contracts /
   journeys / runner all unchanged.

## Backend Honesty Mapping

| Truth tier | Source of truth | How we test |
|---|---|---|
| DB truth | `app.crud.*` writes to in-memory SQLite (for unit-like steps) or live dev DB (for browser-driven steps) | `assertions.assert_db_field` / `assert_row_count` |
| UI truth | `app/templates/*.html` + Jinja context built by route handler | `pm_views.assert_overview_shows`, `assert_variant_page_shows` — read DOM via stable `data-*` selectors |
| History/audit truth | `project_changes` table + Timeline History feed | `pm_views.assert_history_explains` — verify a row in the visible Timeline History that contains the reason text |
| PM comprehension | Timeline Command Center section (Build 06+ feature) | `pm_views.assert_timeline_command_center_shows` — verify all 4 concrete fields: current phase, active blocker, reason, next action |
| Cross-page consistency | Variant page vs Overview page (different routes, same data) | `pm_views.assert_overview_and_variant_consistent` — open both pages, read the same field via stable selector on each, compare |
| Viewer privacy | rendered HTML when role=viewer | `pm_views.assert_viewer_does_not_see` — log in as viewer, navigate to project page, assert protected `data-*` element is absent or hidden |

## Critical decision before implementation: the selector audit

Per User lock 8, before writing any assertion I will audit:
- `app/templates/project_detail.html`
- `app/templates/components/timeline_*.html` (Timeline Command Center)
- `app/templates/variant_*.html` or wherever variant detail lives
- `app/templates/components/timeline_history*.html`

For each assertion the journey needs, I must find either:
- a stable `data-*` attribute that exposes the value, OR
- a stable semantic class/id that's load-bearing (used by the JS or
  by other features that won't be removed casually)

If neither exists, the assertion goes into `UI_TESTABILITY_GAPS.md`
with:
- what the assertion needs to check
- what selector would make it testable
- a proposed 1-3-line template patch (e.g. add
  `data-pm-current-phase="{{ project.current_stage }}"`)

I will NOT add `page.locator("text=current phase:")`-style fragile
assertions. The journey may end up smaller than 12-15 steps if many
gaps are found — that's the right outcome.

## Discipline boundary

All acceptance journeys:
- `setup(db)` — creates the PM user; the test project is created in
  step 1 of `STEPS` so its lifecycle is part of the journey
- `do_*(world, db, http)` — uses `actions.*`, `disruptions.*`, and
  Playwright via the existing `page` parameter
- `check_*(db, world)` — uses `assertions.*` AND `pm_views.*`. The
  discipline boundary widens to include `pm_views.*` since those
  ARE assertions (they raise `AssertionFailure` on mismatch).

`test_qa_build11.py` regex-checks the boundary for each function
body.

## Files Added (new)

- `scenario_contracts/lib/pm_views.py`
- `scenario_contracts/acceptance/__init__.py`
- `scenario_contracts/acceptance/football_knife_asd_lifecycle.py`
- `SCENARIO_AUTHORING_GUIDE.md`
- `test_qa_build11.py`
- `QA_BUILD11_EXECUTION_PLAN.md` (this file)
- Possibly `UI_TESTABILITY_GAPS.md` if the audit finds blockers

## Files Modified (additive only)

- `STABLE_CREDIBILITY.md` — add the acceptance tier
- `QA_ROADMAP.md` — mark QA-11 as shipped

## Test Plan

Pre-conditions:
- `python run.py` running on `localhost:8000`
- `playwright install chromium` already done

```bash
# 1. The acceptance journey passes against the live dev server
python3 -m scenario_contracts.lib.runner scenario_contracts/acceptance/football_knife_asd_lifecycle.py
# Expect: exit 0; "N steps OK"; PASS: 1

# 2. SKIPs cleanly when dev server unreachable
BASE_URL=http://127.0.0.1:1 python3 -m scenario_contracts.lib.runner scenario_contracts/acceptance/football_knife_asd_lifecycle.py
# Expect: exit 0; SKIP: 1; reason dev_server_unreachable

# 3. QA-11 regression
python3 test_qa_build11.py
# Expect: PASSED: N / FAILED: 0

# 4. Existing regressions stay green
bash run_qa_suite.sh
# Expect: Suite green.
```

`test_qa_build11.py` must cover:
- Plan file exists.
- `lib/pm_views.py` exposes the 6 named assertions.
- The journey loads with `acceptance` tag, `MATURITY="candidate"`, and ≥ 10 steps.
- Journey passes via subprocess when dev server reachable; SKIPs cleanly otherwise.
- Discipline boundary: every `do_*` uses only `actions/disruptions/page methods`; every `check_*` uses only `assertions.*` or `pm_views.*` (no raw `app.*` imports anywhere).
- The journey body contains at least one cross-page consistency check (Variant vs Overview) and at least one viewer-privacy check (`assert_viewer_does_not_see` call).
- `SCENARIO_AUTHORING_GUIDE.md` locks the 4-truth rule.
- `STABLE_CREDIBILITY.md` includes the acceptance tier.
- `app/*` is untouched; `app/version.py` stays at `1.4.0`.

## Acceptance Criteria

- Football Knife acceptance journey PASS against running dev server.
- `test_qa_build11.py` exits 0.
- All earlier regressions stay green (`bash run_qa_suite.sh` green).
- No `app/*` modification.
- If `UI_TESTABILITY_GAPS.md` is created, it lists each gap with a
  proposed patch (the user reviews + approves separately).

## What QA-11 is NOT

- Not auto-generating scenarios.
- Not adding live LLM to the QA system.
- Not building the coverage matrix or context pack.
- Not changing `app/*` (UI testability patches are a separate
  user-approved follow-up).
- Not bumping the product version.

## Why this is the right next build (not coverage tooling)

QA-10 closed the QA system as infrastructure. The next question is
**what scenarios do we put on top of it that actually catch PM
bugs?** The honest answer is "acceptance journeys with UI truth and
comprehension checks." Coverage matrix tooling is a refinement of
the engineering-tooling-first detour the user pushed back on; it
can come later, if it earns its keep.

## Open questions

None blocking. User-confirmed: synthetic-plausible data, soft-archive
cleanup. Selector audit is the implementation-time discovery that
shapes the journey body.
