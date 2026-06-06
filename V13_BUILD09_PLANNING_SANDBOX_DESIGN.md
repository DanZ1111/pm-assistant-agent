# v1.3 Build 09 — Planning Sandbox Engineering Design (design-only)

> **Status:** Amended 2026-06-06. This document is the **engineering response** to the Planning Sandbox PRD (captured verbatim in Appendix A). The PRD is the canonical product vision; this doc is the canonical engineering plan that satisfies it.
>
> Build 09 ships **zero code, zero schema, zero migrations, zero routes, zero UI**. Build 09's deliverable is this document. v1.4 implements it across 8 sub-builds.

---

## Amendment note (2026-06-06)

The original Build 09 doc (shipped at commit `fc064a6`) targeted a form-based editor with sandbox state persisted directly on the project. After PRD review with ChatGPT, the user clarified that the actual product is a **visual workflow canvas with explicit draft/apply separation** — closer to XMind/Miro than a form editor.

User direction (verbatim):
> *"what ChatGPT has here is nothing more than a PRD. What you need is to come up with how you can satisfy this PRD. Evaluate how to achieve my goal under the context with your best judgement is what you should be thinking of. So you don't take or reject ChatGPT's file because it is a starting point for your build 9 not replacing your build 9."*

This amendment rewrites Build 09 as an engineering response to the PRD. The PRD's 10 open questions are locked with best-judgement defaults (user confirmed) in §6 below.

The original doc's Q1–Q6 engineering decisions (DB rows vs config, join table vs JSON, copy-down vs FK, etc.) are preserved where consistent with the PRD; one — original Q4 "persisted on the project itself" — is **flipped** because the PRD requires explicit draft/apply separation.

The original doc's 4-sub-build v1.4 sequence is **expanded to 8 sub-builds** to match the higher UI complexity of a true visual canvas (cycle detection + drag connection handles + dagre auto-layout).

---

## Status

Design-only build per `V13_MASTERPLAN.md` §"Non-Negotiable Product Decisions" → *"Planning Sandbox is design-only in initial v1.3."*

Predecessor: Build 08 shipped at `3ab1dc8` (Timeline Updates / History — derived view).
Successor: Build 10 (v1.3.0 Release Hardening — version bump + release-proof regression + legacy Change Log viewer leak fix).

---

## 1. Architecture overview

The v1.4 Planning Sandbox sits in the **planning lane** — separate from the execution lane that the Timeline Command Center (Builds 06–08) already owns.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        PROJECT DETAIL PAGE                                     │
│                                                                                │
│   Overview tab      │  Timeline tab                                            │
│   (Build 01–05B)    │                                                          │
│                     │  ┌─────────────────────────────┐                         │
│                     │  │  Timeline Command Center    │  ← Build 06+07A+07B    │
│                     │  │  (execution surface)         │     phase strip, tiles, │
│                     │  └─────────────────────────────┘     blockers, actions   │
│                     │                                                          │
│                     │  ▶ Detailed Table (collapsed)     ← Build 17            │
│                     │                                                          │
│                     │  Timeline Updates / History       ← Build 08            │
│                     │  (derived feed)                                          │
│                     │                                                          │
│                     │  ┌─────────────────────────────┐                         │
│                     │  │  Planning Sandbox (v1.4)     │  ← v1.4 NEW           │
│                     │  │  [Open Sandbox →]            │     planning surface   │
│                     │  └─────────────────────────────┘                         │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       │ "Open Sandbox" navigates to:
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  /projects/{id}/sandbox                                                        │
│                                                                                │
│  ┌────────────────────────────────────────────┬─────────────────────────────┐ │
│  │                                            │ MODULE LIBRARY              │ │
│  │                                            │ (or Node Properties when    │ │
│  │   Cytoscape.js canvas                      │  a node is selected)        │ │
│  │   top-to-bottom workflow                   │                             │ │
│  │   nodes scale by duration                  │ ┌─────────────────────────┐ │ │
│  │   edges show dependencies                  │ │ Design                  │ │ │
│  │   one-click "Tidy" auto-layout             │ ├─────────────────────────┤ │ │
│  │                                            │ │ Prototype               │ │ │
│  │   ── reads/writes ──>                      │ ├─────────────────────────┤ │ │
│  │   planning_sandbox_nodes                   │ │ Engineering Review      │ │ │
│  │   planning_sandbox_edges                   │ └─────────────────────────┘ │ │
│  │                                            │                             │ │
│  └────────────────────────────────────────────┴─────────────────────────────┘ │
│                                                                                │
│  [Save Draft]                          Estimate: 45 days        [Apply ▶]     │
└──────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       │ "Apply" triggers an explicit
                                       │ confirmation flow that:
                                       │   1. validates the graph (no cycles,
                                       │      title not empty, duration > 0)
                                       │   2. refuses if any phase has
                                       │      actual_start_date (Q2 lock)
                                       │   3. creates/updates ProjectPhase rows
                                       │      from sandbox nodes (copy-down)
                                       │   4. writes a planning_apply_events row
                                       │   5. Build 08 Timeline History renders
                                       │      "Plan applied from sandbox by
                                       │       Alice" as a new event type
                                       ▼
                              committed project plan
                              (existing ProjectPhase rows)
```

Key invariants:
- **Two-lane model.** Planning lane (sandbox) is for design; execution lane (project_phases + Command Center) is for action. Sandbox edits never mutate live phases.
- **Apply is the only bridge.** Sandbox → project_phases happens only through the explicit Apply route.
- **Reversible until Apply.** Sandbox edits are cheap; PMs can experiment freely.
- **Audit-visible.** Apply events surface in Build 08 Timeline History so the team can see "the plan changed on Jun 4."
- **Backward-compatible.** Existing `PHASE_TEMPLATES` flow in `app/crud.py:24` stays operational; v1.4-02's apply flow is an *additional* path, not a replacement.

---

## 2. Schema (locked)

7 new tables across 4 v1.4 migrations.

### Migration 007 (v1.4-01) — sandbox + module library + edges

```sql
CREATE TABLE planning_module_library (
    module_key             VARCHAR PRIMARY KEY,           -- 'design', 'prototype', etc.
    title                  VARCHAR NOT NULL,
    category               VARCHAR NOT NULL,              -- PRODUCT / FACTORY / COMMERCIAL
    default_duration_days  INTEGER NOT NULL,
    default_owner_role     VARCHAR NULL,                  -- pm / designer / engineer / factory / null
    default_deliverable    TEXT NULL,
    default_exit_criteria  TEXT NULL,
    description            TEXT NULL,
    is_active              BOOLEAN NOT NULL DEFAULT 1,
    sort_order             INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE planning_sandboxes (
    id                          INTEGER PRIMARY KEY,
    project_id                  INTEGER NOT NULL UNIQUE REFERENCES projects(id),  -- Lock Q9: one per project
    name                        VARCHAR NOT NULL,
    status                      VARCHAR NOT NULL DEFAULT 'draft',   -- draft / applied / archived
    base_template_key           VARCHAR NULL,                       -- the template this sandbox was cloned from, if any
    created_by_user_id          INTEGER NULL REFERENCES users(id),
    created_at                  DATETIME NOT NULL,
    updated_at                  DATETIME NOT NULL,
    applied_at                  DATETIME NULL,                      -- timestamp of the last successful Apply
    applied_by_user_id          INTEGER NULL REFERENCES users(id),
    last_computed_total_days    INTEGER NULL                        -- cached schedule estimate; recomputed server-side
);
CREATE INDEX ix_planning_sandboxes_project ON planning_sandboxes(project_id);

CREATE TABLE planning_sandbox_nodes (
    id                     INTEGER PRIMARY KEY,
    sandbox_id             INTEGER NOT NULL REFERENCES planning_sandboxes(id),
    module_key             VARCHAR NULL REFERENCES planning_module_library(module_key),  -- nullable for bespoke nodes
    title                  VARCHAR NOT NULL,
    duration_days          INTEGER NOT NULL CHECK (duration_days > 0),
    owner_role             VARCHAR NULL,
    deliverable            TEXT NULL,
    exit_criteria          TEXT NULL,
    x_position             REAL NOT NULL DEFAULT 0,
    y_position             REAL NOT NULL DEFAULT 0,
    sort_order             INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_planning_sandbox_nodes_sandbox ON planning_sandbox_nodes(sandbox_id);

CREATE TABLE planning_sandbox_edges (
    id                INTEGER PRIMARY KEY,
    sandbox_id        INTEGER NOT NULL REFERENCES planning_sandboxes(id),
    from_node_id      INTEGER NOT NULL REFERENCES planning_sandbox_nodes(id),
    to_node_id        INTEGER NOT NULL REFERENCES planning_sandbox_nodes(id),
    dependency_type   VARCHAR NOT NULL DEFAULT 'finish_to_start',
    UNIQUE (from_node_id, to_node_id)
);
CREATE INDEX ix_planning_sandbox_edges_sandbox ON planning_sandbox_edges(sandbox_id);
CREATE INDEX ix_planning_sandbox_edges_to ON planning_sandbox_edges(to_node_id);
```

Notes:
- `planning_sandboxes.project_id UNIQUE` enforces Lock Q9 (one sandbox per project).
- `UNIQUE(from_node_id, to_node_id)` prevents duplicate edges between the same pair.
- Edge table ships in migration 007 alongside the nodes table for schema cohesion; v1.4-04 starts USING it but doesn't create it.
- Module library is seeded in the same migration (idempotent `INSERT WHERE NOT EXISTS`) with ~20 module rows.

### Migration 008 (v1.4-04 — optional column adjustments)

Reserved for tweaks that surface during the Connect Nodes build (e.g., `planning_sandbox_edges.label` for future labeled deps). Plan-time placeholder.

### Migration 009 (v1.4-07) — apply audit

```sql
CREATE TABLE planning_apply_events (
    id                 INTEGER PRIMARY KEY,
    project_id         INTEGER NOT NULL REFERENCES projects(id),
    sandbox_id         INTEGER NOT NULL REFERENCES planning_sandboxes(id),
    applied_at         DATETIME NOT NULL,
    applied_by_user_id INTEGER NULL REFERENCES users(id),
    snapshot_json      JSON NOT NULL,    -- full graph at apply time; debugging + rollback reference
    phases_created     INTEGER NOT NULL DEFAULT 0,
    phases_updated     INTEGER NOT NULL DEFAULT 0,
    phases_deleted     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_planning_apply_events_project ON planning_apply_events(project_id, applied_at DESC);
```

Apply events are the **read source for Build 08 Timeline History** — a new bucket "Plan Applied" appears alongside the existing Delays/Decisions/Blockers/Phase Changes/Files+Renderings chips.

### Migration 010 (v1.4-08) — templates

```sql
CREATE TABLE planning_templates (
    id                  INTEGER PRIMARY KEY,
    template_key        VARCHAR UNIQUE NOT NULL,
    name                VARCHAR NOT NULL,
    description         TEXT NULL,
    is_system           BOOLEAN NOT NULL DEFAULT 0,
    created_by_user_id  INTEGER NULL REFERENCES users(id),
    created_at          DATETIME NOT NULL,
    sort_order          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE planning_template_nodes (
    id                    INTEGER PRIMARY KEY,
    template_id           INTEGER NOT NULL REFERENCES planning_templates(id),
    module_key            VARCHAR NULL REFERENCES planning_module_library(module_key),
    title                 VARCHAR NOT NULL,
    duration_days         INTEGER NOT NULL,
    owner_role            VARCHAR NULL,
    deliverable           TEXT NULL,
    exit_criteria         TEXT NULL,
    x_position            REAL NOT NULL DEFAULT 0,
    y_position            REAL NOT NULL DEFAULT 0,
    sort_order            INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ix_planning_template_nodes_template ON planning_template_nodes(template_id);

CREATE TABLE planning_template_edges (
    id              INTEGER PRIMARY KEY,
    template_id     INTEGER NOT NULL REFERENCES planning_templates(id),
    from_node_id    INTEGER NOT NULL REFERENCES planning_template_nodes(id),
    to_node_id      INTEGER NOT NULL REFERENCES planning_template_nodes(id),
    UNIQUE (from_node_id, to_node_id)
);
CREATE INDEX ix_planning_template_edges_template ON planning_template_edges(template_id);
```

Templates are stored as their own tables — NOT as sandboxes flagged `is_template=true` — because they have `project_id` semantics of NULL and need to be discoverable globally. Mixing forces every sandbox query to filter `is_template=false`.

Seed migration 010 with the 6 system templates from PRD §22:
1. Simple OEM Knife
2. Standard Folding Knife
3. New Mechanism Knife
4. Gift Set / Combo Pack
5. Packaging-heavy Retail Product
6. Amazon Launch Product

### Total schema impact

- **4 migrations** (007–010).
- **7 new tables.**
- **~10 new indexes.**
- Existing tables: zero columns added. `PHASE_TEMPLATES` in `app/crud.py:24` stays as-is; v1.4-02's apply flow lives alongside it.

---

## 3. Canvas-rendering library decision (locked)

**Cytoscape.js + cytoscape-dagre.** Locked in this design.

| Option | Considered for | Rejected because |
|---|---|---|
| React Flow / xyflow | Industry standard for node-edge editors | Forces React into a Jinja2 + vanilla JS codebase. Build system overhaul + state management split-brain. |
| D3 | Maximum flexibility | Too low-level; re-implements drag, connection handles, cycle detection, layout. Net 5× the code of Cytoscape. |
| Bespoke SVG + custom JS | Zero new dependency | Connection handles + drag with snap + cycle detection + layout = ~1000+ LOC of fragile UI. Bad trade for a knife-PM tool. |
| **Cytoscape.js + cytoscape-dagre** ✅ | Vanilla JS, no framework, purpose-built for graphs | **Lock.** ~60 KB gzipped. Cycle detection + topological sort + dagre auto-layout out of the box. Integrates cleanly with Jinja2-rendered HTML host page. |

Implementation hooks Cytoscape needs:
- `cy.add()` / `cy.remove()` for node/edge CRUD with server roundtrip.
- `cy.elements().topologicalSort()` for client-side preview before server roundtrip.
- `cytoscape-dagre` for the "Tidy" auto-layout button.
- Custom node renderer for the duration-as-height visual (Lock Q6 — discrete size bins).

Subsequent v1.4 builds use Cytoscape unless a Decision log entry overrides.

---

## 4. v1.4 sub-build sequence (locked, 8 builds)

| # | Build | Scope | Migration | Risk | Why this slice |
|---|---|---|---|---|---|
| **v1.4-01** | Schema + Module Library | 4 tables + seed ~20 module rows. Admin-only `/admin/modules` read-only list. NO canvas. | 007 | Low | Schema is load-bearing; isolate. |
| **v1.4-02** | Schedule Engine | Pure Python `crud.compute_sandbox_schedule(sandbox_id)`. Topological sort + earliest-start propagation. ~30 assertions, fixture sandboxes. NO UI. | — | Medium | Correctness locked before any UI consumes it. Standalone testable. |
| **v1.4-03** | Static Canvas Renderer | Read-only canvas at `/projects/{id}/sandbox` using Cytoscape.js. Nodes + edges + duration-bin visual. NO drag, NO module palette, NO edits. | — | Medium | Visual rendering decoupled from interaction risk. |
| **v1.4-04** | Module Palette + Drag-to-Add | Right-panel library, draggable. Drop creates a node with default values. Node position persisted. NO edges yet (edges from v1.4-05). | 008 (placeholder) | Medium-high | Most contained drag interaction. |
| **v1.4-05** | Connect Nodes | Drag from connection handle to create edge. Cycle detection at edit time (rejects with inline error). | — | High | The hard UI build. |
| **v1.4-06** | Node Property Panel | Right-panel state transition: library ↔ properties when a node is selected. Edit title/duration/owner/deliverable/exit_criteria. Live schedule recompute on duration change. | — | Medium | Naturally follows v1.4-05 once nodes are selectable. |
| **v1.4-07** | Apply to Project Plan | Explicit confirm dialog. Server-side commit creates/updates `ProjectPhase` rows from sandbox graph (copy-down). Refuses if any phase has `actual_start_date` (Q2 lock). Writes `planning_apply_events` row. Build 08 Timeline History gains a new "Plan Applied" event bucket. | 009 | High | Touches real project data. |
| **v1.4-08** | Save as Template | Convert a sandbox to a template via modal. AI tools `list_timeline_templates` + `apply_timeline_template` land here. Seed 6 system templates. | 010 | Medium | Reverse of v1.4-07 + AI registry update. |

Total v1.4 Sandbox surface:
- **4 migrations** (007–010).
- **~7 new tables.**
- **~12 new crud helpers** across the 8 sub-builds.
- **3 new AI tools** (`list_timeline_templates`, `apply_timeline_template`, `apply_sandbox_to_project`).
- **~150 test assertions** across 8 test files (~18 avg per build).

Each sub-build follows the project's plan-first execution pattern (`V14_BUILD0N_EXECUTION_PLAN.md` written and committed before any code).

---

## 5. Backend Honesty Mapping

Per the project's discipline pattern (Builds 06, 07A, 07B, 08). Every visible canvas element traces to source-of-truth.

| Visible element | Source of truth | Write path | Derived-state rule | Permission rule | Planned test coverage |
|---|---|---|---|---|---|
| **Canvas node** | `planning_sandbox_nodes` row | Drag-from-palette POST (v1.4-04) + property panel edit POST (v1.4-06) | Render position from `(x_position, y_position)`; render height from `duration_days` binned (Q6) | `can_edit_project` to edit; all roles to view | v1.4-03 markup; v1.4-04 drag; v1.4-06 edit |
| **Canvas edge** | `planning_sandbox_edges` row | Drag-connection POST (v1.4-05) | Render as Cytoscape edge with finish-to-start arrowhead | `can_edit_project` to edit; all roles to view | v1.4-05 drag + cycle rejection |
| **Module library item** | `planning_module_library` row where `is_active=1` | Seed migration 007 | Render in right panel sidebar grouped by `category`, sorted by `sort_order` | All authenticated to view; admin-only edit at `/admin/modules` | v1.4-01 |
| **Node property — title/duration/owner/etc.** | `planning_sandbox_nodes` columns | Property panel POST (v1.4-06) | Direct render | `can_edit_project` to edit; all roles to view | v1.4-06 |
| **Schedule estimate ("45 days")** | `crud.compute_sandbox_schedule(sandbox_id)` | (read-only; recomputed on every change) | Topological sort + earliest-start propagation per PRD §11 | All authenticated to view | v1.4-02 (engine), v1.4-06 (live recompute) |
| **"Apply" button** | n/a (action) | New POST `/projects/{id}/sandbox/apply` (v1.4-07) | Visible only when sandbox has ≥1 node, no cycles, every node has duration>0 | `can_edit_project`; refuses if any phase has `actual_start_date` (Q2) | v1.4-07 happy + refuse + audit row + Timeline History integration |
| **"Save as Template" button** | n/a (action) | New POST `/projects/{id}/sandbox/save-as-template` (v1.4-08) | Visible whenever sandbox has ≥1 node | `can_edit_project` | v1.4-08 happy + name uniqueness |
| **Template picker (on first-open)** | `planning_templates` rows | Seed migration 010 | Render system templates first, then user templates by created_at desc | All authenticated to view; `can_edit_project` to start a sandbox from a template | v1.4-08 |
| **Cycle warning** | Client-side Cytoscape check + server-side validation on edge POST | Edge POST refuses with `{ok:false, error:'cycle'}` | Inline error chip on the canvas | `can_edit_project` | v1.4-05 |
| **Disconnected branch soft warning** | Server-side graph analysis | (read-only) | Banner above canvas when ≥1 connected component has no path to a terminal node | All authenticated to view | v1.4-05 |
| **"Plan Applied" event in Timeline History** | `planning_apply_events` row + Build 08 helper extension | (read-only; rendered by Build 08) | `crud.get_timeline_events` gains a 4th source table | All authenticated; viewer sees event but not snapshot detail | v1.4-07 + Build 08 regression update |

No visible field is fabricated. Every UI affordance has a deterministic data source.

---

## 6. Engineering decisions Q1–Q10 (PRD §28 open questions, locked)

User confirmed 2026-06-06: lock with defaults now.

### Q1. Start blank / template / both?

**Locked: Both.** First-open at `/projects/{id}/sandbox` shows a picker:
- "Start blank canvas" (1 button)
- "Start from template" (the 6 system templates listed below as cards)

Once a sandbox exists, the picker is hidden; user lands directly on the canvas.

**Rationale:** PRD §22 explicitly lists templates as starting points; PRD §18.1 explicitly shows the blank-canvas affordance. Both are required. Forcing one is the wrong default.

**Locks/unlocks:** v1.4-08 (templates) must ship before v1.4-07 (apply) to make the template-start path viable. → Sequence respects this by landing templates LAST. Acceptable because the blank-canvas path works from v1.4-04 onward; templates are an enhancement, not a blocker for the first usable sandbox.

### Q2. Apply replace existing plan or new version?

**Locked: Replace draft only; never silently overwrite execution data.**

Apply behavior:
- If every existing `ProjectPhase.actual_start_date IS NULL`: replace all phases with the sandbox graph. Write `planning_apply_events` row with `phases_deleted=N, phases_created=M`.
- If ANY phase has `actual_start_date IS NOT NULL`: refuse with explicit error message. Offer two paths: (a) "Archive these advanced phases first" (manual admin action), or (b) "Append new sandbox phases AFTER the advanced ones" (Phase B feature, deferred to v1.4-07b).

For v1.4-07's first ship: only (a) is supported. Path (b) becomes a v1.5 candidate if PMs request.

**Rationale:** PRD §20 explicitly says: *"Avoid silently overwriting active execution data."* The conservative rule prevents data loss.

**Locks/unlocks:** Apply route returns a structured `{ok:false, error:'phases_in_progress', advanced_phase_ids:[...]}` so the UI can render the explanation. Test coverage in v1.4-07 must include the refuse path.

### Q3. Client / server / both graph computation?

**Locked: Server is source of truth; client mirrors for responsiveness.**

- Every node/edge/duration change POSTs to server.
- Server returns the recomputed schedule in the response.
- Client caches the last response and renders optimistically.
- On disagreement (e.g., concurrent edit by another PM), server response wins; client re-syncs.

**Rationale:** Avoids the class of bugs where two PMs see different schedules. Server-side schedule engine in v1.4-02 is single source of truth.

**Locks/unlocks:** Cytoscape's client-side `topologicalSort()` is used ONLY for optimistic preview, not the persisted estimate. Server's `compute_sandbox_schedule()` is the only writer of `planning_sandboxes.last_computed_total_days`.

### Q4. Manual node positioning vs auto-layout?

**Locked: Manual primary; one-click "Tidy" auto-arrange via cytoscape-dagre.**

- Initial node placement on drag-from-palette respects the drop point.
- Adding an edge does NOT auto-rearrange the canvas.
- A "Tidy" button (top-right of canvas) runs `cy.layout({name:'dagre',rankDir:'TB'}).run()` and persists the new positions.

**Rationale:** Auto-layout on every change is jarring; users want control over canvas layout. But "tidy this mess" is a frequent ask. Manual + on-demand-tidy is the right balance.

**Locks/unlocks:** Positions persist to `planning_sandbox_nodes.x_position/y_position`. v1.4-04 must implement position persistence; v1.4-03 reads them.

### Q5. Dependency creation: drag handles / property panel / both?

**Locked: Both.**

- **Primary:** Drag from a node's edge handle to another node creates an edge. Cytoscape's `edgehandles` extension.
- **Fallback:** Node property panel has a "Depends on" multi-select listing all other nodes in the sandbox. Useful for keyboard-only users + when the canvas is dense.

**Rationale:** Accessibility + flexibility. Drag is fast; property-panel checkboxes work without a mouse.

**Locks/unlocks:** v1.4-05 ships the drag interaction; v1.4-06 adds the property panel control. Both write through the same edge POST route.

### Q6. Node height: strict scale or rough?

**Locked: Rough — 4 discrete size bins.**

| Bin | Duration range | Node height |
|---|---|---|
| S | 1–3 days | 40 px |
| M | 4–10 days | 70 px |
| L | 11–25 days | 110 px |
| XL | 26+ days | 160 px |

**Rationale:** PRD §12 explicitly says *"does not need to be mathematically perfect."* Bins are honest + readable. Avoids 1-day nodes being invisible and 60-day nodes filling the screen.

**Locks/unlocks:** Bin thresholds become a constant in `app/static/js/sandbox.js`. Tunable in v1.4-03 if PMs report they feel wrong.

### Q7. Disconnected branches allowed?

**Locked: Yes, with soft warning banner.**

Per PRD §18.3. Multiple disconnected branches are treated as independent starting paths in the schedule engine — each branch starts at day 0; the project estimate is `max(branch_estimates)`.

A soft-warning banner ("This sandbox has 2 disconnected branches — they will run in parallel from day 0.") renders above the canvas. Apply does NOT refuse.

**Rationale:** Flexibility for early planning when PMs are still sketching. The warning catches accidents.

**Locks/unlocks:** Server's `compute_sandbox_schedule()` must support multi-root DAGs; v1.4-02 test coverage includes a disconnected fixture.

### Q8. Sandbox permissions vs project permissions?

**Locked: Inherit project permissions exactly.**

- `can_edit_project(user, project)` ⇒ can edit sandbox (drag, connect, edit properties, apply, save-as-template).
- View-only role (any authenticated user with `Project` access) can READ sandbox (canvas + schedule estimate).
- Viewer sees the canvas but no edit affordances; no "Apply" button; no "Save as Template" button.

**Rationale:** Zero new permission concept. Matches Build 07A/07B/08 pattern.

**Locks/unlocks:** Every new sandbox route re-runs `require_auth` + `can_edit_project`. Defense-in-depth.

### Q9. One sandbox per project or multiple drafts?

**Locked: One per project for v1.4 first release.**

`UNIQUE(project_id)` on `planning_sandboxes` enforces. Multiple drafts deferred to v1.5+ if PMs report they need scenario comparison.

**Rationale:** Avoid the "which draft is canonical" UX trap. Single sandbox = clean Apply semantics. PRD §28 lists this as an open question precisely because it's a known UX tradeoff; the conservative answer is one.

**Locks/unlocks:** Apply replaces the in-place sandbox's contents on next edit; previous-graph history is captured in `planning_apply_events.snapshot_json` for forensic review only, not for "switch back to draft" UX.

### Q10. Global templates only or project-specific?

**Locked: Global with ownership.**

- **System templates** (`is_system=true`, `created_by_user_id=NULL`): the 6 PRD-named templates. Cannot be deleted. Visible to all authenticated users.
- **User-saved templates** (`is_system=false`, `created_by_user_id=N`): visible to creator + admin. Creator (or admin) can delete.
- **No project-scoped templates.** A template is reusable by definition; project-scoping contradicts the concept.

**Rationale:** Matches `delete_variant` admin-only pattern for system data; lets PMs save successful workflows for re-use.

**Locks/unlocks:** v1.4-08 implements both system seed + user save-as-template. AI tool `apply_timeline_template` filters by visibility for the calling user.

---

## 7. Risk register (top 5 for v1.4 implementation)

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| 1 | **Cytoscape.js drag + cycle detection in v1.4-05 ships buggy** — UX feels janky, users abandon | High | Ship v1.4-03 (static renderer) first so visual rendering is locked before adding interaction. Implement cycle check both client-side (Cytoscape `elesByGroup('edges')` traversal) AND server-side (graphlib in Python). Reject at the lower layer too. Manual test plan: try to create A→B→A; expect rejection chip. |
| 2 | **Apply route in v1.4-07 silently overwrites a project where Phase 1 just started** | Critical (data loss) | Q2 lock + explicit `actual_start_date` refuse path + test coverage for the refuse case + `planning_apply_events.snapshot_json` post-mortem trail. Audit log makes any incident reconstructable. |
| 3 | **Schedule engine in v1.4-02 is wrong on edge cases (deep DAG, parallel chains, disconnected branches)** | Medium | Pure Python function in isolation; fixture-driven test file with ~30 cases covering: linear chain, fork-join, deeper-than-7 chain, two disconnected components, single-node sandbox, zero-edge sandbox. |
| 4 | **Cytoscape adds 60 KB to every Timeline page load even when sandbox not opened** | Low | Cytoscape JS bundle lazy-loaded only on `/projects/{id}/sandbox` route. Timeline tab still uses vanilla JS. v1.4-03 sets this pattern. |
| 5 | **PMs use the sandbox to mock plans for projects they don't own** (permission edge case) | Low (data integrity) | Q8 lock — sandbox permissions inherit `can_edit_project`. Defense-in-depth re-check on every route. Test coverage in every v1.4 build that adds a sandbox route. |

---

## 8. Out of scope (Build 09 + v1.4)

**Out of scope for Build 09 (this revision):**
- Any source code change.
- Any database table.
- Any migration.
- Any UI surface.
- Any AI tool addition.
- Any change to `app/crud.py:PHASE_TEMPLATES`.
- Any introduction of Cytoscape.js as a dependency (the choice is *locked*, the install happens in v1.4-03).

**Out of scope for the v1.4 sandbox implementation:**
- Cross-project resource allocation, factory capacity planning (PRD §4).
- AI-generated full project plans (PRD §4).
- Real-time multi-user editing (PRD §4).
- Calendar / iCal integration (PRD §4).
- CSV / Excel export (PRD §4).
- Sandbox as the source of truth after Apply (PRD §4).
- Multiple sandbox drafts per project (Q9 — v1.5+).
- Append-after-advanced-phases apply mode (Q2 — v1.5+).
- Project-scoped templates (Q10).
- Working-days / weekend / holiday handling (PRD §5; calendar days only).
- Critical-path highlighting (PRD §5; nice-to-have for v1.5+).
- Lag time between phases (PRD-implicit; PMs add a buffer phase if they need it).
- Resource constraints ("alice can only work on one phase at a time") (PRD §4).
- Probabilistic / PERT three-point estimates (out of product scope).

If any of the above lands in v1.4, it's a Lock violation — revert + open a new design decision.

---

## 9. Acceptance criteria for Build 09 (this revision)

- This document exists at `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md`.
- All 13 sections from §"Structure of the new design doc" above are present and substantive.
- PRD appendix (Appendix A) is captured verbatim.
- All 10 PRD open questions are locked with rationale.
- Schema sketch is complete for all 7 tables + 4 migrations.
- Canvas library decision is locked (Cytoscape.js).
- v1.4 sub-build sequence is 8 builds with risk labels.
- Backend Honesty Mapping covers every visible canvas element.
- Decision log includes a new dated row for the 2026-06-06 amendment.
- `git diff` between the prior Build 09 commit and this amendment shows zero changes to `app/`, `app/migrations.py`, `app/i18n/`, or any test file other than `test_v13_build09.py`.
- v1.3 Builds 01–08 + v1.2.1 baseline regression all pass unchanged.
- i18n parity still 714/714.
- Migration count still 6.

---

## 10. Cross-references

- **PRD source** — Appendix A below (the user-pasted ChatGPT doc).
- **Codex's original brief** at `V13_BUILD09_PLANNING_SANDBOX_DESIGN_PLAN.md` — checklist this document fulfills.
- **Masterplan** at `V13_MASTERPLAN.md` §"Build Sequence" entry for v1.3 Build 09 → *"Document future template/dependency sandbox; no implementation."*
- **Current `PHASE_TEMPLATES`** at `app/crud.py:24` — stays untouched. v1.4-02's apply flow lives alongside it.
- **Build 08 Timeline History** at `V13_BUILD08_EXECUTION_PLAN.md` — `crud.get_timeline_events` source-table union. v1.4-07 extends it with `planning_apply_events`.
- **Build 27 confirmation pattern** at `app/ai/tools.py:CONFIRMATION_TOOLS` — new sandbox AI tools (v1.4-08) follow this.
- **Build 30A's `_create_project_creation_tokens`** at `app/migrations.py:152` — migration pattern v1.4-01 mirrors.
- **FK enforcement** at `app/database.py` (added 2026-06-06) — new tables must declare FKs cleanly.

---

## 11. Decision log

| Date | Decision | Rationale |
|---|---|---|
| 2026-06-06 | Build 09 stays design-only (Interpretation A) | Per masterplan; avoids enlarging v1.3 mid-stream. User confirmed. |
| 2026-06-06 | DB rows for sandboxes/templates (not static config) | Need user-saved templates; hybrid path is worse than single-source-of-truth DB. |
| 2026-06-06 | Edges as join table (not JSON column on nodes) | Cycle detection + topological sort need queryable edges. |
| 2026-06-06 | Copy-down sandbox node → ProjectPhase on Apply | Historical phases must not mutate when sandboxes evolve. |
| 2026-06-06 | Python DAG (not SQL CTE) for schedule engine | Project scale (8–14 nodes per sandbox) doesn't warrant DB-side recursion. |
| **2026-06-06** | **AMENDMENT: visual canvas + draft/apply separation locked** (PRD-driven) | **ChatGPT-shaped PRD made clear the product is a visual workflow editor with explicit Apply, not a form-based directly-persisted editor. Original Build 09 Q4 "persisted on project itself" FLIPPED. v1.4 sequence expanded from 4 to 8 sub-builds to match UI complexity.** |
| **2026-06-06** | **Cytoscape.js + cytoscape-dagre chosen for canvas rendering** | Vanilla JS, ~60 KB, cycle detection + topological sort + dagre layout out of the box. Avoids forcing React into a Jinja2 codebase. |
| **2026-06-06** | **All 10 PRD §28 open questions locked with defaults** (per user direction) | See §6 above for question-by-question rationale. Future v1.4 implementer can override with a new dated Decision log row. |
| **2026-06-06** | **v1.4 sub-build sequence locked at 8 builds** | Schema → schedule engine → static render → drag-to-add → connect → property panel → apply → save-as-template. Each its own plan-first execution. |

Updates to design require a new dated row above + an updated section, not a silent rewrite.

---

# Appendix A — Planning Sandbox PRD (canonical product vision)

> Source: ChatGPT discussion with user, 2026-06-06. Captured verbatim. This is the canonical product reference. Engineering response is the body of this document above.

## A.1 Purpose

The Planning Sandbox is a visual workflow planning tool for building, simulating, and later applying project workflows.

It is not a table-first planner.
It is not primarily a traditional Gantt chart.
It is not the live project tracking system.

The intended product is a visual workflow canvas where the user can drag reusable planning modules onto a canvas, connect them into a workflow, assign durations and properties, and see the estimated project sequence.

The key mental model is:

```text
Module library → visual canvas → nodes + edges → estimated workflow → apply to project plan
```

The purpose is to help a non-technical PM form a project process visually instead of filling out a long table.

## A.2 Product Problem

Today, project planning is too implicit.

A PM may know that a project needs design, engineering review, sampling, quotation, packaging, and production, but the system does not yet help them reason about:

- What steps should this project include?
- Which steps must happen before others?
- Which steps can happen in parallel?
- How long does each step usually take?
- Which upstream task blocks a downstream task?
- What is the estimated total project duration?
- How should a reusable project workflow be created for future similar projects?

A normal table can technically capture this, but it is not a good planning interface. Users do not naturally "think in rows." They think in flows.

## A.3 Product Definition

Planning Sandbox is a **visual workflow canvas**.

The page should have:
- A large canvas on the left.
- A module/tagbox library on the right.
- Draggable modules that become workflow nodes.
- Connectable nodes that form dependencies.
- Node properties such as duration, owner, deliverable, and exit criteria.
- Visual duration representation, especially if the workflow is top-to-bottom.
- Automatic schedule calculation based on dependency graph.
- Save Draft behavior.
- Apply to Project behavior, which converts the sandbox workflow into the actual project plan.

The sandbox is a planning tool. It is used to design a workflow before committing it.

The existing project timeline / phase tracking system remains the actual tracking system.

## A.4 Non-Goals (first implementation must avoid)

- Full Gantt chart product
- Cross-project resource allocation
- Factory capacity planning
- AI-generated full project plans
- Real-time multi-user editing
- Calendar integration
- CSV / Excel export
- Complex permission matrix
- Automatic live tracking from the canvas
- Canvas as the source of truth after the plan is applied
- Version comparison between multiple sandbox drafts
- Infinite canvas collaboration features
- Complex animations
- Full graph editor with all advanced node-editor features

The first version should focus on one strong interaction:

> Drag modules, connect nodes, define duration, calculate plan, apply to project.

## A.5 Key Product Principle (non-negotiable)

The Planning Sandbox and the committed project plan must be separate.

```text
Sandbox = draft / simulation
Committed project plan = actual execution plan
```

Users should be able to freely test ideas in the sandbox without immediately mutating the real project timeline.

Correct flow:

```text
Template / blank canvas → Sandbox draft → User edits workflow visually
                       → User saves sandbox draft → User explicitly applies sandbox
                       → Project phase plan is created or updated
```

**Incorrect flow:** Dragging a node immediately mutates live project tracking. That should not happen.

## A.6 Core UX — page layout

The left side is the planning canvas.
The right side is the module library by default.
When a node is selected, the right panel changes into a node property editor.

## A.7 User Story

As a PM, I want to visually assemble a project workflow by dragging reusable modules into a canvas and connecting them, so that I can quickly understand what steps are needed, what can happen in parallel, and how long the project may take before committing it to the real project plan.

## A.8 Main User Flow

Open Project → Open Planning Sandbox → Choose template or blank canvas → Drag modules → Connect nodes → Edit node properties → System calculates estimated schedule → Save sandbox draft → Apply to project plan.

## A.9 Core Objects

**Module:** reusable planning block in the right-side library. Examples: Design / Engineering Review / Structure Validation / Prototype / Sample Review / Factory Feedback / Quotation / Packaging / Rendering / Production / QC / Amazon Listing Prep / Launch Prep.

Each module has default properties: module_key / name / category / default_duration_days / default_owner_role / default_deliverable / default_exit_criteria / description.

**Node:** project-specific instance of a module on the canvas. Contains: node_id / sandbox_id / module_key / title / duration_days / owner_role / deliverable / exit_criteria / x_position / y_position / computed_start_day / computed_end_day.

The visual node should show at least: Title / Duration / Owner or category / Warning state (if any).

**Edge:** dependency. If Design points to Prototype, it means Prototype depends on Design. Contains: edge_id / sandbox_id / from_node_id / to_node_id / dependency_type. First version: only `finish_to_start`.

**Sandbox:** draft workflow for a project. Contains: sandbox_id / project_id / name / status (draft|applied|archived) / base_template_id / created_by / created_at / updated_at / last_computed_total_days.

## A.10 Workflow Graph Rule

The sandbox is fundamentally a directed acyclic graph. The system should prevent or warn against circular dependencies.

## A.11 Schedule Calculation Rule

For each node:
```
node start day = max(end day of all upstream dependency nodes)
node end day = node start day + duration days
```

If no upstream deps: `node start day = 0`.

Project estimate = `max(end day of all terminal nodes)`.

Examples from PRD:
- Design 14 + Engineering 10 + Prototype 21 (Design→Prototype, Engineering→Prototype): estimate = max(14,10) + 21 = 35 days.
- Same but Engineering 24: estimate = max(14,24) + 21 = 45 days. Engineering Test becomes the blocking path.

## A.12 Visual Duration Rule

If the workflow is shown top-to-bottom, duration should be visible through node height. A 24-day node should look taller than a 10-day node. Does not need to be mathematically perfect in the first version.

## A.13 Example Workflows

- Simple linear: Design → Prototype → Production. Estimate = sum.
- Parallel pre-prototype: Design + Engineering Review converge into Prototype. Estimate = max(Design, Engineering) + Prototype.

## A.14 Right Panel States

Two main states: **Module Library** (default) and **Node Properties** (when a node is selected).

## A.15 Drag and Drop Behaviors

- **Drag module to blank canvas:** create node with module defaults; save position; select; show properties.
- **Drag below existing node:** may offer auto-connect suggestion. User can remove.
- **Drag beside existing node:** no auto-connect. Parallel placement does not always mean dependency.
- **Connect nodes:** user must be able to create dependency edges between nodes (drag handles, property panel, or auto-connect on drop-below all acceptable).
- **Multiple parents:** a node may depend on multiple upstream nodes.
- **Delete node:** remove node + all edges + recalculate + warn if downstream estimates change.
- **Delete edge:** remove dependency + recalculate.

## A.16 Canvas Orientation

Preferred first orientation: **top-to-bottom.** Maps naturally to "first this, then that"; node height can reflect duration; downstream deps visually lower; parallel work side-by-side.

## A.17 Visual States

Nodes should have visual states: Normal / Selected / Warning / Critical Path / Disconnected / Terminal.

## A.18 Empty States

- **No sandbox yet:** "Start blank canvas" + template options.
- **Empty canvas:** "Drag modules from the right panel to build a project workflow."
- **Disconnected nodes:** "Some nodes are disconnected from the main workflow. They will be treated as independent starting branches."

## A.19 Warnings and Validation

**Hard validation (blocks save/apply):**
- Circular dependency.
- Node with missing required title.
- Node with duration ≤ 0.
- Edge pointing to missing node.
- Sandbox with zero nodes when applying.

**Soft warnings (visible, do not block):**
- Disconnected branches.
- Very long duration node.
- Terminal nodes that don't look like launch/production/completion.
- Packaging starts before design done.
- Production starts before prototype/sample approval.
- Missing owner / deliverable / exit criteria.

## A.20 Apply to Project Plan

Applying a sandbox converts the graph into the actual project plan. Explicit + user-confirmed.

First version: create or replace planning phases from sandbox. Write a project change event. Surface in Build 08 Timeline History. Keep sandbox as an applied snapshot.

**Recommendation:** Apply creates a new committed planning version or replaces current draft plan only. Avoid silently overwriting active execution data.

## A.21 Relationship to Existing Project Tracking

Canvas does not become the day-to-day tracking surface. After applying, actual tracking continues through existing project detail, timeline, blockers, journal, files, and phase plan UI. Canvas is for Planning / Simulation / Template creation / Workflow design. Existing system is for Execution / Status tracking / History / Files / Journal / Blockers / Phase completion.

## A.22 Template System

Initial template candidates:
1. Simple OEM Knife
2. Standard Folding Knife
3. New Mechanism
4. Gift Set
5. Packaging-heavy Retail
6. Amazon Launch

Each template defines a default graph, not just a list.

## A.23 Data Storage Intent

Store graph data, not an image.

```
planning_sandboxes (id / project_id / name / status / base_template_id / created_by / created_at / updated_at / last_computed_total_days)
planning_sandbox_nodes (id / sandbox_id / module_key / title / duration_days / owner_role / deliverable / exit_criteria / x_position / y_position / sort_order)
planning_sandbox_edges (id / sandbox_id / from_node_id / to_node_id / dependency_type)
planning_module_library (module_key / title / category / defaults / description / is_active)
```

## A.24 Computed Fields

The following can be computed rather than stored: `computed_start_day`, `computed_end_day`, `is_critical_path`, `has_warning`, `terminal_node`.

## A.25 Build 09 Deliverable

Markdown design doc only. No code.

Required coverage: Product definition / Non-goals / Canvas UX / Module library / Node property panel / Drag/drop / Node connection / Duration-to-height / Schedule calc / Graph data model intent / Templates / Apply-to-project / v1.4 sequence / Open questions / Risks.

## A.26 Suggested v1.4 Build Sequence

- **v1.4-01 — Workflow Graph Schema + Module Library** (medium risk, schema is load-bearing).
- **v1.4-02 — Static Canvas Renderer** (medium, visual layout).
- **v1.4-03 — Module Palette + Drag Node Onto Canvas** (medium-high, frontend).
- **v1.4-04 — Connect Nodes** (high, graph interactions).
- **v1.4-05 — Schedule Engine** (medium-high, very testable).
- **v1.4-06 — Parallel Branch Layout + Visual Duration** (high, auto-layout can become complex).
- **v1.4-07 — Apply Sandbox to Project Plan** (high, touches real project plan).
- **v1.4-08 — Save Workflow as Template** (medium).

> **Engineering note (this doc):** the engineering response reorders this slightly — Schedule Engine moves from v1.4-05 to v1.4-02 (before any UI) for testability, and "Parallel Branch Layout + Visual Duration" folds into the static renderer + dagre auto-layout decisions. See body §4 for the locked sequence.

## A.27 Implementation Philosophy

Build incrementally. Do not ship the full visual sandbox in one build.

```text
First make the graph correct.
Then make it visible.
Then make it draggable.
Then make it connectable.
Then make it applicable to real projects.
```

## A.28 Open Questions (must be answered before implementation — locked in body §6)

1. Should the canvas start from a blank canvas, a selected template, or both?
2. Should Apply replace the existing project phase plan or create a new version?
3. Should graph computation happen client-side, server-side, or both?
4. Should the first implementation support manual node positioning only, or auto-layout?
5. Should dependency creation be through drag handles, property panel, or both?
6. Should node height strictly scale with duration, or only roughly communicate duration?
7. Should disconnected branches be allowed?
8. How should sandbox permissions map to existing project permissions?
9. Should a project have one active sandbox or multiple drafts?
10. Should templates be global only, or can users save project-specific templates?

## A.29 Acceptance Criteria (PRD)

Build 09 produces a clear markdown design doc covering all required topics, defines Planning Sandbox as a visual workflow canvas (not table-first or Gantt-first), includes wireframes, explains module library + node property panel + node/edge behavior + schedule calculation + duration-to-height + sandbox draft vs committed plan, lists non-goals, proposes v1.4 sequence, does not implement code, does not add migrations, does not change current project behavior.

## A.30 Summary

Planning Sandbox should help the PM visually build a project workflow. The final user experience should feel closer to: **XMind + Railway + lightweight project planning** — not Spreadsheet + Gantt table.

The user should drag modules, connect boxes, define durations, and see the workflow estimate.

The database should store structured graph data. The visual canvas is the planning interface. The existing project phase/timeline system remains the execution and tracking interface.

Build 09 should lock this design only. Implementation should begin in v1.4 after v1.3 is hardened and released.

---

End of Planning Sandbox engineering design. v1.4 implementation team treats this as canonical reference. Updates require a new dated Decision log row + updated section.
