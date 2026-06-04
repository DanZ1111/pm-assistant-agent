# CURRENT_TASK.md

## Task
v1.3 Build 05B — Structured Variant Specs. Implemented + tested. Awaiting push.

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth.

## What just shipped in this session

- **Builds 03 + 04** committed as one atomic commit (`bc80506`) — Product Concept (renamed thesis section + chip-row Inspired By with `#thesis` compatibility anchor) + Renderings Overview (standalone section with 4-tier cascade, document fallback, disabled Designer Portal placeholder).
- **V13_BUILD05_EXECUTION_PLAN.md** revised with 4 locks + Option A scope decision committed at `3a63a94`.
- **Build 05** implemented + committed (see latest `git log`):
  - `app/templates/components/variants_section.html` — rewritten with `<details class="variant-command-card">` cards + wireframe-derived 2×2 grid.
  - `app/routes/projects.py` — `components_by_variant` derived grouping in `project_detail` (single O(C) pass, no new DB query).
  - `app/static/css/styles.css` — `.variant-command-*` styles (native marker suppression + `bi-chevron-right` custom marker, 2×2 grid, single-column at ≤768px).
  - `app/static/js/main.js` — `#variant-N` anchor bootstrap (force-opens targeted card, scrolls into view).
  - `app/i18n/en.json` + `zh.json` — 19 new Build 05 keys; parity 604/604.
  - `test_v13_build05.py` — **34/34 PASS** (i18n parity, 4-cell grid, naive margin computation, viewer permission, anchor markup, route grouping, custom chevron CSS, CRUD preservation, manage-components link).
  - `test_build29.py` — removed stale `commercial-snapshot` assertion (section was demoted by v1.3 Build 01).

## Build 05 — 4 Locked decisions

1. **Route-side `components_by_variant` grouping** — O(C) once vs O(V × C) per render.
2. **Component count format**: `"X shared + Y for this variant"` / `"X shared"` / omitted.
3. **`#variant-N` JS bootstrap** — overrides default-open primary, force-opens target, scrolls into view.
4. **Native `<details>` marker suppressed + custom `bi-chevron-right`** rotates 90° when open.

Plus **Option A (layout-only)**: structured spec schema (`sales_format`, `blade_steel`, `handle_material`, `lock_type`, `dimensions`, separate `packaging_cost`) **deferred to Build 05B**. Build 05 ships the wireframe-matched LAYOUT using existing free-text summary fields.

Plus **Profit Placeholder content**: naive margin for `can_view_costs` when both prices set; "(other value not set)" when one; "Not enough data..." when neither; v1.4 footnote always. Viewer never sees the Profit cell.

## Verification at ship time

- `python3 test_v13_build05.py` — **34/34 PASS**.
- Regression: `test_v13_build01-04` all green; `test_build29` 26/26 (after stale-assertion fix); `test_build_v121` 19/19; `test_build30/30b/30c` all green; `test_ai_e2e.py` 15P/2S/0F.
- Browser smoke: project 29 renders variant cards with all 4 grid cells, primary badge, custom chevron, component-count summary.
- i18n parity: 604/604.

## Reference: uploaded v1.3 product spec docs

User-provided canonical references for v1.3:
- `project_overview_redesign_plan.md` (Overview tab; covers Builds 01-05)
- `timeline_command_center_redesign_plan.md` (Timeline tab; covers Builds 06-09)

These are the canonical product vision. Existing `V13_BUILD0N_EXECUTION_PLAN.md` files are implementation slices that match those docs.

## v1.3 Build series status

| Build | Status | Commit |
|---|---|---|
| 01 — Workspace Shell | shipped | `448364e` |
| 02 — Project Pulse v1 | shipped | `ea0460c` |
| 03 — Product Concept | shipped (with 04) | `bc80506` |
| 04 — Renderings Overview | shipped (with 03) | `bc80506` |
| 05 — Variant Command Cards | shipped | `4d8c847` |
| **05B — Structured spec schema** | **shipped this session** | latest |
| 06 — Timeline Command Center Shell | planned | — |
| 07 — Timeline Command Actions Backend | planned | — |
| 08 — Timeline History | planned | — |
| 09 — Planning Sandbox (design-only) | planned | — |

## Next step

Wait for user direction. Suggested next moves:
1. **Push** to origin (currently several commits ahead).
2. **Build 05B** — structured spec schema (`sales_format`, blade/handle/mechanism fields, separate `packaging_cost`). Schema change + migration 005 + edit form expansion + AI tool registry updates. ~2-3 sessions.
3. **Build 06** — Timeline Command Center Shell per `timeline_command_center_redesign_plan.md` Section 1. Per the user's "high-risk, move slowly" guidance: should have a Backend Honesty Mapping per visible field BEFORE coding starts.
4. **Browser walkthrough** of the Build 05 result on a project with multiple variants + components before pushing, to catch any UX issues the test missed.

## Deferred to future builds (carried forward from v1.2.1)

- Native-speaker Chinese review of strings added in Builds 26-30C + 01-05.
- AI prompt translation, Help modal body translation, `/admin/*` page translation.
- Full Profit Model implementation (variant cell shows naive margin now; full model is v1.4).
- Row-level multi-tenancy (`Organization` table + `org_id` everywhere). Deployment-level isolation (Build 25) remains the answer for ≤3 departments.
- Bulk delete from the projects list / soft-delete with undo window.
- Auto-provisioning script for Railway (the DEPLOYMENT.md runbook is still manual).
- One-time admin cleanup of the original 6 admin-linked duplicates from the Build 30A incident.

## v1.3 process pattern (continues)

Every build gets a short build-specific execution plan before coding. Plan files are committed/reviewed first. Locks (route choices, anchor strategies, i18n keys with EN/zh translations) are resolved in-plan before implementation starts.
