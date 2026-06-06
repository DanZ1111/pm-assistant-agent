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
