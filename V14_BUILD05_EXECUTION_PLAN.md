# v1.4 Build 05 Execution Plan — Connect Nodes

## Status

Execution plan for the fifth v1.4 Planning Sandbox implementation build.

Predecessor: v1.4 Build 04 — Module Palette + Add/Edit Nodes.

Successor: v1.4 Build 06 — Canvas Interaction Hardening.

Canonical design reference: `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md`
§4 v1.4 sub-build sequence, §5 Backend Honesty Mapping, §6 Q5, §12
validation codes, and `V14_PLANNING_SANDBOX_IMPLEMENTATION_PLAN.md`
§v1.4 Build 05.

## Purpose

Let PM/admin users express dependency logic inside the draft Planning Sandbox
without touching the live project Timeline.

Build 05 makes edges editable. The required path is property-panel dependency
editing: select a node, choose which other nodes it depends on, save, and the
server replaces that node's incoming dependency edges. This is the accessibility
and correctness fallback promised by the design docs. Canvas edge drag handles
remain optional polish and may be deferred if they would increase risk.

## Scope

In:

1. Add service helpers in `app/crud.py`:
   - `create_sandbox_edge`
   - `delete_sandbox_edge`
   - `replace_sandbox_node_dependencies`
   - graph validation helpers for same-sandbox nodes, duplicate edge handling,
     self-dependency rejection, and cycle detection.
2. Add JSON routes in `app/routes/projects.py`:
   - `POST /projects/{project_id}/sandbox/{sandbox_id}/edges`
   - `POST /projects/{project_id}/sandbox/{sandbox_id}/edges/{edge_id}/delete`
   - `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/dependencies`
3. Extend `get_sandbox_canvas_payload(...)` node data with dependency metadata
   needed by the property panel:
   - `depends_on_ids`
   - `dependent_ids`
4. Update `planning_sandbox.html`:
   - Add a "Depends on" multi-select in the node property panel.
   - Add a dependency list / status area near the canvas or panel.
   - Keep viewers read-only; no dependency mutation affordances render.
5. Update `planning_sandbox.js`:
   - Populate the dependency multi-select from current payload nodes.
   - Save dependency edits through fetch + JSON payload replacement.
   - Allow direct edge deletion by selecting/clicking an edge or from a small
     dependency list if simple and testable.
   - Surface server errors such as `circular_dependency` and `self_dependency`
     through the existing node message area.
6. Update CSS for dependency controls, edge selected state, and error messages.
7. Add EN/zh i18n keys with exact parity.
8. Add `test_v14_build05.py`.

Out:

- No Apply route.
- No Save as Template route.
- No timeline / `project_phases` mutation.
- No migrations.
- No AI tools.
- No automatic layout/tidy behavior.
- No dependency types beyond `finish_to_start`.
- No client-only schedule math.

## Architecture Review

1. Problem solved: PMs need to define sequence logic before a sandbox plan can
   become a trustworthy launch estimate.
2. Tables affected: `planning_sandbox_edges` mutates; `planning_sandbox_nodes`
   is read for validation; `project_phases` is untouched.
3. Real column vs notes: dependencies are already modeled as edge rows because
   schedule math and cycle detection need a queryable graph.
4. Service layer: all edge mutations live in `crud.py`; routes only handle auth,
   project lookup, form parsing, and JSON response.
5. Change log: no `write_change()` yet because sandbox edits are draft-only and
   become auditable at Apply in Build 07.
6. Rollback: remove Build 05 routes/helpers/template/JS/CSS/test changes; schema
   remains unchanged.

## Backend Honesty Mapping

| Visible UI | Source Of Truth | Write Path | Derived Rule | Permission | Test |
|---|---|---|---|---|---|
| Canvas edge arrow | `planning_sandbox_edges` | `create_sandbox_edge` or `replace_sandbox_node_dependencies` | `get_sandbox_canvas_payload` emits Cytoscape edge; schedule recomputes from DB | all can view; `can_edit_project` + draft sandbox to edit | service + browser test |
| Depends-on multi-select | incoming `planning_sandbox_edges.to_node_id == selected node` | `replace_sandbox_node_dependencies` | selected options mirror `depends_on_ids`; cannot include self | `can_edit_project` + draft sandbox | route + JS source test |
| Edge deletion | `planning_sandbox_edges.id` | `delete_sandbox_edge` | removing edge recomputes schedule | `can_edit_project` + draft sandbox | service + route test |
| Cycle warning/error | server-side graph validation | edge/dependency POST returns `{ok:false,error:'circular_dependency'}` | no cyclic edge is committed | `can_edit_project` + draft sandbox | cycle rejection test |
| Schedule summary after dependency edit | `compute_sandbox_schedule` | none directly | recomputed after every edge mutation | all authenticated to view | graph estimate test |

## Locked Implementation Decisions

1. **Property-panel dependency editing must ship.** Drag handles may be deferred,
   but dependency editing cannot depend on drag-only UI.
2. **Server is authoritative.** Client-side checks are convenience only; the
   service rejects self-dependency, cross-sandbox edges, duplicate edges, and
   cycles.
3. **Replace incoming dependencies for a node.** The property panel submits the
   complete selected prerequisite list for the selected node. The service diffs
   existing incoming edges and creates/deletes rows as needed.
4. **Duplicate edge is idempotent.** Creating an already-existing edge returns
   the existing row rather than failing noisily.
5. **Multiple parents are valid.** A node may depend on more than one upstream
   node, and the schedule waits for the longest upstream branch.
6. **No auto-layout on edge changes.** Adding/deleting a dependency does not move
   nodes; Build 06 owns tidy/layout hardening.
7. **No live Timeline mutation.** No Build 05 route touches `project_phases`,
   `phase_plan_changes`, project status, launch date, or Timeline History.
8. **Viewer affordances hidden.** Viewers can see edges and dependency labels
   but cannot see dependency Save/Delete controls.

## UX Behavior

- Select a node to open Node Properties.
- The panel shows a "Depends on" multi-select listing every other node in the
  draft sandbox.
- Saving dependencies replaces the selected node's prerequisite edges and
  refreshes canvas, dependency selections, warning strip, and schedule summary
  from the returned server payload.
- Attempting a cycle shows a clear inline error and leaves the previous graph
  unchanged.
- Existing edges render as arrows on the canvas.
- Edge deletion is available through a small dependency list in the panel or
  direct edge interaction if implementation stays simple.

## i18n Lock

Build 05 should add exactly these 8 keys unless implementation amends this plan
before coding:

| Key | EN intent | ZH intent |
|---|---|---|
| `sandbox.field_depends_on` | Depends on | 依赖于 |
| `sandbox.depends_on_hint` | Choose prerequisite nodes for this step. | 选择此步骤的前置节点。 |
| `sandbox.no_dependency_options` | Add another node before creating dependencies. | 先添加另一个节点，再创建依赖。 |
| `sandbox.save_dependencies` | Save dependencies | 保存依赖 |
| `sandbox.dependencies_saved` | Dependencies saved. | 依赖已保存。 |
| `sandbox.dependency_error` | Could not update dependencies. | 无法更新依赖。 |
| `sandbox.cycle_error` | That dependency would create a cycle. | 这个依赖会形成循环。 |
| `sandbox.delete_edge` | Delete dependency | 删除依赖 |

Current post-Build-04 count is 758 keys; Build 05 should reach 766/766.

## Test Plan

Run:

```bash
python3 test_v14_build05.py
python3 test_v14_build04.py
python3 test_v14_build03.py
python3 test_v14_build02.py
python3 test_build_v121.py
```

`test_v14_build05.py` must cover:

- Plan file exists and locks no Apply / no migration / no `project_phases` mutation.
- Service helpers create edge, delete edge, and replace node dependencies.
- Duplicate create is idempotent.
- Self-dependency is rejected.
- Missing/cross-project/cross-sandbox nodes are rejected.
- Cycle creation is rejected and the original graph remains unchanged.
- Multiple parents are accepted.
- Schedule estimate updates after dependency changes.
- JSON routes return `{ok, sandbox_payload}`.
- Viewer/non-owner cannot mutate dependencies.
- Template renders dependency multi-select and hides mutation affordances for viewers.
- JS populates dependency options from payload and posts dependency changes through fetch.
- i18n parity is exactly 766/766 if the 8-key list remains unchanged.
- Browser smoke verifies dependency controls render and mobile has no horizontal overflow.

## Screenshots

Build 05 should generate:

- `test_artifacts/v14_build05_sandbox_dependencies_desktop.png`
- `test_artifacts/v14_build05_sandbox_dependencies_mobile.png`

## Acceptance Criteria

- PM/admin can create and remove dependency edges inside a draft sandbox.
- Property-panel dependency editing works without drag handles.
- Cycles are rejected server-side before commit.
- Multiple parents are accepted and schedule math reflects the dependency graph.
- Viewers can see dependency arrows but cannot mutate them.
- No live project timeline data changes.
- All new labels preserve exact i18n parity.
