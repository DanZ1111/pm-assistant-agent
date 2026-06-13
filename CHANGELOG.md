# PM Product Tracker — Changelog

## Unreleased

- No unreleased changes after v1.5.0 release hardening.

## v1.5.0 — Designer Portal MVP
_2026-06-13_

v1.5.0 adds a restricted Designer Portal for design briefs, submissions,
revision loops, final selection, and explicit design completion. PMs continue
working in Project Detail `Renderings & Design`; designers work only inside
`/designer`; selected work flows back into project renderings with source
metadata.

- **v1.5 Build 01 — Roles & Portal Shell.** Adds `designer` and
  `designer_manager` roles, invite PIN support, `/designer` shell, and route
  blocking so Designer Portal users cannot access PM Workspace project pages.
- **v1.5 Build 02 — Design Quest Data Model.** Adds design quest,
  assignment, reference, and event models/migration plus designer-safe read
  shaping and visibility rules.
- **v1.5 Build 03 — PM Renderings & Design Quest MVP.** Replaces the old
  Designer Portal placeholder with PM quest creation/edit/publish/close,
  guarded reference linking, and designer-safe preview.
- **v1.5 Build 04 — Designer Portal Quest View.** Designers can browse
  available/assigned quests, view safe brief fields/references, and download
  references through guarded routes.
- **v1.5 Build 05 — Submissions & Versions.** Designers can upload validated
  images/PDFs, preserving every version; PMs see incoming submissions with
  guarded version downloads.
- **v1.5 Build 06 — Revision Loop & Review Actions.** PMs can shortlist,
  reject, and request structured revisions; designers can answer open revision
  requests with linked revised versions.
- **v1.5 Build 07 — Select Final & Promote Rendering.** PMs select a specific
  submission version as final; the app copies it into project renderings with
  `design_submission_version` source metadata.
- **v1.5 Build 08 — Design Status In Timeline/Pulse.** Project Pulse and
  Timeline Command Center show derived design status. `Mark Design Complete`
  is explicit and does not mutate phase status.
- **v1.5 Build 09 — Designer Manager Operations.** Designer managers get a
  safe operations page for assigning designers to assigned-only quests and
  reopening mistakenly rejected submissions; they remain blocked from PM
  project pages.
- **v1.5 Build 10 — Release Hardening.** Bumps runtime/docs to v1.5.0,
  documents deferred AI write handlers, and adds `test_v15_build10.py`.

Migrations 011-015 are the v1.5 schema changes. No Designer Portal AI write
handlers are registered in this release; future handlers must use the standard
confirmation flow and the same permission boundaries as the manual UI.

## v1.4.0 — Planning Sandbox Release
_2026-06-10_

v1.4.0 turns the Planning Sandbox from a design lock into a usable PM planning
surface. PMs can start from six seeded workflow templates or a blank canvas,
add/edit workflow modules, connect dependencies, review server-computed schedule
warnings, tidy the graph, explicitly Apply a valid sandbox into the live
Timeline, and save useful workflows as private reusable templates. Sandbox draft
edits stay isolated from `project_phases` until Apply is confirmed. Release
hardening adds `test_v14_build09.py`, a scenario contract runner that exercises
all six system templates through create/edit/save/apply/history verification;
bumps runtime/docs to v1.4.0; preserves v1.2.1 and v1.3.0 release-proof
markers; and documents the sandbox AI tool surface as planned/deferred.

- **v1.4 Build 08 — Save Workflow as Template.** Adds the reusable template loop for Planning Sandbox without changing live project timelines. PM/admin users can save draft or applied sandbox snapshots as private user templates through a compact Save as Template panel; archived sandboxes cannot be saved. Saved templates copy sandbox nodes and dependency edges into the existing `planning_templates`, `planning_template_nodes`, and `planning_template_edges` tables, generate unique service-owned template keys, and become available immediately in the picker under My Templates. System templates remain immutable; user templates are visible to their creator and admins only; viewers see no dead Save/Create mutation affordances. Template creation from private user templates is permission-filtered, while admins can create from user templates. Adds `list_planning_templates_for_user`, `save_sandbox_as_template`, `POST /projects/{project_id}/sandbox/{sandbox_id}/save-template`, grouped template picker UI, a planned/deferred AI registry row, `test_v14_build08.py`, and 14 EN/zh labels, bringing i18n parity to 805/805. No migration, no template edit/delete UI, no Apply changes, no AI handler, and no `project_phases` mutation.
- **v1.4 Build 07 — Planning Sandbox Apply to Timeline.** Adds the explicit audited bridge from draft sandbox to live project phases. PM/admin users can apply a valid draft sandbox through a confirmation panel with node count, total days, start/end dates, launch-date toggle, and replacement warning. Apply is refused for invalid graphs, zero-node sandboxes, non-draft snapshots, active phase blockers, actual phase dates, or active statuses including `in_progress`, `done`, and `delayed`; skipped phases without actual dates can be replaced and are shown in the warning. Successful Apply deletes untouched not-started/skipped phases, creates new phases from the server-computed topological schedule, optionally updates the project launch date, marks the sandbox applied/read-only, writes `planning_apply_events`, writes a `plan_applied` project change, and surfaces a plan-applied card in Timeline History. Adds migration 009, `PlanningApplyEvent`, `test_v14_build07.py`, and 16 EN/zh labels, bringing i18n parity to 791/791. No Save Template route, AI tools, multi-draft support, partial active-plan merge, or `phase_plan_changes` rows.
- **v1.4 Build 06 — Planning Sandbox Canvas Interaction Hardening.** Makes the sandbox canvas feel like a real planning workspace while keeping all mutations sandbox-only. Adds duration-based node sizing, clearer hard/soft warning chips, editable/read-only empty states, snapshot read-only handling, and a Tidy Canvas action that lays out the draft graph and persists node positions through a new bulk position route. Applied snapshots can be inspected through `?sandbox_id=...` but cannot be mutated. The route/service layer still does not add Apply, Save Template, AI behavior, migrations, or live `project_phases` writes. Adds `V14_BUILD06_EXECUTION_PLAN.md`, `test_v14_build06.py`, 9 EN/zh labels, and desktop/mobile sandbox-hardening screenshots; i18n parity is 775/775.
- **v1.4 Build 05 — Planning Sandbox Connect Nodes.** Adds sandbox-only dependency edge editing without touching the live Timeline. PM/admin users can define prerequisites through the node property panel's Depends On multi-select, replace a node's incoming dependencies, create/delete dependency edges through JSON routes, and see the canvas/schedule refresh from the server payload. The service layer rejects self-dependencies, cross-sandbox edges, missing nodes, and circular dependencies before commit; duplicate edge creation is idempotent, and multiple parents are supported. Viewers can inspect dependency arrows but cannot mutate them. No Apply route, Save Template route, migration, AI tools, auto-layout, or `project_phases` mutation. Adds `V14_BUILD05_EXECUTION_PLAN.md`, `test_v14_build05.py`, and 8 EN/zh labels, bringing i18n parity to 766/766.
- **v1.4 Build 04 — Planning Sandbox Module Palette + Add/Edit Nodes.** Turns the sandbox canvas from read-only preview into the first draft editor while preserving the draft/apply boundary. PM/admin users can add nodes from the active module library, drag modules onto the canvas, select nodes, edit title/duration/owner/deliverable/exit criteria through a property panel, persist node positions, and delete draft nodes with attached sandbox-only edges. All mutation routes include `{sandbox_id}` and return JSON `{ok, sandbox_payload}` so the canvas and schedule summary refresh from server-derived data. Viewers see the module library as read-only inventory with Add/Save/Delete affordances hidden. No edge creation, dependency editing, Apply route, Save Template route, AI tools, migration, or `project_phases` mutation. Adds `V14_BUILD04_EXECUTION_PLAN.md`, `test_v14_build04.py`, and cache-busts `planning_sandbox.js`.
- **v1.3 UI-R4 — Timeline History event feed polish.** Reworks the existing Timeline Updates / History section into a more intentional audit feed without changing its derived data model. Filter chips now behave and render as app-native segmented controls with synchronized `aria-selected` state. Events now render as bordered feed cards with type icons, timestamp, bucket/subtype badges, optional AI badge, summary, details, actor/meta, and stable View links. Empty and no-match states are styled as deliberate feed states. Adds `test_v13_ui_r4.py`, which creates a small fixture project, proves filter behavior still works against the same event data, checks desktop/mobile computed layout, verifies no horizontal overflow, and saves history feed screenshots.
- **v1.3 UI-R3 — AI composer overlap fix + collapsible bottom dock.** The bottom assistant composer is still expanded by default, but now has a compact collapse button and a small `AI` restore affordance. Collapsing moves the full composer out of the PM workspace without clearing draft text, mode, scope, or attachments. Expanded and collapsed dock states reserve appropriate page space so Timeline Command Center actions remain visible/clickable instead of sitting underneath the composer. Mobile dock layout now wraps into readable rows instead of squeezing the textarea into a narrow vertical strip. Adds `test_v13_ui_r3.py`, which proves default expanded state, no overlap with `.timeline-action-row`, clickable Finish Current Phase, collapse/restore behavior, draft/mode/scope preservation, and desktop/small viewport screenshots.
- **v1.3 UI-R2 — Timeline Command Dashboard rescue.** Reworks the Timeline first fold into a coherent command dashboard card instead of a vertical list: dashboard header, horizontal phase strip, current phase / next action / deadline tiles, blocker + assistant suggestion support row, and action row in the same card. The old planned/actual table is relabeled as a secondary Timeline Map. Removes user-facing raw placeholder copy from the assistant suggestion panel while keeping the `data-placeholder="ai-nudge"` regression hook. Timeline workspace tabs now target `#timeline-command-center` while preserving old `#timeline` hash activation. Adds `test_v13_ui_r2.py`, which proves the dashboard card/grid/flex layout with Playwright, checks i18n parity, confirms the Finish Current Phase action remains available, and saves desktop/mobile dashboard screenshots.
- **v1.3 UI-R1 — Static asset cache-busting for Timeline rescue.** Pauses v1.4 continuation and begins the v1.3 UI Rescue. First-party CSS/JS now render with a `STATIC_ASSET_VERSION` query derived from runtime version/date plus static file mtimes, reducing stale browser asset risk after deploys. Adds `test_v13_ui_r1.py`, which proves rendered HTML includes versioned asset URLs and Playwright-computed Timeline CSS is actually applied (`.timeline-phase-strip` flex row, `.timeline-tiles-grid` grid, history chips styled). No Timeline redesign yet; UI-R2 is the command dashboard rescue.
- **v1.4 Build 03 — Planning Sandbox Static Canvas Renderer.** Adds the first project-facing Planning Sandbox page at `/projects/{project_id}/sandbox` plus a guarded `POST /projects/{project_id}/sandbox/create` flow. PM/admin users can create one draft sandbox from a blank canvas or clone an active system template; repeated creates reuse the existing draft to avoid duplicate sandboxes. The page renders a read-only Cytoscape preview using server-provided node/edge elements and the Build 02 schedule estimate, with node list, warning strip, template picker, and EN/zh i18n. Cytoscape is lazy-loaded only on the sandbox page. No drag/drop editing, no node/edge mutation routes, no Apply behavior, no live `project_phases` mutation, and no AI tools yet.
- **v1.4 Build 02 — Planning Sandbox Schedule Engine.** Adds `crud.compute_sandbox_schedule(...)`, a read-only server-authoritative DAG scheduler for sandbox graphs. It computes earliest start/end days, total duration, topological order, terminal nodes, and connected component count. Hard validation covers missing sandbox, zero-node apply validation, missing title, invalid duration, dangling edge, cross-sandbox edge, and cycles. Soft warnings cover disconnected branches, very long durations, terminal-not-launch-like flows, packaging before design, production before sample/review, and missing owner/deliverable/exit criteria. No UI, routes, schema, Apply behavior, or `project_phases` mutation.
- **v1.4 Build 01 — Planning Sandbox Schema + Module Library.** First implementation slice for the visual Planning Sandbox. Adds the isolated graph foundation only: SQLAlchemy models and idempotent migrations for `planning_module_library`, `planning_sandboxes`, `planning_sandbox_nodes`, `planning_sandbox_edges`, `planning_templates`, `planning_template_nodes`, and `planning_template_edges`. Seeds 24 reusable knife-development planning modules and 6 system workflow templates (Simple OEM Knife, Standard Folding Knife, New Mechanism Knife, Gift Set / Combo Pack, Packaging-heavy Retail Product, Amazon Launch Product). Adds read-only admin inspection at `/admin/modules` plus small admin nav link. No canvas route, no schedule engine, no Apply behavior, no AI tools, and no `project_phases` schema change. v1.3 regression migration-count assertions were relaxed to preserve v1.3 migration IDs while allowing legitimate v1.4 additive migrations.

## v1.3.0 — Project Detail Command Center
_2026-06-06_

The v1.3.0 release turns Project Detail from a database-style record page into a daily PM command center. 10 plan-first builds shipped: 9 visible features + 1 design-lock for v1.4 Planning Sandbox + 1 cross-cutting fix for the Railway project-delete bug.

The Project Detail page splits cleanly into **Overview** workspace (product concept, renderings, variants, files) and **Timeline** workspace (Command Center, Detailed Table, History) — each tuned for the daily PM workflow. Two new schema additions (migration 005 structured variant specs, migration 006 first-class blocker model). i18n bundle locked at 714/714 EN/zh parity (up from 651/651 at v1.3 Build 06 start). Every build in the series followed the plan-first execution pattern with a dedicated `V13_BUILD0N_EXECUTION_PLAN.md` reviewed and committed before code landed.

Per-build entries (chronological — preserved verbatim from the Unreleased rollup):

- **v1.3 Build 10 — Legacy Change Log viewer leak fix + v1.3.0 release hardening.** Build 13's `#changes` (legacy Change Log section, distinct from Build 08's Timeline History) rendered `event_note` audit rows to viewers with summaries like `"Journal entry added: '{first 80 chars of journal text}'"` — leaking journal body content to viewers who cannot view the source journal entry (gated on `can_view_journal`). Build 08 fixed this in its own History feed but deferred the legacy section's fix per Lock 11 scope discipline. Build 10 closes the leak: 3-line patch in `project_detail.html` skips journal-mirror event_notes when `not can_view_journal`, mirroring Build 08's rule. End-to-end smoke-tested: viewer page no longer shows journal content in the Change Log; admin/PM continue to see everything. Plus version bump to v1.3.0, VERSION.md narrative for v1.3.0, MASTERPLAN.md ship status, test_v13_build10.py release-proof regression, and a relaxed `test_build_v121.py` CURRENT_VERSION assertion that survives v1.3+ while preserving every v1.2.1 release marker.

- **v1.3 Build 09 amended again — Codex's V14 implementation plan folded in (still design-only).** Codex produced an independent v1.4 implementation plan (`V14_PLANNING_SANDBOX_IMPLEMENTATION_PLAN.md`) that strongly agrees with Amendment 1's load-bearing locks (visual canvas, draft/apply separation, server-authoritative graph, explicit Apply, no live mutation before Apply, 4 height bins, top-to-bottom orientation, finish_to_start-only edges, one sandbox per project). It adds engineering rigor in 15 specific places — all folded into the doc in this second amendment. Build 09 still ships zero code; only the design lock is refined. Key additions: (1) **Apply precondition expanded** — Codex caught that an `active ProjectBlocker` attached to an existing phase should also refuse Apply (an open blocker means the team has flagged the plan as in-flight discussion). Now 4 precondition checks instead of 3. (2) **10-step Apply transaction** explicitly enumerated (recompute → open tx → re-check preconditions → delete untouched phases → create new phases → set planned dates → optional launch update → mark applied → audit row → write_change → commit). (3) **6-field Apply confirm modal spec** (node count, total days, planned start [default today], computed end, "update launch date?" toggle, replacement warning listing phase names to be deleted). (4) **Semantic soft warnings** (packaging-before-design, production-before-sample, terminal-not-launch-like, very-long-duration, missing owner/deliverable/exit-criteria) — much richer than my original generic warning list. (5) **"Edge crosses sandbox boundary" as a new hard error** for data-integrity protection. (6) **Concrete route URL list** — every POST endpoint specified by path (`/sandbox/{id}/nodes/{id}/position` etc.). (7) **12+ service-helper enumeration** for `app/crud.py` (now actually 14 once `update_node_position` and `validate_sandbox_for_apply` were broken out). (8) **Mobile guidance** — canvas horizontal scroll, 44×44 touch targets, library/property panel as slide-in drawer, Playwright screenshots at 390×844 + 768×1024. (9) **v1.4 sub-build sequence expanded from 8 to 9** — new **v1.4-06 "Canvas Interaction Hardening"** slice (Tidy + duration bins + warning banner + read-only applied-snapshot enforcement) inserted between Connect Nodes and Apply; new **v1.4-09 "Release Hardening"** slice at the end (version bump + scenario contract runner + roll-up regression). (10) **Schema additions** — `phase_type` carried to `planning_sandbox_nodes` (Apply needs it for ProjectPhase.phase_type), `created_at`/`updated_at` on `planning_module_library`, `updated_project_planned_launch_date` boolean on `planning_apply_events`. (11) **Explicit sandbox lifecycle** — draft / applied / archived, enforced via partial unique index `WHERE status='draft'`; applied/archived snapshots remain readable for forensic review. (12) **AI_TOOLS_REGISTRY.md must be updated before v1.4 release** documenting the 3 implemented + 2 deferred sandbox AI tools. NOT folded in: Codex left canvas library choice open; Amendment 1's Cytoscape.js + cytoscape-dagre lock stays. test_v13_build09.py target raised from 56 to **99/99 PASS** covering both amendment notes + Codex's 15 additions + the original design-only invariants. Regression: v1.3 Builds 01-08 all green; `test_build_v121` 19/19; delete-fix regression 17/17.

- **v1.3 Build 09 amended — engineering response to the Planning Sandbox PRD (still design-only).** The original Build 09 doc shipped at `fc064a6` targeted a form-based editor with sandbox state persisted directly on the project. After PRD review (the ChatGPT-shaped product spec the user pasted), the user clarified the actual product is a **visual workflow canvas with explicit draft/apply separation** — closer to XMind/Miro than a form editor. Two of the original doc's load-bearing locks were wrong for the real product: Q3 specced form-based "number input + multi-select for depends_on" UI, and Q4 explicitly REJECTED a separate sandbox table in favor of "persisted on the project itself." This amendment rewrites `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md` as the **engineering response to the PRD** (PRD captured verbatim as Appendix A). Build 09 still ships zero code, zero schema, zero migrations, zero UI, zero AI tools — the deliverable is the corrected design lock. Key locked decisions in the amended doc: (1) **visual canvas + draft/apply separation** as non-negotiable invariants ("Sandbox edits never mutate live phases"). (2) **Cytoscape.js + cytoscape-dagre** chosen as the canvas-rendering library (React Flow rejected for forcing React into a Jinja2 codebase; D3 + bespoke SVG rejected as too low-level). (3) **All 10 PRD §28 open questions locked with rationale** — start blank OR template, replace draft only on Apply (refuse if any phase has actual_start_date), server-side schedule source-of-truth with optimistic client mirror, manual node positioning + one-click "Tidy" auto-layout, both drag-handle and property-panel edge creation, 4 discrete node-height bins (S/M/L/XL), disconnected branches allowed with soft warning, sandbox permissions inherit project permissions, one sandbox per project (UNIQUE constraint), global templates with ownership. (4) **7-table schema sketch** spanning 4 v1.4 migrations: `planning_module_library`, `planning_sandboxes`, `planning_sandbox_nodes`, `planning_sandbox_edges` (migration 007); `planning_apply_events` (migration 009); `planning_templates` + `planning_template_nodes` + `planning_template_edges` (migration 010). Templates stored in their own tables, not as `is_template=true` sandboxes — because `project_id` is NULL for templates and mixing forces every sandbox query to filter. (5) **v1.4 sub-build sequence expanded from 4 to 8 builds** to match true visual canvas complexity: schema → schedule engine → static renderer → drag-to-add → connect nodes (cycle detection) → property panel → Apply → Save-as-template. (6) **Backend Honesty Mapping** covers every visible canvas element (node / edge / module-library item / property edit / schedule estimate / Apply button / Save-as-template button / template picker / cycle warning / disconnected-branch warning / Plan Applied event in Timeline History) → source-of-truth table + write path + derived rule + permission rule + planned test coverage. (7) **Risk register** identifies 5 top risks for v1.4 implementation with mitigations: cycle-detection-in-canvas UX bugs, silent Apply overwriting a started project (Q2 lock mitigation), schedule engine edge cases, Cytoscape bundle size (lazy-load), permission edge cases. `test_v13_build09.py` rewritten — 56/56 PASS — asserts amendment note + PRD appendix presence + 7 PRD section markers + visual canvas + draft/apply phrasing + Cytoscape lock + 10 Q&A markers + 8 sub-builds + zero old "v1.4 Build 01-04" naming + 7-table schema + 4-migration plan + 6 PRD-named templates + Backend Honesty Mapping + Risk register + amendment row in Decision log + design-only invariants (migration count 6, i18n parity 714/714, no sandbox tables in DB, no Planning Sandbox AI tools). Regression: v1.3 Builds 01-08 all green; `test_build_v121` 19/19; delete-fix regression 17/17.

- **v1.3 Build 09 — Planning Sandbox Design (design-only).** Ships one comprehensive markdown design lock at `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md` and a single regression-guard test file. Zero code, zero schema, zero migration, zero UI, zero AI tools — per masterplan §"Non-Negotiable Product Decisions" → *"Planning Sandbox is design-only in initial v1.3."* User confirmed Interpretation A (2026-06-06): keep Build 09 as design-only, do not enlarge v1.3 mid-stream. The design doc locks all 8 user-specified sections: (1) purpose of the Planning Sandbox + what it is NOT (not a Gantt chart, not PM software, not a resource scheduler); (2) the 6 template types (Simple OEM Knife / Standard Folding Knife / New Mechanism Knife / Gift Set / Packaging-heavy Retail Product / Amazon Launch Product) with approximate phase counts and durations; (3) the Module model with 11 per-module fields (id, name, phase_type, order, default_duration_days, default_owner_role, can_overlap, overlap_group, depends_on, deliverable, exit_criteria); (4) dependency/overlap concepts including hard `depends_on` DAG + soft `overlap_group` parallel-run rule, plus an explicit list of what is NOT modeled (partial deps, lag time, resource constraints, probabilistic durations); (5) estimated launch date math via topological sort + per-phase earliest-start/end + overlap-group snapping + max(launch-phase earliest_end); (6) save-current-as-template flow with permission rules and explicit non-versioning decision; (7) six open schema decisions (Q1 DB rows vs config, Q2 join table vs JSON, Q3 copy-down vs FK, Q4 persisted vs ephemeral sandbox state, Q5 AI tool surface, Q6 Python DAG vs SQL CTE) each with recommendation + rationale; (8) the recommended v1.4 implementation sequence — 4 sub-builds (template data model + seed → apply-template flow → sandbox UI → save-as-template) with risk labels low/medium/high/low. `test_v13_build09.py` 31/31 enforces the design-only invariant: design doc exists + all 8 sections + all 6 templates + all 6 schema decisions + 4 v1.4 sub-builds + zero migration drift + zero i18n drift + zero new tables + zero new AI tools + dated decision log entry. Regression: v1.3 Builds 01-08 all green; `test_build_v121` 19/19; i18n parity unchanged at 714/714; migration count unchanged at 6.

- **v1.3 Build 08 — Timeline Updates / History (derived view).** New `#timeline-history` section at the bottom of the Timeline workspace gives PMs a chronological "what happened and why" feed. Pure derivation over existing tables — `project_changes` + `phase_plan_changes` + `project_journal_entries` — no new schema, no migration. Single helper `crud.get_timeline_events(db, project_id, limit=200, viewer=False)` merges the 3 sources and normalizes each row into a TimelineEvent dict with `source_table` + `source_id` (every event traces to exactly one source row per ChatGPT amendment). Six filter chips (All / Delays / Decisions / Blockers / Phase Changes / Files+Renderings) match the canonical doc exactly; client-side CSS toggle (no round-trip per click); applies to the full loaded 200-event array, not just the first 50 visible (Lock 5). Lock 2: every event has one primary bucket from the 6 chips — no orphans hidden under "All only." Subtypes (Sample / Rendering / Packaging / Cost) are display-only overlay badges, not buckets. AI overlay badge (`bi-robot`) fires when `source_type='ai_chat'` OR `changed_by='ai'` — independent of bucket (Lock 6). Lock 7: deterministic tiebreaker on `occurred_at` ties — sort by `(source_priority, source_id DESC)` where source_priority is 1=project_changes, 2=phase_plan_changes, 3=project_journal_entries. Lock 3: viewer permission filtering removes restricted events entirely (cost field_updates, sensitive `factory_feedback`/`quotation` file uploads, journal-mirror event_note rows whose summary begins with "Journal entry added:", and all journal-sourced rows); `viewer_hidden_count` returned alongside the visible list so the template can render empty-state case 3. Lock 10: anchor links are best-effort — `link_anchor` set to None when target is permission-hidden (e.g., `#journal` for viewer) or DOM-missing; template conditionally renders. Three explicit empty states: "No events yet for this project." (zero-event); "No events match this filter." + "← Back to All" affordance (filter yields zero, JS-toggled); "Some recent updates are not visible to your role." (viewer's permission filter hides everything). Default 50 visible · "Show more (N)" reveals up to 200 (Lock 4). Layout: filter chips + numbered list + per-event row with timestamp, bucket badge, optional subtype badge, optional AI badge, title, optional body, actor, optional View link anchor. Mobile breakpoint stacks the row head + meta lines. Build 06/07A/07B layout invariants preserved. 26 new i18n keys (Build 08 history strings); parity at **714/714**. test_v13_build08.py 55/55 covers helper-level (shape + ordering + all 3 source tables + bucket coverage + classification + viewer filter + source_id traceability + deterministic ordering + Lock 10 graceful fallback), template-level (section + 6 chips + event rows + bucket/subtype/AI badges + anchor targets + 3 empty states + Show More gate + viewer scoped to History section), regression (all v1.3 Builds 01-07B + v1.2.1). Lock 11 scope discipline honored: no AI summaries, no semantic re-classification, no edit-from-history, no CSV export, no cross-project feed, no date-range picker, no cursor pagination beyond 200, no email digest. Discovered + intentionally deferred: the legacy Build 13 Change Log section (`#changes`) renders journal-mirror event_note rows to viewers without filtering them — that's pre-existing behavior and out of Build 08 scope per Lock 11; Build 08 hides those rows specifically in its new History feed.

- **v1.3 Build 07B — Project Blockers (first-class lifecycle model + Command Center wiring).** Promotes "blocker" from narrative concept to a real table with active / resolved lifecycle. New `project_blockers` table (migration 006, idempotent CREATE TABLE IF NOT EXISTS + 2 indexes): 11 columns including project_id, optional phase_id (Lock 3 — must belong to same project; project-level blockers do NOT light up any phase strip block), title, optional description, severity (low / medium / high default medium), status (active / resolved default active), created_at, created_by_user_id, resolved_at, resolved_by_user_id. Six new crud helpers (`create_blocker / update_blocker / resolve_blocker / get_active_blockers_for_project / get_blockers_by_phase / get_active_phase_blocker_ids`). Each mutating helper writes a `project_changes` audit row with `change_type` of `blocker_opened` / `blocker_updated` / `blocker_resolved` (Lock 6 audit explicit). Three new dedicated POST routes — `/command/add-blocker`, `/command/edit-blocker`, `/command/resolve-blocker` — each re-validates auth + `can_edit_project` server-side and redirects via PRG with `?cc_action=...&cc_result=...#timeline-command-center`. Template: Build 06 placeholder block replaced with honest tile that shows newest active blocker + severity chip (Low/Medium/High color-coded) + opened-meta line + Resolve + Edit buttons; when `count_active > 1` a small `+N more active` text badge appears (Lock 4 — no expanded `<details>` list; full list lands in Build 08 Timeline History). Empty state renders "No active blockers." with an enabled `[Add Blocker]` form trigger (replaces the Build 07A disabled placeholder). Add Blocker form panel inside the existing `#cc-action-form` mount (4 fields: title required, description optional, severity select default medium, phase select optional with "— Project-wide —" first option). Edit Blocker form panel JS-prefilled from the [Edit] button's data-blocker-* attrs. Pulse cascade gains a new FIRST branch (Lock 5): when ≥1 active blocker exists, Pulse renders "Resolve blocker: '{title}'" — beats delay/thesis/missing-field. Phase strip blocks for phases with ≥1 active phase-linked blocker carry `data-blocker="active"` + a red dot. Add Blocker form gets Build 07A's `data-cc-disable-on-submit` JS (Lock 8 carried over). AI tools: 3 new schemas (`create_blocker / update_blocker / resolve_blocker`) all in `CONFIRMATION_TOOLS` (Lock 9 — no exceptions); `UPDATE_BLOCKER_ALLOWED = {title, description, severity, phase_id}`; relationship checks reject wrong-project blocker_id with `forbidden` and wrong-project phase_id with `phase_not_found`. `delete_blocker` is NOT exposed to AI (admin-only UI path; matches `delete_variant` pattern). 24 new i18n keys − 2 removed (Build 07A's btn_add_blocker_disabled + btn_add_blocker_tooltip strings) = net +22; parity at 688/688. test_v13_build07b.py 66/66 covers migration + model + i18n + crud (create / update with whitelist / resolve with audit + Lock 3 phase mismatch) + query helpers + template (active tile + +N more badge + empty state + phase-strip dot only for phase-linked blockers) + routes (happy paths + 3 validation rejections + viewer + cross-project) + Pulse cascade Lock 5 (blocker beats delay) + AI tools (schemas + confirmation gating + no delete_blocker + dispatcher confirmed=False vs True) + Build 06/07A invariants. Build 06 test updated for the honest tile + enabled Add Blocker button + key churn. Build 07A test updated for the removed tooltip key + new blocker-tile marker. test_ai_e2e.py TOOL_SCHEMAS count assertion loosened to `>= 20`. No scope creep per Lock 10: no project health engine, no SLA timers, no proactive AI blocker proposal, no recently-resolved section, no `+N more` expanded list, no blocker comments.

- **v1.3 Build 07A — Timeline Command Center Actions Backend.** The three honest Command Center actions (Finish Current Phase, Adjust Due Date, Add Update) now move real backend state through dedicated POST routes. `POST /projects/{pid}/command/finish-phase` re-derives the project's current phase server-side and rejects stale form submissions where `request.phase_id != current_phase.id` (Lock 3 — protects against the race where two PMs / a PM + the Detailed Table flow attempt to finish the same phase). `POST /projects/{pid}/command/adjust-due-date` enforces a non-empty reason server-side (Lock 4), matching the Detailed Table reason-required behavior; delegates to `crud.update_phase` which writes `phase_plan_changes` + `project_changes` and re-runs `recalculate_stage_and_delay()`. `POST /projects/{pid}/command/add-update` is gated on `can_view_journal AND can_edit_project` (viewer cannot POST even if they craft a request); delegates to `crud.create_journal_entry` with author_user_id. All three redirect to `/projects/{pid}?cc_action=...&cc_result=...#timeline-command-center`; the Command Center renders a dismissible result banner (`ok` green / 4 error codes red). Buttons now toggle inline forms inside a shared `<div id="cc-action-form">` mount (Lock 1 — keeps phase strip + tiles in view, no modal); Cancel hides the mount. Finish form shows a 3-line pre-flight checklist (current phase name, started date or backfill warning, owner or "Not assigned"). Adjust form pre-fills current `planned_end_date` and requires reason. Add Update form has a 9-option entry_type select. Add Update's submit button additionally disables on first click with a spinner (Lock 7 amendment — UX belt-and-suspenders against duplicate journal entries; no server-side token). Add Blocker remains a disabled placeholder; tooltip updated to "Coming Build 07B — needs Architecture Review for blocker model". AI Intake button unchanged from Build 06 (opens existing assistant side panel). NO schema, service, migration, or AI-tool change — all 3 routes call existing services. 15 new i18n keys + 1 updated tooltip; EN/zh parity at 666/666. test_v13_build07.py 57/57 covers all 3 routes (happy path / stale-race / empty-reason / empty-text / viewer / non-owner-PM), result banner rendering, Detailed Table edit/finish regression, and all Build 06 layout invariants. Build 06's test updated to accept Build 07A's form-trigger button pattern in place of the original anchor href.

- **v1.3 Build 06 — Timeline Command Center Shell (display-only).** The Timeline tab opens to a new `#timeline-command-center` section above the legacy planned/actual table. Display + visual structure only — action wiring is Build 07. Phase strip renders Done / Current / Next / Skipped / Later states per phase (horizontal-scroll on narrow widths). 3-tile grid: Current Phase (name + health badge + started date), Next Action (current phase forward + owner / "Not assigned"), Deadline (due date + days-left/overdue badge + pressure dots). Health bands are deterministic per Lock 3 (`on_track` / `at_risk` ≤3 days_late / `delayed` >3 / `not_scheduled` for unscheduled not-started current phase). Days badges follow Lock 4 (red overdue / amber ≤7 / neutral >7). Pressure dots follow Lock 5 (3 red if overdue / 2 amber ≤3 / 1 amber ≤7). Main blocker and AI Nudge render as EXPLICIT placeholders with "coming Build 07" labels — no fake intelligence per the canonical doc §1.5. Action buttons (Finish Current Phase / Adjust Due Date / Add Update / Add Blocker disabled / Open AI Intake) link to existing Detailed Table controls via `#phase-row-{id}` anchors with auto-expand JS. Existing `timeline-table-v2` markup wrapped in `<details id="timelineDetailedTable">` "Detailed Table" summary, collapsed by default. Phase `<tr>` rows now carry `id="phase-row-{phase.id}"` for anchor navigation. Permissions: admin/PM see all 5 buttons; viewer sees none (`can_use_ai_intake` is admin/pm only); all roles see the phase strip + tiles + placeholders. NO schema, service, migration, or AI-tool change — `command_center_state` derived in one O(N) pass over the phases already loaded by the project_detail route. Plan committed at `75db65c` includes a full Backend Honesty Mapping (16 rows: 13 honest fields + 3 explicit placeholders). 31 new i18n keys with EN/zh parity at 651/651. test_v13_build06.py 59/59. Build 01's Playwright regression updated to expand the Detailed Table before clicking phase-edit (planned behavior change, no behavior regression).

- **v1.3 Build 05B — Structured Variant Specs.** Adds 6 new nullable columns on `project_variants` matching the Overview redesign wireframe (§5.4-5.7) without redesigning the Build 05 card layout: `sales_format` (single / combo / colorway / packaging_variant / retail / amazon / other), `packaging_cost` (separate from factory cost), and four per-section narrative columns: `blade_summary`, `handle_summary`, `mechanism_summary`, `dimensions_summary`. Migration 005 is additive + idempotent. Sales Format renders as a chip in the collapsed summary; the expanded Specs cell now shows 4 labeled sub-sections (Blade / Handle / Mechanism / Dimensions); the Pricing cell adds a Packaging Cost row (gated on `can_view_costs`). Existing `material_summary` / `size_color_summary` / `packaging_summary` columns are NOT removed; their content now renders inside a collapsible "Legacy notes" details element so existing data isn't lost. Add + Edit forms gain 6 new inputs with format-suggesting placeholders ("Steel: VG-10; Length: 3.5\""...). AI tool registry extended: `create_variant` tool schema declares all 6 new optional fields; `UPDATE_VARIANT_ALLOWED` whitelist includes them. Naive margin computation in the Profit cell remains `target_msrp - target_factory_cost` (packaging_cost NOT subtracted — that's a v1.4 real-profit-model concern). 16 new i18n keys with EN/zh parity at 620/620.

- **v1.3 Build 05 — Variant Command Cards.** Variants render as expandable `<details>` cards inside the existing `#variants` section. Collapsed summary shows variant name + Primary badge + SKU + status badge + (cost/MSRP for `can_view_costs`) + component count in `"X shared + Y for this variant"` format. Expanded body uses a 2×2 CSS grid: Specs | Packaging & Accessories above Pricing & Cost | Profit, with Notes & Actions row spanning both columns. Profit cell shows naive margin (`target_msrp − target_factory_cost`) for PM/admin when both prices are set; viewer never sees Pricing or Profit cells. First primary variant opens by default; if no primary exists, first variant opens. `#variant-N` URL anchors open the targeted card and scroll to it (JS bootstrap in main.js). Native `<details>` marker suppressed; custom `bi-chevron-right` chevron rotates 90° when open. Components grouped route-side via `components_by_variant` derived dict (no new DB query). No schema change. New file `V13_BUILD05_EXECUTION_PLAN.md` documents the 4 locked decisions + the layout-only scope (Option A) deferring structured spec schema (`sales_format`, blade/handle/mechanism fields, separate `packaging_cost`) to a future Build 05B. 19 new i18n keys with EN/zh parity locked at 604/604.

- **v1.3 Build 04 — Overview Renderings Section.** Overview now has a standalone Renderings section immediately after Product Concept, showing the latest existing rendering/prototype visual by upload time with bounded preview sizing, metadata, history links, non-image document fallback, and a disabled Designer Portal placeholder. No schema, service, new route, AI, pinning, or lightbox behavior changes.
- **v1.3 Build 01 — Workspace Shell.** Project Detail now has explicit Overview / Timeline workspaces under the project header. Overview is the default; `#timeline` opens Timeline directly. The old promoted Commercial Snapshot section is removed; created/updated dates plus project-level price estimates now live in a quiet Project Metadata section near Change Log. Existing Timeline table and phase edit modal are preserved without behavior/schema changes.
- **v1.3 Build 02 — Project Pulse v1 (rules-based).** Overview now starts with a two-column Project Pulse that summarizes current stage/status, PM/owner, sensitive team/factory facts for PM/admin, launch target, and the next suggested PM action from existing data. Actions are rules-only: delay → Timeline, missing Thesis → Thesis, other missing critical field → fill it, early no-inspiration → Inspired By, otherwise no urgent action. No schema, route, AI, or mutation changes.
- **v1.3 Build 03 — Overview Product Concept.** The old Product Thesis detail section is reframed as Product Concept with a primary `#product-concept` anchor and hidden `#thesis` compatibility anchor. Inspired By is no longer a standalone peer section; linked Ideas now render as compact internal concept-reference chips inside Product Concept, while existing Link / Create & Link / unlink modals and thesis edit/re-extract routes are preserved. Build 02 Pulse wording now points to Product Concept. No schema, route, service, or AI behavior changes.

## v1.2.1 — Workflow polish + Excel batch intake + draft delete
_2026-06-03_

A workflow-polish + onboarding-unlock release. PMs onboarding from existing Excel sheets, day-to-day PM ergonomics, and Chinese-keyboard typing all see meaningful improvements. Packages 7 patches that landed on the v1.2.0 line between 2026-06-02 and 2026-06-03.

**Onboarding + intake unlocks**

- **Excel batch intake (Build 30B).** Upload `.xlsx` / `.xlsm` / `.xls` / `.csv` portfolios; AI extracts a `projects` array preserving source-sheet provenance and pricing fidelity; per-row review table with Create / Skip / Update Existing; one click commits everything atomically via a Build 30A idempotency token.
- **PM-facing price strings.** Project Target Factory Cost and Target MSRP now preserve real-world planning expressions such as `under 120 RMB` and `$70-100` instead of forcing USD-only floats. Simple USD values still mirror into the legacy numeric columns for old displays and future profit math.

**Project workflow safety**

- **Project creation safety (Build 30A).** Server-side idempotency tokens prevent duplicate creates from slow-submit double-clicks. Blank `product_manager` defaults to the creator's username so PM-created projects land in their My Projects, not orphaned on admin. `get_projects_for_user` matches by username OR display_name for legacy rows.
- **PM draft delete (Build 30C).** PMs can now hard-delete their own projects when no phase has started (every phase still `status='not_started'` with no `actual_start_date`). Once any phase advances, the project leaves draft state and PM must use Archive instead. Admin retains unrestricted delete; viewer can delete nothing. Workflow-tied, not clock-tied.

**Day-to-day ergonomics**

- **Chinese IME chat fix (v2).** Both assistant composers (dock + side panel) now share a reusable controller with four-layer IME defense including a one-shot post-`compositionend` suppression window (`IME_CONFIRM_ENTER_SUPPRESS_MS = 80`). Chinese-keyboard typing of English fragments like `LC200N` no longer fires premature submits. 10 JSDOM behavioral cases.
- **Project detail layout refactor.** Removed the low-value left sidebar; promoted PM / Engineer / Factory / Stage / Launch into a compact header facts grid under the project title; added a full-width Commercial Snapshot section near the top.

**Ops**

- **Railway build fix (nixpacks).** `nixpacks.toml` pins `providers = ["python"]` so Nixpacks ignores the new `package.json` (which exists only for local JSDOM tests) and stops trying to run `npm install` during deploy.

**No database schema change** in this release-hardening build itself. Build 30A's `project_creation_tokens` table (migration 004) shipped with that patch and is preserved.

**Test:** `test_build_v121.py` is the release-proof regression. Full Build 20-30C suite + `test_ai_e2e.py` (15P/2S/0F baseline) must stay green. JSDOM IME suite 10/10.

## v1.2.0 — Assistant Workspace Release
_2026-06-02_

The v1.2.0 release packages Builds 26-28 plus this release-hardening build (29). It turns the AI assistant from an experimental bottom chat into a professional, project-aware workspace where every write is reviewed before it lands.

- **Professional assistant workspace** (Build 26): resizable desktop split panel, mobile full-screen pane, compact collapsed dock, panel composer, Ask / Capture and This Project / Global segmented controls, immutable conversation scope, role-filtered project context injection, project-aware Idea capture with duplicate detection and one-step Create-and-Link.
- **Confirmed daily PM actions** (Build 27): editable proposal cards in chat for journal entries, Idea actions, variants, packaging / accessory components, file comments, allowlisted project fields, reasoned phase-plan adjustments, and Finish Phase. Confirmation revalidates auth, role, ownership, allowlists, and proposal state; double-confirmed and cancelled proposals are rejected. Sensitive fields (factory, engineer, costs, MSRP, launch date, Thesis) are proposal-only. Derived `current_stage` and operational `status` remain non-writable.
- **Global read-only search** (Build 27): `search_projects` and `get_project_context` wired as immediate read-only tools. Results are role-filtered so viewers never see PM-only fields.
- **Assistant attachments** (Build 28): PDF, DOCX, PNG, JPG/JPEG, WEBP, and GIF discussion with bytes held in pending storage outside `/uploads` until the user confirms `save_pending_attachment`. PDF + DOCX text extracted locally; pending images passed to the assistant as image content. Confirmed saves move bytes through the normal audited file service with `changed_by="ai"` and `source_type="ai_chat"`. 10 MB cap and 24-hour request-time cleanup.
- **Audit + safety**: every confirmed mutation reuses existing CRUD helpers and writes change-log rows. Viewers remain read-only across the new surfaces.
- **No schema migration in Build 29**. Pending proposals live in assistant-message metadata; confirmed writes use existing tables. Deployment isolation from Build 25 is unchanged.

**Test:** `test_build29.py` is the release-proof regression. Full Build 20-28 suite + `test_ai_e2e.py` (10 passed, 7 external-AI skips, 0 failed) must stay green.

## v1.2.0-build28 — Assistant PDF, DOCX, and image intake (Build 28)
_2026-06-01_

**Goal:** let PMs discuss file-backed product evidence naturally without silently adding project files.

**Pending attachment lifecycle:**
- Adds PDF, DOCX, PNG, JPG/JPEG, WEBP, and GIF attachment controls to the compact dock and expanded assistant composer.
- Stores pending original bytes and JSON sidecars in ignored, non-public `app/pending_uploads/`.
- Extracts PDF and DOCX text locally; passes pending image bytes into the current assistant turn for visual discussion.
- Rejects unsupported extensions and inputs over 10 MB before writing; request-time cleanup removes pending inputs after 24 hours.

**Confirmed persistence:**
- Adds `save_pending_attachment(project_id, attachment_id, file_category, source_note)`.
- Project scope offers a save proposal automatically after attachment discussion, even when the external model call is unavailable.
- Global scope allows discussion without auto-targeting a project.
- Confirm and cancel reuse the Build 27 proposal lifecycle. Confirm moves original bytes through `crud.upload_file()` with `changed_by="ai"` and `source_type="ai_chat"`; cancel removes pending bytes.

**Test:** `test_build28.py` covers accepted and rejected inputs, DOCX extraction, non-public storage, cleanup, permissions, auto-proposal behavior, cancel cleanup, byte-preserving confirmed persistence, audit attribution, Global behavior, and workspace markup.

## v1.2.0-build27 — Confirmed daily PM actions + Global read-only search (Build 27)
_2026-06-01_

**Goal:** turn the assistant workspace into a trustworthy daily PM copilot while preserving explicit human control over writes.

**Proposal framework:**
- Generalized Build 26 Idea review cards into editable proposal cards for every chat-driven mutation.
- Confirmation merges only reviewed fields from the original stored proposal, then re-checks auth, project access, record relationships, allowlists, and handler validation.
- Keeps pending state in assistant-message metadata; no migration or pending-actions table.

**Daily PM actions + Global lookup:**
- Wires confirmed journal capture, Idea actions, variants, package/accessory components, file comments, allowlisted project fields, reasoned phase-plan adjustments, and Finish Phase.
- Adds immediate read-only `search_projects` and `get_project_context` tools for truthful Global conversations.
- Role-filtered lookup keeps viewer responses clear of factory, engineer, cost, and journal details.

**Audit + safety:**
- Reused CRUD helpers now accept AI attribution and write change-log rows before commit.
- Sensitive fields remain proposal-only; derived `current_stage` and operational `status` remain blocked.
- Corrected older AI-schema drift for variant statuses and component cost fields.

**Test:** `test_build27.py` covers schema parity, Global role filtering, every wired daily handler, audit attribution, relationship and ownership checks, editable HTTP confirmation, and double-confirm rejection.

## v1.2.0-build26 — Professional assistant workspace + project-aware Idea capture (Build 26)
_2026-06-01_

**Goal:** make bottom chat feel like a professional second workspace while fixing the awkward inspiration workflow.

**Assistant workspace:**
- Replaced the overlay-style expanded state with a resizable desktop split workspace and a mobile full-screen assistant pane.
- Moved the active composer into the pane and reduced the collapsed state to a compact dock.
- Replaced raw mode/scope dropdowns with Ask / Capture and This Project / Global segmented controls.
- Added immutable conversation scope: switching project/global context starts a fresh conversation after confirmation.
- Kept assistant header controls above tracker navigation so Archive, History, and Close stay reachable.

**Project-aware capture:**
- Injects role-filtered project context into project-scoped chat. Viewers do not receive factory, engineer, or cost fields.
- Adds `create_idea`, `link_idea_to_project`, and allowlisted `update_idea` handlers.
- Adds small Idea-specific review cards with Confirm / Cancel and duplicate-aware Link Existing / Create New actions.
- Adds manual **Create & Link Idea** in the project-detail Inspired By section.
- Aligns viewers with read-only Good Ideas behavior.

**Audit + safety:**
- No schema migration.
- Idea linkage and linked-Idea edits use service-layer writes and project change-log entries.
- Chat writes remain preview-confirm; Build 27 will generalize proposal cards to the broader daily PM tool set.

**Test:** `test_build26.py` covers schema parity, i18n parity, role-filtered prompt context, guarded Idea tools, audit writes, duplicate matching, HTTP proposal lifecycle, immutable scope, manual Create & Link, workspace markup, and viewer restrictions.

## v1.1.0-build25 — Beauty Department isolated deployment (Build 25)
_2026-05-30_

**Goal:** unblock the Beauty department's adoption of the tracker without disrupting the existing PM department's data. Architectural review (recorded in `~/.claude/plans/can-you-still-find-nested-cook.md`) chose **separate-deployment-per-department** (multi-tenancy Option 4) over row-level multi-tenancy: hard isolation, zero code-change risk, ships in hours of devops work. The trade-off (no cross-department views) is acceptable since none are planned.

**Code changes: none.** Per-instance isolation comes for free from existing patterns:
- `app/database.py` reads `DATABASE_URL` from env (Railway PostgreSQL plugin auto-provides it).
- `app/main.py:_bootstrap_admin_from_env()` (shipped in Build 9) lets each instance bootstrap its own first admin from env vars.
- `OPENAI_API_KEY` is read from env, so each instance can have its own.

**New file: `DEPLOYMENT.md`** at the project root — canonical runbook covering Railway service creation, PostgreSQL plugin attachment, per-instance env vars (`INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_PASSWORD`, `OPENAI_API_KEY`, `SECRET_KEY`, `DISABLE_RELOAD`), custom domain CNAME setup (subdomain convention: `pm.tracker.example.com`, `beauty.tracker.example.com`), 5-step post-deploy verification checklist (health check, version string, first admin login, cross-instance isolation check, bootstrap-cleanup), and multi-instance operating guidance (migrations, backups, code changes, user accounts, OpenAI spend, file uploads).

**Bumps:**
- `app/version.py` → `1.1.0-build25`
- `VERSION.md` → "What's new" block at top.
- `MASTERPLAN.md` → Build 25 detail section (FDR + scope + verification).

**Test — `test_build25.py`** verifies what Claude can verify remotely:
- `DEPLOYMENT.md` exists at project root with the required runbook sections.
- `app/version.py` is bumped to `1.1.0-build25` with the right build name.
- `VERSION.md` has a `v1.1.0-build25` "What's new" block.
- `CHANGELOG.md` has a Build 25 entry.
- The existing v1.1.0 PM instance still passes its health check and serves the bumped version string.

The actual Railway provisioning is on the user (Claude can't reach into your Railway account); the runbook is the deliverable.

**Out of scope (deferred to v1.2 if needed):** cross-department views, shared Good Ideas board, org-wide AI search, SSO across departments, per-department branding, auto-provisioning script. All of these would require row-level multi-tenancy (Option 1) — a v1.2-scoped conversation.

**Files created:** `DEPLOYMENT.md`, `test_build25.py`

**Files modified:** `app/version.py`, `VERSION.md`, `MASTERPLAN.md`, `CHANGELOG.md`, `CURRENT_TASK.md`

## v1.1.0 — Product Development Workspace Release (Build 24)
_2026-05-30_

**Goal:** close the v1.1.0 roadmap with a final release bump, consolidated user documentation, and a release-level regression test.

**Release theme:** the app is now a product development workspace rather than only a static project database. v1.1.0 adds daily PM workflows around project memory, thesis extraction, SKU/packaging detail, timeline reality, visual iteration, and AI-assisted capture.

**Major features included across v1.1.0:**
- **Governance + migration foundation** — canonical runtime version source, product/AI working rules, idempotent migration infrastructure, and additive schema for v1.1 data.
- **Project Journal** — internal PM/admin project notes with AI summary support; viewers cannot access journal content.
- **Business Plan Upload + Thesis Extraction** — AI proposes Product Thesis text and inspiration links from uploaded plans; users preview, edit, and confirm before data is written.
- **Variants, Packaging, Quotation, and Profit Model placeholder** — multi-SKU tracking, package/accessory components, quotation file surfacing, and the intended profit formula documented for the future full model.
- **Timeline 2.0** — Plan / Reality columns, required reason capture for planned-date changes, plan-change history, and Finish Phase workflow.
- **Rendering History + Prototype Photos** — dedicated visual iteration sections, per-file comments, latest rendering thumbnails on project cards.
- **My Projects + project memory** — focused PM/admin project list, delay-only attention banner, and browser-side last-opened project memory.
- **AI tools architecture + Bottom AI Chat** — OpenAI tool schemas, security-first dispatcher, viewer permission guard checks before model calls, persistent chat threads, and wired `create_journal_entry`.
- **AI-Assisted Create Project** — manual and AI-assisted create flows consolidated into `/projects/new`, with `/ai/intake` preserved as a redirect.
- **Chinese i18n** — EN / 中文 switcher with durable preference, cookie fallback for logged-out visitors, broad first-pass translation coverage of primary user-facing screens, and exact English/Chinese bundle parity.

**Build 24 changes:**
- `app/version.py` bumped to final `1.1.0`.
- `VERSION.md` now carries a consolidated "What's new in v1.1.0" release summary.
- `USER_GUIDE.md` now has a short Chinese summary plus English sections for all v1.1 features and the intended Profit Model formula.
- `MASTERPLAN.md` marks Build 24 shipped.
- `test_build24.py` added release-doc/version checks and regression inventory checks.

**No schema migration in Build 24.** This build changes only docs, version metadata, and tests.

## v1.1.0-build23 — Chinese i18n (Build 23)
_2026-05-30_

**Goal:** ship a Chinese UI option for the PM tracker. The architecture has been ready since Build 13 (which added `users.language` with default `"en"`); Build 23 is the actual translation layer + switcher.

**New module `app/i18n`** (Python package):
- `app/i18n/__init__.py` — `TRANSLATIONS` dict loaded from JSON bundles; `t(key, **kwargs)` Jinja2 `pass_context` global; `get_locale(request, current_user)` helper.
- `app/i18n/en.json` and `app/i18n/zh.json` — 520 keys each, dot-namespaced by area (`nav.*`, `title.*`, `section.*`, `btn.*`, `form.*`, `badge.*`, `status.*`, `filter.*`, `alert.*`, `empty.*`, `chat.*`, `idea_*`, `timeline.*`, `files.*`, `journal.*`, `variant.*`, `component.*`, `profit.*`, `common.*`).
- Locale resolution: authenticated `users.language` → `lang` cookie → `"en"`. No `Accept-Language` header (per agreed plan).
- Fail-safe: missing key returns literal key string, missing locale falls back to en, format errors return the raw template. **Pages never 500 on i18n issues.**

**New route `POST /lang/set`** (`app/routes/i18n.py`):
- Accepts a `lang` form value; silently falls back to `"en"` if not in `SUPPORTED_LOCALES`.
- Sets `lang` cookie (1-year, samesite=lax).
- For authenticated users, also persists to `users.language` (durable across browser/cookie clears).
- 303 redirect back to the `next` form value (sanitized to local paths only).

**Switcher UI** — new partial `app/templates/components/lang_switcher.html`. Two small `EN | 中文` buttons in the navbar (visible to everyone). Active locale is styled distinctly. POSTs to `/lang/set` with `next=<current path>` so users stay on the same page after switching.

**Template sweep — primary surfaces translated:**
- `base.html` — navbar links, Help button, Sign Out button.
- Auth pages — login/register labels, buttons, helper copy, and emergency reset labels.
- `projects_list.html` / `my_projects.html` — page titles, counts, filters, table headers, badges, empty states, and primary actions.
- `project_form.html` — page title, both tab labels (Manual / AI), section headers, form labels, required/critical/recommended badges, prototype controls, Thesis help, Cancel / Save / Create buttons.
- `project_detail.html` — sidebar labels, Product Thesis controls, Inspired By, Timeline table/modals, Files & Renderings, Change Log, and file upload labels.
- Detail sub-components — Project Journal, Variants, Packaging & Accessories, Quotation Files, Profit Model placeholder, Rendering History, Prototype Photos.
- Calendar and Good Ideas board/form pages.
- AI-assisted create panel — paste/upload states, review/confirm forms, classification banner, status copy, and actions.
- `components/bottom_chat.html` — mode toggle (Intake/Ask), scope toggle (Project/Global), placeholder text, panel title, history/archive/close titles.
- `components/lang_switcher.html` — uses i18n keys for its labels too.

**Translation philosophy** (per agreed clarification): product language, not mechanical translation. Industry-standard terms stay as-is — `Thesis`, `MSRP`, `SKU`, `AI`, `PM`, brand names, factory names, product codes are not translated. Goal is to read naturally to a Chinese-speaking PM who already works in this domain.

**Out of scope for this first pass** (deferred to a v1.2 i18n update):
- Help modal body (~240 lines of deep doc).
- AI prompts in `app/ai/prompts.py` (English performs better; not user-visible).
- `/admin/*` pages (internal tools).
- Legacy `app/templates/intake.html` (kept as historical artifact; no longer rendered).

**Safety rails (confirmed):**
- No business logic, permission, AI behavior, or schema change. UI i18n only.
- No `Accept-Language` browser detection. Manual switcher only.
- User reviews `zh.json` wording before final v1.1.0 release.

**No schema migration.** `users.language` already exists (Build 13).

**Files created:** `app/i18n/__init__.py`, `app/i18n/en.json`, `app/i18n/zh.json`, `app/routes/i18n.py`, `app/templates/components/lang_switcher.html`, `test_build23.py`

**Files modified:** `app/main.py` (mount i18n router; register `t` and locale helper as Jinja2 globals), `app/routes/auth.py`, `app/routes/projects.py`, `app/routes/intake.py`, `app/routes/calendar.py`, `app/routes/ideas.py` (locale contexts), user-facing templates across projects/auth/calendar/ideas/detail components, `app/version.py`, `VERSION.md`, `USER_GUIDE.md` (one-line note), `CURRENT_TASK.md` (handoff status).

## v1.1.0-build22 — AI-Assisted Create Project (Build 22)
_2026-05-30_

**Goal:** consolidate the two ways to create a project (manual form + AI intake) into a single page with two tabs. Removes the standalone AI Intake nav link now that Bottom AI Chat (Build 21) is the daily AI entry point.

**`/projects/new` is now a two-tab page:**
- **Manual Form tab** — the existing project_form.html content, unchanged.
- **AI-Assisted tab** — new partial `app/templates/components/ai_intake_panel.html` containing both intake states (input + review/confirm).
- Tabs use the same Bootstrap pattern as the Help modal in base.html.
- `?tab=ai` query param picks the AI tab on initial render; default is Manual.

**Server-side endpoints unchanged in behavior:**
- `/ai/intake/extract`, `/ai/intake/extract-file`, `/ai/intake/confirm`, `/ai/intake/confirm-idea` — all 4 POST routes keep their paths and create/update logic. They now render `project_form.html` with `initial_tab="ai"` so the AI panel shows after extraction.
- `GET /ai/intake` becomes a 303 redirect to `/projects/new?tab=ai`. Old bookmarks and any test that GETs `/ai/intake` continue to work.

**Code cleanup:** introduced `_ai_panel_response(request, current_user, **overrides)` helper in `app/routes/intake.py` so every intake response gets the project_form.html scaffolding (project=None, is_edit=False, initial_tab="ai", current_user) plus safe defaults for all intake context keys. Eliminated 8+ near-duplicate context dicts.

**Navbar:** the "AI Intake" link is removed from `base.html`. A short Jinja comment is left in its place pointing to the new home.

**Edit Project (existing projects)** is untouched — tabs only render when `is_edit=False`. The edit flow stays a single form (no AI-Assisted edit in v1.1).

**No schema change. No AI logic change.** UI relocation + helper refactor.

**Files modified:** `app/routes/intake.py` (helper + 8 TemplateResponse call-sites refactored, GET /ai/intake → redirect), `app/routes/projects.py` (GET /projects/new accepts tab=, passes initial_tab + intake defaults), `app/templates/project_form.html` (Bootstrap tab wrapper on create flow), `app/templates/base.html` (AI Intake nav link removed), `app/version.py`, `VERSION.md`, `USER_GUIDE.md`

**Files created:** `app/templates/components/ai_intake_panel.html`, `test_build22.py`

**Files removed:** none (intake.html is no longer rendered but the file stays in the repo as a historical artifact for now; can be deleted in a follow-up if desired).

## v1.1.0-build21 — Bottom AI Chat + Side Panel + Conversation History (Build 21)
_2026-05-29_

**Goal:** Build 20 shipped the AI tool schemas + dispatcher; nothing called them. Build 21 puts a ChatGPT-style chat bar on every authenticated page so users can actually invoke the one wired tool (`create_journal_entry`) — and lays the UI groundwork for the other 15 tools to come online in follow-ups without UI rework.

**Bottom chat bar** (`app/templates/components/bottom_chat.html` included from `base.html` inside `{% if current_user %}` so anonymous pages don't render it):
- Fixed-position bar at the viewport bottom, dark accent.
- Mode toggle: `Intake` (AI can call tools) / `Ask` (read-only Q&A; no tools passed to the model).
- Scope toggle (only on project detail pages): `Project` (passes `project_id` so AI has project context) / `Global`.
- Textarea auto-grows from 38px up to 200px on `input`; `Enter` submits, `Shift+Enter` inserts a newline.
- Body gets `.has-bottom-chat` class so `.main-content` adds `padding-bottom: 80px` (no footer overlap).

**Right-side panel** slides in from the right when the user submits:
- Header: conversation title + history dropdown + archive button + close button.
- Message thread: user bubbles right-aligned (primary blue), assistant bubbles left-aligned (gray).
- Tool-call cards rendered inline beneath the assistant message:
  - `ok` (green): "✓ create_journal_entry — Success (id 47)"
  - `not_wired_until_build_21` (yellow): "⚠ delete_variant — not_wired_until_build_21"
  - other errors (red): "⚠ tool_name — error_string"
- Close button collapses the panel but leaves the bar in place.

**Backend — new file `app/routes/ai_chat.py`:**
- `POST /ai/chat` — accepts `{message, mode, conversation_id?, project_id?}`. Flow:
  1. `require_auth`.
  2. Reject early with `question_blocked_by_permission_guard` if `is_forbidden_ai_question(user, message)` returns True (NO OpenAI call).
  3. Load or create `AIConversation` (idempotent if `conversation_id` is supplied and owned; else create new).
  4. Persist the user message via `crud.save_ai_message(...)` with `metadata={"conversation_id": ..., "mode": ...}`.
  5. Build OpenAI `messages` list: mode-specific system prompt + last 10 history messages.
  6. Call `gpt-5.4`. In `intake` mode, pass `tools=TOOL_SCHEMAS, tool_choice="auto"`.
  7. If `tool_calls` present, run each through `app.ai.tools.dispatch(...)` and capture results.
  8. Persist the assistant message with `metadata={"tool_calls": [...]}`.
  9. Return `{ok, conversation_id, assistant_message, tool_calls}`.
- `GET /ai/conversations` — returns user's active (non-archived) conversations, newest-first.
- `GET /ai/chat/{conversation_id}` — returns full thread; 404 if not user's.
- `POST /ai/conversations/{id}/archive` — flips status; idempotent.

**Backend — new crud functions in `app/crud.py`:**
- `create_ai_conversation(db, user_id, project_id=None, title=None)` — auto-titles `"{project.name}"` or `"(global chat)"`.
- `list_ai_conversations(db, user_id, include_archived=False)` — ordered by `updated_at desc`.
- `get_ai_conversation(db, conversation_id, user_id)` — enforces ownership (returns None if not user's).
- `get_ai_messages_for_conversation(db, conversation_id, limit=None)` — chronological order; `limit=N` returns the last N still chronologically.
- `archive_ai_conversation(db, conversation_id, user_id) -> bool` — idempotent.
- **`save_ai_message` was modified** to also set `conversation_id` from metadata AND bump `AIConversation.updated_at` (so the history dropdown shows most-recently-active threads at top).

**Backend — 2 new system prompts in `app/ai/prompts.py`:** `CHAT_ASK_SYSTEM_PROMPT` (read-only Q&A; no tools), `CHAT_INTAKE_SYSTEM_PROMPT` (knows it has 16 tools but only `create_journal_entry` is wired; politely defers when other tools fail).

**Permission discipline:**
- Chat bar gated by `{% if current_user %}` in `base.html` — never renders for anonymous users.
- `POST /ai/chat` re-checks `require_auth`, then `is_forbidden_ai_question` BEFORE any OpenAI call.
- Tool calls run through `app.ai.tools.dispatch(...)` which already enforces role + project ownership per Build 20.

**No schema migration.** `ai_conversations` + `ai_messages` (with `conversation_id` column) have existed since Build 13.

**Out of scope (deferred):**
- Drag-and-drop file/image upload into chat → defers to Build 22 (AI-Assisted Create Project).
- Streaming responses (SSE/chunked) — v1.1 returns the full response.
- Two-turn tool follow-up (feeding result back to model for a natural-language wrap-up).
- Confirmation cards for destructive tools (none of those are wired in v1.1 anyway).
- Per-conversation title editing — titles are auto-generated only.

**Files modified:** `app/crud.py`, `app/ai/prompts.py`, `app/main.py`, `app/routes/projects.py` (added `current_project_id` to context), `app/templates/base.html`, `app/static/css/styles.css`, `app/static/js/main.js`, `app/version.py`, `VERSION.md`, `USER_GUIDE.md`

**Files created:** `app/routes/ai_chat.py`, `app/templates/components/bottom_chat.html`, `test_build21.py`

## v1.1.0-build20 — AI Tools Architecture + Permission Guard (Build 20)
_2026-05-28_

**Goal:** Build 21's Bottom Chat will need to invoke our v1.1 features via OpenAI function-calling. Today the AI has no schema describing those operations, no dispatcher, no permission discipline applied at the tool boundary. Build 20 builds that foundation: schemas for everything, ONE real handler to prove the pattern, and a security-first dispatcher.

**New module `app/ai/tools.py`** —
- `TOOL_SCHEMAS` — 16 OpenAI function-calling schemas (`{"type": "function", "function": {"name", "description", "parameters"}}`) covering every AI-callable operation: 13 mapped to existing HTTP routes from Builds 14-18, plus 3 new (`update_project_field`, `link_idea_to_project`, `create_idea`).
- `TOOL_PERMISSIONS` — per-tool role/project/journal/allowlist rules consulted by the dispatcher.
- `UPDATE_PROJECT_FIELD_ALLOWED` — conservative set: `name, brand, sku, product_type, project_owner, product_manager, planned_launch_date, project_thesis, notes`. **Deliberately excludes `current_stage`** (derived per CLAUDE.md §5) and **`status`** (operationally consequential — will get a dedicated `change_project_status` tool with mandatory confirmation in Build 21+ if needed).
- `dispatch(tool_name, args, db, user)` — 6-step pipeline: tool exists → role check → project ownership → journal access → field allowlist → handler (or `not_wired_until_build_21` stub). **Permission discipline applies even when the handler is a stub.**

**Only `create_journal_entry` is fully wired in v1.1.** Reuses `crud.create_journal_entry` (Build 14) end-to-end; on success returns `{"ok": True, "entry_id": <int>}`. The other 15 schemas have stubs that return `{"ok": False, "error": "not_wired_until_build_21"}` after permission has passed. This means Build 21 only needs to add handlers — the schema layer, permission layer, and dispatcher contract are all done.

**AI Permission Guard verified.** `_VIEWER_FORBIDDEN` in `app/dependencies.py:92` already covered every v1.1 sensitive source. Build 20 adds explicit per-source test coverage (business plan, journal entries, variant cost, packaging cost, quotation) so the guard can't silently rot.

**AI_TOOLS_REGISTRY.md updated** — "Current Tools" now lists all 16 with `route + schema implemented (Build NN/20); handler wiring lands in Build 21` status strings. New "How the dispatcher works" subsection documents the 6-step pipeline. The "Planned" table now only has post-v1.1 entries (`search_projects`, `get_project_context`, `change_project_status`).

**No schema change. No user-facing UI changes.** Infrastructure for Build 21.

**Files modified:** `AI_TOOLS_REGISTRY.md`, `app/version.py`, `VERSION.md`

**Files created:** `app/ai/tools.py`, `test_build20.py`

## v1.1.0-build19 — My Projects + Attention banner cleanup + last-project memory (Build 19)
_2026-05-28_

**Goal:** small UX polish pass — give PMs a focused view, cut noise from the attention banner, and stop sending them back to the full list every time they click the Projects nav.

**My Projects** — new `/my-projects` route (admin + PM only; viewer is 303-redirected to `/projects`). Wide table layout: name, current stage, planned launch (with inline delay badge), status, last updated. Admin sees all projects; PM sees only projects where `product_manager` matches their username (case-insensitive). Empty-state copy differs by role.

**Attention banner is now delay-only.** `needs_attention = [e for e in active_enriched if e["delay"]]` in `app/routes/projects.py` (was `e["delay"] or e["health"]["needs_info"]`). The Needs-Info per-card badge, the Needs-Info filter tab, the `card-needs-info` row class, the table-view badge, and the route filter logic all remain — only the banner block changed.

**Last-opened project memory** — `app/templates/project_detail.html` writes `localStorage.pm_last_project_id` on every page load. The Projects navbar link gets a 250ms click handler in `app/templates/base.html`: single-click → `/projects/{last_id}` if set, else `/projects`; double-click → clear and go to `/projects`. The click handler uses a setTimeout that's cancelled by `dblclick` so the two events don't compound.

**Navbar** — new "My Projects" link with `bi-person-circle` icon, gated `{% if current_user.role in ('admin', 'pm') %}`. Sits between Good Ideas and AI Intake.

**Permissions** —
- Viewer: `/my-projects` redirects to `/projects`; navbar link hidden.
- PM: sees own projects only.
- Admin: sees all projects in the same view.

**No schema migration.** Pure UI + a new service function (`crud.get_projects_for_user`).

**Files modified:**
- `app/crud.py` — new `get_projects_for_user(db, user)`
- `app/routes/projects.py` — new `/my-projects` route; `needs_attention` tightened to delay-only
- `app/templates/base.html` — My Projects nav link + Projects-nav click/dblclick handler
- `app/templates/projects_list.html` — Needs-Info badge removed from attention banner block
- `app/templates/project_detail.html` — `localStorage.pm_last_project_id` writer in extra_js
- `app/version.py`, `VERSION.md`, `USER_GUIDE.md`

**Files created:**
- `app/templates/my_projects.html`
- `test_build19.py`

## v1.1.0-build18 — Rendering History + Prototype Photos (Build 18)
_2026-05-28_

**Goal:** product development is visual — renderings get iterated, prototypes get photographed, and PMs need a chronological record of "what did this thing look like in week 3?" with a quick note about why each version mattered. Build 18 surfaces this history without forcing a new schema.

**Two new sections** on every project detail page (inserted after the existing Files & Renderings section, before the Change Log):
- **Rendering History** — every file uploaded with `file_category="rendering"`, newest first. Image previews render inline (96×96 thumb, clickable to full-size). Non-image files (PDF mocks etc.) render as a generic doc icon.
- **Prototype Photos** — same pattern, dedicated section for `file_category="prototype_photo"` (new category added to the upload dropdown).

**Per-file comments** — each entry shows the current `source_note` plus an inline-edit link (PM + admin only). The comment uses the existing `project_files.source_note` column — no new schema. Saving writes a `change_log` row (`change_type=event_note`).

**New POST route:** `/projects/{project_id}/files/{file_id}/comment` — guarded by `can_edit_project`, redirects back to the originating anchor.

**Latest rendering thumbnail on the project card** — `/projects` card view shows the most recent rendering (image only) as a 56×56 thumbnail in the top-right corner. `get_projects_enriched` attaches `latest_rendering` per project; card hides cleanly when no rendering exists.

**Reusable partial** — `app/templates/components/media_history_section.html` is parameterized by `media_kind` / `media_title` / `media_icon` / `media_files` / `media_anchor` so both new sections share one template.

**Permissions** —
- Viewer: see filenames, thumbnails, comments. Cannot edit comments or delete (existing rule).
- PM: edit comments on own projects; can delete files PM uploaded? — delete stays admin-only per existing pattern.
- Admin: full control.

**No schema migration.** All data lives in pre-existing columns of `project_files`.

**Files modified:**
- `app/crud.py` — new `get_files_by_category`, `get_latest_rendering`, `update_file_comment`; `get_projects_enriched` now attaches `latest_rendering` per project
- `app/routes/files.py` — new POST `/projects/{pid}/files/{fid}/comment` route
- `app/routes/projects.py` — `project_detail()` passes `renderings` + `prototype_photos` to template
- `app/templates/project_detail.html` — two new `{% include %}` blocks + `toggleMediaCommentEdit()` JS + `prototype_photo` added to upload category select
- `app/templates/projects_list.html` — `card-rendering-thumb` block
- `app/static/css/styles.css` — Build 18 media-history + card-thumb styles
- `app/version.py`, `VERSION.md`, `USER_GUIDE.md`, `AI_TOOLS_REGISTRY.md`

**Files created:**
- `app/templates/components/media_history_section.html`
- `test_build18.py`
- `AGENTS.md`, `HANDOFF.md` (Claude/Codex handoff protocol — applies project-wide, not specific to this build)

## v1.1.0-build17 — Timeline 2.0 (Plan / Reality split + Finish Phase) (Build 17)
_2026-05-27_

**Goal:** projects evolve — original plans slip, and we need to capture WHY without losing the original commitment. Build 17 separates Plan from Reality on the timeline, makes plan-date shifts auditable with a required reason, and adds a one-click Finish Phase that correctly advances the next phase.

**Plan / Reality column split** — each phase row now has two visually distinct column groups: Plan (Planned Start, Planned End) and Reality (Actual Start, Actual End). Plan group is blue-tinted; Reality is neutral.

**Plan-date changes are tracked** — any change to `planned_start_date` or `planned_end_date` via the phase edit modal writes a `phase_plan_changes` row (table existed since Build 13) capturing `old_date`, `new_date`, `changed_by_user_id`, `changed_at`, and `reason`. Reason is required by the route — saving plan-date changes without one redirects with `?timeline_error=reason_required` and a friendly banner.

**Visual indicators** —
- `*` appears next to any planned date that's been adjusted (one star per field with history, with adjustment count in tooltip).
- The current in-progress phase row is outlined in blue.
- A "N plan changes" link under each phase reveals an inline history accordion showing every old → new date shift, who changed it, when, and the reason.

**Finish Phase button** (green checkmark on every active phase row) — one click does the right thing:
- Marks the current phase done: sets `actual_end_date=today`, `status=done`, and `actual_start_date` if it was still empty (best guess: planned_start or today).
- Advances the next phase (next `phase_order` that's not done/skipped): sets `actual_start_date=today` (if not already set), `status=in_progress`.
- Writes one combined change-log event_note recording both transitions.
- Triggers `recalculate_stage_and_delay` so `current_stage` + `estimated_launch_date` stay correct.

**Permissions** — Finish Phase requires `can_edit_project` (admin + PM on own project). Phase delete now also gated to admin only (consistent with variants/components from Build 16). The reason field appears in the modal only for users who can edit.

**Modal updates** — phase edit modal explicitly splits Plan (with the reason field next to the planned dates) from Reality (with a tip to use the Finish Phase button instead). Reason field is cleared every time the modal opens to avoid stale text.

**No schema migration** — `phase_plan_changes` was created in Build 13.

**Files modified:**
- `app/crud.py` — `update_phase` extended (reason + changed_by_user_id params, writes `PhasePlanChange` rows on plan-date changes); new `finish_phase`, `get_plan_changes_for_phase`, `get_plan_changes_by_project`
- `app/routes/projects.py` — phase_edit accepts `plan_change_reason` Form param + redirects with `timeline_error=reason_required` if a plan date changed without one; new `phase_finish` route
- `app/templates/project_detail.html` — full timeline section rebuild + reason field in modal + plan-history accordion JS
- `app/static/css/styles.css` — Plan/Reality column tinting, asterisk marker, history accordion, Finish Phase button
- `app/version.py`, `VERSION.md`, `AI_TOOLS_REGISTRY.md`

**Files created:** `test_build17.py`

## v1.1.0-build16 — Variants + Packaging + Quotation + Profit Model placeholder (Build 16)
_2026-05-27_

**Goal:** real product development isn't one SKU. Build 16 adds the data scaffolding for multi-SKU projects: variants with per-SKU cost/MSRP, packaging/accessory components scoped per-variant or project-wide, a dedicated Quotation Files surface, and a Profit Model placeholder that documents the future v1.2 formula.

**Variants** — new section on project detail (after Inspired By, before Timeline). Card grid with CRUD via inline form + per-card edit form. Fields: variant_name, sku, status (idea/evaluating/selected/rejected/launched), is_primary (★), target_factory_cost, actual_factory_cost, target_msrp, material/size/color/packaging summaries, notes. `is_primary` is enforced at the service layer — setting one to primary unsets the others (no DB unique constraint, safer for migrations).

**Packaging & Accessories** — table-style section below Variants. Each component has type (packaging/accessory), name, scope (project-wide or per-variant), target_cost, actual_cost, notes. Per-variant components only apply to their variant; project-wide components apply to all.

**Quotation Files** — filtered view of `project_files` where `file_category="quotation"`. Listed with friendly UI separately from the general Files area. Server-side guard on download: `GET /projects/{id}/files/{fid}/download` redirects viewers away from quotation files (other categories pass through to the existing static `/uploads/` path).

**Profit Model placeholder** — surfaces the intended v1.2 formula in a callout, shows the primary variant's costs as a preview, and computes a naive per-unit margin if MSRP + factory_cost are both set. Costs hidden from viewers. Full model design in `PROFIT_MODEL_INTENT.md`.

**Permissions** —
- View variants/components (no costs): all roles
- View cost columns: admin + PM only (new `can_view_costs()` helper)
- Create/edit variant or component: admin + PM on own project
- Delete variant or component: admin only
- Download quotation file: admin + PM only (server-side route guard)

**AI Permission Guard** — `_VIEWER_FORBIDDEN` extended with `variant cost`, `actual cost`, `quotation`, `packaging cost`, `component cost`.

**Files created:** `app/routes/variants.py`, `app/templates/components/variants_section.html`, `app/templates/components/packaging_section.html`, `app/templates/components/quotation_section.html`, `app/templates/components/profit_model_section.html`, `PROFIT_MODEL_INTENT.md`, `test_build16.py`
**Files modified:** `app/crud.py` (10 new helpers), `app/dependencies.py` (`can_view_costs`, `_VIEWER_FORBIDDEN`), `app/main.py` (mount router), `app/routes/projects.py` (detail context), `app/routes/files.py` (quotation download guard), `app/templates/project_detail.html` (4 new section includes), `app/static/css/styles.css`, `app/version.py`, `VERSION.md`, `AI_TOOLS_REGISTRY.md`

**No schema migration** — tables (`project_variants`, `project_variant_components`) already created in Build 13.

## v1.1.0-build15 — Business Plan Upload + Thesis Extraction (Build 15)
_2026-05-27_

**Goal:** lower the burden of getting a Product Thesis onto a project. PMs upload a business plan once and AI proposes a thesis + any inspirations to capture as Ideas — preview, edit, then confirm before any DB write.

**One-time AI, then pure GET preview** — the AI extraction runs once on POST. The result is persisted as an `ai_messages` row (`message="thesis_extraction"`, payload in `metadata_json`). The preview page is a pure GET render — refreshing it does NOT re-trigger AI.

**File formats supported:** PDF, DOCX, DOC (via LibreOffice if installed; friendly error otherwise), and image (PNG/JPG/WEBP/GIF via vision). New dependency: `python-docx`.

**Two entry points:**
- Create Project form: optional Business Plan file input. On submit → project created → file saved as `file_category="business_plan"` → AI runs once → redirect to preview.
- Project Detail Thesis section: "Extract from Business Plan" button (or "Re-extract" if a plan is already attached) reveals an inline upload form that follows the same path.

**Preview screen** (`thesis_preview.html`): two-column. Proposed thesis textarea (editable) + detected inspirations checklist. Each inspiration is fuzzy-matched against existing open Ideas; matches above 65% surface a "Link existing IDEA-005 (87% match)" suggestion with radio toggle Link/Create new/Skip. Cancel returns to project; Confirm writes everything in one transaction.

**Confirm transaction:** `update_project(project_thesis=...)` writes automatic per-field change-log row; each inspiration with action=create/link creates/links an Idea; `write_change(event_note, changed_by="ai", source_type="ai_chat")` marks AI source; AIMessage row updated with `confirmed_at` + `confirmed_thesis` + `confirmed_inspirations` for full audit.

**Inline thesis edit on detail page:** click Edit on the Thesis section → textarea + Save without leaving the page. Distinct route from the full edit form so it only needs the thesis field.

**Detail page Thesis section:** now scrollable (max-height 220px) so long theses don't dominate the page. Extract/Re-extract button is admin/PM only.

**AI Permission Guard:** `_VIEWER_FORBIDDEN` extended with `business plan`, `thesis extraction`, `margin target`, `pricing strategy`.

**AI Tools Registry:** `extract_thesis_from_business_plan` added (HTTP route implemented; bottom-chat tool wiring lands in Build 20/21).

## v1.0.0 — Good Ideas + Project Linkage + AI Dual-Mode (Build 11)
_2026-05-24_

**Good Ideas board** (`/ideas`)
- New `ideas` table with: name, description, idea_type, source, source_detail, contributor, status
- Six type columns: material · structure · feature · aesthetic · manufacturing · other
- Seven sources: factory · tradeshow · internet · customer · team · competitor · other
- Serial number auto-derived: `IDEA-001`, `IDEA-002`, …
- Source filter on board
- Card visual style with source-tinted badges
- Permissions: all roles create; PM+admin edit; admin only deletes

**Project ↔ Idea linkage** (many-to-many via new `project_ideas` table)
- "Inspired By" section on project detail page
- Modal picker to link an existing idea, with optional usage note
- Unlink button per linked idea
- Idea status auto-flips: `open` → `in_use` on first link, back to `open` on last unlink

**AI Dual-Mode Intake**
- New `extract_intake()` in `app/ai/parser.py` classifies pasted text as project or idea
- Ambiguous input defaults to "idea" (low-friction capture)
- Confirmation page conditionally renders the project form OR the idea form
- User can toggle classification if AI got it wrong (link in banner)
- New route `POST /ai/intake/confirm-idea` creates an idea from confirmed extraction
- File-upload intake (PDF/image) still goes to the project path (unchanged)

## v0.9.0 — Calendar + Admin Nav Hardening (Build 10)
_2026-05-23_

- New `/calendar` route showing planned vs. actually-launched projects by month
- Year navigation; click a month in the left list to view its project roster on the right
- "Planned" = projects with `planned_launch_date` in the selected month
- "Actually launched" = projects whose Launch phase is marked done with `actual_end_date` in the selected month (no schema change — derived from existing phase data)
- Each project row shows SKU, name, brand, status, planned date, actual date, and variance ("5 days late" / "on time")
- Calendar visible to all authenticated users (admin/pm/viewer) — only non-sensitive fields shown
- Verified Database and Users nav links are admin-only (lock-in test added to test_build8.py)

## v0.8.0 — Multi-Role Auth + Railway Deploy (Build 8 + 9)
_2026-05-22_

**Auth & Permissions (Build 8):**
- New `users`, `invite_pins`, `user_sessions` tables
- Login / logout / register routes with HTTP-only session cookies
- Three roles: admin, pm, viewer
- Admin can generate role-prefixed invite PINs (`PM-XXXXXX` / `VW-XXXXXX`)
- Field-level permissions: factory + engineer hidden from viewers (sidebar + change log)
- AI Permission Guard: viewers cannot extract sensitive fields via AI, no role can extract system internals (.env, API keys, model name)
- `/admin/users` page for user management
- `create_admin.py` bootstrap script with hidden password prompt
- Help/Ask AI now requires auth

**Railway Deploy (Build 9):**
- `app/database.py` now reads `DATABASE_URL` env var (PostgreSQL on Railway, SQLite locally)
- Auto-normalizes legacy `postgres://` URLs to `postgresql://`
- `run.py` honors `$PORT` and disables reload when `RAILWAY_ENVIRONMENT` is set
- New `/healthz` endpoint for Railway healthchecks
- One-time admin bootstrap via `INITIAL_ADMIN_USERNAME` + `INITIAL_ADMIN_PASSWORD` env vars (idempotent, never overwrites existing admin)
- `railway.toml`, `runtime.txt`, `.env.example` added
- `psycopg2-binary` added to requirements.txt

## v0.6.0 — AI File/Image Intake (Build 6)
_2026-05-21_

- Added file upload option to AI Intake page (PDF + image)
- PDF extraction: text extracted via pypdf, fields parsed by GPT-5.4
- Image extraction: GPT-5.4 Vision analyzes image, generates ai_summary + extracts fields
- Uploaded file automatically attached to project on confirm
- `project_files.ai_summary` populated from AI vision analysis
- OR divider between text paste and file upload on intake form

## v0.5.0 — AI Text Intake (Build 5)
_2026-05-21_

- New AI Intake page at `/ai/intake`
- Paste messy notes → GPT-5.4 extracts structured project fields
- Health check preview: shows which critical fields are still missing before confirm
- Confirmation step required — AI never silently creates or overwrites
- Change log records `changed_by=ai` on AI-created projects
- `ai_messages` table stores full conversation history per project

## v0.4.0 — Change Log (Build 4)
_2026-05-21_

- Change log section (Section 4) on project detail page
- All field edits recorded with old → new values
- Phase updates, file uploads, and archive events recorded
- Change log header shows entry count
- `changed_by` column distinguishes user vs. AI edits

## v0.3.0 — File Uploads + Rendering Gallery (Build 3)
_2026-05-20_

- Drag-drop file upload zone on project detail page
- Image gallery with category filter tabs (All / Rendering / Reference / Quotation…)
- Full-resolution lightbox with left/right navigation and keyboard shortcuts
- Non-image files shown in document list with download link
- File category selector (rendering, reference, quotation, factory feedback, packaging, other)
- Delete file from gallery with confirmation

## v0.2.0 — Timeline + Delay (Build 2)
_2026-05-20_

- Project phases auto-created at project creation (single or double prototype template)
- Phase edit modal (8 fields: name, type, status, planned/actual dates, owner, notes)
- Add/delete phases from project detail
- Delay calculation: auto-detected from overdue phases, never stored as a status
- Red delay banner on project detail with days late + estimated launch date
- Delay badge on project cards
- "Phases Due This Week" in Needs Attention section

## v0.1.5 — Database Inspector (Build 1.5)
_2026-05-20_

- `/admin/database` read-only inspector page
- Table overview: row counts for all 5 tables
- Field usage report: % of projects with each field filled
- Project health summary: which active projects are missing critical fields
- Recent changes feed (last 50 entries)
- `ARCHITECTURE.md` added as living architecture document

## v0.1.0 — Project CRUD Skeleton (Build 1)
_2026-05-20_

- Clean project structure (FastAPI + SQLAlchemy + Jinja2 + Bootstrap 5)
- Create, view, edit, archive projects
- All 5 database tables: projects, project_phases, project_files, project_changes, ai_messages
- Project detail: Product Thesis as Section 1 (first-class, not buried)
- Projects list: card grid + table toggle view
- Filters: All / Active / Delayed / Needs Info / Completed / Archived
- Needs Info badge (count of missing critical fields)
- "Needs Attention" section at top of projects list
- `get_project_health()` service — calculated, never stored
- `CLAUDE.md` and `TESTING_RULES.md` governance files
