# v1.4 Build 06 Execution Plan — Canvas Interaction Hardening

## Status

Execution plan for the sixth v1.4 Planning Sandbox implementation build.

Predecessor: v1.4 Build 05 — Connect Nodes.

Successor: v1.4 Build 07 — Apply Sandbox To Project Plan.

Canonical design reference: `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md`
§4, §6 Q4, §12.2, §14 mobile guidance, and
`V14_PLANNING_SANDBOX_IMPLEMENTATION_PLAN.md` §v1.4 Build 06.

## Purpose

Make the editable sandbox canvas feel robust enough to trust before Build 07
allows applying it to the live project timeline.

Build 06 does not add new product behavior. It hardens existing Build 04/05
interactions with layout, visual duration, clearer warnings/states, and
read-only handling for non-draft sandbox snapshots.

## Scope

In:

1. Add a one-click **Tidy** action:
   - Uses Cytoscape dagre layout when available.
   - Persists the resulting node positions through a server route.
   - Changes `x_position` / `y_position` only.
2. Add service helper in `app/crud.py`:
   - `update_sandbox_node_positions`
3. Add JSON route in `app/routes/projects.py`:
   - `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/positions`
4. Add 4 duration bins to canvas payload and rendering:
   - `S`: 1-7 days
   - `M`: 8-21 days
   - `L`: 22-45 days
   - `XL`: 46+ days
5. Improve warning banner:
   - Hard errors and soft warnings render as chip-like items.
   - Warnings do not block draft saves.
6. Improve empty/loading/error states:
   - Empty canvas copy reflects the current editable state.
   - Canvas gets a loading state during Tidy.
   - Fetch errors surface in the existing inline message area.
7. Enforce read-only applied snapshot behavior:
   - Any sandbox whose `status != "draft"` renders as read-only.
   - Existing service helpers already reject non-draft mutations; this build
     locks the UI affordance and route tests.
8. Add EN/zh i18n keys with exact parity.
9. Add `test_v14_build06.py`.

Out:

- No Apply route.
- No Save as Template route.
- No migration.
- No AI tools.
- No new dependency types.
- No live `project_phases` mutation.
- Explicit lock: no `project_phases` mutation.
- No full scenario contract runner yet; that belongs in v1.4 release hardening
  after Apply exists.

## Architecture Review

1. Problem solved: PMs need the sandbox canvas to stay readable and predictable
   as real workflows grow beyond a few nodes.
2. Tables affected: `planning_sandbox_nodes.x_position/y_position` only for
   Tidy; `project_phases` is untouched.
3. Real column vs notes: positions already exist as structured node columns.
4. Service layer: route delegates bulk position writes to `crud.py`.
5. Change log: no `write_change()` because sandbox edits are draft-only and
   Apply will create the auditable project-level event in Build 07.
6. Rollback: remove Tidy route/helper/template/JS/CSS/test changes; schema
   remains unchanged.

## Backend Honesty Mapping

| Visible UI | Source Of Truth | Write Path | Derived Rule | Permission | Test |
|---|---|---|---|---|---|
| Tidy button | action over current canvas nodes | `update_sandbox_node_positions` | saves client-computed dagre positions only | `can_edit_project` + draft sandbox | route + DB test |
| Duration bin visual | `planning_sandbox_nodes.duration_days` | none directly | server maps duration to S/M/L/XL in payload | all authenticated view | payload + browser test |
| Warning chips | `compute_sandbox_schedule` hard/soft errors | none directly | render current schedule warnings from server payload | all authenticated view | browser/source test |
| Empty/loading/error states | current payload / fetch state | no DB write except successful Tidy | JS toggles states; server remains source after writes | all view; edit-only actions hidden | browser/source test |
| Applied snapshot read-only | `planning_sandboxes.status` | existing non-draft guards | UI `can_edit` is false unless status is draft | all can view; no edit affordances | template + route test |

## Locked Implementation Decisions

1. **Draft editability is stricter than role editability.** `can_edit` for the
   sandbox page means `can_edit_project(user, project) and sandbox.status ==
   "draft"`.
2. **Tidy changes positions only.** It must not change title, duration,
   dependencies, module keys, project fields, or live phases.
3. **Dagre primary, deterministic fallback allowed.** The page loads dagre
   support, but JS may fall back to a deterministic breadthfirst/grid layout if
   the external layout script is unavailable in a test/browser environment.
4. **No auto-layout after edge changes.** Tidy is manual; adding/deleting edges
   preserves PM-controlled node placement.
5. **Warnings are display-only.** Soft warnings do not block node, edge, or
   position saves.
6. **Applied snapshots stay visible.** Non-draft sandboxes render as read-only
   snapshots instead of disappearing.

## UX Behavior

- Toolbar shows **Tidy** for editable draft sandboxes.
- Clicking Tidy runs a top-to-bottom layout, saves all node positions, then
  refreshes from the returned server payload.
- Nodes visually scale by duration bin while retaining stable readable labels.
- Warning strip displays hard/soft warning chips instead of raw comma text.
- Empty canvas copy is intentional and edit-aware.
- Non-draft sandboxes show "Snapshot view" / read-only messaging and hide Add,
  Save, Delete, Dependencies Save, and Tidy affordances.

## i18n Lock

Build 06 should add exactly these 9 keys unless implementation amends this plan
before coding:

| Key | EN intent | ZH intent |
|---|---|---|
| `sandbox.tidy` | Tidy | 整理 |
| `sandbox.tidy_hint` | Auto-arrange this draft canvas. | 自动整理此草稿画布。 |
| `sandbox.tidy_saved` | Canvas tidied. | 画布已整理。 |
| `sandbox.tidy_error` | Could not tidy the canvas. | 无法整理画布。 |
| `sandbox.snapshot_view` | Snapshot view. Editing is disabled. | 快照视图，编辑已禁用。 |
| `sandbox.empty_canvas_editable` | Empty canvas. Add modules from the library to start planning. | 空画布。从模块库添加模块开始规划。 |
| `sandbox.empty_canvas_readonly` | Empty canvas. No workflow has been drafted yet. | 空画布。尚未草拟流程。 |
| `sandbox.warning_hard_label` | Hard error | 硬性错误 |
| `sandbox.warning_soft_label` | Warning | 提醒 |

Current post-Build-05 count is 766 keys; Build 06 should reach 775/775.

## Test Plan

Run:

```bash
python3 test_v14_build06.py
python3 test_v14_build05.py
python3 test_v14_build04.py
python3 test_v14_build03.py
python3 test_build_v121.py
```

`test_v14_build06.py` must cover:

- Plan file exists and locks no Apply / no migration / no `project_phases`
  mutation.
- Tidy route/helper updates positions only.
- Tidy rejects non-draft/applied sandboxes.
- Duration bins are emitted as S/M/L/XL from server payload.
- Warning banner renders hard/soft chip hooks.
- Applied sandbox page hides edit affordances.
- Existing mutation routes reject applied sandboxes.
- Browser smoke proves Tidy button, duration-bin classes, warning chips, and no
  mobile horizontal overflow.
- i18n parity is exactly 775/775 if the 9-key list remains unchanged.

## Screenshots

Build 06 should generate:

- `test_artifacts/v14_build06_sandbox_hardened_desktop.png`
- `test_artifacts/v14_build06_sandbox_hardened_mobile.png`

## Larger Scenario Contract Runner

After v1.4 is complete, Build 09 / release hardening should add a broader PM
scenario contract runner. It should simulate PM workflows across the sandbox:
template creation, module edits, dependency edits, tidy, warnings, Apply, and
resulting Timeline verification. Build 06 should not implement that runner yet
because Apply does not exist until Build 07.

## Acceptance Criteria

- PM/admin can tidy a draft canvas and persist positions.
- Tidy changes positions only.
- Duration bins are visually stable.
- Warning banners look intentional and do not block draft saves.
- Applied/non-draft sandboxes render as read-only snapshots.
- No live project timeline data changes.
- All new labels preserve exact i18n parity.
