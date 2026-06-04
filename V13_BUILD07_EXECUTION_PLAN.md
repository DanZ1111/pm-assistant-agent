# v1.3 Build 07 Execution Plan — Timeline Command Actions Backend

## Status

Plan-only execution gate. No code until this plan is reviewed and approved.

Predecessor: Build 06 shipped at `4a800d6` (Timeline Command Center display-only shell). Today the Command Center's five action buttons either link to existing Detailed Table controls via `#phase-row-{id}` anchors with auto-expand JS (Finish, Adjust Due Date) or to `#journal` (Add Update); [Add Blocker] is a disabled placeholder; [Open AI Intake] opens the existing assistant side panel.

Build 07 replaces those link-stubs with dedicated Command Center routes so each visible action **moves real backend state, refreshes derived state, and leaves an audit/history record behind** — per the user's `V13_BUILD07_TIMELINE_COMMAND_ACTIONS_PLAN.md` (committed `75db65c`) acceptance criteria.

## User Problem (from the canonical doc + Build 07 pre-doc)

> "Timeline actions move real backend state, refresh derived state, and leave audit/history behind. No action is wired by merely changing frontend text."

> "This is the highest-risk build in v1.3."

> "If a row [in the action mapping] cannot be completed honestly, that action remains placeholder."

## Scope Decision Gate — proposed split into 07A + 07B

Build 07's full surface (Finish + Adjust + Add Update + Add Blocker + AI Intake) couples three unrelated risk profiles:

| Risk profile | Actions | Why grouped |
|---|---|---|
| **Low risk** — reuses existing services unchanged | Finish Current Phase, Adjust Due Date, Add Update | Each maps to an existing `crud.*` write that already handles audit + derived-state refresh. Build 07 only adds a new POST route + a small inline form/modal. |
| **High risk** — needs Architecture Review + new schema | Add Blocker | Doc says: "Add Blocker always requires the pre-build Architecture Review." New `project_blockers` table + service + migration + Pulse/Command Center display impact. |
| **Zero risk** — already wired | Open AI Intake | Build 06 already opens the existing assistant side panel; no backend route needed. Project context is already injected by the panel's existing `?project_id` handling. |

### Recommendation: ship Build 07 in two slices

- **Build 07A — Wire 3 honest actions + keep Add Blocker placeholder.** Ships Finish / Adjust / Add Update via dedicated Command Center routes. AI Intake stays as-is. Add Blocker stays disabled with updated tooltip pointing at Build 07B. Lower risk, smaller footprint.
- **Build 07B — Blocker model + Add Blocker wiring + Command Center "Main blocker" honest field.** Architecture Review committed first; migration 006 + `project_blockers` table + Pulse impact + Command Center display + AI tool registry update.

Rationale per user's "high-risk, move slowly; correctness matters more than speed" mandate:

- 07A's risk is mostly UX (where redirect lands, how reason input appears) — backend writes are unchanged services with existing tests.
- 07B is a true new-feature build. Splitting it out means the Architecture Review happens in a dedicated plan file, not as a section of a larger plan.
- If the user rejects this split, this plan can absorb 07B in full — but the doc explicitly contemplates "If this decision is not complete, Build 07 must leave Add Blocker as a placeholder," which is exactly the 07A split.

**Open question — locked decision required before implementation starts: 07A-only, or 07A+07B in one build?** Default assumption in the rest of this plan: **07A-only**. The 07B section at the end sketches the follow-on for visibility.

## Wireframe Alignment Check (per canonical doc §5.2)

User's wireframe specifies inline confirmation panels — not separate pages. Each action either:
- Inline form expansion (Add Update, Adjust Due Date) below the action button row.
- Confirmation checklist (Finish Current Phase) — small modal-style overlay listing pre-finish checks (e.g., "All required fields set? Owner assigned? Actual end date filled?") then a single submit.
- One-click (AI Intake — opens existing side panel).

Build 07A renders these as:
1. **Finish Current Phase** → confirmation card that appears in place of the action row when clicked. Lists 3 derived pre-flight checks + textarea for an optional completion note + Confirm / Cancel buttons.
2. **Adjust Due Date** → inline form that expands below the action row: new date input (pre-filled with current planned_end_date) + REQUIRED reason textarea + Save / Cancel.
3. **Add Update** → inline form below the action row: entry_text textarea + entry_type select (general / risk / decision / factory_discussion / cost_discovery) + Save / Cancel.

All three forms render with a single shared `<details>` toggle pattern OR a single shared form-mount `<div id="command-action-form">` that the action button populates via existing template fragments. **Lock 1** picks between these two patterns.

## Backend Honesty Mapping (per action — completes the doc's Required Action Mapping table)

| UI action | Route (new) | Service called | DB write | Derived state refresh | Audit/history entry | Permission rule | Reason required | Build 07 test coverage |
|---|---|---|---|---|---|---|---|---|
| **Finish Current Phase** | `POST /projects/{pid}/command/finish-phase` | `crud.finish_phase(db, phase_id, changed_by, changed_by_user_id)` (existing, Build 17) | `project_phases`: status='done', actual_end_date=today (if NULL); next phase status='in_progress', actual_start_date=today | `project.current_stage` recalculated via `recalculate_stage_and_delay()` (already inside service) | `project_changes` row "phase_finished" (already written by service); optional completion note → second `project_changes` row of type "event_note" if textarea non-empty | `can_edit_project` AND `current_phase.status != 'done'` AND `current_phase.id == request_phase_id` (server re-validates so a stale form can't finish a phase that's already been advanced by someone else) | No (optional completion note free-text) | New test: finish from CC writes status='done' + advances next; pre-flight check displayed; viewer 403; cross-user race protection |
| **Adjust Due Date** | `POST /projects/{pid}/command/adjust-due-date` | `crud.update_phase(db, phase_id, data, changed_by, reason, changed_by_user_id)` (existing, Build 17) | `project_phases.planned_end_date` shifted | `recalculate_stage_and_delay()` runs inside `update_phase` — Command Center `health_band`, `days_left`, `pressure_dots` all recompute on next page load | `phase_plan_changes` row (already written by service) + `project_changes` row "phase_update" (already written) | `can_edit_project` AND `current_phase` exists | **YES** — empty reason redirects with `?timeline_error=reason_required` (mirrors existing Detailed Table behavior at `app/routes/projects.py:737`) | New test: shift accepted with reason; empty reason rejected; phase_plan_changes row created with reason; health_band recomputes |
| **Add Update** | `POST /projects/{pid}/command/add-update` | `crud.create_journal_entry(db, project_id, entry_text, entry_type, author_user_id)` (existing, Build 14) | `project_journal_entries` row | None directly (Journal section + Project Pulse pick it up on next render) | The new journal row itself IS the audit record. Build 14 doesn't write a separate `project_changes` row for journal creates — this matches existing behavior. | `can_edit_project` AND `can_view_journal` (admin + PM only — viewer cannot use this action; Build 06 already hides the button) | No (entry_text required by service; empty = reject with `?command_error=empty_update`) | New test: entry inserted with correct author_user_id + entry_type; viewer cannot POST (403/redirect); empty text rejected |
| **Add Blocker** | **NO ROUTE — placeholder remains** | (none in 07A) | (none) | (none) | (none) | `can_edit_project` for visual consistency (button stays rendered, disabled) | n/a | Existing Build 06 disabled-state test continues to pass; tooltip updated to "Coming Build 07B" |
| **Open AI Intake** | **NO NEW ROUTE — JS-only** | (existing AI assistant panel) | (none until user confirms a proposal in chat — that path is Build 27's confirmation system) | (none) | (existing AI message + confirmation audit covers this; no Command Center–specific audit) | `can_use_ai_intake` (admin + PM only — Build 06 already hides for viewer) | n/a | Existing Build 06 button-visibility test continues to pass; verify clicking still opens `#aiSidePanel` |

### Reading the mapping

**Build 07A ships honest backend wiring for 3 of 5 actions.** All three reuse Build 14/17 services whose audit + derived-state refresh paths are already tested. The new code is route plumbing + form templates + redirect-with-flag for inline error/success messages.

**Add Blocker stays placeholder** with a tooltip pointing at Build 07B. The button keeps its `disabled` attribute. No behavior change vs. Build 06 for this button.

**AI Intake stays as-is** — Build 06 wired the JS opener; there is no new backend write to add. AI-confirmed mutations already flow through the Build 27 confirmation system, which is audited.

## Feature Design Review (11 questions)

1. **Real workflow problem:** PMs currently have to scroll to the Detailed Table, open the row's edit modal, fill in dates, click save. Build 07A puts the three most-frequent actions directly in the Command Center where the PM already is.
2. **Repeated or edge-case:** Repeated daily; Finish Phase happens at every phase boundary, Adjust Due Date during every slip, Add Update for any meeting/decision.
3. **Structured data:** Existing — `ProjectPhase`, `ProjectJournalEntry`, `PhasePlanChange`, `ProjectChange`. No new schema.
4. **Could live in notes first:** Already exists in the Detailed Table; Build 07A elevates the call-to-action.
5. **Intake burden:** Zero new intake — just relocates existing controls.
6. **AI role:** Unchanged. AI Intake button opens existing assistant; AI-driven phase finishes / journal entries still flow through Build 27's confirmation system.
7. **Display payoff:** PM lands on Timeline, sees the deadline pressure, and acts in one click without scrolling.
8. **Migration impact:** None (07A). 07B will add migration 006.
9. **Minimal schema:** Zero (07A).
10. **Minimal UI change:** Three new dedicated POST routes; three new inline form templates; one shared form-mount container; one new "Command Center action result" toast/banner; updated `[Add Blocker]` tooltip; small JS to toggle which form is visible.
11. **Deferred:** Add Blocker model + wiring (Build 07B); AI Nudge generator (Build 07B+); Timeline History view (Build 08); Templates / Planning Sandbox (Build 09+).

## Locked Decisions (require user confirmation before implementation)

### Lock 1 — Form-mount pattern
Single shared mount container `<div id="cc-action-form" class="cc-action-form-mount">` directly below the action button row. The 3 action buttons (Finish / Adjust / Add Update) gain `data-cc-form="finish|adjust|add-update"`. A tiny inline script (~15 lines) shows/hides one of three inline-rendered `<form>` blocks based on which button was clicked. Each form is server-rendered with the current phase's pre-filled values; no AJAX. Cancel button hides the mount; Save submits via PRG.

**Alternative considered:** A single Bootstrap modal that re-skins per action. Rejected because the Command Center is supposed to *reduce* mental burden — a modal pulls focus away from the surrounding context (phase strip, tile state) the PM is using to decide what to do. Inline form keeps it all on one screen.

### Lock 2 — Redirect target + result feedback
All three POST routes redirect to `/projects/{pid}?cc_result={ok|error_code}&cc_action={finish|adjust|add-update}#timeline-command-center` (PRG). The Command Center renders a dismissible toast/banner at the top of the section when `cc_result` is present. Error codes: `reason_required` (Adjust), `empty_update` (Add Update), `phase_already_done` (Finish race), `not_authorized` (any). Success: brief green banner with the action name.

### Lock 3 — Server-side phase-id validation for Finish
The Finish form includes `<input type="hidden" name="phase_id" value="{{ current_phase.id }}">`. The route MUST re-derive the project's actual current phase server-side and reject if `request.phase_id != server.current_phase.id` (return `?cc_result=phase_already_done`). This protects against the race where two PMs open the page, PM-A finishes the phase, PM-B's stale form would otherwise advance the next phase by accident.

### Lock 4 — Reason enforcement for Adjust Due Date
Same rule as the existing Detailed Table flow at `app/routes/projects.py:737`: empty `reason` on a plan-date change → redirect with `?cc_result=reason_required`. Reuses `crud.update_phase(reason=...)`. Reason field has `required` HTML attribute as belt-and-suspenders; server check is load-bearing.

### Lock 5 — Add Update entry_type vocabulary
Reuse Build 14's existing vocabulary: `general / factory_discussion / cost_discovery / design_feedback / decision / risk / packaging / variant / other`. Default = `general`. The select element is sourced from a small Python list `ENTRY_TYPES` in `app/routes/projects.py` (lifted from journal.py if needed) so future additions stay in one place.

### Lock 6 — Permission re-validation (defense in depth)
Each new route independently re-runs `require_auth` + `can_edit_project` (and `can_view_journal` for Add Update). Form rendering hides buttons the user can't use, but server-side checks are the load-bearing protection. Mirrors the Build 14 / Build 17 pattern.

### Lock 7 — No idempotency tokens for these routes
Build 30A's `project_creation_tokens` covers project creation. For Finish/Adjust/Add Update, idempotency comes from server-side state: Finish re-checks `current_phase.id` (Lock 3); Adjust is idempotent because the same date set twice is a no-op (`update_phase` only writes a `phase_plan_changes` row when the date actually changed); Add Update is per-journal-entry so double-submit creates two rows — accepted risk since journal entries are cheap and PMs can edit/delete in Build 14. If duplicate-journal becomes a real problem, Build 07B can add the same token pattern (small scope).

## UI Scope

Touch (Build 07A):
- `app/templates/project_detail.html` — add `data-cc-form="..."` to the 3 action buttons; add the shared `<div id="cc-action-form">` mount with 3 inline `<form>` children (rendered conditionally on `can_edit` + `can_view_journal`); add the dismissible result banner at the top of `#timeline-command-center`; update `[Add Blocker]` tooltip to "Coming Build 07B".
- `app/routes/projects.py` — add 3 new routes (`POST /projects/{pid}/command/finish-phase`, `/command/adjust-due-date`, `/command/add-update`). Each is thin — re-auth, re-check permissions, run server-side state validation, delegate to existing service, redirect with `?cc_result=...`.
- `app/static/css/styles.css` — append `.cc-action-form*` + `.cc-result-banner*` styles. Form-mount has a subtle background to visually attach to the action it came from.
- `app/static/js/main.js` — add ~20 lines: show/hide form mount, focus first field, Cancel button hide.
- `app/i18n/en.json` + `zh.json` — ~14 new keys: form labels (reason, completion note, entry text, entry type), result-banner texts (success / 4 error codes), updated Add Blocker tooltip. Parity target 665/665.
- `test_v13_build07.py` — new file (target ~30 assertions).
- `CURRENT_TASK.md`, `CHANGELOG.md`.

Do not touch (Build 07A):
- `app/models.py` (no schema change)
- `app/migrations.py` (no migration)
- `app/crud.py` (no service change — routes call existing services)
- AI tool registry (already covers the relevant tools; Build 07B may extend it for blockers)
- Existing `/projects/{pid}/phases/{phase_id}/edit`, `/finish`, `/journal` routes (unchanged; Detailed Table still uses them)

## Permissions

| Action | Visibility (button) | Server-side enforcement |
|---|---|---|
| Finish Current Phase | `can_edit_project` AND `current_phase.status != 'done'` | re-run both checks + Lock 3 phase-id race check |
| Adjust Due Date | `can_edit_project` AND `current_phase` exists | re-run + Lock 4 reason check |
| Add Update | `can_edit_project` AND `can_view_journal` | re-run both |
| Add Blocker | `can_edit_project` (button stays disabled — no route) | n/a |
| Open AI Intake | `can_use_ai_intake` | n/a (no route) |

Viewer sees only the phase strip, tiles, and placeholders. No action buttons render. Server-side route POSTs from a viewer return `?cc_result=not_authorized` (defense in depth — UI hides them but never trust the client).

## i18n Keys (locked EN + zh, parity-required)

| Key | EN | ZH |
|---|---|---|
| `timeline.cc_finish_confirm_title` | Finish this phase? | 完成此阶段？ |
| `timeline.cc_finish_checklist` | This will mark the phase done and start the next phase. | 此操作将完成当前阶段并开启下一阶段。 |
| `timeline.cc_finish_note_label` | Completion note (optional) | 完成备注（可选） |
| `timeline.cc_adjust_new_date` | New due date | 新的截止日期 |
| `timeline.cc_adjust_reason_label` | Why is this date changing? | 截止日期变更原因 |
| `timeline.cc_adjust_reason_placeholder` | Required — e.g., factory pushed sample 1 week | 必填 — 例如：工厂将样品延后一周 |
| `timeline.cc_update_text_label` | Update | 更新内容 |
| `timeline.cc_update_type_label` | Type | 类型 |
| `timeline.cc_btn_confirm` | Confirm | 确认 |
| `timeline.cc_btn_cancel` | Cancel | 取消 |
| `timeline.cc_result_ok` | Done. | 已完成。 |
| `timeline.cc_result_reason_required` | A reason is required for date changes. | 调整截止日期必须填写原因。 |
| `timeline.cc_result_empty_update` | The update text cannot be empty. | 更新内容不能为空。 |
| `timeline.cc_result_phase_already_done` | This phase was already finished — refreshing. | 此阶段已被完成 — 正在刷新页面。 |
| `timeline.cc_result_not_authorized` | You do not have permission for that action. | 您无权执行此操作。 |
| `timeline.btn_add_blocker_tooltip` (UPDATE) | Coming Build 07B — needs Architecture Review for blocker model | 即将在 Build 07B 上线 — 需先完成阻碍数据模型架构评审 |

15 new + 1 updated = 16 string changes. Parity target: 665/665 (651 + 14 net-new — `btn_add_blocker_tooltip` already exists, so only its value updates).

## Tests — test_v13_build07.py

Target ~30 assertions. Mirrors existing v1.3 test files (requests.Session + sqlite3).

### Finish Current Phase
1. POST with valid phase_id (admin / PM owner): phase status → done, actual_end_date set, next phase status → in_progress, project.current_stage advanced, `project_changes` rows created.
2. POST while phase is already done (Lock 3 race): redirects with `?cc_result=phase_already_done`, no state change.
3. POST with wrong phase_id (stale form): same race redirect, no state change.
4. POST from viewer: redirects with `?cc_result=not_authorized`, no state change.
5. POST from non-owner PM (project assigned to different PM): same not_authorized redirect.
6. Optional completion note (textarea non-empty): a second `project_changes` row of type `event_note` written with the note text.

### Adjust Due Date
7. POST with new date + reason: `project_phases.planned_end_date` updated, `phase_plan_changes` row written with reason, `project_changes` "phase_update" row written.
8. POST with empty reason (Lock 4): redirects with `?cc_result=reason_required`, no state change.
9. POST with same date as current: no `phase_plan_changes` row (idempotent at service layer).
10. After Adjust, Command Center health_band / days_left recompute correctly (request page, assert badge class changed).
11. Viewer POST: `?cc_result=not_authorized`.

### Add Update
12. POST with text + entry_type='risk': `project_journal_entries` row written with `entry_type='risk'`, `author_user_id=current_user.id`.
13. POST with empty text: `?cc_result=empty_update`.
14. POST from viewer: `?cc_result=not_authorized` (gated on `can_view_journal`).
15. POST from PM on a project they don't own: `?cc_result=not_authorized`.
16. Created entry appears in `#journal` section markup on next render.

### Cross-cutting
17. All 3 new routes redirect to `/projects/{pid}...#timeline-command-center` on success.
18. Result banner renders with `data-cc-result="ok"` / `data-cc-result="reason_required"` etc. when `?cc_result` is present.
19. `[Add Blocker]` tooltip text contains "07B" (regression on the updated string).
20. AI Intake button still triggers the side-panel open script (Build 06 invariant preserved).
21. Detailed Table still works: existing `/projects/{pid}/phases/{phase_id}/edit` and `/finish` routes unchanged (POST + 303 + state assertions). This is the **critical regression check** — we must not break the existing flow.
22. i18n parity at 665/665.
23. No new migration (still 5).
24. Inline form renders pre-filled current planned_end_date in the Adjust form.
25. Inline form for Add Update has all 9 entry_type options.
26. Finish confirmation card shows the 3 pre-flight check lines.
27. Viewer never sees any of the 3 forms (forms gated on `can_edit` + appropriate role).
28. Build 06 invariants preserved: phase strip data-status ordering, 3-tile grid, placeholders, Detailed Table `<details>` closed by default, phase-row id anchors.
29. Build 01/02/03/04/05/05B invariants preserved (run those suites; assert 0 regressions).
30. `test_build_v121.py` 19/19 (release-proof regression).

### Manual browser walkthrough (acceptance criteria check)
- Log in as PM on an owned project; click Finish — see confirmation card; Confirm; page reloads with success banner; phase strip shows next phase as current.
- Adjust Due Date inline; leave reason blank; click Save; see red banner; reason becomes required; refill; Save; page reloads; new days_left badge color matches new date.
- Add Update inline; pick type=risk; type some text; Save; page reloads with banner; refresh and confirm entry appears in Journal section.

## Explicit Deferrals

- Add Blocker model + wiring → **Build 07B**.
- AI Nudge generation → Build 07B+ (architecture review for rule engine vs LLM call).
- Timeline History view derived from `project_changes` + `phase_plan_changes` + journal + files → Build 08.
- Templates / Planning Sandbox → Build 09+.
- Bulk phase operations (finish multiple, shift all due dates) → not planned for v1.3.
- AJAX form submit (no page reload) → out of scope. PRG matches the rest of the app.
- Per-phase Owner change via Command Center → out of scope (use Detailed Table).
- Per-phase Actual Start Date manual edit via Command Center → out of scope (Finish service auto-fills next phase's actual_start_date; manual edit lives in Detailed Table).

## Rollback / Safety

Backend rollback is route/template/i18n/test only:
- Delete the 3 new routes from `app/routes/projects.py`.
- Restore the 3 link-anchor action buttons in `project_detail.html` (pre-Build-07 form).
- Remove the 3 inline form templates + form-mount + result banner.
- Remove Build 07 CSS + JS hooks + i18n keys.
- Remove `test_v13_build07.py`.

Existing services (`crud.finish_phase`, `crud.update_phase`, `crud.create_journal_entry`) are unchanged — Build 07 only adds *callers*, not modifications. The Detailed Table flow remains the alternate path the entire build.

No database state is at risk. Even mid-build with broken routes, the Detailed Table provides the full edit surface.

## Acceptance Criteria

- All 3 Command Center actions (Finish, Adjust, Add Update) move real DB state via dedicated routes.
- Each action shows pre-flight info inline (no separate page).
- Adjust Due Date rejects empty reason server-side, not just in the HTML.
- Finish protects against the stale-form race (Lock 3).
- Success and error feedback render as a Command Center banner, not a generic flash.
- Derived state (phase strip, health_band, days_left, current_phase) refreshes correctly after each action.
- Viewer cannot execute any of the 3 routes (server-side rejection, not just hidden buttons).
- PM can act only on projects they own.
- `[Add Blocker]` remains disabled; tooltip says "Coming Build 07B".
- AI Intake button still opens existing side panel; no new wiring needed.
- Detailed Table flow (Build 17) continues to work unchanged.
- All 3 actions produce audit/history records (phase change log row, phase_plan_changes row, journal entry).
- i18n parity at 665/665.
- No schema change, no migration, no service change, no AI tool change.

## What Build 07A Solves From the User's Doc

| Acceptance criterion (from `V13_BUILD07_TIMELINE_COMMAND_ACTIONS_PLAN.md`) | Build 07A response |
|---|---|
| "Wire Finish Current Phase from Command Center" | ✓ New `POST /command/finish-phase` route |
| "Wire Adjust Due Date only through a reason-required flow" | ✓ Lock 4 enforces reason server-side |
| "Wire Add Update to a confirmed/auditable record" | ✓ Journal entry is the audit record; author_user_id captured |
| "Wire Add Blocker only if source-of-truth mapping is approved" | ✓ Deferred to Build 07B (matches doc's "if decision not complete, leave as placeholder") |
| "Keep AI Intake confirmation-gated; no silent mutation" | ✓ No change from Build 06; existing Build 27 confirmation system unchanged |
| "Ensure every action updates derived display after redirect" | ✓ All redirects target `#timeline-command-center`; existing services already call `recalculate_stage_and_delay` |
| "Timeline actions move real backend state, refresh derived state, and leave audit/history behind" | ✓ All three actions verified end-to-end in `test_v13_build07.py` |
| "No action is wired by merely changing frontend text" | ✓ Three new dedicated routes with re-validated permissions, not template hacks |

## Sketch of Build 07B (not in 07A scope — Architecture Review required before plan write)

For visibility:

### Architecture Review questions to resolve in the 07B plan
1. **Model choice (final).** Default: new `project_blockers` table (per the doc's default planning assumption). Confirm vs. extending `project_journal_entries` (per-doc alternative).
2. **Per-phase vs per-project association.** If per-phase: `phase_id` FK + display under the phase in the strip. If per-project: blockers can predate phase creation. Likely per-project with optional `phase_id` FK.
3. **Active/resolved state model.** `status` enum (`active` / `resolved`) + `resolved_at` timestamp + `resolved_by_user_id`? Or computed from absence of an "open" record? Likely the former.
4. **Display impact.**
   - Command Center "Main blocker" tile → newest active blocker (or "No active blockers" honest empty state).
   - Project Pulse v1 (Build 02) → active-blocker count drives the next-action recommendation.
   - Phase strip → optional red dot on phases with at least one active blocker.
5. **Permission model.** PM creates / edits / resolves their own project's blockers; admin all; viewer read-only.
6. **AI tool registry.** New `create_blocker` + `resolve_blocker` tools, gated through Build 27 confirmation system.
7. **Migration 006.** Additive, idempotent, mirrors Build 05B / Build 30A pattern.

### Skeleton 07B scope (estimate)
- New table `project_blockers` (id, project_id, phase_id NULL, title, description, severity ENUM, status ENUM, created_at, created_by_user_id, resolved_at, resolved_by_user_id).
- New routes: `POST /projects/{pid}/blockers`, `POST /projects/{pid}/blockers/{bid}/resolve`, `POST /projects/{pid}/blockers/{bid}/edit`.
- New service: `crud.create_blocker`, `crud.resolve_blocker`, `crud.update_blocker` — each writes `project_changes` audit.
- Command Center "Main blocker" tile flips from placeholder to honest field.
- AI tool registry updated; UPDATE_BLOCKER_ALLOWED whitelist added.
- Migration 006.
- `test_v13_build07b.py` ~25 assertions.

This sketch is for context only — Build 07B starts with its own Architecture Review document, not by editing this file.

---

End of Build 07 (07A scope) execution plan. Implementation begins only after this is reviewed and approved. **The scope-split question (07A-only vs 07A+07B in one build) is the primary user decision required before coding.**
