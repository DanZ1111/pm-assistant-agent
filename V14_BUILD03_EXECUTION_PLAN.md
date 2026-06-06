# v1.4 Build 03 Execution Plan — Static Canvas Renderer

## Status

Execution plan for the third v1.4 Planning Sandbox implementation build.

Predecessor: v1.4 Build 02 — Schedule Engine.

Successor: v1.4 Build 04 — Module Palette + Add/Edit Nodes.

## Purpose

Make the Planning Sandbox visible as a read-only visual workflow canvas.

This build adds a project-scoped sandbox page, creates a draft sandbox from blank or a seeded template, renders nodes/edges through Cytoscape.js, and displays server-computed estimate/warnings from Build 02.

## Scope

In:

1. Add service helpers:
   - `get_active_planning_sandbox`
   - `create_sandbox_blank`
   - `create_sandbox_from_template`
   - `get_sandbox_canvas_payload`
2. Add routes:
   - `GET /projects/{project_id}/sandbox`
   - `POST /projects/{project_id}/sandbox/create`
3. Add `app/templates/planning_sandbox.html`.
4. Add `app/static/js/planning_sandbox.js`.
5. Add CSS for the read-only canvas shell.
6. Add `test_v14_build03.py`.

Out:

- No drag/drop.
- No add/edit/delete node route.
- No edge creation route.
- No Apply route.
- No Save as Template route.
- No mutation of `project_phases`.
- No AI tools.

## Backend Honesty Mapping

| Visible UI | Source Of Truth | Write Path | Derived Rule | Permission | Test |
|---|---|---|---|---|---|
| Template picker | `planning_templates` | seed migration | active templates sorted by sort order | authenticated view; edit permission to create sandbox | route/template test |
| Canvas nodes | `planning_sandbox_nodes` | create-from-template only | Cytoscape node payload from DB rows | authenticated view | payload test |
| Canvas edges | `planning_sandbox_edges` | create-from-template only | Cytoscape edge payload from DB rows | authenticated view | payload test |
| Estimate | `compute_sandbox_schedule` | none | server-authoritative total days | authenticated view | route content test |
| Warnings | `compute_sandbox_schedule` | none | server-authoritative warning codes | authenticated view | route content test |

## Test Plan

Run:

```bash
python3 test_v14_build03.py
python3 test_v14_build02.py
python3 test_v14_build01.py
python3 test_v13_build10.py
```

`test_v14_build03.py` must cover:

- GET route exists
- template picker renders when no draft sandbox exists
- create blank creates draft sandbox with zero nodes and does not touch `project_phases`
- create from system template clones nodes and edges
- existing draft redirects/renders instead of creating duplicate draft
- route uses `compute_sandbox_schedule`
- viewer can view but cannot create
- admin/PM with edit permission can create
- Cytoscape scripts are only referenced by sandbox template
- no add/edit/delete/apply sandbox routes exist yet

