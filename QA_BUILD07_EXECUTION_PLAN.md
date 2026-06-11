# QA Build 07 Execution Plan — Sandbox UI Mutation (Add Module from Palette)

## Status

Execution plan for the seventh QA Build.

Predecessor: QA Build 06 — Tier 1 contract gaps (`a91bd5e`).

Successor: QA Build 07b — Sandbox UI mutation (node edit + connect + cycle rejection + tidy).

Canonical roadmap: [QA_ROADMAP.md](QA_ROADMAP.md).

Plan-first commit so Codex can see scope before any code lands.

## Purpose

Directly answer the "Codex Timeline planner" UI deep-dive concern: prove
that the v1.4 Planning Sandbox **mutation flow** works end-to-end in a
real browser, against a real dev server, against the real route handlers
+ service helpers + DB.

QA-03 shipped read-only UI smoke (page renders). QA-07 adds the first
mutation: clicking the "Add module" button on a palette card creates a
new sandbox node and the canvas updates. This is the single most common
PM action in the new sandbox UI.

The scope is **one** focused UI scenario. Other Codex Timeline planner
mutations (node property edit, connect nodes, cycle rejection, Tidy,
Apply through the modal) defer to QA-07b so each gets its own
dev-DB-cleanup story.

## Scope

In:

1. Extend `scenario_contracts/lib/actions.py` with UI helpers:
   - `ensure_sandbox_exists(page, project_id, template_key="simple_oem_knife")`
     — visit `/projects/{id}/sandbox`; if `.sandbox-picker` is rendered
     (no draft yet), submit the picker form for `template_key`; return
     when the canvas is visible.
   - `click_add_first_module(page)` — click the first
     `.sandbox-add-module-btn` (which triggers the JS `addModule()`
     function at [planning_sandbox.js:386-397](app/static/js/planning_sandbox.js#L386-L397)).
   - `read_sandbox_node_count(page)` — read `cy.nodes().length` via
     `page.evaluate`; falls back to counting `[data-node-id]` markers
     when Cytoscape isn't ready.
2. Extend `scenario_contracts/lib/assertions.py` with one new UI
   assertion:
   - `assert_canvas_node_count_increased_by(page, snapshot, delta)` —
     uses `actions.read_sandbox_node_count` internally; raises
     `AssertionFailure` if the actual delta differs.
3. One contract scenario under `scenario_contracts/contracts/`:
   - `ui_sandbox_add_module.py` — tagged `ui` (so QA-01/02/06 runners
     SKIP it cleanly when Playwright/dev-server unavailable), `release_gate`
     (joins the v1.5 release gate set), `sandbox`, `mutation`.
4. `test_qa_build07.py` regression.

Out:

- Node property panel edit (QA-07b).
- Connect nodes via edge handle (QA-07b).
- Cycle rejection (QA-07b).
- Tidy auto-layout button (QA-07b).
- Apply via the confirmation modal (QA-07c — destructive; needs
  test-project lifecycle).
- Drag-to-canvas (deferred — Playwright's HTML5 drag-drop simulation
  is brittle on Cytoscape canvas elements; the button-click path
  covers the same service-layer code).
- New fixtures or seeded test projects (QA-07 uses whatever project
  the dev DB already has).
- `app/*` modifications.
- Version bump.

## Architecture Review

1. **Problem solved.** QA-03 only proved the sandbox page *renders*.
   The Codex Timeline planner ships actual mutation behavior, and
   none of it is locked. The "Add module" button is the single most
   common action; locking it catches the broadest class of UI
   regression for the least scenario surface.
2. **Tables touched.** `planning_sandboxes`, `planning_sandbox_nodes`
   in the LIVE dev DB. (No in-memory SQLite for UI scenarios — the
   in-memory DB still spins up because the runner is uniform, but
   the scenario does not read or write to it.)
3. **Service layer.** Goes through the real `POST
   /projects/{pid}/sandbox/{sid}/nodes/add` route which calls
   `crud.create_sandbox_node_from_module`. The JS layer is also in
   scope — the click event bound in
   [planning_sandbox.js:472](app/static/js/planning_sandbox.js#L472)
   calls `addModule()` which POSTs the form.
4. **Change log.** Sandbox draft mutations do NOT write
   `project_changes` rows (per v1.4 spec: only Apply writes to
   Timeline History). The scenario does not assert change-log rows.
5. **Rollback.** Delete the new scenario + UI action/assertion
   additions. Existing scenarios are unaffected.

## Backend Honesty Mapping

| Visible behavior | Source of truth | Write path | Derived rule | Permission | Test |
|---|---|---|---|---|---|
| Module palette renders | `crud.get_sandbox_canvas_payload(...)["modules"]` | n/a | server renders `.sandbox-module-card` per module per category | `can_edit_project` + sandbox is `draft` | UI smoke (already in QA-03) |
| "Add module" button click | JS `addModule()` → `POST /projects/{pid}/sandbox/{sid}/nodes/add` → `crud.create_sandbox_node_from_module` | route handler at [projects.py:789-816](app/routes/projects.py#L789-L816) | one new `planning_sandbox_nodes` row; sandbox payload refreshed | `can_edit_project` + sandbox is `draft` (enforced in `_sandbox_mutation_guard`) | `ui_sandbox_add_module` (this build) |
| Canvas node count update | Cytoscape's reactive render via `refreshFromPayload` | client-side JS | `cy.nodes().length` reflects the server's `elements` payload | n/a | `read_sandbox_node_count` via `page.evaluate` |
| Sandbox snapshot read | `crud.get_sandbox_canvas_payload(...)["elements"]` | n/a | nodes derived from `planning_sandbox_nodes` rows | all authenticated view | server-side payload + browser count |

## Locked Implementation Decisions

1. **Single scenario in QA-07.** Other sandbox UI mutations split out
   to QA-07b/c. Keeps the dev-DB-cleanup story tight: one button
   click adds one node. No destructive operations.
2. **No test-project lifecycle in QA-07.** We mutate whatever sandbox
   the discovered project has. The dev DB accumulates one extra node
   per run; bounded and acceptable. QA-07c (Apply UI) will introduce
   a proper test-project lifecycle because Apply is destructive.
3. **Sandbox auto-creation via the picker form.** If the discovered
   project has no draft sandbox yet, the scenario submits the
   `<form>` that posts to `/sandbox/create` with `template_key=simple_oem_knife`.
   The next page renders the canvas + palette, and the scenario
   proceeds. Idempotent: re-runs reuse the existing draft.
4. **Click via `.sandbox-add-module-btn`, not drag.** Per the v1.4
   plan (User lock 9 in QA-02 era), the Add button is the
   accessible fallback to drag. Testing the button covers the same
   service path with much less Playwright brittleness.
5. **Verify via `cy.nodes().length` snapshot.** `page.evaluate` reads
   the Cytoscape instance directly so we don't depend on DOM
   inspection of canvas pixels. Fallback: count `[data-node-id]`
   markers if `window.cy` isn't exposed.
6. **MATURITY = "candidate".** First UI mutation scenario. Promoted to
   `stable` after 10 consecutive green runs (per QA_ROADMAP.md
   stable-credibility definition).
7. **TAGS include `release_gate`.** Joining the release-gate set
   ratchets the gate from 15 PASS → 16 PASS once QA-07 is shipped.

## Discipline boundary (User lock 9)

The single scenario:
- `setup(db)` — empty world (the dev server has its own DB).
- `run(world, db, http, page)` — uses only `actions.*` (open_url,
  ensure_sandbox_exists, read_sandbox_node_count, click_add_first_module,
  wait_for_load).
- `check(db, world, page)` — uses only `assertions.*`
  (assert_canvas_node_count_increased_by, assert_ui_shows).

## Critical files to reference (read-only during implementation)

- [app/routes/projects.py:789-816](app/routes/projects.py#L789-L816)
  — `POST /sandbox/{sid}/nodes/add` route + service call
- [app/routes/projects.py:647-679](app/routes/projects.py#L647-L679)
  — `POST /sandbox/create` route (used by `ensure_sandbox_exists`
  when no draft yet)
- [app/static/js/planning_sandbox.js:386-397](app/static/js/planning_sandbox.js#L386-L397)
  — JS `addModule()` function the button click triggers
- [app/static/js/planning_sandbox.js:472](app/static/js/planning_sandbox.js#L472)
  — click binding for `.sandbox-add-module-btn`
- [app/templates/planning_sandbox.html:323-345](app/templates/planning_sandbox.html#L323-L345)
  — module card markup with `data-module-key` + the Add button
- [scenario_contracts/lib/browser.py](scenario_contracts/lib/browser.py)
  — already has admin login + screenshot capture from QA-03

## Files Added (new)

- `scenario_contracts/contracts/ui_sandbox_add_module.py`
- `test_qa_build07.py`
- `QA_BUILD07_EXECUTION_PLAN.md` (this file)

## Files Modified (additive only)

- `scenario_contracts/lib/actions.py` — 3 UI actions
- `scenario_contracts/lib/assertions.py` — 1 UI assertion
- `QA_ROADMAP.md` — mark QA-07 as shipped (after implementation
  commit)

## Test Plan

Pre-conditions:
- `python run.py` running on `localhost:8000`.
- `playwright install chromium` already done.
- Dev DB has at least one project (the UI scenario discovers any one).

Run:

```bash
# 1. The scenario passes against the live dev server
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ui_sandbox_add_module.py
# Expect: exit 0, PASS: 1

# 2. SKIPs cleanly when Playwright unavailable or dev server unreachable
BASE_URL=http://127.0.0.1:1 python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ui_sandbox_add_module.py
# Expect: exit 0, SKIP: 1 with detail dev_server_unreachable

# 3. QA-07 regression
python3 test_qa_build07.py
# Expect: PASSED: N / FAILED: 0

# 4. Existing regressions still green
python3 test_qa_build06.py     # 26/26 PASS
python3 test_qa_build05.py     # 23/23 PASS
python3 test_qa_build04.py     # 13/13 PASS
python3 test_qa_build03.py     # 21/21 PASS
python3 test_qa_build02.py     # 24/24 PASS
python3 test_qa_build01.py     # 24/24 PASS
python3 test_v14_build09.py    # 15/15 PASS
python3 test_build_v121.py     # 19/19 PASS

# 5. release_gate aggregation
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ --tag release_gate
# Expect: 16 PASS (golden_pass + 5 QA-02 + 4 QA-05 + 5 QA-06 + 1 QA-07)
```

`test_qa_build07.py` must cover:

- Plan file exists and locks "single scenario" + the Codex Timeline planner intent.
- 3 new UI actions present (`ensure_sandbox_exists`, `click_add_first_module`, `read_sandbox_node_count`).
- 1 new UI assertion present (`assert_canvas_node_count_increased_by`).
- Scenario declares 5 metadata + `ui` + `release_gate` + `mutation` tags + `MATURITY="candidate"`.
- Scenario runs as PASS against live dev server.
- Scenario SKIPs cleanly when dev server unreachable (verified via `BASE_URL` override).
- Discipline boundary holds.
- `lib/runner.py` LOC budget unchanged.
- `app/*` is untouched.

## Acceptance Criteria

- `ui_sandbox_add_module` PASSes against a running dev server.
- `--tag release_gate` aggregates 16 PASS once shipped.
- `test_qa_build07.py` exits 0.
- All earlier QA + v1.4 + v1.2.1 regressions stay green.
- No `app/*` modification.

## What QA Build 07 is NOT

- Not testing node property panel edits (QA-07b).
- Not testing edge creation or cycle rejection (QA-07b).
- Not testing the Tidy button (QA-07b).
- Not testing Apply through the modal (QA-07c — destructive flow needs test-project lifecycle).
- Not testing drag-and-drop (deferred; button click covers same service path).
- Not creating test projects via HTTP (kept for QA-07c when destructive flows ship).
- Not changing the runner, the journey shape, or any existing scenarios.
- Not bumping the product version.

## Open questions

None blocking. The biggest implementation question is "does `cy` get
exposed as a window global?" — checked during implementation; the
fallback (counting `[data-node-id]` markers) handles the "not exposed"
case. If Cytoscape exposes its instance differently, the action
adapts.
