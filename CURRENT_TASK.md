# CURRENT_TASK.md

## Task
v1.4 Builds 01-03 and the v1.3 UI Rescue fixes UI-R1 through UI-R4 are implemented in the working tree and are ready to be checkpointed. User asked to commit/push these fixes and then return to building the sandbox app. After the checkpoint commit/push, resume v1.4 with Build 04 planning/implementation discipline.

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth.

## What changed in v1.4 Build 01

- `V14_BUILD01_EXECUTION_PLAN.md` — per-build execution plan with scope, Architecture Review, Backend Honesty Mapping, test plan, and acceptance criteria.
- `app/models.py` — added 7 Planning Sandbox models:
  - `PlanningModule`
  - `PlanningSandbox`
  - `PlanningSandboxNode`
  - `PlanningSandboxEdge`
  - `PlanningTemplate`
  - `PlanningTemplateNode`
  - `PlanningTemplateEdge`
  - Added `Project.planning_sandboxes` relationship.
- `app/migrations.py` — added migrations:
  - `007_v1_4_create_planning_sandbox_core`
  - `010_v1_4_create_planning_templates`
  - 008 and 009 intentionally remain unclaimed for later v1.4 builds.
  - Seeds 24 active planning modules.
  - Seeds 6 system templates: Simple OEM Knife, Standard Folding Knife, New Mechanism Knife, Gift Set / Combo Pack, Packaging-heavy Retail Product, Amazon Launch Product.
- `app/crud.py` — added read-only helpers:
  - `list_planning_modules`
  - `list_planning_templates`
  - `get_planning_template_counts`
- `app/routes/admin.py` — added admin-only read route `GET /admin/modules`.
- `app/templates/admin_modules.html` — new read-only inspection page for modules/templates.
- `app/templates/base.html` — added admin-only "Modules" nav link.
- `test_v14_build01.py` — new Build 01 regression, 23/23 PASS.
- v1.3 regression tests relaxed where they had exact migration-count locks, so they preserve v1.3 migration IDs while allowing v1.4 additive migrations:
  - `test_v13_build07b.py`
  - `test_v13_build08.py`
  - `test_v13_build09.py`
  - `test_v13_build10.py`

## What changed in v1.4 Build 02

- `V14_BUILD02_EXECUTION_PLAN.md` — focused plan for the server-authoritative schedule engine.
- `app/crud.py` — added `compute_sandbox_schedule(db, sandbox_id, require_nodes=False)` and private helpers for topological sort, ancestor lookup, component counting, and payload shaping.
- Schedule engine is read-only and never touches `project_phases`.
- Hard errors: missing sandbox, zero-node apply validation, missing title, invalid duration, dangling edge, cross-sandbox edge, circular dependency.
- Soft warnings: disconnected branch, very long duration, terminal-not-launch-like, packaging before design, production before sample/review, missing owner, missing deliverable, missing exit criteria.
- `test_v14_build02.py` — 9/9 PASS.

## What changed in v1.4 Build 03

- `V14_BUILD03_EXECUTION_PLAN.md` — focused plan for the static canvas renderer.
- `app/crud.py` — added:
  - `get_active_planning_sandbox`
  - `create_sandbox_blank`
  - `create_sandbox_from_template`
  - `get_sandbox_canvas_payload`
- `app/routes/projects.py` — added:
  - `GET /projects/{project_id}/sandbox`
  - `POST /projects/{project_id}/sandbox/create`
- `app/templates/planning_sandbox.html` — new sandbox page with template picker, read-only Cytoscape canvas, schedule summary, warning strip, and node list.
- `app/static/js/planning_sandbox.js` — lazy-loaded Cytoscape renderer using server-provided preset positions.
- `app/static/css/styles.css` — sandbox page layout and responsive canvas styling.
- `app/i18n/en.json` and `app/i18n/zh.json` — 20 sandbox UI keys added with exact parity.
- `test_v14_build03.py` — 16/16 PASS.

## Scope discipline

Builds 01-03 intentionally do **not** add:
- drag/drop editing
- module add/delete routes
- edge connect/delete routes
- property panel editing
- Apply behavior
- `planning_apply_events`
- AI tools
- live `project_phases` mutation

## Verification

- `python3 -m py_compile app/crud.py app/routes/projects.py test_v14_build01.py test_v14_build02.py test_v14_build03.py` — PASS.
- `python3 test_v14_build01.py` — 23/23 PASS.
- `python3 test_v14_build02.py` — 9/9 PASS.
- `python3 test_v14_build03.py` — 16/16 PASS.
- `python3 test_build_v121.py` — 19/19 PASS.
- `python3 test_v13_build09.py` — 99/99 PASS.
- `python3 test_v13_build10.py` — 51/51 PASS, run with localhost network access because it invokes HTTP regressions against the already-running dev server.
- Non-destructive Playwright live smoke — PASS: admin login 303, `GET /projects/{id}/sandbox` 200, Planning Sandbox title visible.
- `git diff --check` — PASS.

## Current pause / reset

- New reset doc: `V13_UI_REWORK_EXPECTATION_RESET.md`.
- Original PRDs read:
  - `/Users/Mordred5687/Downloads/project_overview_redesign_plan.md`
  - `/Users/Mordred5687/Downloads/timeline_command_center_redesign_plan.md`
- Key finding: production screenshot looks like a combination of stale/missing v1.3 CSS and real visual-design failure.
- `base.html` currently loads `/static/css/styles.css` and `/static/js/main.js` without version query/cache-busting, which can plausibly leave production browsers with old CSS while HTML has new v1.3 markup.

## Next step

Review `V13_UI_REWORK_EXPECTATION_RESET.md` with the user/Claude/ChatGPT before implementing anything.

Likely first rescue build:
- asset cache-busting for CSS/JS,
- production/live smoke proving v1.3 Timeline CSS is actually loaded,
- Playwright screenshot/computed-style checks for Timeline Command Center.

Do not continue v1.4 Build 04 until user explicitly unpauses v1.4.

## v1.3 UI-R1 completed in working tree

- `app/main.py` — added `STATIC_ASSET_VERSION` Jinja global derived from `CURRENT_VERSION`, `LAST_UPDATED`, and the latest mtime of `app/static/css/styles.css` / `app/static/js/main.js`.
- `app/templates/base.html` — first-party app CSS/JS now load as:
  - `/static/css/styles.css?v={{ STATIC_ASSET_VERSION }}`
  - `/static/js/main.js?v={{ STATIC_ASSET_VERSION }}`
- `test_v13_ui_r1.py` — new regression for asset URLs and browser-computed Timeline CSS.
- `CHANGELOG.md` — added UI-R1 note.

Verification:
- `python3 -m py_compile app/main.py test_v13_ui_r1.py` — PASS.
- `python3 test_v13_ui_r1.py` — 10/10 PASS, run with localhost network access.

Next approved build, if user says proceed:
- UI-R4 — Timeline History event feed polish.
- Do not continue v1.4 Build 04 until user explicitly unpauses v1.4.

## v1.3 UI-R2 completed in working tree

- `app/templates/project_detail.html` — Timeline first fold is now one `timeline-command-card` inside `#timeline-command-center`, with a dashboard header, current-phase status, phase strip, 3 core status tiles, blocker/support grid, assistant suggestion panel, and action row in the same card. Timeline tab hash target changed to `#timeline-command-center`; old `#timeline` hash still activates the Timeline workspace for compatibility. The secondary detailed table section is now labeled Timeline Map.
- `app/static/css/styles.css` — replaced the thin Timeline shell styles with a dashboard card layout, polished phase strip/tile/support/action-row styling, responsive single-column stacking, and desktop/mobile scroll margins for Timeline anchors.
- `app/i18n/en.json` / `app/i18n/zh.json` — added UI-R2 labels and changed visible AI nudge wording from raw placeholder language to "Assistant suggestions" / "助手建议" with exact parity. `timeline.placeholder_label` remains for older regressions, but no longer renders in the dashboard.
- `test_v13_ui_r2.py` — new UI-R2 regression. It checks source structure, i18n parity, Playwright-computed dashboard layout, the Timeline tab hash target, absence of user-facing placeholder copy, Finish Current Phase availability, and mobile no-horizontal-overflow. It writes screenshots:
  - `test_artifacts/v13_ui_r2_timeline_desktop.png`
  - `test_artifacts/v13_ui_r2_timeline_small.png`

Verification:
- `python3 -m py_compile test_v13_ui_r2.py app/main.py` — PASS.
- `python3 test_v13_ui_r2.py` — 26/26 PASS, run with localhost network access.
- `python3 test_v13_ui_r1.py` — 10/10 PASS, run with localhost network access.
- `python3 test_v13_build06.py` — 59/59 PASS, run with localhost network access.
- `python3 test_build_v121.py` — 19/19 PASS.
- `git diff --check` — PASS.

## v1.3 UI-R3 completed in working tree

- `app/templates/components/bottom_chat.html` — bottom dock now has:
  - `#bottomChatCollapseBtn` inside the expanded composer.
  - `#bottomChatRestoreBtn` compact `AI` restore affordance when collapsed.
- `app/static/js/main.js` — added `setDockCollapsed(collapsed)` to toggle dock state. It does not persist collapsed state, so the dock remains expanded by default on page load. It preserves the live composer DOM, so draft text, selected mode, selected scope, and pending attachments stay in place while collapsed.
- `app/static/css/styles.css` — added collapsed/restore dock styling, larger reserved bottom padding for the expanded dock, reduced padding for collapsed state, mobile wrapping so the textarea no longer becomes a vertical sliver, and `scroll-margin-bottom` on `.timeline-action-row` so scrolling Timeline actions into view leaves clearance above the dock.
- `app/i18n/en.json` / `app/i18n/zh.json` — added `chat.collapse_dock` and `chat.expand_dock` with exact parity.
- `test_v13_ui_r3.py` — new UI-R3 regression. It checks source markers, i18n parity, default expanded state, expanded no-overlap, Finish Current Phase clickability, collapsed state, collapsed no-overlap, draft preservation, restore behavior, and mode/scope preservation on desktop + small viewport. It writes screenshots:
  - `test_artifacts/v13_ui_r3_desktop_expanded.png`
  - `test_artifacts/v13_ui_r3_desktop_collapsed.png`
  - `test_artifacts/v13_ui_r3_small_expanded.png`
  - `test_artifacts/v13_ui_r3_small_collapsed.png`

Verification:
- `python3 -m py_compile test_v13_ui_r3.py app/main.py` — PASS.
- `python3 test_v13_ui_r3.py` — 30/30 PASS, run with localhost network access.
- `python3 test_v13_ui_r2.py` — 26/26 PASS, run with localhost network access.
- `python3 test_v13_ui_r1.py` — 10/10 PASS, run with localhost network access.
- `python3 test_v13_build06.py` — 59/59 PASS, run with localhost network access.
- `python3 test_build_v121.py` — 19/19 PASS.
- `git diff --check` — PASS.

## v1.3 UI-R4 completed in working tree

- `app/templates/project_detail.html` — Timeline History keeps the same derived events and six filters, but rows now render as feed cards with type icon, timestamp, bucket/subtype badges, optional AI badge, summary, optional body/details, actor/meta, and stable View link. Filter buttons now expose `role="tab"` and initial `aria-selected` state.
- `app/static/css/styles.css` — History filters now render as app-native segmented chips; events render as bordered audit/feed cards with per-bucket icon colors; empty states use intentional dashed-card styling; mobile stacks cards and filters without horizontal overflow.
- `app/static/js/main.js` — Timeline History filtering now updates `aria-selected` alongside `.timeline-history-chip-active`.
- `test_v13_ui_r4.py` — new regression. It checks source markers, i18n parity, browser-computed segmented filters, bordered feed cards, type icon visibility, summary/meta/event-type content, preserved filter behavior, no-match empty state, and mobile no-horizontal-overflow. It writes screenshots:
  - `test_artifacts/v13_ui_r4_history_desktop.png`
  - `test_artifacts/v13_ui_r4_history_small.png`
- `CHANGELOG.md` — added UI-R4 note.

Verification:
- `python3 -m py_compile test_v13_ui_r4.py app/main.py` — PASS.
- `python3 test_v13_ui_r4.py` — 20/20 PASS, run with localhost network access.
- `python3 test_v13_ui_r1.py` — 10/10 PASS, run with localhost network access.
- `python3 test_v13_ui_r2.py` — 26/26 PASS, run with localhost network access.
- `python3 test_v13_ui_r3.py` — 30/30 PASS, run with localhost network access.
- `python3 test_v13_build08.py` — 55/55 PASS, run with localhost network access.
- `python3 test_v13_build06.py` — 59/59 PASS, run with localhost network access.
- `python3 test_build_v121.py` — 19/19 PASS.
- `git diff --check` — PASS.

Remaining known state:
- UI-R1 through UI-R4 are complete in the working tree.
- v1.4 Builds 01-03 are complete in the working tree.
- User explicitly unpaused sandbox work on 2026-06-06 after asking to commit/push these fixes.
- Next sandbox work should start with v1.4 Build 04. Follow the established pattern: create/review the specific build plan first, then code only the approved Build 04 scope.
- No UI-R4 routes, service functions, DB tables, migrations, or AI behavior changed.

## v1.4 Build 04 plan drafted after checkpoint

- `V14_BUILD04_EXECUTION_PLAN.md` has been created as the next sandbox build plan.
- Plan revised after Claude Code review:
  - mutation routes now include `{sandbox_id}`: `/projects/{project_id}/sandbox/{sandbox_id}/nodes/...`,
  - `get_sandbox_canvas_payload` must include active module-library data,
  - property edits / position writes use fetch + JSON payload replacement,
  - viewer mutation affordances are hidden, not merely disabled,
  - i18n Build 04 key list is locked at 18 new keys, taking bundles from 740/740 to 758/758 if unchanged,
  - plan references `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md` as canonical product/engineering rationale.
- Build 04 planned scope: Module Palette + Add/Edit Nodes.
- Planned mutations are sandbox-only:
  - add node from module library,
  - edit node title/duration/owner/deliverable/exit criteria,
  - persist node x/y position,
  - delete node and attached sandbox edges.
- Planned non-scope:
  - no edge creation/deletion UI,
  - no dependency editing,
  - no Apply route,
  - no Save as Template,
  - no AI tools,
  - no `project_phases` mutation,
  - no migration unless a true schema gap appears.
- Build 04 has now been implemented and verified.

## v1.4 Build 04 completed in working tree

- `V14_BUILD04_EXECUTION_PLAN.md` — completed execution plan for Module Palette + Add/Edit Nodes, revised after Claude review.
- `app/crud.py` — added draft-only sandbox node services:
  - `_get_project_draft_sandbox`
  - `_get_project_sandbox_node`
  - `_planning_module_payload`
  - `create_sandbox_node_from_module`
  - `update_sandbox_node`
  - `update_sandbox_node_position`
  - `delete_sandbox_node`
  - `get_sandbox_canvas_payload` now returns `elements`, `schedule`, and `modules`.
- `app/routes/projects.py` — added JSON mutation routes:
  - `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/add`
  - `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/update`
  - `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/position`
  - `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/delete`
- `app/templates/planning_sandbox.html` — added module palette, node property panel, viewer read-only inventory behavior, JSON payload data, and versioned sandbox JS URL.
- `app/static/js/planning_sandbox.js` — added shared fetch+JSON update flow, add/select/edit/move/delete behavior, payload refresh, and schedule-summary refresh.
- `app/static/css/styles.css` — added palette, module-card, property-panel, node-message, and responsive sandbox editor styling.
- `app/main.py` — `STATIC_ASSET_VERSION` now also tracks `app/static/js/planning_sandbox.js`.
- `app/i18n/en.json` / `app/i18n/zh.json` — added exactly 18 Build 04 keys; parity is 758/758.
- `test_v14_build04.py` — new Build 04 regression with source locks, temp-DB service coverage, live JSON routes, Playwright desktop/mobile smoke, and screenshots:
  - `test_artifacts/v14_build04_sandbox_desktop.png`
  - `test_artifacts/v14_build04_sandbox_mobile.png`
- `test_v14_build03.py` — relaxed stale Build 03 assertions so it still forbids Apply/edge/template mutation and phase mutation, while allowing Build 04's approved node routes and editor-mode canvas dragging.
- `CHANGELOG.md` — added Build 04 Unreleased entry.

## v1.4 Build 04 verification

- `python3 -m py_compile app/main.py app/crud.py app/routes/projects.py test_v14_build04.py` — PASS.
- `git diff --check` — PASS before docs; rerun before final handoff/commit.
- `python3 test_v14_build04.py` — 26/26 PASS, run with localhost network access.
- `python3 test_v14_build01.py` — 23/23 PASS.
- `python3 test_v14_build02.py` — 9/9 PASS.
- `python3 test_v14_build03.py` — 16/16 PASS, run with localhost network access after adjusting stale Build 03 route/read-only assertions.
- `python3 test_v13_ui_r4.py` — 20/20 PASS, run with localhost network access.
- `python3 test_build_v121.py` — 19/19 PASS.

## Next step after Build 04

- Stop and report Build 04. Do not continue to Build 05 until the user explicitly asks.
- Likely next sandbox build: v1.4 Build 05 — Connect Nodes. Before coding, write/review a specific `V14_BUILD05_EXECUTION_PLAN.md`.
- Build 04 intentionally still has no edge creation/deletion UI, dependency editing, Apply route, Save Template route, AI tools, migration, or live `project_phases` mutation.

## v1.4 Build 05 completed in working tree

- `V14_BUILD05_EXECUTION_PLAN.md` — new execution plan for Connect Nodes, anchored to the v1.4 sandbox design docs.
- `app/crud.py` — added draft-only dependency edge services:
  - `_get_project_sandbox_edge`
  - `_parse_node_id_list`
  - `_validate_sandbox_node_ids`
  - `_raise_if_sandbox_has_hard_graph_error`
  - `create_sandbox_edge`
  - `delete_sandbox_edge`
  - `replace_sandbox_node_dependencies`
  - `get_sandbox_canvas_payload` now emits per-node `depends_on_ids` and `dependent_ids`.
- `app/routes/projects.py` — added JSON dependency routes:
  - `POST /projects/{project_id}/sandbox/{sandbox_id}/edges`
  - `POST /projects/{project_id}/sandbox/{sandbox_id}/edges/{edge_id}/delete`
  - `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/dependencies`
- `app/templates/planning_sandbox.html` — added Depends On multi-select, dependency save form, dependency list container, warning-strip update hook, and dependency error/success labels.
- `app/static/js/planning_sandbox.js` — added multi-value form posting, warning-strip refresh, dependency option/list rendering, dependency save/delete fetch flows, cycle-error messaging, and edge selected styling.
- `app/static/css/styles.css` — added dependency form/list/row styling and mobile stacking.
- `app/i18n/en.json` / `app/i18n/zh.json` — added exactly 8 Build 05 keys; parity is 766/766.
- `test_v14_build05.py` — new Build 05 regression with source locks, temp-DB graph validation, live JSON routes, Playwright desktop/mobile smoke, and screenshots:
  - `test_artifacts/v14_build05_sandbox_dependencies_desktop.png`
  - `test_artifacts/v14_build05_sandbox_dependencies_mobile.png`
- `test_v14_build04.py` — adjusted exact i18n count assertion to allow later builds while still proving Build 04 keys and exact EN/zh parity.
- `test_v14_build03.py` — adjusted stale route assertion so Build 03 still forbids Apply/Save Template and phase mutation while allowing later approved node/edge sandbox routes.
- `CHANGELOG.md` — added Build 05 Unreleased entry.

## v1.4 Build 05 verification

- `python3 -m py_compile app/main.py app/crud.py app/routes/projects.py test_v14_build03.py test_v14_build04.py test_v14_build05.py` — PASS.
- `git diff --check` — PASS.
- `python3 test_v14_build05.py` — 24/24 PASS, run with localhost network access.
- `python3 test_v14_build04.py` — 26/26 PASS, run with localhost network access.
- `python3 test_v14_build03.py` — 16/16 PASS, run with localhost network access.
- `python3 test_v14_build02.py` — 9/9 PASS.
- `python3 test_v14_build01.py` — 23/23 PASS.
- `python3 test_v13_ui_r4.py` — 20/20 PASS, run with localhost network access.
- `python3 test_build_v121.py` — 19/19 PASS.

## Next step after Build 05

- Stop and report Build 05. Do not continue to Build 06 until the user explicitly asks.
- Likely next sandbox build: v1.4 Build 06 — Canvas Interaction Hardening. Before coding, write/review a specific `V14_BUILD06_EXECUTION_PLAN.md`.
- Build 05 intentionally still has no Apply route, Save Template route, migration, AI tools, auto-layout/tidy behavior, dependency types beyond `finish_to_start`, or live `project_phases` mutation.

## v1.4 Build 06 completed in working tree

- `V14_BUILD06_EXECUTION_PLAN.md` — new execution plan for Canvas Interaction Hardening. It also records the user's larger-test request: after the full v1.4 version is complete, add a broader PM Scenario Contract Runner during Build 09/release hardening to simulate realistic PM workflows end to end.
- `app/crud.py` — added canvas hardening helpers:
  - `_sandbox_duration_bin`
  - `update_sandbox_node_positions`
  - `get_sandbox_canvas_payload` now emits `duration_bin` and `node_height` for each node.
- `app/routes/projects.py` — sandbox view can inspect an explicit sandbox through `?sandbox_id=...`; non-draft snapshots render read-only. Added:
  - `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/positions`
- `app/templates/planning_sandbox.html` — added Tidy Canvas toolbar action for editors, read-only snapshot affordance, warning-chip labels, edit-aware empty states, and dagre/cytoscape-dagre script loading with fallback-safe JS.
- `app/static/js/planning_sandbox.js` — added loading state, warning-chip rendering, duration-height styling, Tidy Canvas via dagre with deterministic fallback, and bulk position persistence through the new JSON route.
- `app/static/css/styles.css` — added toolbar action layout, warning chips, canvas loading overlay, duration-size support, and mobile toolbar stacking.
- `app/i18n/en.json` / `app/i18n/zh.json` — added exactly 9 Build 06 keys; parity is 775/775.
- `test_v14_build06.py` — new Build 06 regression with plan/source locks, temp-DB position/duration/snapshot coverage, live JSON route coverage, Playwright Tidy/duration/warning/snapshot/mobile checks, and screenshots:
  - `test_artifacts/v14_build06_sandbox_hardened_desktop.png`
  - `test_artifacts/v14_build06_sandbox_hardened_mobile.png`
- `test_v14_build04.py` / `test_v14_build05.py` — adjusted exact i18n count assertions to allow later builds while still proving their required keys and exact EN/zh parity.

## v1.4 Build 06 verification

- `python3 -m py_compile app/crud.py app/routes/projects.py test_v14_build06.py` — PASS.
- `python3 test_v14_build06.py` — 17/17 PASS, run with localhost network access.
- `python3 test_v14_build05.py` — 24/24 PASS, run with localhost network access.
- `python3 test_v14_build04.py` — 26/26 PASS, run with localhost network access.
- `python3 test_v14_build03.py` — 16/16 PASS, run with localhost network access.
- `python3 test_v14_build02.py` — 9/9 PASS.
- `python3 test_v14_build01.py` — 23/23 PASS.
- `python3 test_v13_ui_r4.py` — 20/20 PASS, run with localhost network access.
- `python3 test_build_v121.py` — 19/19 PASS.

## Next step after Build 06

- Stop and report Build 06. Do not continue to Build 07 until the user explicitly asks.
- Likely next sandbox build: v1.4 Build 07 — Apply Sandbox to Live Timeline. Before coding, write/review a specific `V14_BUILD07_EXECUTION_PLAN.md`.
- Build 06 intentionally still has no Apply route, Save Template route, migration, AI tools, dependency types beyond `finish_to_start`, or live `project_phases` mutation.
- Larger PM scenario testing should happen after the version is functionally complete, likely in v1.4 release hardening, so the test can cover the final Apply/Template flows instead of locking an incomplete workflow.

## v1.4 Build 07 plan drafted

- `V14_BUILD07_EXECUTION_PLAN.md` has been created as the next sandbox build plan.
- Revised on 2026-06-09 after Claude Code review:
  - `delayed` phases now block Apply,
  - `skipped` phases are replaceable only when they have no actual dates and must appear in the replacement warning,
  - phase deletion predicate is locked:
    `project_id=? AND actual_start_date IS NULL AND actual_end_date IS NULL AND status IN ('not_started','skipped')`,
  - new phase notes null-handling is locked,
  - service argument uses `apply_start_date` to avoid ambiguity,
  - stage/delay recalculation must happen inside the Apply transaction before one final commit,
  - Apply creates no `phase_plan_changes` rows,
  - tests must cover each active-execution precondition separately,
  - tests must assert viewer Apply affordances are hidden and no AI Apply tool is registered.
- Build 07 planned scope: Apply Sandbox To Project Plan.
- Planned schema addition:
  - migration 009 for `planning_apply_events`,
  - `PlanningApplyEvent` model and relationship(s).
- Planned live mutation boundary:
  - Apply is the only bridge from sandbox draft to `project_phases`,
  - no phase mutation before explicit Apply POST,
  - service must reject active execution before deleting/recreating phases.
- Planned route:
  - `POST /projects/{project_id}/sandbox/{sandbox_id}/apply`
- Planned services:
  - `validate_sandbox_for_apply`
  - `get_sandbox_apply_preview`
  - `apply_sandbox_to_project`
- Planned active-execution refusal checks:
  - any existing phase `actual_start_date`,
  - any existing phase `actual_end_date`,
  - any existing phase status `in_progress`, `done`, or `delayed`,
  - any active phase-linked blocker on the project.
- Planned Apply transaction:
  - recompute schedule server-side,
  - reject hard graph errors and preconditions,
  - delete only untouched phases matching the locked not_started/skipped predicate,
  - create new `ProjectPhase` rows from sandbox topological order with planned dates,
  - optionally update `projects.planned_launch_date`,
  - mark sandbox `applied`,
  - insert `planning_apply_events`,
  - write `project_changes` row with `change_type='plan_applied'`,
  - recalculate project stage/delay before one final commit.
- Planned UI:
  - Apply confirmation modal/panel,
  - planned start date defaulting to today,
  - computed end date preview,
  - launch-date update checkbox default off,
  - replacement warning listing existing phase names,
  - blocked state for hard graph errors or active execution.
- Planned Timeline History integration:
  - plan-applied event card derived from `planning_apply_events` and/or project change data.
- Planned i18n addition: 16 keys, expected parity 791/791 if unchanged.
- Planned tests: `test_v14_build07.py` plus Build 06/05/04 and v1.2.1 baseline.
- Do not implement Build 07 code until the user approves this plan.

## v1.4 Build 07 completed in working tree

- `app/models.py` — added `PlanningApplyEvent` plus relationships from `Project` and `PlanningSandbox`.
- `app/migrations.py` — added migration `009_v1_4_create_planning_apply_events` with idempotent `planning_apply_events` table and project/sandbox indexes.
- `app/crud.py` — added Apply helpers:
  - `_sandbox_apply_preconditions`
  - `validate_sandbox_for_apply`
  - `get_sandbox_apply_preview`
  - `_sandbox_apply_snapshot`
  - `_sandbox_phase_notes`
  - `apply_sandbox_to_project`
- `app/crud.py` — extended `get_timeline_events` with `planning_apply_events` as a new derived source and suppresses duplicate `project_changes.plan_applied` cards.
- `app/routes/projects.py` — sandbox GET now passes `apply_preview`; added:
  - `POST /projects/{project_id}/sandbox/{sandbox_id}/apply`
- `app/templates/planning_sandbox.html` — added Apply confirmation panel for editable draft sandboxes, blocked Apply state, start/end date preview, launch-date checkbox, replacement warning, success/error messages, and viewer-hidden Apply affordance.
- `app/templates/project_detail.html` — Timeline History maps `plan_applied` subtype to the localized label.
- `app/static/css/styles.css` — added Apply panel, metrics, warning, replacement-chip, blocked-state, and responsive styles.
- `app/static/js/planning_sandbox.js` — added client-side computed-end-date preview for the Apply panel; server still recomputes dates on submit.
- `app/i18n/en.json` / `app/i18n/zh.json` — added exactly 16 Build 07 keys; parity is 791/791.
- `test_v14_build07.py` — new Build 07 regression with source locks, temp-DB service/migration coverage, live Apply route checks, Playwright Apply panel smoke, and screenshots:
  - `test_artifacts/v14_build07_apply_blocked_desktop.png`
  - `test_artifacts/v14_build07_apply_modal_desktop.png`
  - `test_artifacts/v14_build07_apply_mobile.png`
- `test_v14_build01.py` — updated stale future-build assertions now that migration 009 legitimately exists.
- `test_v14_build03.py` — updated stale future-route assertion to continue forbidding Save Template while allowing Build 07 Apply.
- `test_v14_build06.py` — adjusted exact i18n count assertion to allow later builds while still proving Build 06 keys and exact EN/zh parity.
- `CHANGELOG.md` — added Build 07 Unreleased entry.

## v1.4 Build 07 verification

- `python3 -m py_compile app/models.py app/migrations.py app/crud.py app/routes/projects.py test_v14_build07.py` — PASS.
- `git diff --check` — PASS before final handoff; rerun before commit.
- `python3 test_v14_build07.py` — 26/26 PASS, run with localhost network access.
- `python3 test_v14_build06.py` — 17/17 PASS, run with localhost network access.
- `python3 test_v14_build05.py` — 24/24 PASS, run with localhost network access.
- `python3 test_v14_build04.py` — 26/26 PASS, run with localhost network access.
- `python3 test_v14_build03.py` — 16/16 PASS, run with localhost network access.
- `python3 test_v14_build02.py` — 9/9 PASS.
- `python3 test_v14_build01.py` — 23/23 PASS.
- `python3 test_v13_ui_r4.py` — 20/20 PASS, run with localhost network access.
- `python3 test_build_v121.py` — 19/19 PASS.

## Next step after Build 07

- Stop and report Build 07. Do not continue to Build 08 until the user explicitly asks.
- Likely next sandbox build: v1.4 Build 08 — Save Workflow As Template. Before coding, write/review a specific `V14_BUILD08_EXECUTION_PLAN.md`.
- Build 07 intentionally still has no Save Template route, AI tools, multiple-draft sandbox support, partial merge into active execution, append-after-started-phases mode, or new dependency types beyond `finish_to_start`.

## v1.4 Build 08 plan drafted

- `V14_BUILD08_EXECUTION_PLAN.md` has been created as the next sandbox build plan.
- Plan scope: Save Workflow As Template.
- Planned docs/code targets for implementation after approval:
  - `app/crud.py` service helpers:
    - `list_planning_templates_for_user`
    - `save_sandbox_as_template`
  - `app/routes/projects.py` route:
    - `POST /projects/{project_id}/sandbox/{sandbox_id}/save-template`
  - `app/templates/planning_sandbox.html` save-template form/panel and grouped template picker.
  - `app/i18n/en.json` / `app/i18n/zh.json` exactly 14 new keys, expected parity 805/805 if current base remains 791/791.
  - `AI_TOOLS_REGISTRY.md` planned/deferred row for future `save_sandbox_as_template` AI tool; no AI handler in Build 08.
  - `test_v14_build08.py`.
- Locked decisions:
  - no migration by default; use existing `planning_templates`, `planning_template_nodes`, and `planning_template_edges`,
  - saved templates are global reusable records, not project-scoped records,
  - system templates remain immutable,
  - template keys are generated by the service and never user-supplied,
  - draft and applied sandboxes can be saved; archived sandboxes cannot,
  - saving a template does not write `ProjectPhase`, `PlanningApplyEvent`, launch date, or phase-plan-change rows,
  - user templates are visible to creator and admins only,
  - viewers do not see dead Save/Create buttons,
  - AI registry is updated, but no `app/ai/tools.py` handler is added.
- Do not implement Build 08 code until the user approves this plan.

## v1.4 Build 08 completed in working tree

- Plan-first commit was created before implementation:
  - `6ab43bd Plan v1.4 Build 08 save workflow templates`
- `app/crud.py` — added:
  - `list_planning_templates_for_user`
  - `_template_key_slug`
  - `_unique_template_key`
  - `save_sandbox_as_template`
  - `create_sandbox_from_template` now filters private user templates by creator/admin visibility.
- `app/routes/projects.py` — sandbox GET now uses filtered template visibility and passes grouped template data plus `can_save_template`; added:
  - `POST /projects/{project_id}/sandbox/{sandbox_id}/save-template`
- `app/templates/planning_sandbox.html` — template picker now groups System Templates and My Templates; user templates show a badge; editable draft/applied sandboxes show a compact Save as Template panel; viewers do not see Save/Create mutation affordances.
- `app/static/css/styles.css` — added grouped template-picker and save-template-panel styling.
- `app/i18n/en.json` / `app/i18n/zh.json` — added exactly 14 Build 08 keys; parity is now 805/805.
- `AI_TOOLS_REGISTRY.md` — added planned/deferred `save_sandbox_as_template` row; no AI handler was added.
- `test_v14_build08.py` — new Build 08 regression with service, visibility, route, i18n, and browser smoke coverage.
- `test_v14_build03.py` / `test_v14_build07.py` — refreshed stale forward-looking assertions so earlier build regressions allow Build 08's legitimate route and later i18n key count while still proving their own invariants.
- `CHANGELOG.md` — added Build 08 Unreleased note.

Build 08 intentionally does **not** add:
- migrations,
- template edit/delete UI,
- project-scoped templates,
- Apply behavior changes,
- live `project_phases` writes,
- `planning_apply_events` writes,
- AI chat handler,
- multiple draft sandbox support.

Build 08 verification:
- `python3 -m py_compile app/crud.py app/routes/projects.py test_v14_build08.py test_v14_build03.py` — PASS.
- `git diff --check` — PASS before changelog/handoff update; rerun before commit.
- `python3 test_v14_build08.py` — 22/22 PASS, run with localhost network access.
- `python3 test_v14_build07.py` — 26/26 PASS, run with localhost network access.
- `python3 test_v14_build06.py` — 17/17 PASS, run with localhost network access.
- `python3 test_v14_build03.py` — 16/16 PASS.
- `python3 test_build_v121.py` — 19/19 PASS.

Next step:
- Stop and report Build 08. Do not continue to Build 09 until the user explicitly asks.
- Likely next sandbox build: v1.4 Build 09 — Release Hardening, version bump to v1.4.0, scenario/PM workflow regression, AI registry roll-up, i18n parity, and full v1.4 regression sweep.

## v1.4 Build 09 completed in working tree

- `V14_BUILD09_EXECUTION_PLAN.md` — new release-hardening execution plan with Architecture Review, Feature Design Review, Backend Honesty Mapping, scenario contract test plan, and acceptance criteria.
- `app/version.py` — bumped runtime to:
  - `CURRENT_VERSION = "1.4.0"`
  - `CURRENT_BUILD_NAME = "v1.4.0 — Planning Sandbox Release (v1.4 Builds 01-09)"`
  - `LAST_UPDATED = "2026-06-10"`
- `VERSION.md` — added v1.4.0 release section and updated current-version header/status.
- `CHANGELOG.md` — added v1.4.0 rollup and cleared Unreleased.
- `USER_GUIDE.md` — added concise v1.4 Planning Sandbox workflow summary.
- `MASTERPLAN.md` — marked v1.4.0 Planning Sandbox Release shipped and summarized shipped scope.
- `AI_TOOLS_REGISTRY.md` — documented planned/deferred sandbox AI surface:
  - `list_timeline_templates`
  - `apply_timeline_template`
  - `apply_sandbox_to_project`
  - `save_sandbox_as_template`
  - `explain_sandbox_estimate`
  - `propose_sandbox_edits`
  - no `app/ai/tools.py` handler was added.
- `test_v14_build09.py` — new v1.4 release-proof scenario contract runner:
  - checks runtime/docs/registry/test inventory/i18n/migration markers,
  - verifies 24+ module seeds and exactly six system templates,
  - runs all six system templates through create sandbox → edit first node → persist position → save user template → prove no `project_phases` before Apply → Apply → verify phases/apply event/history.
- `test_v13_build10.py` — relaxed runtime-version assertions so the v1.3 release proof remains valid after v1.4.0.

Build 09 intentionally does **not** add:
- migrations,
- sandbox behavior changes,
- UI redesign,
- AI handlers,
- new product features.

Build 09 verification:
- `python3 -m py_compile test_v14_build09.py test_v13_build10.py app/version.py` — PASS.
- `git diff --check` — PASS before final handoff; rerun before commit.
- `python3 test_v14_build09.py` — 15/15 PASS.
- `python3 test_v14_build08.py` — 22/22 PASS, run with localhost network access.
- `python3 test_v14_build07.py` — 26/26 PASS, run with localhost network access.
- `python3 test_v14_build06.py` — 17/17 PASS, run with localhost network access.
- `python3 test_v14_build05.py` — 24/24 PASS, run with localhost network access.
- `python3 test_v14_build04.py` — 26/26 PASS, run with localhost network access.
- `python3 test_v14_build03.py` — 16/16 PASS.
- `python3 test_v14_build02.py` — 9/9 PASS.
- `python3 test_v14_build01.py` — 23/23 PASS.
- `python3 test_v13_build10.py` — 51/51 PASS, run with localhost network access.
- `python3 test_build_v121.py` — 19/19 PASS.

Next step:
- Stop and report Build 09. v1.4.0 is code-complete in the working tree.
- Do not continue into post-v1.4 work until the user explicitly asks.
