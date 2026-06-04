# CURRENT_TASK.md

## Task
v1.3 Build 07A — Timeline Command Center Actions Backend (Finish / Adjust / Add Update). Implemented + tested. Awaiting push.

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth.

## What just shipped in this session

- **Plan** committed at `0616af5` (V13_BUILD07_EXECUTION_PLAN.md) — proposed 07A/07B split, Backend Honesty Mapping per button, 7 locks. User approved 07A-only and confirmed locks 1/3/4/7 (with Lock 7 amendment: Add Update gets a client-side submit-disable since no idempotency token).
- **Build 07A implementation** committed as one atomic commit (see latest `git log`):
  - `app/routes/projects.py` — 3 new POST routes (`/command/finish-phase`, `/command/adjust-due-date`, `/command/add-update`) + `_cc_redirect()` helper + `_derive_current_phase()` race-check helper. project_detail view passes `cc_action` + `cc_result` query params into the template.
  - `app/templates/project_detail.html` — action buttons swapped from `<a href="#phase-row-N">` to `<button data-cc-form="...">` form triggers; new `<div id="cc-action-form">` shared mount with 3 inline `<form>` panels (Finish confirmation card with 3-line preflight, Adjust with required reason, Add Update with 9-option entry_type select). Result banner renders above action row when `?cc_result` is present.
  - `app/static/css/styles.css` — `.cc-result-banner`, `.cc-action-form-mount`, `.cc-action-form-*` (~100 lines). Mount has light grey background to visually attach the form to the action that opened it. Mobile collapses padding.
  - `app/static/js/main.js` — `initCommandCenter()` IIFE: button click shows matching panel, focuses first field, Cancel hides mount, Add Update submit click disables button + shows spinner (Lock 7 amendment).
  - `app/i18n/en.json` + `zh.json` — 15 new `timeline.cc_*` keys + updated `timeline.btn_add_blocker_tooltip` to point at Build 07B. Parity 666/666.
  - `test_v13_build07.py` — **57/57 PASS** (15 i18n + migration count + project setup + 13 template markup + 3 viewer-leak + 9 Finish [happy/stale-race/viewer/non-owner] + 4 Adjust [happy/empty-reason/viewer] + 4 Add Update [happy/empty/viewer/PM-non-owner] + 2 banner render + 1 AI Intake invariant + 3 Detailed Table regression + 8 Build 06 invariants).
  - `test_v13_build06.py` — updated assertion: accepts either Build 06 anchor pattern or Build 07A form-trigger pattern for the Finish button (planned behavior change, not regression).

## Build 07A — Confirmed locks

1. **Lock 1**: Inline forms inside shared mount, not modals — phase strip + tiles stay visible.
2. **Lock 2**: PRG redirect to `#timeline-command-center` with `?cc_action=...&cc_result=...` query params; banner renders ok-green or error-red.
3. **Lock 3**: Server-side stale-form race protection on Finish — re-derives `current_phase` and rejects if `request.phase_id != server.current_phase.id` OR phase is already `done`.
4. **Lock 4**: Reason required server-side for Adjust Due Date (whitespace-only also rejected).
5. **Lock 5**: Reused Build 14 entry_type vocabulary unchanged (9 options).
6. **Lock 6**: Defense-in-depth — every new route re-runs `require_auth` + `can_edit_project` + (Add Update) `can_view_journal`.
7. **Lock 7**: No server-side idempotency tokens for these 3 routes (race protection / service-layer no-op / journal cheapness handle it). **Amendment**: Add Update form has `data-cc-disable-on-submit` → JS disables submit on first click with spinner. UX only, not load-bearing.

## What stays placeholder

- **Add Blocker** — disabled button, tooltip now says "Coming Build 07B — needs Architecture Review for blocker model". Architecture Review for the blocker model will be its own plan file before Build 07B implementation.

## Verification at ship time

- `python3 test_v13_build07.py` — **57/57 PASS**.
- Regression: `test_v13_build01..06` all green (Build 06 updated for Build 07A button pattern); `test_build_v121` 19/19; `test_build30` 23/23; `test_ai_e2e.py` 15P/2S/0F.
- i18n parity: 666/666.
- No new migration (still 5); no schema change; no service change; no AI tool change.

## Reference: uploaded v1.3 product spec docs

User-provided canonical references for v1.3:
- `project_overview_redesign_plan.md` (Overview tab; covers Builds 01-05)
- `timeline_command_center_redesign_plan.md` (Timeline tab; covers Builds 06-09)
- `V13_BUILD07_TIMELINE_COMMAND_ACTIONS_PLAN.md` — user's high-level Build 07 doc with the Required Action Mapping checklist that Build 07A's Backend Honesty Mapping satisfies for 3 of 5 actions.

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
| **07A — Timeline Command Actions (3 routes)** | **shipped this session** | latest |
| 07B — Blocker model + Add Blocker wiring | planned (needs Architecture Review) | — |
| 08 — Timeline History | planned | — |
| 09 — Planning Sandbox (design-only) | planned | — |

## Next step

Wait for user direction. Suggested next moves:
1. **Push** to origin (currently several commits ahead of `origin/main` after this build).
2. **Build 07B Architecture Review** — write the Architecture Review document for the blocker model first (per user's V13_BUILD07_TIMELINE_COMMAND_ACTIONS_PLAN.md gate). Resolve the 7 open questions sketched at the end of V13_BUILD07_EXECUTION_PLAN.md. Then write V13_BUILD07B_EXECUTION_PLAN.md before any 07B coding.
3. **Build 08** — Timeline History view, derived from `project_changes` + `phase_plan_changes` + `project_journal_entries` + file uploads. No new table per the doc.
4. **Browser walkthrough** of Build 07A: click each of the 3 buttons, verify forms appear inline below the action row, fill and submit each, verify banner appears and state updates correctly.

## Deferred to future builds (carried forward from v1.2.1)

- Native-speaker Chinese review of strings added in Builds 26-30C + v1.3 Builds 01-07A.
- AI prompt translation, Help modal body translation, `/admin/*` page translation.
- Full Profit Model implementation (variant cell shows naive margin; full model is v1.4).
- Row-level multi-tenancy (`Organization` table + `org_id` everywhere). Deployment-level isolation (Build 25) remains the answer for ≤3 departments.
- Bulk delete from the projects list / soft-delete with undo window.
- Auto-provisioning script for Railway (the DEPLOYMENT.md runbook is still manual).
- One-time admin cleanup of the original 6 admin-linked duplicates from the Build 30A incident.

## v1.3 process pattern (continues)

Every build gets a build-specific execution plan before coding. Plan files are committed/reviewed first. Locks (route choices, anchor strategies, i18n keys, schema/service constraints) are resolved in-plan before implementation starts. Builds 06 + 07A both added a **Backend Honesty Mapping** per visible field — every field is either honestly sourced (with source-of-truth path + write-path + permission rule + test coverage) or marked as an EXPLICIT placeholder. Build 07A also added **Locked Decisions** (7 locks) — explicit named choices the user confirmed before coding started. This discipline scales to higher-risk builds (07B, blocker model; 09, planning sandbox).
