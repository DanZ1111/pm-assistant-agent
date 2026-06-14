# v1.4 Planning Sandbox UI Rescue Plan

Status: Revised plan-only handoff for Claude/Codex review
Target: v1.4 Planning Sandbox usability rescue  
Do not implement from this file until the plan is explicitly approved.

## 1. Why This Plan Exists

The Planning Sandbox has real backend and interaction machinery: graph tables,
node and edge routes, template creation, drag/drop, node editing, dependency
editing, Tidy, Apply, and QA coverage. However, the current UI is not usable
for PM planning.

User-observed problems:

- The page feels visually broken and hard to understand.
- Connections between nodes are hard to see or appear missing.
- The canvas keeps zooming/fitting after edits, causing lost spatial context.
- Selecting a node opens editing mode, but there is no obvious way back to
  adding/selecting modules.
- Save as Template, adding modules, node editing, warnings, and Apply controls
  are mixed into the same area.
- Warnings and Apply-blocked states take too much space and block the planning
  view.
- Default node cards are too large for the expected workflow length.
- The module library is awkward: one long module per row, no useful search or
  category workflow, and some seeded modules are too granular for normal PM use.
- Examples such as Blade Steel Validation feel like engineering/factory checks,
  not default PM milestone modules.

This is a usability rescue, not a new product feature. Existing schema, routes,
and service functions should be reused. No migration is planned.

## 2. Current Diagnosis

Confirmed from code review:

- `app/static/js/planning_sandbox.js` initializes Cytoscape with `fit: true`
  and destroys/recreates the graph on payload refresh. Removing `fit: true`
  alone is not enough; refresh must update the existing graph in place.
- The right panel has only two hidden/shown states: module palette and property
  panel. Selecting a node hides the palette, and there is no first-class
  visible "Back to Modules" control.
- `app/templates/planning_sandbox.html` stacks Save Template, module library,
  node properties, dependency controls, warnings, and Apply controls in ways
  that blur separate PM jobs.
- Nodes are styled around duration-height visual language. The latest product
  preference is compact, stable planning blocks because the chain length is
  usually similar.
- Edges exist in the model and Cytoscape payload, but the visual treatment is
  too subtle for PM confidence.
- Seeded module data includes granular validation rows such as
  `blade_steel_validation` and `handle_material_validation`. These can stay in
  the database, but should not be prominent default PM modules.

Design correction:

- Planning Sandbox should feel like a stable workflow planner, closer to a
  clean milestone chain builder than a freeform Miro graph.
- PMs should always know which job they are doing: choosing modules, editing a
  selected node, reviewing issues, choosing a template, saving a template, or
  applying to timeline.

## 3. Done Bar

Do not mark this rescue complete because screenshots look better.

The done bar is:

> An unfamiliar PM can enter the sandbox, choose a template, add modules, edit
> a node, recover back to modules, inspect warnings, and understand apply
> status without getting lost or having the canvas jump.

Measurable requirements:

- Canvas zoom/pan are preserved after node save/edit/delete unless the user
  explicitly clicks Fit, Tidy, or Reset View.
- Right panel can always return from Selected Node mode to Modules mode.
- Warnings render as human-readable PM copy, not raw codes.
- Apply disabled/blocked state is visible but does not cover the canvas.
- Existing sandbox discoverability from project detail remains green.

## 4. Rescue Build Sequence

Do not implement this as one large build. Use the four builds below.

### SB-Rescue-01 — Information Architecture Reset

Goal: separate the mixed UI jobs into stable zones without changing canvas
internals yet.

Required changes:

- Create four visible zones: Header, Action Bar, Canvas, Right Work Panel.
- Move Template chooser and Save as Template out of the right panel.
- Add right panel tabs: `Modules`, `Selected Node`, `Issues`.
- Add a visible `Back to Modules` recovery control.
- Move warnings out of the giant canvas-blocking strips/cards and into action
  bar chips plus the Issues tab.
- Keep the project Timeline entry point and `/projects/{id}/sandbox` page.

Wireframe:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Header                                                                      │
│ ← Project    Planning Sandbox · 自由女神刀          63 days · 8 steps        │
├─────────────────────────────────────────────────────────────────────────────┤
│ Action Bar                                                                  │
│ [Template ▾] [Save Draft] [Save as Template]      [Warnings: 2] [Apply]      │
├───────────────────────────────────────────────┬─────────────────────────────┤
│ Canvas                                        │ Right Work Panel             │
│                                               │ [Modules] [Selected] [Issues]│
│ Concept ─▶ Design ─▶ Prototype ─▶ Production  │                             │
│             └────────▶ Quotation ───────────▶ │ Search modules               │
│                                               │ Product / Sample / Commercial│
│                                               │ Module cards                 │
└───────────────────────────────────────────────┴─────────────────────────────┘
```

Zone rules:

- Header: navigation and project identity only.
- Action Bar: template/save/apply workflow only.
- Canvas: workflow nodes and dependency edges only.
- Right Work Panel: module adding, selected-node editing, or issue review.
- No inline Save Template card inside the module library.
- No giant warnings above the canvas after the user has entered the workspace.

Template chooser behavior:

- Open from action bar only.
- Use a compact dropdown/modal listing system and user templates.
- If no sandbox exists, keep the clean start screen with templates and
  Start Blank.

Save-template behavior:

- Open from action bar only.
- Use a modal/form; do not occupy the module panel.

Template chooser wireframe:

```text
Choose Template
┌ Standard Folding Knife       10 steps · balanced workflow      [Use] ┐
┌ Simple OEM Knife              6 steps · fast factory workflow  [Use] ┐
┌ Gift Set / Combo Pack         9 steps · packaging branch       [Use] ┐

[Start blank instead]
```

Save-template modal wireframe:

```text
Save Workflow as Template

Template name        [自由女神刀 standard sample workflow]
Description          [optional text...]

[Cancel] [Save Template]
```

Acceptance for SB-Rescue-01:

- PM sees Header, Action Bar, Canvas, Right Work Panel as separate zones.
- Right panel tabs are visible.
- Selecting a node opens Selected Node tab.
- Back to Modules restores the module library.
- Save as Template is no longer inline above the module library.
- Warning/action summary no longer blocks the canvas.

### SB-Rescue-02 — Canvas Stability

Goal: stop canvas jumping and make the graph visually legible.

Required changes:

- Stop destroy-and-rebuild refresh behavior.
- Replace `renderCanvas()` refresh with in-place Cytoscape element diffing:
  - add new nodes/edges with `cy.add`
  - remove deleted nodes/edges with `cy.remove`
  - update existing element data with `element.data(...)`
  - update positions only for changed nodes or explicit Tidy/Fit flows
- Preserve zoom, pan, and selected node across save/edit/delete.
- Disable wheel zoom by default.
- Add explicit controls: `Fit`, `Tidy`, `Reset View`.
- Fit only on first load, explicit Fit, explicit Tidy, or Reset View.
- Use fixed compact nodes rather than duration-height nodes.
- Make arrows thicker and higher contrast.
- Default Tidy layout should be left-to-right with simple branch spacing.

Canvas wireframe:

```text
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Concept     │ ──▶ │ Design      │ ──▶ │ Prototype   │
│ 3d · PM     │     │ 10d · Des.  │     │ 21d · Fac.  │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                                │
                         ┌─────────────┐        ▼
                         │ Quotation   │ ──▶ ┌─────────────┐
                         │ 5d · Fac.   │     │ Production  │
                         └─────────────┘     │ 30d · Fac.  │
                                             └─────────────┘
```

Acceptance for SB-Rescue-02:

- Saving a node does not change Cytoscape zoom or pan.
- Deleting a node does not change Cytoscape zoom or pan except where necessary
  to remove the selected element.
- Selected node remains selected after save if it still exists.
- Edges are visually obvious in screenshots.
- Mouse wheel over the canvas does not unexpectedly zoom the graph.
- Fit, Tidy, and Reset View are the only normal ways to change global view.

### SB-Rescue-03 — PM-Friendly Module Library

Goal: make the library useful to PMs without changing schema.

Decision: no migration in this rescue. Use a documented hardcoded default
allowlist/denylist or Advanced-filter mechanism in route/template/JS.

Default PM milestone modules:

- Product Concept
- Design Direction
- Engineering Review
- Rendering / Visual Direction
- Prototype Sample
- Sample Review
- Factory Feedback
- Quotation
- Cost Review
- Packaging
- Pre-production Sample
- Mass Production
- QC / Inspection
- Launch Prep
- Launch

Hide from default view:

- `blade_steel_validation`
- `handle_material_validation`
- similarly granular validation/check rows

Required changes:

- Add module search.
- Add category chips.
- Show compact module cards.
- Show PM milestone modules by default.
- Keep hidden granular modules available only under `Advanced`, or omit them
  from the default palette while preserving rows in the database.

Module card wireframe:

```text
Modules
Search [ sample____________ ]

[All] [Product] [Sample] [Commercial] [Launch] [Advanced]

Sample
┌ Prototype Sample      21d · Factory        [+] ┐
┌ Sample Review          5d · PM             [+] ┐
┌ Factory Feedback       7d · Factory        [+] ┐
```

Acceptance for SB-Rescue-03:

- Default Modules tab does not show Blade Steel Validation or Handle Material
  Validation.
- Search filters visible module cards.
- Category chips filter visible module cards.
- Advanced module filtering is explicitly documented in code or plan comments.
- No migration is added.

### SB-Rescue-04 — Warnings, Apply Polish, and QA

Goal: make status and validation understandable, then prove the whole rescue
with scenario-level QA.

Required warning/error copy map:

- `zero_nodes` -> Add at least one workflow step before applying.
- `missing_title` -> Some steps need a title before applying.
- `invalid_duration` -> Some steps need a duration greater than zero.
- `dangling_edge` -> A dependency points to a step that no longer exists.
- `cross_sandbox_edge` -> A dependency points outside this sandbox.
- `circular_dependency` -> This workflow has a circular dependency.
- `preconditions_failed` -> The current timeline cannot be replaced because
  execution has already started.
- `terminal_not_launch_like` -> The workflow ends before Launch or Production.
  Confirm if intentional.
- `missing_owner` -> Some steps do not have an owner.
- `disconnected_branch` -> Some steps are not connected to the main workflow.

Apply behavior:

- Apply button is disabled when blocked.
- Disabled Apply explains why through nearby text, tooltip, or Issues tab.
- Apply status must be visible without a large card covering the canvas.
- Apply remains explicit and guarded; no automatic timeline mutation.

Required acceptance scenario:

- Add `scenario_contracts/acceptance/sandbox_right_panel_mode_recovery.py`.
- Scenario must verify:
  - PM opens sandbox from project detail.
  - PM can reach Modules tab.
  - PM selects or creates a node and enters Selected Node tab.
  - PM saves a node without canvas refit.
  - PM clicks Back to Modules and returns to module library.
  - PM opens Issues tab.
  - Issues show human-readable warnings, not raw warning codes.

Existing acceptance requirement:

- Existing sandbox discoverability scenario must remain green.

Acceptance for SB-Rescue-04:

- All mapped warning/error codes render with human-readable copy.
- Apply blocked state is understandable and compact.
- `sandbox_right_panel_mode_recovery.py` passes.
- Existing sandbox discoverability acceptance remains green.
- Full QA scenario suite remains green.

## 5. Testing Requirements Across All Rescue Builds

Screenshots:

- Empty sandbox start screen.
- Active sandbox with Modules tab.
- Active sandbox with Selected Node tab.
- Issues tab with warnings.
- Save-template modal.
- Template chooser modal.
- Canvas after dependency creation.

Interaction tests:

- Module search filters cards.
- Add module keeps or returns the right panel to Modules tab.
- Select node switches to Selected Node tab.
- Back to Modules restores module library.
- Save node preserves canvas zoom/pan.
- Delete node returns to Modules tab.
- Save as Template opens modal and does not replace module library.
- Template chooser opens from action bar only.

Regression:

- Existing `test_v14_build*.py` sandbox tests remain green or are updated only
  for intentional UI assertions.
- v1.5 release tests remain green.
- Full QA scenario suite remains green.

## 6. Feature Design Review

1. Real problem: PMs cannot trust or operate the current sandbox UI even though
   backend graph features exist.
2. Repeated use: workflow planning will be repeated for new knife projects and
   template creation.
3. Structured data: this rescue reuses existing sandbox graph tables.
4. Notes fallback: not appropriate; planning graph must remain structured.
5. Intake burden: the rescue reduces cognitive burden by separating modes.
6. AI role: no new AI writes in this rescue.
7. Display payoff: PMs get a clear workflow canvas, recoverable side panel, and
   readable warnings.
8. Migration impact: no migration expected.
9. Minimal schema: no schema change; use a default PM-module filter/denylist.
10. Minimal UI change: visually significant, but scoped to sandbox page and
    project sandbox entry.
11. Deferred: advanced graph editor, resource planning, AI plan generation,
    real-time collaboration, and complex Gantt behavior.

## 7. Assumptions and Locks

- This is a usability rescue, not a new schema/product feature.
- Do not add a migration for module filtering in this rescue.
- Existing backend routes for nodes, edges, templates, tidy, and apply remain.
- Save Draft can remain implicit through existing node/edge writes, but visible
  copy should make the state feel saved.
- Save as Template is secondary and must live in a modal/dropdown flow.
- Apply to Timeline remains explicit and guarded.
- Default PM library shows milestone modules; detailed validation modules are
  hidden from default PM flow.
- Compact stable nodes beat duration-scaled giant nodes.
- The old PRD is useful context, but this plan reflects the latest product
  correction from live UI review.
