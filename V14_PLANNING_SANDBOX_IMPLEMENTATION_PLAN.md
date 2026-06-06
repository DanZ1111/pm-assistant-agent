# v1.4 Planning Sandbox Implementation Plan

## Status

Plan-only document for Claude Code / ChatGPT evaluation.

No code, schema, route, test, or migration changes are included in this commit.

## Purpose

v1.4 turns the Build 09 Planning Sandbox design into a real PM planning surface:

- PMs build a simulated workflow plan before committing it to the live project timeline.
- The sandbox is a visual graph of modules, nodes, and dependencies.
- Sandbox edits never mutate live execution data.
- Applying a sandbox is explicit, audited, permission-checked, and refused when it would overwrite active execution.

This plan treats the current v1.3 Project Detail / Timeline Command Center as stable execution UI. The Sandbox is a planning workspace, not a replacement for Timeline.

## Product Non-Negotiables

1. Sandbox is draft/simulation.
2. Committed project phases remain the execution source of truth.
3. Dragging, editing, deleting, or connecting sandbox nodes must not update `project_phases`.
4. Applying a sandbox requires an explicit user confirmation.
5. Applying a sandbox writes an audit event readable by Timeline History.
6. Applying is refused if the existing phase plan has started execution.
7. Schedule computation is server-authoritative.
8. The visual canvas may be interactive, but it cannot be the source of truth.
9. AI may assist later, but AI cannot silently apply or mutate sandbox/project state.
10. Every implementation build must prove the "sandbox-only until Apply" invariant.

## Locked Product Decisions

| Decision | Locked Answer |
|---|---|
| Build series | v1.4 Sandbox implementation starts after v1.3 release hardening. |
| Sandbox count | One active draft sandbox per project in v1.4. Applied/archived snapshots may remain readable. |
| Start flow | PM can start from Blank Canvas or a system/user template. |
| Canvas orientation | Top-to-bottom workflow. |
| Node duration display | 4 discrete visual height bins: S/M/L/XL. |
| Dependency type | `finish_to_start` only in v1.4. |
| Dependency creation | Drag handles plus property-panel multi-select if feasible; property panel is the fallback that must ship. |
| Disconnected branches | Allowed with warning. |
| Server/client truth | Server computes and validates graph; client mirrors for responsiveness. |
| Apply safety | Refuse Apply if any existing phase has execution evidence. |
| Active-plan versioning | Deferred. No partial overwrite of active execution in v1.4. |
| Critical path | Deferred. |
| Working days/holidays | Deferred; use calendar days. |
| Resource capacity | Deferred. |
| AI-generated plans | Deferred. |

## Architecture Review

1. Problem solved: PMs need to design and compare project execution plans without risking live project data.
2. Affected tables/services: new planning tables, sandbox CRUD helpers, schedule engine, Apply service, project change log.
3. Why structured data: a graph with reusable templates, dependencies, and schedule estimates cannot live safely in notes.
4. Service layer: all mutations must go through `crud.py` service helpers, not direct route writes.
5. Change log: only Apply writes live project audit history; draft edits update sandbox timestamps but do not create noisy project history by default.
6. Rollback: v1.4 migrations add isolated planning tables. If disabled, existing project/timeline behavior continues.

## Data Model

Create the planning graph model in additive migrations.

### `planning_module_library`

Reusable module catalog.

Required fields:

- `id`
- `module_key`
- `title`
- `category`
- `phase_type`
- `default_duration_days`
- `default_owner_role`
- `default_deliverable`
- `default_exit_criteria`
- `description`
- `is_active`
- `created_at`
- `updated_at`

### `planning_sandboxes`

One active planning graph per project.

Required fields:

- `id`
- `project_id`
- `name`
- `status`: `draft`, `applied`, `archived`
- `base_template_id`
- `created_by_user_id`
- `applied_by_user_id`
- `last_computed_total_days`
- `created_at`
- `updated_at`
- `applied_at`

Constraint:

- Only one `draft` sandbox per project in v1.4.

### `planning_sandbox_nodes`

Editable node copies inside a sandbox.

Required fields:

- `id`
- `sandbox_id`
- `module_key`
- `title`
- `category`
- `phase_type`
- `duration_days`
- `owner_role`
- `deliverable`
- `exit_criteria`
- `x_position`
- `y_position`
- `sort_order`
- `created_at`
- `updated_at`

### `planning_sandbox_edges`

Dependency edges inside a sandbox.

Required fields:

- `id`
- `sandbox_id`
- `from_node_id`
- `to_node_id`
- `dependency_type`: initially `finish_to_start`
- `created_at`

Hard rules:

- Both nodes must belong to the same sandbox.
- No circular dependency.
- Deleting a node deletes its incoming/outgoing edges.

### `planning_templates`

Reusable workflow templates.

Required fields:

- `id`
- `template_key`
- `name`
- `description`
- `is_system`
- `created_by_user_id`
- `is_active`
- `created_at`
- `updated_at`

### `planning_template_nodes`

Template node definitions.

Fields mirror sandbox nodes, excluding sandbox-specific timestamps.

### `planning_template_edges`

Template dependency definitions.

Fields mirror sandbox edges.

### `planning_apply_events`

Audit table for Apply operations.

Required fields:

- `id`
- `project_id`
- `sandbox_id`
- `applied_by_user_id`
- `phase_count`
- `total_days`
- `planned_start_date`
- `computed_end_date`
- `updated_project_planned_launch_date`
- `created_at`

Timeline History should read this as a planning event.

## Schedule Engine

Implement pure Python graph computation before wiring Apply.

Inputs:

- nodes: id, duration_days
- edges: from_node_id, to_node_id, dependency_type

Rules:

- Graph must be a DAG.
- Node start day = max upstream end day, or 0 if no upstream.
- Node end day = start day + duration.
- Total estimate = max terminal node end day.
- Multiple parents are supported.
- Disconnected branches are supported with warning.
- Duration must be positive.

Outputs:

- computed node start/end day
- terminal nodes
- total estimated days
- hard validation errors
- soft warnings

Hard errors:

- zero nodes when applying
- circular dependency
- missing title
- duration <= 0
- edge points to missing node
- edge crosses sandbox boundary

Soft warnings:

- disconnected branch
- very long node duration
- terminal node is not launch / production / completion-like
- packaging before design
- production before sample approval
- missing owner
- missing deliverable
- missing exit criteria

## Apply Semantics

Apply is the only operation that mutates live project planning.

Apply modal must show:

- node count
- total estimated days
- planned start date, default today
- computed end date
- whether project planned launch date will be updated
- warning that existing untouched phases will be replaced

Apply is allowed only when:

- user can edit project
- sandbox belongs to project
- sandbox status is `draft`
- sandbox has at least one node
- graph has no hard validation errors
- no existing phase has `actual_start_date`
- no existing phase has `actual_end_date`
- no existing phase is `in_progress`, `completed`, or equivalent active execution status
- no active blocker is attached to existing phases

Apply behavior:

1. Recompute graph server-side.
2. Open DB transaction.
3. Refuse if any Apply precondition fails.
4. Delete only untouched existing project phases.
5. Create new `ProjectPhase` rows from sandbox nodes in topological / computed order.
6. Set planned start/end dates from Apply start date plus computed offsets.
7. Update project planned launch date only if user explicitly selected that option.
8. Mark sandbox as `applied`.
9. Create `planning_apply_events` row.
10. Call `write_change()` with an auditable summary.
11. Commit transaction.

If execution already started, v1.4 must refuse Apply and explain that active-plan versioning is deferred.

## Routes And Service Boundaries

Routes stay thin. Business logic belongs in service helpers.

Expected page routes:

- `GET /projects/{project_id}/sandbox`
- `POST /projects/{project_id}/sandbox/create`
- `POST /projects/{project_id}/sandbox/{sandbox_id}/apply`
- `POST /projects/{project_id}/sandbox/{sandbox_id}/save-template`

Expected interaction endpoints:

- `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes`
- `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/update`
- `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/position`
- `POST /projects/{project_id}/sandbox/{sandbox_id}/nodes/{node_id}/delete`
- `POST /projects/{project_id}/sandbox/{sandbox_id}/edges`
- `POST /projects/{project_id}/sandbox/{sandbox_id}/edges/{edge_id}/delete`

Expected service helpers:

- create sandbox from blank
- create sandbox from template
- list modules
- list templates
- create/update/delete sandbox node
- update node position
- create/delete sandbox edge
- compute sandbox schedule
- validate sandbox for apply
- apply sandbox to project plan
- save sandbox as template

## UI Design Requirements

Sandbox page layout:

- large visual canvas on the left
- module/template library on the right when no node is selected
- node property panel on the right when a node is selected
- top summary bar: estimate, warning count, node count, Apply button
- clear read-only treatment for applied snapshots

Canvas behavior:

- template nodes auto-layout top-to-bottom
- manual node positions persist
- Tidy button may re-run layout
- node height uses duration bins
- dependency edges are visible
- warnings are visible but not alarming unless Apply is blocked

Node panel:

- title
- duration days
- owner role
- deliverable
- exit criteria
- dependency selector
- delete node

Module library:

- searchable/filterable by category
- add by drag or click
- blank state and error state

Mobile:

- canvas can scroll horizontally if necessary
- property panel becomes a drawer or stacked section
- Apply confirmation remains usable on mobile

## v1.4 Build Sequence

### v1.4 Build 01 — Schema + Module Library

Scope:

- Add planning migrations and ORM models.
- Seed module library.
- Seed system templates.
- Add admin/read page for module/template inspection if low risk.

Tests:

- migrations idempotent
- seed data not duplicated
- system templates present
- no existing project/timeline behavior changes

### v1.4 Build 02 — Schedule Engine

Scope:

- Implement pure Python schedule/validation engine.
- No UI dependency.
- No project phase writes.

Tests:

- linear graph
- parallel graph
- multiple parent graph
- disconnected graph warning
- cycle rejection
- missing-node edge rejection
- duration validation
- total days calculation

### v1.4 Build 03 — Static Canvas Renderer

Scope:

- Add sandbox page.
- Create sandbox from blank/template.
- Render read-only graph using seeded/template data.
- Show estimate and warnings from server output.

Tests:

- sandbox from template renders
- sandbox from blank renders empty state
- create sandbox does not mutate `project_phases`
- permissions enforced
- desktop/mobile screenshots

### v1.4 Build 04 — Module Palette + Add/Edit Nodes

Scope:

- Add module library panel.
- Add node from module.
- Edit node fields.
- Persist node position.
- Delete node and its edges.

Tests:

- add/edit/delete node
- node validation
- position persistence
- sandbox-only mutation invariant
- mobile property panel usable

### v1.4 Build 05 — Connect Nodes

Scope:

- Add dependency creation and deletion.
- Add drag-handle edge creation if feasible.
- Property-panel dependency editing must ship even if drag handles are deferred.
- Enforce cycle validation server-side.

Tests:

- create edge
- delete edge
- reject cycle
- reject cross-sandbox edge
- multiple parents accepted
- graph estimate updates after dependency change

### v1.4 Build 06 — Canvas Interaction Hardening

Scope:

- Tidy layout.
- Duration height bins.
- Warning banner.
- Better empty/loading/error states.
- Read-only applied snapshot behavior.

Tests:

- Tidy changes positions only.
- duration bin rendering is stable
- warnings render without blocking draft save
- applied snapshots cannot be edited
- no horizontal layout break on mobile

### v1.4 Build 07 — Apply Sandbox To Project Plan

Scope:

- Apply confirmation modal.
- Apply service.
- Project phase creation.
- Planning apply event.
- Timeline History integration.

Tests:

- apply creates phases with computed planned dates
- apply writes `planning_apply_events`
- apply writes project change log
- apply refuses active execution
- apply refuses invalid graph
- apply updates planned launch only when selected
- sandbox-only invariant holds before Apply

### v1.4 Build 08 — Save Workflow As Template

Scope:

- Save sandbox as reusable template.
- Template ownership/permission rules.
- Template picker includes user templates.

Tests:

- save template
- create sandbox from saved template
- system template cannot be overwritten
- non-owner cannot edit private user template
- admin can manage templates

### v1.4 Build 09 — Release Hardening

Scope:

- Version bump to v1.4.0.
- Changelog/user guide updates.
- Roll-up regression.
- Scenario contract runner for sandbox workflows.
- i18n parity.

Tests:

- all `test_v14_buildNN.py`
- v1.3 release baseline
- sandbox scenario tests
- migration count and seed invariants
- no live project mutation before Apply

## Backend Honesty Mapping Requirement

Before every v1.4 implementation build, update that build's execution plan with a mapping table:

| Visible UI | Source Of Truth | Write Path | Derived Rule | Permission | Test |
|---|---|---|---|---|---|

No Sandbox UI may present fake intelligence. If data is not backed by a real source, label it as placeholder or warning.

## AI Tools Registry Requirement

Because Sandbox creates structured planning data, AI tool coverage must be planned before release.

Minimum deferred AI tools:

- list templates
- explain sandbox estimate
- propose sandbox edits
- apply sandbox only through confirmation

AI implementation is deferred until manual sandbox behavior is stable, but `AI_TOOLS_REGISTRY.md` must document the planned tool surface before v1.4 release.

## Test Strategy

Every build must run:

- current `test_v14_buildNN.py`
- previous v1.4 build test when available
- v1.3 release baseline

Critical assertions:

- sandbox edits do not mutate `project_phases`
- Apply is the only live-plan mutation path
- invalid graphs cannot apply
- active execution cannot be overwritten
- schedule computation is deterministic
- permission checks match project edit permissions
- i18n parity remains exact

Manual verification:

- PM creates sandbox from template.
- PM edits durations and owners.
- PM creates a parallel packaging branch.
- PM triggers a cycle and sees rejection.
- PM applies to untouched project.
- PM is blocked from applying to active project.
- PM saves sandbox as template.

## Out Of Scope For v1.4

- Multiple draft sandboxes per project
- Applying to active execution plans
- Plan version diff/merge
- Working-day calendars
- Holidays
- Critical path highlighting
- Resource capacity
- Factory capacity
- AI-generated complete workflow plans
- Real-time collaborative editing
- Project-scoped templates
- Calendar/iCal/CSV export

## Evaluation Notes For Claude Code

This plan intentionally differs from the original Build 09 "persist on project" direction.

It agrees with the amended Build 09 PRD response on the important product lock:

- visual canvas
- draft/apply separation
- server-authoritative graph logic
- explicit Apply
- no live project mutation before Apply

The main implementation bias here is conservative:

- ship graph correctness before fancy interaction
- make property-panel dependency editing the required path
- allow drag-handle edge creation only if it does not threaten correctness
- refuse active-plan Apply in v1.4 instead of inventing partial overwrite logic

