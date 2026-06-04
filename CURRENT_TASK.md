# CURRENT_TASK.md

## Task
v1.3 Build 06 — Timeline Command Center Shell. Implemented + tested. Awaiting push.

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth.

## What just shipped in this session

- **Build 06** implemented per `V13_BUILD06_EXECUTION_PLAN.md` (plan committed at `75db65c`).
  - `app/routes/projects.py` — `command_center_state` dict computed in one O(N) pass (phase_strip with done/current/next/skipped/later states, days_left/days_overdue, pressure_dots, health_band). `can_use_ai_intake_user` passed into template context.
  - `app/templates/project_detail.html` — `<section id="timeline-command-center">` prepended inside `workspace-panel-timeline`; existing `timeline-table-v2` wrapped in `<details id="timelineDetailedTable">` "Detailed Table" summary (closed by default); phase `<tr>` rows now carry `id="phase-row-{phase.id}"`.
  - `app/static/css/styles.css` — `.timeline-command-*` styles: phase strip horizontal-scroll (Lock 1), 3-tile grid (single column at ≤768px), 4 health badge variants, days badges (overdue/amber/neutral), pressure dots, placeholder blocks with accent border + Placeholder badge, Detailed Table summary chevron.
  - `app/i18n/en.json` + `zh.json` — 31 new Build 06 keys (29 in plan + 2 extras: `timeline.due` and `timeline.placeholder_label`); parity 651/651.
  - `test_v13_build06.py` — **59/59 PASS** (i18n parity, no new migration, markup presence, phase strip data-status ordering, 4 health bands, 3 days-badge bands, pressure dots, owner empty-state, action button permissions per role, [Add Blocker] disabled, [Finish Current Phase] anchor target, Detailed Table is closed-by-default `<details>`, phase-row id anchors, no-phase edge case, PM permission, Build 01-05B invariants preserved).
  - `test_v13_build01.py` — updated: opens `<details id="timelineDetailedTable">` before clicking phase-edit (planned behavior change from Build 06; not a regression).

## Build 06 — Locked decisions implemented

1. **Lock 1**: Phase strip horizontal-scroll on mobile, not wrap.
2. **Lock 2**: "Current Phase" semantic = `derive_current_stage()` exactly.
3. **Lock 3**: Health bands deterministic — `on_track` / `at_risk` (≤3 days_late) / `delayed` (>3) / `not_scheduled` (no planned_end + status=not_started).
4. **Lock 4**: Days badge bands — overdue red / amber ≤7 / neutral >7 / muted if no due date.
5. **Lock 5**: Pressure dots — 3 red (overdue) / 2 amber (≤3) / 1 amber (≤7) / none otherwise.
6. **Lock 6**: Action button targets — Finish & Adjust → `#phase-row-{id}` with auto-expand JS; Add Update → `#journal`; Add Blocker disabled; AI Intake opens existing side panel.

## Explicit placeholders (per doc §1.5 "no fake intelligence")

- Main blocker — "No blocker model yet…" + link to Journal (gated on `can_view_journal`).
- AI Nudge — "AI nudges coming later…" + link to assistant chat panel.
- [Add Blocker] button — `disabled` + tooltip "Blocker model coming in Build 07".

## Verification at ship time

- `python3 test_v13_build06.py` — **59/59 PASS**.
- Regression: `test_v13_build01` 16/16 (updated for details wrapper); `test_v13_build02` 11/11; `test_v13_build03` 20/20; `test_v13_build04` 20/20; `test_v13_build05` 34/34; `test_v13_build05b` 42/42; `test_build_v121` 19/19; `test_build30` 23/23; `test_ai_e2e.py` 15P/2S/0F.
- i18n parity: 651/651.
- No new migration (still 5); no schema change; no service change; no AI tool change.

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
| 05B — Structured spec schema | shipped | `dd96cf2` |
| **06 — Timeline Command Center Shell** | **shipped this session (display-only)** | latest |
| 07 — Timeline Command Actions Backend | planned | — |
| 08 — Timeline History | planned | — |
| 09 — Planning Sandbox (design-only) | planned | — |

## Next step

Wait for user direction. Suggested next moves:
1. **Push** to origin (currently several commits ahead of `origin/main` after this build).
2. **Build 07** — Wire each Command Center action button to its dedicated backend route. Per the user's "high-risk, move slowly" guidance: should have a per-button Backend Honesty Mapping BEFORE coding. Architecture review required for the Add Blocker model (likely `project_blockers` table with phase_id FK, OR reuse `journal.entry_type='blocker'`).
3. **Browser walkthrough** of the Build 06 result on a project with set planned_end_dates to visually confirm health badges + pressure dots + placeholder treatments before pushing.

## Deferred to future builds (carried forward from v1.2.1)

- Native-speaker Chinese review of strings added in Builds 26-30C + 01-06.
- AI prompt translation, Help modal body translation, `/admin/*` page translation.
- Full Profit Model implementation (variant cell shows naive margin; full model is v1.4).
- Row-level multi-tenancy (`Organization` table + `org_id` everywhere). Deployment-level isolation (Build 25) remains the answer for ≤3 departments.
- Bulk delete from the projects list / soft-delete with undo window.
- Auto-provisioning script for Railway (the DEPLOYMENT.md runbook is still manual).
- One-time admin cleanup of the original 6 admin-linked duplicates from the Build 30A incident.

## v1.3 process pattern (continues)

Every build gets a short build-specific execution plan before coding. Plan files are committed/reviewed first. Locks (route choices, anchor strategies, i18n keys with EN/zh translations) are resolved in-plan before implementation starts. Build 06 added a **Backend Honesty Mapping** per visible field — every field is either honestly sourced (with source-of-truth path + write-path + permission rule + test coverage) or marked as an EXPLICIT placeholder. This discipline is per the user's `timeline_command_center_redesign_plan.md` §1.5 and applies to all v1.3+ builds touching display surfaces.
