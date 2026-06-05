# v1.3 Build 09 — Planning Sandbox Design (design-only)

> **This document is a design lock, not an implementation.** Build 09 ships ZERO code, ZERO schema, ZERO routes, ZERO UI. The Planning Sandbox is a future v1.4+ feature; Build 09's purpose is to capture the locked design now so the v1.4 implementation team has a single canonical reference.

## Status

Design-only build per `V13_MASTERPLAN.md` §"Non-Negotiable Product Decisions" → *"Planning Sandbox is design-only in initial v1.3."* User confirmed Interpretation A (2026-06-06): keep Build 09 as design-only; do not enlarge v1.3 mid-stream.

Predecessor: Build 08 shipped at `3ab1dc8` (Timeline Updates / History — derived view).

Successor: Build 10 (v1.3.0 Release Hardening — version bump + release-proof regression).

---

## 1. Purpose of the Planning Sandbox

### Problem

Today PMs create projects from a fixed `PHASE_TEMPLATES` dictionary in `app/crud.py:24` — `"single"` = 8 phases, `"two_round"` and `"three_round"` add prototype iterations. The list, the names, and the per-phase durations are hard-coded. PMs cannot:

- Pick a template that matches the product type (a Gift Set has different phases than a Standard Folding Knife).
- Adjust per-phase durations without manually editing each phase one at a time after creation.
- Express that two phases run in parallel (e.g., Packaging can overlap Sample Dev).
- Express that a phase depends on another (e.g., Mass Production cannot start until Sample Approval).
- See an automatically calculated estimated launch date that responds to changes.
- Save a working timeline as a reusable template for the next similar product.

### Solution shape

The Planning Sandbox is a **what-if editor** for project timelines. It is **not** a Gantt chart, **not** project-management software, **not** a replacement for the existing Timeline Detailed Table. It exists strictly to let PMs:

1. **Bootstrap** a new project from a typed template (e.g., "Standard Folding Knife → 12 phases, ~140 days").
2. **Reshape** the timeline before commitment — adjust durations, mark phases as overlappable, set dependencies — and see the estimated launch date update live.
3. **Re-use** what worked — turn a successful project's timeline into a new template for the next launch.

### What the sandbox is NOT

- Not a runtime execution surface. Once a project is created, the existing Timeline Command Center (Build 06–08) is where PMs actually push it forward. The sandbox is a planning-time surface.
- Not a critical-path / PERT engine. Estimated launch date uses honest dependency-aware summation, not statistical analysis.
- Not a resource-leveling tool. We do not model "alice can only work on one phase at a time."
- Not a portfolio view. Single-project scope.
- Not a calendar export. iCal / Google Calendar integration is explicitly out.

---

## 2. The 6 template types

Locked taxonomy. New template types added via v1.4+ Sandbox UI's "Save current as template," not via code edit.

| # | Template name | Typical use | Approximate phase count | Approximate duration | Notable structure |
|---|---|---|---|---|---|
| 1 | **Simple OEM Knife** | White-label OEM order, no in-house design work | 6 | ~75 days | No design phase; starts at Engineering Review. |
| 2 | **Standard Folding Knife** | Default for most in-house folding knives | 12 | ~140 days | Two prototype rounds; sample → mass production handoff. Mirrors today's `"two_round"` PHASE_TEMPLATES. |
| 3 | **New Mechanism Knife** | First-of-kind locking/opening mechanism | 14 | ~190 days | Adds Mechanism Engineering + extra Prototype rounds + Patent Review phase. |
| 4 | **Gift Set / Combo Pack** | Multi-knife retail SKU sold as a set | 10 | ~115 days | Adds Combo Composition + Multi-variant Coordination phases; shorter design (parts reuse). |
| 5 | **Packaging-heavy Retail Product** | Retail-channel knife where packaging is critical (window box, blister) | 11 | ~130 days | Adds Packaging Spec + Packaging Sample + Compliance Review phases. |
| 6 | **Amazon Launch Product** | Direct-to-Amazon SKU | 10 | ~110 days | Adds Listing Asset Prep + FBA Inbound phases. Skips Wholesale Distribution. |

### Template metadata (per template)

```yaml
- id: string                      # stable slug, e.g. "standard_folding_knife"
  name: string                    # display name
  description: string             # 1-2 sentence what-this-is-for
  default_duration_days: integer  # summed from module defaults (auto-derived)
  module_count: integer           # auto-derived
  is_system: boolean              # true for the 6 above; false for user-saved
  created_by_user_id: int | null  # for user-saved templates
  modules: [TemplateModule, ...]  # see §3
```

System templates (`is_system=true`) ship seeded; cannot be deleted, can be cloned-and-edited. User templates (`is_system=false`) are PM/admin-owned and freely editable/deletable.

---

## 3. The Module model

A **Module** is the building block of a template. It is what becomes a `ProjectPhase` when the template is applied. Modules carry richer metadata than today's `PHASE_TEMPLATES` tuples.

```yaml
TemplateModule:
  id: string                       # stable slug, e.g. "engineering_review"
  name: string                     # display name, e.g. "Engineering Review"
  phase_type: string               # design / engineering / prototype / review / production / launch / packaging / compliance / asset
  order: integer                   # default position in template (1..N)
  default_duration_days: integer   # used for estimated launch calc
  default_owner_role: string?      # 'engineer' | 'designer' | 'pm' | 'factory' | null
  can_overlap: boolean             # default false; true = can run in parallel with sibling overlap_group
  overlap_group: string?           # phases sharing the same group run in parallel; e.g., "post_sample"
  depends_on: [module_id, ...]     # list of module ids that must complete first
  deliverable: string?             # short human description ("Final 3D files signed off")
  exit_criteria: string?           # what counts as "done"
  description: string?             # longer context for the PM
```

### Concrete module example (Standard Folding Knife — partial)

```yaml
- id: idea_brief
  name: Idea Brief
  phase_type: design
  order: 1
  default_duration_days: 7
  default_owner_role: pm
  depends_on: []
  deliverable: "Approved product brief"
  exit_criteria: "Brief signed off by PM and product manager"

- id: design_round_1
  name: Design Round 1
  phase_type: design
  order: 2
  default_duration_days: 14
  default_owner_role: designer
  depends_on: [idea_brief]
  deliverable: "3D model v1"

- id: engineering_review_1
  name: Engineering Review 1
  phase_type: engineering
  order: 3
  default_duration_days: 5
  default_owner_role: engineer
  depends_on: [design_round_1]
  deliverable: "Engineering feedback document"

# ... 9 more modules through Mass Production + Launch
```

### Why per-module fields matter

- `default_duration_days` → estimated launch math (§5).
- `default_owner_role` → pre-fills `ProjectPhase.owner` when the user has selected a PM/engineer/designer/factory user. Reduces post-creation editing.
- `can_overlap` + `overlap_group` → §4 below.
- `depends_on` → §4 below.
- `deliverable` + `exit_criteria` → render as part of the Detailed Table tooltip and the future "Finish Phase" preflight (Build 07A's confirmation card could surface these).
- `description` → tooltip on hover in the sandbox UI.

---

## 4. Dependency / overlap concepts

### Hard dependencies

A module's `depends_on` list captures phases that **must complete** before this module can start. Examples:
- `mass_production` `depends_on: [sample_approval]` — cannot pour production until samples sign off.
- `launch_prep` `depends_on: [mass_production, packaging_sample]` — wait for both.

Dependencies form a **directed acyclic graph (DAG)**. The Sandbox UI must:
- Reject cycle creation at edit time.
- Render the DAG visually (left-to-right swim lanes, or a flat list with arrows).
- Re-order phases automatically by topological sort.

### Soft overlaps

The `can_overlap` flag (+ `overlap_group` string) lets phases run **in parallel** instead of sequentially. Two phases with the same `overlap_group` start together and finish independently. Example:
- `packaging_design` and `sample_round_2` both have `overlap_group: "post_first_sample"` — they run concurrently after sample_round_1 finishes.

This is **not** dependency reversal. Both phases still respect their own `depends_on`. The overlap flag only says "do not serialize this with its sibling overlap-group phases."

### What we explicitly do NOT model

- **Partial dependencies** (e.g., "this can start when 50% of upstream is done"). Phases are atomic.
- **Lag time** (e.g., "wait 3 days after upstream before starting"). PMs add a phase if they need lag.
- **Resource constraints** (e.g., "alice can only do one phase at a time"). Out of scope.
- **Probabilistic durations** (PERT three-point estimates). Out of scope.

### Dependency display rules

| Phase status | Predecessors all `done` | Has any `not_started` predecessor |
|---|---|---|
| `not_started` | Renders as "Ready" (green outline) | Renders as "Blocked: waiting on {predecessor names}" (gray outline) |
| `in_progress` | Render unchanged | Render warning chip "Started early — predecessor not done" |
| `done` | Render unchanged | Render unchanged |

The Sandbox UI uses these to nudge PMs, but does NOT prevent them from starting a "blocked" phase — execution is the PM's call, not the tool's.

---

## 5. Estimated launch date logic

### The math

Given a project's phases with `planned_start_date`, `planned_end_date`, `depends_on` graph, and `overlap_group` flags:

1. **Build the DAG.** Nodes = phases. Edges = dependencies.
2. **Topological sort.** Get a linear order respecting dependencies.
3. **Compute each phase's earliest start date:**
   - For phases with no `depends_on`: earliest_start = project_start_date.
   - For phases with `depends_on`: earliest_start = max(predecessor.computed_end_date for each predecessor).
4. **Compute each phase's earliest end date:**
   - earliest_end = earliest_start + (phase.planned_end_date − phase.planned_start_date) OR + module.default_duration_days if the phase has no plan dates yet.
5. **Apply overlap groups:** for any group of phases sharing an `overlap_group`, snap all of their earliest_start dates to the max of their individual earliest_starts (they begin together). End dates stay independent.
6. **Estimated launch date = max(earliest_end_date for all phases of `phase_type=launch`)** — usually the single Launch phase.

### What this gives the PM

- A **live number** that updates as they adjust durations or add/remove dependencies.
- A **what-if delta** ("If I shorten Sample Round 2 by 7 days, launch moves from Jul 28 → Jul 21").
- A **risk view** by comparing estimated launch date to `Project.planned_launch_date` (already exists today).

### What this does NOT give

- A guarantee. Estimated launch is honest math on PM-entered durations. If the PM says "Mass Production = 14 days" and reality is 28, the estimate is wrong.
- A critical path highlight. We could add this later; not in initial v1.4 scope.
- Working-days / weekend / holiday handling. Days are calendar days. PMs can pad their durations if they care.

### Recomputation triggers

- Add / remove / reorder a phase.
- Edit a phase's duration.
- Edit a phase's `depends_on`.
- Toggle a phase's `can_overlap` or change its `overlap_group`.
- Finish a phase (re-snaps earliest_start of dependents to actual_end_date).

Estimated launch is **always derived**, never stored. Same discipline as the existing `delay` calculation in `app/crud.py:165`.

---

## 6. Save-current-as-template concept

### Flow

1. PM navigates to an in-flight or completed project where the phase shape worked well.
2. Clicks "Save as Template" (sandbox action).
3. Modal prompts for: template name, description, optional "snapshot dependencies from current state" toggle (default on).
4. System builds a new `Template` row with:
   - One `TemplateModule` per `ProjectPhase`, in current `phase_order`.
   - `default_duration_days` = phase's `actual_end_date − actual_start_date` if both set, else `planned_end_date − planned_start_date`, else fallback to a sensible default.
   - `default_owner_role` = mapped from `phase.owner` if the owner is a known internal user with a role, else null.
   - `depends_on` = derived from the dependency edges the PM set in the sandbox (if the sandbox stored them on the project — see §7 schema decisions).
   - `is_system=false`, `created_by_user_id=current_user.id`.
5. Template appears in the picker for the next New Project flow.

### Permission model

- Anyone with `can_edit_project` on the source project can save it as a template.
- User-saved templates are visible to admin + PM roles (not viewer).
- Only the creator (or admin) can delete a user-saved template.
- System templates can never be deleted.

### What this does NOT do

- No template versioning (v1, v2 of the same template). User edits the existing template or saves under a new name.
- No template sharing across deployments / accounts (v1.4 is still single-tenant per masterplan).
- No template inheritance (no "extends StandardFoldingKnife"). Flat list.

---

## 7. Open schema decisions

These are the **decisions to lock when v1.4 implementation starts**. Each is presented as: question + recommended default + alternatives + rationale.

### Q1. Templates as DB rows vs. static config

**Recommendation:** **DB rows.** New tables `timeline_templates` + `timeline_template_modules`.

| Option | When acceptable | Rejected because |
|---|---|---|
| Static config (Python dict / YAML file) | If the 6 templates never change post-deploy and we don't need user-saved templates | We DO need user-saved templates (§6); a hybrid (system in code, user in DB) doubles the read path. DB rows for both is cleaner. |
| DB rows (recommended) | When templates are mutable + user-creatable | — |

Migration 007 (v1.4) creates the two tables. Seed the 6 system templates in the same migration (idempotent `INSERT WHERE NOT EXISTS`). Module count for the 6 templates: ~70 module rows total.

### Q2. Dependencies — join table vs. JSON column

**Recommendation:** **Join table** `timeline_template_module_dependencies` (and parallel `project_phase_dependencies` for instantiated projects).

| Option | When acceptable | Rejected because |
|---|---|---|
| JSON column on the module (`depends_on JSON` array of module ids) | Simple lookups; SQLite-friendly | Cycle detection and topological sort on a JSON column require app-side parsing every query; cannot index. |
| Join table (recommended) | When we need to query "what depends on X" cheaply | — |

Both source and target reference the module by id; a 2-column index makes both directions fast.

### Q3. Module copy-down vs. shared reference

**Recommendation:** **Copy-down.** When a template is applied to a new project, instantiate `ProjectPhase` rows from `TemplateModule` rows — do NOT keep a foreign key from `ProjectPhase` to `TemplateModule`.

| Option | When acceptable | Rejected because |
|---|---|---|
| Shared FK (`ProjectPhase.template_module_id`) | If we ever want "edit the template, all projects update" | NEVER want that — once a project ships, its phases are historical and must not mutate when someone edits the source template. |
| Copy-down (recommended) | When project phases must be independent of template evolution | — |

ProjectPhase already has all the fields it needs (`phase_name`, `phase_type`, `phase_order`, `planned_*`, `actual_*`, `owner`, `notes`). We add:
- `ProjectPhase.can_overlap` (boolean, nullable, default false) — additive.
- `ProjectPhase.overlap_group` (string, nullable) — additive.
- A new `project_phase_dependencies` join table — additive.

No existing data needs migration; existing phases get `can_overlap=false`, `overlap_group=null`, zero dependency rows — which is the current behavior exactly.

### Q4. Sandbox state — persisted or ephemeral

**Recommendation:** **Persisted on the project itself.** The "sandbox" is just a working view of the project's planned dates + dependencies + overlap groups. Every edit immediately writes to `project_phases` (+ the new join table). No separate `sandbox_drafts` table.

| Option | When acceptable | Rejected because |
|---|---|---|
| Separate `sandbox_drafts` table with "Apply to project" button | If we want full draft/commit semantics | Adds two-phase complexity, divergence risk, and a new UI mental model. The existing Detailed Table writes directly; sandbox should too. |
| Persisted (recommended) | When the sandbox is just "the project's plan, with richer editing" | — |

Side benefit: every sandbox edit naturally flows through `crud.update_phase` and writes a `phase_plan_changes` audit row (Build 17) + a `project_changes` event for Timeline History (Build 08). No new audit path needed.

### Q5. AI tool registry — read-only or write tools?

**Recommendation:** **Both, gated.** Add `list_timeline_templates` (read), `apply_timeline_template` (write, confirmation-required per Build 27), `add_phase_dependency` / `remove_phase_dependency` (write, confirmation-required).

Do NOT add `create_timeline_template` to the AI registry in v1.4 — keep template creation in the user's hands. Matches the `delete_*` pattern where destructive actions are UI-only.

### Q6. Dependency engine — Python or DB-side

**Recommendation:** **Python.** Single function `crud.compute_estimated_launch(db, project_id)` that loads phases + dependency rows, builds an in-memory DAG, runs `graphlib.TopologicalSorter` (stdlib), returns the estimated launch date dict. Same shape as `crud.calculate_delay()`.

DB-side recursion (CTE) is faster at scale but our scale is 8–14 phases per project; Python is more readable and easier to test.

---

## 8. Recommended v1.4 implementation sequence

The Planning Sandbox naturally splits into **4 sub-builds**. Implement in this order; pause for review between each.

### v1.4 Build 01 — Template data model + seed
- Migration 007 creates `timeline_templates`, `timeline_template_modules`, `timeline_template_module_dependencies`.
- Seed the 6 system templates from §2 (idempotent `INSERT WHERE NOT EXISTS`).
- New crud helpers: `list_templates`, `get_template`, `get_template_modules`.
- Admin-only `/admin/templates` page (list + read-only detail view).
- NO project-creation flow change yet.
- ~30 assertions test file.
- **Risk: low.** Pure additive schema; no user-facing behavior change.

### v1.4 Build 02 — "Apply template" during project creation
- Migration 008 adds `ProjectPhase.can_overlap`, `ProjectPhase.overlap_group`, creates `project_phase_dependencies` join table.
- New "Template" select on the New Project form (and the AI intake confirm flow).
- On submit, instantiate phases from the chosen template's modules (copy-down per Q3); copy dependency edges into `project_phase_dependencies`; copy overlap fields onto phases.
- Backward-compatible: existing `prototype_rounds` field stays as a legacy option named "Legacy (Single/Two/Three Round)" in the template list.
- Build 30A idempotency token path stays intact.
- ~30 assertions test file.
- **Risk: medium.** Touches project creation, one of the most-tested paths. Mitigated by leaving the legacy path operational.

### v1.4 Build 03 — Sandbox UI
- New section on the Timeline workspace (above or alongside the Command Center) titled "Sandbox."
- Per-phase editors: duration days (number input), `can_overlap` toggle, `overlap_group` text input, `depends_on` multi-select of other phases.
- Cycle-detection error inline ("This dependency would create a loop").
- Live estimated launch date display + delta vs. project.planned_launch_date.
- All edits flow through `crud.update_phase` + the new dependency helpers — writes audit rows automatically (Build 08 History picks them up).
- Permission: `can_edit_project` to edit; all roles to view.
- ~40 assertions test file.
- **Risk: high.** Most UI complexity. The dependency-graph rendering + cycle detection is non-trivial.

### v1.4 Build 04 — "Save current as template"
- "Save as Template" button on the Timeline workspace.
- Modal prompts for name + description (per §6).
- New crud helper `create_template_from_project(db, project_id, name, description, user)`.
- New AI tool? No — keep template creation in the user's hands per Q5.
- ~20 assertions test file.
- **Risk: low.** Reverse of Build 02; no UI complexity beyond the modal.

### Total v1.4 Sandbox surface

- 2 migrations (007 + 008).
- 3 new tables, 2 new columns on `project_phases`, 1 new join table.
- 6 new crud helpers.
- 4 new template AI tools.
- 4 new UI surfaces.
- 4 new test files (~120 assertions combined).
- 4 sequential commits with plan-first review between each.

Estimated v1.4 effort for the Sandbox alone: **comparable to v1.3 Builds 06+07A+07B combined.**

---

## What Build 09 actually ships

**This document. That is the entire deliverable.** Specifically:

- `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md` (this file) — locks design decisions for v1.4.
- `test_v13_build09.py` — minimal regression-guard: asserts the design doc exists, covers all 8 locked sections, and that no app code, schema, or i18n changed in this build.
- CHANGELOG entry under Unreleased.
- CURRENT_TASK update + Build 10 sketch update.

**No source code, no template, no schema, no migration, no test for behavior that doesn't exist yet.** The design lock prevents Build 09 from drifting into "while we're here, let's add a stub."

---

## Out of scope for Build 09 (and for v1.3 entirely)

- Any database table for templates.
- Any migration.
- Any UI for templates.
- Any route changes.
- Any AI tool addition.
- Any seed data.
- Any change to `PHASE_TEMPLATES` in `app/crud.py`.
- Any cycle-detection / topological-sort code.

If any of the above lands in this build, it's a Lock violation — revert.

---

## Acceptance criteria

- Design doc exists at `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md`.
- All 8 sections from the user's lock list are present and substantive.
- `git diff` between Build 08 commit and Build 09 commit shows zero changes to `app/`, `app/migrations.py`, `app/i18n/`, or any test file other than the new `test_v13_build09.py`.
- v1.3 Builds 01-08 + v1.2.1 baseline regression all pass unchanged.
- i18n parity still 714/714.
- Migration count still 6.

---

## Cross-references

- **Codex's brief** at `V13_BUILD09_PLANNING_SANDBOX_DESIGN_PLAN.md` — checklist this document fulfills.
- **Masterplan**: `V13_MASTERPLAN.md` §"Build Sequence" entry for v1.3 Build 09 → "Document future template/dependency sandbox; no implementation."
- **Current PHASE_TEMPLATES** to replace: `app/crud.py:24` (lines `PHASE_TEMPLATES = {"single": [...], "two_round": [...], "three_round": [...]}`).
- **Existing dependency-like behavior** that the Sandbox subsumes: today the only "dependency" the app models is `phase_order` — a strict linear sequence. The Sandbox introduces real DAG-shaped dependencies.

---

## Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-06-06 | Build 09 stays design-only (Interpretation A) | Per masterplan; avoids enlarging v1.3 mid-stream. User confirmed. |
| 2026-06-06 | 4-sub-build v1.4 sequence proposed | Splits high-risk Sandbox into low/medium/high/low slices with review gates between. |
| 2026-06-06 | DB rows for templates (Q1) | Need user-saved templates; hybrid path is worse than single-source-of-truth DB. |
| 2026-06-06 | Join table for dependencies (Q2) | Cycle detection needs queryable edges, not JSON arrays. |
| 2026-06-06 | Copy-down module → phase (Q3) | Historical phases must not mutate when templates evolve. |
| 2026-06-06 | Persisted sandbox state (Q4) | Sandbox IS the project plan; separate drafts table doubles complexity. |
| 2026-06-06 | AI tools: read + apply, NOT create_template (Q5) | Matches existing delete-tools-UI-only pattern. |
| 2026-06-06 | Python DAG, not SQL CTE (Q6) | Project scale (8–14 phases) doesn't warrant DB-side recursion. |

---

End of Planning Sandbox design lock. v1.4 implementation team should treat this as the canonical reference. Updates to design require a new dated row in the Decision log above + an updated section, not a silent rewrite.
