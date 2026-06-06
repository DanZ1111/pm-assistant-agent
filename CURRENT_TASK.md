# CURRENT_TASK.md

## Task
v1.3 Build 09 **amended** — Planning Sandbox engineering response to ChatGPT-shaped PRD. Shipped. Awaiting Build 10 (release hardening).

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth.

## What just shipped in this session

- **Build 09 amendment** committed as one atomic commit (see latest `git log`). Build 09 stays design-only; this corrects the design target.
  - `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md` (~35 KB) — rewritten as the **engineering response to the Planning Sandbox PRD**. PRD captured verbatim as Appendix A. Original Build 09 shipped at `fc064a6` was form-based + persisted-on-project; that's now corrected to visual canvas + draft/apply separation.
  - `test_v13_build09.py` — rewritten with 56/56 PASS. Asserts the amended structure: PRD appendix, visual-canvas + draft/apply locks, Cytoscape.js decision, 10 PRD open questions locked, 8 v1.4 sub-builds (not 4), 7-table schema sketch, Backend Honesty Mapping, Risk register, amendment row in Decision log, AND the design-only invariants (no migrations, no new tables, no AI tools, no i18n drift).
  - No app code changed. No schema. No migration. No i18n. No AI tools. No routes.
  - Original commit `fc064a6` is preserved in history; the amendment is a new commit so the iteration is visible.

## Build 09 amended — design lock highlights (for v1.4 reference)

### Product invariants (non-negotiable per PRD)
- **Visual workflow canvas**, not a form-based editor. Drag-drop modules from right panel, draw edges, top-to-bottom orientation with height ∝ duration (4 discrete size bins).
- **Sandbox ≠ committed project plan.** Dragging a node MUST NOT mutate live `project_phases`. Users explicitly "Apply" to commit.
- Single sandbox per project (UNIQUE constraint on `planning_sandboxes.project_id`). Multiple drafts deferred to v1.5+.
- All edit paths preserve `actual_start_date` — Apply REFUSES to overwrite a project where any phase has started.

### Schema (locked, 7 new tables, 4 migrations)
| Migration | Tables |
|---|---|
| 007 | `planning_module_library`, `planning_sandboxes`, `planning_sandbox_nodes`, `planning_sandbox_edges` |
| 008 | (reserved; optional column tweaks during v1.4-04 Connect Nodes) |
| 009 | `planning_apply_events` (audit; Build 08 Timeline History reads this) |
| 010 | `planning_templates`, `planning_template_nodes`, `planning_template_edges` + seed 6 system templates |

### Canvas library (locked)
**Cytoscape.js + cytoscape-dagre.** ~60 KB gzipped, vanilla JS, purpose-built for node-edge graphs. Cycle detection + topological sort + dagre auto-layout out of the box. Lazy-loaded only on `/projects/{id}/sandbox` route so Timeline page payload unchanged.

### v1.4 sub-build sequence (locked, 8 builds)
| # | Build | Scope | Risk |
|---|---|---|---|
| v1.4-01 | Schema + Module Library + admin module list page | Low |
| v1.4-02 | Schedule Engine (pure Python, ~30 fixture assertions, no UI) | Medium |
| v1.4-03 | Static Canvas Renderer (read-only Cytoscape.js render) | Medium |
| v1.4-04 | Module Palette + Drag-to-Add (no edges yet) | Medium-high |
| v1.4-05 | Connect Nodes (drag handles + cycle detection) | **High** |
| v1.4-06 | Node Property Panel (right-panel state transition) | Medium |
| v1.4-07 | Apply to Project Plan (audit row + Q2 refuse path) | **High** |
| v1.4-08 | Save as Template + AI tools (3 new: list/apply template, apply sandbox) | Medium |

Total v1.4 Sandbox surface: 4 migrations, 7 new tables, ~12 crud helpers, 3 AI tools, ~150 test assertions across 8 plan-first execution slices.

### 10 PRD open questions — locked answers
| # | Locked answer |
|---|---|
| Q1 | Start blank OR template (both). Picker on first-open. |
| Q2 | Apply replaces draft only; REFUSES if any phase has `actual_start_date IS NOT NULL`. |
| Q3 | Server is source of truth; client mirrors for responsiveness. |
| Q4 | Manual node positioning + one-click "Tidy" via cytoscape-dagre. |
| Q5 | Both drag handles AND property-panel multi-select for edges. |
| Q6 | 4 discrete node-height bins (S/M/L/XL), not strict pixel scaling. |
| Q7 | Disconnected branches allowed with soft warning banner. |
| Q8 | Sandbox permissions inherit `can_edit_project`. |
| Q9 | One sandbox per project (UNIQUE constraint). |
| Q10 | Global templates with creator+admin ownership; no project-scoped templates. |

### Out of scope for v1.4 implementation
Cross-project resource allocation; factory capacity; AI-generated plans; real-time multi-user editing; calendar/iCal/CSV export; sandbox as source of truth post-Apply; multiple drafts per project; append-after-advanced-phases apply mode; project-scoped templates; working-days/holiday handling; critical-path highlighting; lag time; resource constraints; PERT estimates.

## Verification at ship time

- `python3 test_v13_build09.py` — **56/56 PASS**.
- Full regression: v1.3 Builds 01-08 (380 assertions), `test_v13_build09` 56, `test_delete_project_ai_intake_regression` 17, `test_build_v121` 19 — all green.
- i18n parity: **714/714** (unchanged).
- Migration count: **6** (unchanged).
- Code changes outside the doc + test files: **zero** (verified by test invariants).

## v1.3 Build series status

| Build | Status | Commit |
|---|---|---|
| 01 — Workspace Shell | shipped | `448364e` |
| 02 — Project Pulse v1 | shipped | `ea0460c` |
| 03 — Product Concept | shipped (with 04) | `bc80506` |
| 04 — Renderings Overview | shipped (with 03) | `bc80506` |
| 05 — Variant Command Cards | shipped | `4d8c847` |
| 05B — Structured spec schema | shipped | `dd96cf2` |
| 06 — Timeline Command Center Shell | shipped | `4a800d6` |
| 07A — Timeline Command Actions (3 routes) | shipped | `57b48c3` |
| 07B — Project Blockers | shipped | `5dfff4e` |
| 08 — Timeline Updates / History | shipped | `3ab1dc8` |
| Project-delete FK fix (cross-cutting) | shipped | `b8a9687` |
| 09 — Planning Sandbox Design (original) | shipped | `fc064a6` |
| **09 amended — Engineering response to PRD** | **shipped this session** | latest |
| 10 — v1.3.0 Release Hardening | **next** | — |

## Next step — Build 10 (v1.3.0 Release Hardening)

Final v1.3 build. Suggested scope (carried forward from earlier session):
1. **Version bump**: `app/version.py` → `v1.3.0`. Update build name + LAST_UPDATED.
2. **Roll up CHANGELOG**: collapse the Unreleased section's v1.3 Builds 01-09 entries (including the delete-FK fix and the Build 09 amendment) into a single `## v1.3.0` heading with release narrative + dated.
3. **Update MASTERPLAN.md**: mark all 10 v1.3 builds ✓ SHIPPED with commit hashes.
4. **Write `test_v13_build10.py`** as the release-proof regression that re-runs all v1.3 Builds 01-09 + v1.2.1 baseline + delete-fix regression + the new Change Log leak fix below. Asserts the version string and the `## v1.3.0` CHANGELOG entry.
5. **Fix the legacy Change Log viewer leak** discovered during Build 08:
   - Risk: low. Information disclosure to a role that already has project read access. Not a privilege escalation.
   - Fix: ~10 LOC in `app/templates/project_detail.html` `#changes` for-loop to skip `event_note` rows whose summary starts with "Journal entry added:" when `not can_view_journal`.
   - Lock with 1 assertion in `test_v13_build10.py`.
   - Recommendation: include in Build 10 vs. ship v1.3.0 with a known leak.

## Deferred to future builds (carried forward)

- Native-speaker Chinese review of strings added in Builds 26-30C + v1.3 Builds 01-09.
- AI prompt translation, Help modal body translation, `/admin/*` page translation.
- Full Profit Model implementation (v1.4).
- Row-level multi-tenancy.
- Bulk delete from the projects list / soft-delete with undo window.
- Auto-provisioning script for Railway.
- One-time admin cleanup of the original 6 admin-linked duplicates from the Build 30A incident.
- **Planning Sandbox implementation** — design locked in Build 09 amended; implementation is v1.4 sub-builds 01-08 per the sequence in `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md` §4.
- Cursor pagination beyond 200 Timeline History events (per Build 08 Lock 11).
- Recently-resolved blockers section in Command Center (per Build 07B Lock 10).
- Multiple sandbox drafts per project (per Build 09 amended Q9 — v1.5+ candidate).
- Append-after-advanced-phases apply mode (per Build 09 amended Q2 — v1.5+ candidate).
- Critical-path highlighting on the sandbox canvas (v1.5+ nice-to-have).

## v1.3 process pattern (closing the series)

Every build in this series:
- Started with a per-build execution plan (`V13_BUILD0X_EXECUTION_PLAN.md`), committed and reviewed before code.
- Got a Backend Honesty Mapping when display surfaces were introduced.
- Got an Architecture Review when schema changed (Build 07B, Build 05B) OR in reverse when schema was deliberately NOT changed (Build 08 — proved existing tables sufficient; Build 09 — locked the design for v1.4).
- Got a "Scope discipline" lock (introduced in Build 07B Lock 10, carried through Builds 08 and 09) — an explicit out-of-scope list to prevent feature creep mid-build.
- Got a regression sweep + commit before moving to the next build.
- **For Build 09 specifically: the amendment pattern** — when a shipped design doc turned out to assume the wrong product after external (PRD) review, the response was a fresh commit that rewrote the doc + updated the regression test + added a dated Decision log row, NOT a silent rewrite or a `git commit --amend`. The pattern is reusable for future design-doc corrections.

This pattern scales. v1.4 Sandbox builds should reuse it verbatim.
