# v1.4 Build 04 Execution Plan — Module Palette + Add/Edit Nodes

## Status

Execution plan for the fourth v1.4 Planning Sandbox implementation build.

Predecessor: v1.4 Build 03 — Static Canvas Renderer.

Successor: v1.4 Build 05 — Connect Nodes.

Canonical design reference: `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md`,
especially §4 v1.4 sub-build sequence, §6 Q4/Q5/Q8/Q9, §13 route list,
and §14 mobile guidance. This plan refines Build 04 inside those locks:
Cytoscape remains the canvas library, draft/apply separation remains
non-negotiable, and sandbox edits never mutate the live Timeline.

## Purpose

Make the Planning Sandbox editable inside its own draft graph.

Build 04 turns the read-only canvas into the first usable sandbox editor:
PM/admin users can add modules from the module library, edit node properties,
move nodes, and delete nodes. All edits remain sandbox-only and never mutate
`project_phases`.

## Scope

In:

1. Add service helpers in `app/crud.py`:
   - `create_sandbox_node_from_module`
   - `update_sandbox_node`
   - `update_sandbox_node_position`
   - `delete_sandbox_node`
   - small validation helpers for same-project / draft-sandbox checks as needed
2. Add project routes in `app/routes/projects.py`:
   - `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/add`
   - `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/update`
   - `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/position`
   - `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/delete`
3. Update `app/templates/planning_sandbox.html`:
   - Replace read-only side panel with a module palette when no node is selected.
   - Show module cards grouped by category.
   - Add a node property panel for selected nodes.
   - Show delete affordance inside the property panel.
   - Keep schedule summary and warning strip server-derived.
4. Update `app/static/js/planning_sandbox.js`:
   - Enable Cytoscape node dragging for draft sandboxes.
   - Drag/click module cards to add nodes to the canvas.
   - Select a node to populate the property panel.
   - Submit property edits via fetch and replace the local sandbox payload.
   - Persist node positions after drag stop.
   - Delete selected node via the delete route.
   - Re-render the canvas/side panel from the JSON payload returned after writes.
5. Add CSS for the palette, property panel, drag/add affordances, and selected-node state.
6. Extend `crud.get_sandbox_canvas_payload(...)` to include active planning modules,
   grouped/sortable in the payload, so the sandbox page gets canvas elements,
   schedule, and module-library data in one server round-trip.
7. Add i18n keys for the new palette/property controls with exact EN/zh parity.
   Current post-checkpoint count is 740 keys; Build 04 should add exactly the
   18 keys listed in "i18n Lock" below, for 758/758 unless implementation
   intentionally revises the list and updates this plan before coding.
8. Add `test_v14_build04.py`.

Out:

- No edge creation.
- No edge deletion.
- No dependency editing.
- No cycle detection UI beyond existing schedule-engine hard errors.
- No Apply route.
- No Save as Template route.
- No AI tools.
- No mutation of `project_phases`.
- No migration unless implementation discovers a true schema gap. Migration 008 remains reserved and unused by default.

## Architecture Review

1. Problem solved: PMs need to assemble and revise draft workflow nodes visually before committing any live timeline plan.
2. Tables affected: `planning_sandbox_nodes` mutates; `planning_sandbox_edges` is affected only by delete cascade when deleting a node; `project_phases` is not touched.
3. Real column vs notes: node title/duration/owner/deliverable/exit criteria are already structured sandbox columns, so writes belong there.
4. Service layer: all mutations go through `crud.py`; routes stay permission/HTTP thin.
5. Change log: no `write_change()` yet because sandbox edits are draft-only and not visible in Timeline History until Apply. Build 07 will audit Apply.
6. Rollback: delete the Build 04 routes/helpers/template/JS/CSS/test changes; schema remains unchanged.

## Backend Honesty Mapping

| Visible UI | Source Of Truth | Write Path | Derived Rule | Permission | Test |
|---|---|---|---|---|---|
| Module palette card | `planning_module_library` active rows included in `get_sandbox_canvas_payload(...).modules` | seed/admin-only future | group by `category`, sort by `sort_order/title` | authenticated view; viewer read-only | template/source test |
| Add module to canvas | new `planning_sandbox_nodes` row | `create_sandbox_node_from_module` | copy module defaults; position from drop/click | `can_edit_project` + draft sandbox | route + DB test |
| Node title | `planning_sandbox_nodes.title` | `update_sandbox_node` | direct render in Cytoscape label and property panel | `can_edit_project` + draft sandbox | route + page test |
| Node duration | `planning_sandbox_nodes.duration_days` | `update_sandbox_node` | schedule recomputed by `compute_sandbox_schedule` | `can_edit_project` + draft sandbox | schedule-after-edit test |
| Node owner/deliverable/exit criteria | sandbox node columns | `update_sandbox_node` | direct render in panel/list; warnings recompute | `can_edit_project` + draft sandbox | route + DB test |
| Node position | `x_position/y_position` | `update_sandbox_node_position` | Cytoscape preset layout reads saved coordinates | `can_edit_project` + draft sandbox | route + payload test |
| Delete node | `planning_sandbox_nodes` row deleted | `delete_sandbox_node` | ORM/DB cascade removes attached sandbox edges | `can_edit_project` + draft sandbox | delete + cascade test |
| Schedule summary | `compute_sandbox_schedule` | none directly | recomputed after every edit/reload | authenticated view | post-write page test |

## Locked Implementation Decisions

1. **Draft-only editing:** all Build 04 mutation helpers refuse sandboxes whose `status != "draft"`.
2. **Project permission recheck on every route:** routes load the project and call `can_edit_project(current_user, project)` before calling service helpers.
3. **Route shape includes sandbox_id now:** mutation URLs include both `{project_id}` and `{sandbox_id}` even though v1.4 currently has one draft per project. This prevents a Build 07/08 URL migration once applied/template snapshots become addressable.
4. **Same-project validation:** node routes verify `sandbox_id` belongs to `project_id`, the sandbox is the active draft, and `node_id` belongs to that sandbox.
5. **Duration guard:** `duration_days` must be a positive integer; invalid values return an explicit error and do not write.
6. **Module copy-down:** adding a module copies defaults into a sandbox node. Later module library edits do not retroactively change existing nodes.
7. **One payload source:** `get_sandbox_canvas_payload` returns `elements`, `schedule`, and `modules`; route rendering and fetch responses use the same payload shape.
8. **Fetch + JSON for editable canvas flows:** add/update/position/delete routes return JSON containing `{ok, sandbox_payload}` on success and `{ok:false, error}` on failure. The client re-renders from `sandbox_payload`; no client-only schedule math.
9. **No silent live mutation:** no Build 04 route touches `projects`, `project_phases`, `phase_plan_changes`, or Timeline History.
10. **Position writes are small and idempotent:** drag-stop position persistence updates only `x_position`, `y_position`, and `updated_at`.
11. **Delete is destructive only inside the sandbox draft:** deleting a node removes attached sandbox edges but does not delete modules, templates, phases, files, or history.
12. **Accessible fallback for drag:** module cards also have an Add button, so users can add a module without drag/drop.
13. **Viewer affordances hidden:** viewers see module library context as read-only inventory; Add, Save, Delete, and drag handles/active drag classes do not render or activate for viewers.

## UX Behavior

- On a draft sandbox, the right side panel starts as **Module Library**.
- Each module card shows title, category, default duration, and short description/deliverable hint.
- Clicking **Add** creates a node near the right side of the canvas or at a deterministic fallback position.
- Dragging a module card onto the canvas creates a node at the drop position when feasible.
- Clicking a node switches the side panel to **Node Properties**.
- Saving node properties uses fetch, receives a fresh `sandbox_payload`, and refreshes the canvas and schedule summary without losing the whole page.
- Dragging an existing node persists its position after drag stop.
- Deleting a node asks for browser confirmation, deletes the node, removes attached draft edges, and refreshes from the returned payload.
- Viewers can see the canvas and module library context but cannot add/edit/delete; mutation buttons are hidden rather than shown disabled.

## i18n Lock

Build 04 should add exactly these 18 keys unless the implementation plan is
amended before coding:

| Key | EN intent | ZH intent |
|---|---|---|
| `sandbox.module_library` | Module Library | 模块库 |
| `sandbox.module_library_hint` | Choose a workflow module to add to this draft. | 选择一个流程模块加入此草稿。 |
| `sandbox.drag_to_canvas` | Drag to canvas or use Add. | 可拖到画布，或点击添加。 |
| `sandbox.add_module` | Add | 添加 |
| `sandbox.node_properties` | Node Properties | 节点属性 |
| `sandbox.select_node_hint` | Select a node to edit its properties. | 选择节点以编辑属性。 |
| `sandbox.no_node_selected` | No node selected. | 未选择节点。 |
| `sandbox.field_title` | Title | 标题 |
| `sandbox.field_duration_days` | Duration days | 持续天数 |
| `sandbox.field_owner_role` | Owner role | 负责人角色 |
| `sandbox.field_deliverable` | Deliverable | 交付物 |
| `sandbox.field_exit_criteria` | Exit criteria | 完成标准 |
| `sandbox.save_node` | Save node | 保存节点 |
| `sandbox.delete_node` | Delete node | 删除节点 |
| `sandbox.delete_node_confirm` | Delete this sandbox node? | 删除这个沙盒节点？ |
| `sandbox.viewer_read_only` | View only. Editing is available to PM/admin users. | 仅查看。PM / 管理员可编辑。 |
| `sandbox.node_saved` | Node saved. | 节点已保存。 |
| `sandbox.node_error` | Could not update the sandbox node. | 无法更新沙盒节点。 |

## Test Plan

Run:

```bash
python3 test_v14_build04.py
python3 test_v14_build03.py
python3 test_v14_build02.py
python3 test_v14_build01.py
python3 test_v13_ui_r4.py
python3 test_build_v121.py
```

`test_v14_build04.py` must cover:

- Plan file exists and locks no Apply / no edge creation / no `project_phases` mutation.
- Service helpers exist and are importable.
- Add module creates a `planning_sandbox_nodes` row with copied defaults.
- Add module refuses inactive/missing module keys.
- Update node changes title/duration/owner/deliverable/exit criteria only.
- Invalid duration is rejected.
- Position route persists `x_position/y_position`.
- Delete node removes the node and attached sandbox edges.
- Viewer/non-owner cannot mutate sandbox nodes.
- Node routes reject wrong-project node IDs.
- Node routes reject wrong-sandbox IDs under the correct project.
- Draft-only guard rejects applied/read-only sandboxes.
- `get_sandbox_canvas_payload` includes active modules in the same payload as elements/schedule.
- Page renders module palette and property panel markers.
- Viewer page does not render Add/Save/Delete mutation affordances.
- JS contains drag/add/select/position/delete hooks.
- JS update path uses fetch + JSON payload replacement for property edits and position writes.
- Existing sandbox route still uses Cytoscape only on sandbox page.
- i18n parity is exactly 758/758 if the 18-key list above remains unchanged.
- `project_phases` count/content is unchanged after all sandbox edits.
- Browser smoke: desktop canvas can show palette + selected node; mobile page has no horizontal document overflow.

## Screenshots

Build 04 should generate:

- `test_artifacts/v14_build04_sandbox_desktop.png`
- `test_artifacts/v14_build04_sandbox_mobile.png`

Screenshots are verification artifacts only unless the user explicitly asks to commit them.

## Acceptance Criteria

- PM/admin can add, edit, move, and delete sandbox nodes.
- Viewer can inspect but not mutate, and viewer mutation affordances are hidden.
- Schedule summary refreshes from server-derived data after node changes.
- No edge editing or Apply affordance ships in this build.
- No live project timeline data changes.
- All new labels preserve exact i18n parity.
- Build 01-03 and v1.3 UI rescue regressions remain green.
