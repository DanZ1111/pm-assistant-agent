# v1.4 Planning Sandbox UI Rescue Plan

Status: Plan-only handoff for Claude/Codex review  
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
- The canvas keeps zooming/fitting after edits, which makes the user lose
  spatial context.
- Selecting a node switches the right side to edit mode, but there is no
  obvious way back to adding/selecting modules.
- Template saving, module adding, node editing, warnings, and Apply controls
  are mixed into the same right-side area.
- Warnings and Apply-blocked states take too much space and block the planning
  view.
- Default nodes are too large for the expected project-chain length.
- The module library is awkward: one long module per row, no useful search or
  category workflow, and some seeded modules are too granular for normal PM use.
- Examples such as Blade Steel Validation feel like engineering/factory checks,
  not default PM milestone modules.

This is a usability rescue, not a new product feature. Existing schema and
services should be reused unless a concrete blocker is found.

## 2. Current Diagnosis

Confirmed from code review:

- `app/static/js/planning_sandbox.js` initializes Cytoscape with `fit: true`
  and destroys/recreates the graph on payload refresh, so save/edit/delete
  flows can re-fit the canvas and feel like random zooming.
- The right panel has only two hidden/shown states: module palette and property
  panel. Selecting a node hides the palette, and there is no first-class
  visible "Back to Modules" control.
- `app/templates/planning_sandbox.html` places Save Template, module library,
  node properties, dependency controls, warnings, and Apply controls in a way
  that blurs separate jobs.
- Nodes are styled around large duration-height visual language. The latest
  user preference is the opposite: compact, stable planning blocks because the
  chain length is usually similar.
- Edges exist in the model and Cytoscape payload, but the visual treatment is
  too subtle for PM confidence.
- Seeded module data includes granular validation rows such as
  `blade_steel_validation` and `handle_material_validation`. These can stay in
  the database, but should not be prominent default PM modules.

Design correction:

- Planning Sandbox should feel like a stable workflow planner, closer to a
  clean milestone chain builder than a freeform Miro graph.
- PMs should always know which mode they are in: choosing modules, editing a
  selected node, reviewing issues, choosing a template, saving a template, or
  applying to timeline.

## 3. Target Workspace IA

Use both entry points:

- Project Timeline keeps a visible Planning Sandbox entry.
- `/projects/{id}/sandbox` remains the focused full planner page.

Separate the page into four permanent zones:

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
- Right Work Panel: either add modules, edit selected node, or inspect issues.
- No inline Save Template card in the module library.
- No giant warnings above the canvas after the user has entered the workspace.

## 4. Concrete UI Changes

### SB-R1 — Rebuild Page Zones

- Add a top action bar below the header.
- Move template selection, Save Draft status, Save as Template, warning count,
  and Apply into that action bar.
- Keep the canvas and right work panel as the two main workspace columns.
- Make canvas primary: it should receive most horizontal space.
- The right panel is a workbench, not a mixed bag of all sandbox controls.

### SB-R2 — Untangle Template Actions

Move template actions out of the right panel.

- `Template` opens a compact dropdown/modal to choose system/user templates.
- `Save as Template` opens a modal.
- Template actions never appear mixed with module cards or node properties.
- If no sandbox exists, keep a clean start screen with template cards and
  "Start blank."

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

### SB-R3 — Right Panel Becomes Mode-Based

Right panel tabs:

```text
[Modules] [Selected Node] [Issues]
```

Modules tab:

- Search box.
- Category chips.
- Compact module cards.
- Add button per module.

Selected Node tab:

- Opens when a node is clicked.
- Has an explicit `Back to Modules` button.
- Edits only the selected node.
- Shows dependencies in plain language.
- After saving node edits, stay on the node and do not re-fit canvas.
- After deleting a node, return to Modules tab.

Selected Node wireframe:

```text
Selected Node                         [Back to Modules]

Prototype Sample
Duration        [21]
Owner           [Factory ▾]
Deliverable     [Physical prototype sample...]

Depends on
✓ Design Direction        [remove]
✓ Engineering Review      [remove]
[+ Add dependency]

[Save node] [Delete node]
```

Issues tab:

- Shows warnings/errors in PM-friendly language.
- Does not cover the canvas.

### SB-R4 — Stable Linear Canvas Behavior

Optimize for a calm linear workflow planner.

- Disable mouse-wheel zoom by default.
- Keep panning available only when needed.
- Do not call Cytoscape `fit` after every edit/save/delete.
- Fit only on first load, explicit Fit, Tidy, or Reset view.
- Add explicit controls: `Fit`, `Tidy`, `Reset view`.
- Use compact fixed-size nodes, roughly `180x72`.
- Duration/owner/category appear as badges inside the node.
- Edges should be thick, high-contrast arrows.
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

### SB-R5 — PM-Friendly Module Library

Default module library should prioritize PM milestones:

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

Hide granular checks from default PM view:

- Blade Steel Validation
- Handle Material Validation
- Similar narrow validation tasks

Implementation default:

- Do not delete old module rows.
- Show PM milestone modules by default.
- Keep detailed modules available only under an `Advanced` filter if needed.

Module card wireframe:

```text
Modules
Search [ sample____________ ]

[All] [Product] [Sample] [Commercial] [Launch]

Sample
┌ Prototype Sample      21d · Factory        [+] ┐
┌ Sample Review          5d · PM             [+] ┐
┌ Factory Feedback       7d · Factory        [+] ┐
```

### SB-R6 — Warning and Apply Polish

Warnings should guide, not dominate.

- Replace giant warning blocks with action-bar chips.
- Issues tab lists warning/error details.
- Apply button is disabled when blocked and explains why.
- Convert raw codes into PM-friendly copy.

Examples:

- `zero_nodes` → "Add at least one workflow step before applying."
- `terminal_not_launch_like` → "The workflow ends before Launch or
  Production. Confirm if intentional."
- `missing_owner` → "Some steps do not have an owner."
- `disconnected_branch` → "Some steps are not connected to the main workflow."

## 5. Implementation Sequence

Do not batch this into one giant change.

1. **SB-R1 Page IA**
   - Move top-level controls into a proper header/action bar.
   - Create persistent right-panel tabs.
   - No canvas behavior changes yet.

2. **SB-R2 Canvas Stability**
   - Stop automatic re-fit on edits.
   - Add explicit Fit/Tidy/Reset controls.
   - Compact nodes and strengthen edges.

3. **SB-R3 Module Library**
   - Add search/category chips.
   - Filter default PM milestone modules.
   - Keep Advanced modules hidden from default view.

4. **SB-R4 Node Editor and Dependencies**
   - Add Back to Modules.
   - Replace dependency multi-select with a clearer list/check workflow.
   - Keep existing backend routes.

5. **SB-R5 Template and Warning Modals**
   - Move Save as Template into modal.
   - Move template chooser into modal/dropdown.
   - Move warning details into Issues tab.

## 6. Test Plan

Playwright screenshots:

- Empty sandbox start screen.
- Active sandbox with Modules tab.
- Active sandbox with Selected Node tab.
- Issues tab with warnings.
- Save-template modal.
- Template chooser modal.

Interaction tests:

- Module search filters cards.
- Add module keeps the right panel on Modules tab.
- Select node switches to Selected Node tab.
- Back to Modules restores the module library.
- Save node does not change canvas zoom.
- Delete node returns to Modules tab.
- Save as Template opens modal and does not replace module library.
- Template chooser opens from action bar only.

Canvas tests:

- Edges are visible after dependency creation.
- Tidy keeps all nodes visible.
- Edit/save does not trigger automatic fit.

Regression:

- Existing v1.4 sandbox tests stay green.
- v1.5 release tests stay green.
- Full QA scenario suite stays green.

## 7. Feature Design Review

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
9. Minimal schema: no schema change unless implementation finds a hard blocker.
10. Minimal UI change: visually significant, but scoped to sandbox page and
    project sandbox entry.
11. Deferred: advanced graph editor, resource planning, AI plan generation,
    real-time collaboration, and complex Gantt behavior.

## 8. Assumptions and Locks

- This is a usability rescue, not a new schema/product feature.
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
