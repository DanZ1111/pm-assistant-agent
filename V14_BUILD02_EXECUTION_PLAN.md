# v1.4 Build 02 Execution Plan — Planning Sandbox Schedule Engine

## Status

Execution plan for the second v1.4 Planning Sandbox implementation build.

Predecessor: v1.4 Build 01 — Schema + Module Library.

Successor: v1.4 Build 03 — Static Canvas Renderer.

## Purpose

Make the Planning Sandbox graph computationally honest before any canvas UI consumes it.

This build adds a pure Python schedule/validation engine over `planning_sandbox_nodes` and `planning_sandbox_edges`. It does not add routes, UI, Apply behavior, or project phase mutation.

## Scope

In:

1. Add `crud.compute_sandbox_schedule(db, sandbox_id, require_nodes=False)`.
2. Return deterministic schedule shape:
   - `hard_errors`
   - `soft_warnings`
   - `nodes`
   - `topological_node_ids`
   - `terminal_node_ids`
   - `total_days`
   - `connected_component_count`
3. Hard validation:
   - `sandbox_not_found`
   - `zero_nodes` when `require_nodes=True`
   - `missing_title`
   - `invalid_duration`
   - `dangling_edge`
   - `cross_sandbox_edge`
   - `circular_dependency`
4. Soft warnings:
   - `disconnected_branch`
   - `very_long_duration`
   - `terminal_not_launch_like`
   - `packaging_before_design`
   - `production_before_sample`
   - `missing_owner`
   - `missing_deliverable`
   - `missing_exit_criteria`
5. Add `test_v14_build02.py`.

Out:

- No canvas route.
- No JS.
- No Cytoscape dependency.
- No Apply route.
- No `planning_apply_events`.
- No mutation of `project_phases`.

## Backend Honesty Mapping

| Visible Future UI | Source Of Truth | Write Path | Derived Rule | Permission | Test |
|---|---|---|---|---|---|
| Schedule estimate | `compute_sandbox_schedule` | none | topological earliest-start propagation | future sandbox read permission | fixture tests |
| Warning chips | `compute_sandbox_schedule.soft_warnings` | none | deterministic graph/material phase checks | future sandbox read permission | fixture tests |
| Apply disabled state | `hard_errors` | none | non-empty valid DAG required | future `can_edit_project` | `require_nodes=True` tests |

## Test Plan

Run:

```bash
python3 test_v14_build02.py
python3 test_v14_build01.py
python3 test_v13_build10.py
```

`test_v14_build02.py` must cover:

- linear graph estimate
- parallel fork/join estimate
- multi-parent blocking path estimate
- disconnected branches warning and max-branch estimate
- cycle detection
- dangling edge detection
- cross-sandbox edge detection
- invalid duration detection
- missing title detection
- zero-node validation only when `require_nodes=True`
- semantic warnings for packaging before design, production before sample approval, terminal not launch-like, missing owner/deliverable/exit criteria, very long duration
- no `project_phases` mutation

