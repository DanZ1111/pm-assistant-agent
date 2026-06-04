# v1.3 Build 06 Execution Plan — Timeline Command Center Shell

## Status

Plan-only execution gate. No code until this plan is reviewed and approved.

Predecessors: Build 05B shipped at `dd96cf2`. The Timeline tab (`workspace-panel-timeline`) already exists from Build 01; today it renders only the legacy planned/actual `timeline-table-v2`.

The user's `timeline_command_center_redesign_plan.md` is the canonical Timeline product vision. This plan implements Section 5.1 (Command Center) display only — wiring the action buttons to backend mutations is the next build (07).

## User Problem (from the canonical doc)

> "The Timeline tab should not be a passive date list or a database-style planned/actual table. It should become a PM execution command center: a page that pushes the project forward, creates deadline pressure, reminds the PM what needs to happen next, and reduces the mental burden of tracking everything manually."

> "The first section should answer: what is happening now, what needs attention, what should the PM do next?"

> "If the project is normal and has no major issue, the PM should not need to use the full phase map or history log."

## Product Decision

Build 06 ships **display + visual structure only** for the Command Center. Action buttons render as visible affordances but route through the existing Detailed Table controls (Finish Phase / Adjust Due Date) which keep working. Build 07 then wires each Command Center button to its honest backend route with focused tests per action.

Rationale for splitting display from wiring per the user's "move slowly, correctness matters more than speed" mandate:

- Build 06 has zero behavior change risk — only adds new markup; existing Finish Phase / Edit Phase / Add Journal Entry routes continue to work via the Detailed Table.
- Build 07 wires each Command Center button to its existing route with its own test surface; if something subtly breaks, the rollback footprint is small and isolated.
- Build 08 derives Timeline History from existing records (journal + phase_plan_changes + change log + file uploads + AI intake).

The user's Timeline doc §8 Build A merged display + wiring + history into one build. I'm keeping Codex's Builds 06 / 07 / 08 split as approved in `V13_MASTERPLAN.md` for risk control. Build 06 is the smallest of the three.

## Wireframe Alignment Check

User's wireframe §5.1 specifies:

```
TIMELINE COMMAND CENTER

Idea  Design  Quotation  Sample  Packaging  Production
✓Done ✓Done  ✓Done      ●Current ○Next      ○Later

┌──────────────────┬──────────────────┬──────────────┐
│ Current Phase    │ Next Action      │ Deadline     │
│                  │                  │              │
│ Sample Dev       │ Confirm handle…  │ Due Jun 12   │
│ Health: At Risk  │ Owner: Factory   │ 3 days left  │
│ Started: Jun 1   │ AI: ask today    │ Pressure: 🔥 │
└──────────────────┴──────────────────┴──────────────┘

Main blocker
Packaging cost is still missing. This may delay sample approval.

AI Nudge
"You should confirm packaging cost before…"

[Add Update] [Add Blocker] [Adjust Due Date] [Finish Current Phase] [AI Intake]
```

Build 06 covers:
- ✓ Phase strip with Done / Current / Next / Later states (honest — phase data exists)
- ✓ Current Phase tile (name, status, started date)
- ✓ Next Action tile (current phase name + owner — Next Action TEXT is a placeholder until Build 07)
- ✓ Deadline tile (due date from `planned_end_date`; days-left/overdue from today's date)
- ⚠ Main blocker → **explicit placeholder** ("No blocker model yet — Build 07")
- ⚠ AI Nudge → **explicit placeholder** ("AI nudges coming later")
- ✓ Action buttons rendered as placeholders; clicking opens the existing Detailed Table edit modal or scrolls to it. Build 07 wires each to its dedicated route.
- ✓ Detailed Table (existing timeline-table-v2) hidden behind an expand toggle.

Doc compliance: every visible field is either honestly sourced OR an EXPLICIT placeholder. No fake intelligence. ✓ Per doc §1.5.

## Feature Design Review (11 questions)

1. **Real workflow problem:** PMs need first-screen execution pressure on the Timeline tab — current phase, deadline, action — without scrolling through a database-style table.
2. **Repeated or edge-case:** Repeated daily; this is the primary execution screen.
3. **Structured data:** All fields use existing data (`ProjectPhase`, `Project.current_stage`, `calculate_delay()`). Blocker placeholder reserves space for a future model.
4. **Could live in notes first:** The Detailed Table already does this. Build 06 is the upgrade pass.
5. **Intake burden:** Zero new intake — display only.
6. **AI role:** AI Nudge is a placeholder. Existing AI intake button opens the existing assistant panel with `project_id` context (unchanged behavior).
7. **Display payoff:** PM lands on Timeline tab and immediately sees stage / current phase / due date / pressure indicator. Action buttons preview the upcoming Build 07 control surface.
8. **Migration impact:** None. No schema change.
9. **Minimal schema:** Zero. Build 06 reads existing tables.
10. **Minimal UI change:** Add new Command Center section above the existing Detailed Table; wrap the existing table in a collapsible `<details>` element with "Detailed Table" summary.
11. **Deferred:** Action wiring (Build 07), Blocker model + UI (Build 07), AI Nudge generation (Build 07+), Timeline History view (Build 08), Templates / Planning Sandbox (Build 09+).

## Backend Honesty Mapping

| Visible field | Source of truth | Write path | Derived-state rule | Permission rule | Current test coverage |
|---|---|---|---|---|---|
| **Phase strip** (Done / Current / Next / Later) | `ProjectPhase.status` for each phase ordered by `phase_order` | Existing Finish Phase + Edit Phase routes (Build 17) | "Done" = status in ('done','skipped'); "Current" = first non-done by phase_order; "Next" = phase immediately after current; "Later" = all remaining | All authenticated users can view | Build 17 covers status transitions; Build 06 adds rendering tests |
| **Current Phase tile — name** | `derive_current_stage(phases)` from `app/crud.py:190` | (read-only) | First non-(done/skipped) phase by `phase_order` | All authenticated | Build 17 |
| **Current Phase tile — health badge** | `calculate_delay(project, phases)["days_late"]` from `app/crud.py:165` | (read-only) | If `delay` is None → "On track"; if `days_late <= 3` → "At Risk"; else "Delayed" | All authenticated | Build 17 (delay calc); Build 06 adds health-band rendering tests |
| **Current Phase tile — started date** | `current_phase.actual_start_date` | Finish Phase auto-fills if missing | NULL → "Not started" empty state | All authenticated | Build 17 |
| **Next Action tile — text** | `current_phase.phase_name` | (read-only) | Placeholder narrative: "Move {current_phase.phase_name} forward" until Build 07 layers in journal/blocker-derived next action text | All authenticated | Build 06 (new — verifies placeholder string) |
| **Next Action tile — owner** | `current_phase.owner` (free-text String, exists today) | Edit Phase modal | NULL → "Not assigned" empty state | All authenticated | Build 17 owner field exists; Build 06 adds rendering test |
| **Deadline tile — due date** | `current_phase.planned_end_date` | Edit Phase modal (Build 17) — writes `PhasePlanChange` on shift | NULL → "Not set" | All authenticated | Build 17 |
| **Deadline tile — days left / overdue** | Computed from `current_phase.planned_end_date - date.today()` | (read-only) | If today > planned_end → "{N} days overdue" badge red; if 0 < days_left ≤ 7 → "{N} days left" badge amber; if days_left > 7 → "{N} days left" badge neutral; if planned_end is NULL → "No due date set" muted | All authenticated | Build 06 (new — adds days-left derivation) |
| **Deadline tile — pressure indicator** | Same `days_left` derivation | (read-only) | Visual only: ●/●●/●●● dots based on overdue or ≤3 days | All authenticated | Build 06 |
| **Main blocker** | **PLACEHOLDER — no blocker model exists today** | (none) | Renders "No blocker model yet. Blockers are planned for Build 07 — use a journal entry of type=risk in the meantime." (with link to Journal section) | All authenticated | Build 06 (placeholder text + link exists) |
| **AI Nudge** | **PLACEHOLDER — no nudge generator exists today** | (none) | Renders "AI nudges coming later. Use the assistant chat panel below for project-scoped suggestions." (with link to bottom AI chat) | All authenticated | Build 06 (placeholder text + link exists) |
| **[Finish Current Phase] button** | Renders as link to existing Finish Phase form in the Detailed Table | Build 07 will wire a dedicated Command Center submit | Visible only if `current_phase.status != "done"` AND `can_edit_project`; uses `current_phase.id` | `can_edit_project` | Build 06 — verifies link target exists; Build 07 adds backend wiring tests |
| **[Adjust Due Date] button** | Renders as link to existing Edit Phase modal in the Detailed Table | Build 07 will wire a dedicated reason-required form | Visible only if `current_phase` exists AND `can_edit_project` | `can_edit_project` | Build 06 — link exists; Build 07 — backend wiring |
| **[Add Update] button** | Renders as link to existing Journal section "+ Add Entry" form | Build 07 will inline a small entry-text form in the Command Center | Visible only if `can_view_journal` AND `can_edit_project` | `can_view_journal` + `can_edit_project` | Build 14 covers journal CRUD; Build 06 — link exists |
| **[Add Blocker] button** | **PLACEHOLDER — no backend** | (none) | Disabled button with tooltip "Blocker model coming in Build 07" | `can_edit_project` (for visual consistency) | Build 06 — verifies disabled state |
| **[AI Intake] button** | Opens the existing AI assistant side panel | (existing) | Visible if `can_use_ai_intake`; sets `?project_id={project.id}` URL fragment so the panel pre-loads project context | `can_use_ai_intake` | Build 21/22/26 cover the panel; Build 06 — verifies button presence + URL fragment |
| **Detailed Table (expand)** | Existing `timeline-table-v2` markup | Existing Edit Phase modal | (unchanged) | All authenticated to view; can_edit gates the modal | Build 17 |

### Reading the mapping

**Fully honest, can ship Build 06 as-is:** phase strip, current phase tile, deadline tile, all action buttons that link to existing controls, AI Intake button, Detailed Table expand.

**Explicit placeholders (per the doc's discipline rule):** Main blocker, AI Nudge, Add Blocker button. Each renders a clear "coming in Build 07" or "use this workaround instead" message — no fake data.

## UI Scope

Touch:
- `app/templates/project_detail.html` — inside `workspace-panel-timeline` div, prepend the Command Center markup; wrap the existing timeline table in `<details><summary>Detailed Table</summary>…</details>`.
- `app/routes/projects.py` — extend `project_detail` view to compute and pass:
  - `command_center_state` dict with `current_phase`, `phase_strip`, `days_left`, `health_band`, `current_phase_owner` (single O(N) pass over the phases list — no new DB query)
- `app/static/css/styles.css` — append `.timeline-command-*` styles (phase strip, 3-column tile grid, action button row, placeholder treatments).
- `app/i18n/en.json` + `zh.json` — add ~22 new keys for tile titles, status bands, placeholders, action buttons.
- `test_v13_build06.py` — new file (target ~30 assertions).
- `CURRENT_TASK.md`, `CHANGELOG.md`, `V13_BUILD06_TIMELINE_COMMAND_CENTER_SHELL_PLAN.md` (mark plan as superseded by this execution plan).

Do not touch:
- `app/models.py` (no schema change)
- `app/migrations.py` (no migration)
- `app/crud.py` (no service change — Build 07 adds new helpers)
- AI tool registry
- Existing Finish Phase / Edit Phase / Journal routes
- The `timeline-table-v2` markup inside the Detailed Table

## Wireframe-Derived Layout

```
┌─ Timeline Command Center ─────────────────────────────────────┐
│  Phase strip (full width, sticky-ish header)                    │
│  [✓Idea] [✓Design] [✓Quotation] [●Sample] [○Packaging] [○Launch]│
│                                                                 │
│  ┌──────────────┬──────────────┬─────────────────┐              │
│  │ Current Phase│ Next Action  │ Deadline        │              │
│  │ Sample Dev   │ Move Sample  │ Due Jun 12      │              │
│  │ ●At Risk     │ forward      │ ●●  3 days left │              │
│  │ Started Jun 1│ Owner: Tom   │                 │              │
│  └──────────────┴──────────────┴─────────────────┘              │
│                                                                 │
│  Main blocker  [PLACEHOLDER ⓘ]                                  │
│  No blocker model yet. Use a journal entry of type=risk         │
│  in the meantime. → Open Journal                                │
│                                                                 │
│  AI Nudge      [PLACEHOLDER ⓘ]                                  │
│  AI nudges coming later. Use the assistant chat panel for       │
│  project-scoped suggestions. → Open AI chat                     │
│                                                                 │
│  Actions                                                        │
│  [Finish Current Phase] [Adjust Due Date] [Add Update]          │
│  [Add Blocker — coming Build 07] [Open AI Intake]               │
└─────────────────────────────────────────────────────────────────┘

▶ Detailed Table   (collapsed by default)
```

CSS grid for the 3-column tile row: `grid-template-columns: 1fr 1fr 1fr; gap: 1rem`. Collapses to single column at `≤ 768px`.

Phase strip: horizontal flex row with chevron-like phase blocks. Each block renders `phase_name` truncated at 12 chars, status icon (`bi-check-circle-fill` for done, `bi-play-circle-fill` for current, `bi-circle` for not_started, `bi-x-circle` for skipped, `bi-exclamation-circle-fill` red for delayed). On narrow screens, horizontal-scroll instead of wrap so the sequence stays readable.

## Locked Decisions

### Lock 1 — Phase strip layout on mobile
Horizontal scroll, not wrap. Why: maintains left-to-right narrative of project lifecycle ("we're 3 of 7 phases in"). Wrap breaks that mental model.

### Lock 2 — "Current Phase" semantic = `derive_current_stage()` exactly
First phase whose `status` is NOT in `('done', 'skipped')`, ordered by `phase_order`. If all phases are done/skipped, the LAST phase is shown (which means a launched project still shows "Launch — done").

### Lock 3 — Health band rules (deterministic, no AI)
- `delay is None` → "On track" green
- `0 < days_late <= 3` → "At Risk" amber
- `days_late > 3` → "Delayed" red
- Phase has no `planned_end_date` AND status is `not_started` → "Not scheduled" neutral

### Lock 4 — `days_left` derivation
- `today > planned_end` → "{N} days overdue" red
- `0 <= days_left <= 7` → "{N} days left" amber
- `days_left > 7` → "{N} days left" neutral
- `planned_end_date is None` → "No due date set" muted

### Lock 5 — Pressure dots
- Overdue: 3 red dots
- ≤ 3 days left: 2 amber dots
- ≤ 7 days left: 1 amber dot
- Otherwise: no dots

### Lock 6 — Action button targets in Build 06
- `[Finish Current Phase]` → link to existing Finish Phase form via `#phase-row-{current_phase.id}` anchor (Detailed Table expands automatically if user follows the anchor; needs a small JS to expand the `<details>` if a phase row anchor is in the URL hash, similar to Build 05's variant-N pattern).
- `[Adjust Due Date]` → opens the existing `#phaseModal` modal pre-populated for the current phase via the existing Bootstrap data attributes.
- `[Add Update]` → scrolls to `#journal` section and focuses the new-entry textarea.
- `[Add Blocker]` → disabled button + tooltip.
- `[Open AI Intake]` → opens the existing assistant side panel (calls existing JS function used by the navbar AI button).

## Permissions

| Element | Visibility |
|---|---|
| Phase strip | All authenticated |
| Current Phase tile | All authenticated |
| Next Action tile | All authenticated |
| Deadline tile | All authenticated |
| Main blocker placeholder | All authenticated |
| AI Nudge placeholder | All authenticated |
| [Finish Current Phase] | `can_edit_project` |
| [Adjust Due Date] | `can_edit_project` |
| [Add Update] | `can_view_journal` AND `can_edit_project` (viewer can't see Journal at all per Build 14) |
| [Add Blocker] | `can_edit_project` (rendered disabled either way) |
| [Open AI Intake] | `can_use_ai_intake` |
| Detailed Table (expand summary visible) | All authenticated |

Viewer sees: phase strip, current phase tile, deadline tile, placeholders, expand-Detailed-Table summary. No action buttons (or only the AI Intake button if `can_use_ai_intake` is true for viewer — confirm with `can_use_ai_intake` definition before implementing).

## i18n Keys (locked EN + zh, parity-required)

| Key | EN | ZH |
|---|---|---|
| `timeline.command_center` | Timeline Command Center | 时间线指挥中心 |
| `timeline.phase_strip` | Phase progress | 阶段进度 |
| `timeline.current_phase` | Current phase | 当前阶段 |
| `timeline.next_action` | Next action | 下一步动作 |
| `timeline.deadline` | Deadline | 截止日期 |
| `timeline.started` | Started | 开始于 |
| `timeline.not_started_yet` | Not started yet | 尚未开始 |
| `timeline.no_due_date` | No due date set | 未设置截止日期 |
| `timeline.days_left` | {n} days left | 还剩 {n} 天 |
| `timeline.days_overdue` | {n} days overdue | 已逾期 {n} 天 |
| `timeline.health_on_track` | On track | 正常推进 |
| `timeline.health_at_risk` | At Risk | 存在风险 |
| `timeline.health_delayed` | Delayed | 已延期 |
| `timeline.health_not_scheduled` | Not scheduled | 未排期 |
| `timeline.owner_not_assigned` | Not assigned | 未指派 |
| `timeline.move_phase_forward` | Move {phase} forward | 推进 {phase} |
| `timeline.blocker_placeholder_title` | Main blocker | 主要阻碍 |
| `timeline.blocker_placeholder_body` | No blocker model yet. Use a journal entry of type Risk in the meantime. | 阻碍模型尚未上线。当前请使用类型为「风险」的项目日志记录。 |
| `timeline.blocker_open_journal` | Open Journal | 查看日志 |
| `timeline.ai_nudge_title` | AI Nudge | AI 提醒 |
| `timeline.ai_nudge_body` | AI nudges coming later. Use the assistant chat panel for project-scoped suggestions. | AI 提醒功能稍后上线，请先使用助手聊天面板获取项目建议。 |
| `timeline.ai_nudge_open_panel` | Open AI chat | 打开 AI 聊天 |
| `timeline.btn_finish_phase` | Finish Current Phase | 完成当前阶段 |
| `timeline.btn_adjust_due_date` | Adjust Due Date | 调整截止日期 |
| `timeline.btn_add_update` | Add Update | 添加更新 |
| `timeline.btn_add_blocker_disabled` | Add Blocker (Build 07) | 添加阻碍（Build 07） |
| `timeline.btn_open_ai_intake` | Open AI Intake | 打开 AI 录入 |
| `timeline.detailed_table` | Detailed Table | 详细表格 |

29 new keys × 2 languages = 58 new translations. Parity must hold at 649/649.

## Tests — test_v13_build06.py

Target ~30 assertions. Structure mirrors existing v1.3 test files (requests.Session + sqlite3 direct DB inspection).

### Required automated checks

**Markup presence (admin view, project with active in-progress phase):**
- `#timeline-command-center` section renders inside `workspace-panel-timeline`.
- Phase strip renders one `.timeline-phase-block` per project phase, in `phase_order`.
- Current phase block has `data-status="current"` (or equivalent CSS class).
- Done phases have `data-status="done"`.
- Not-started phases have `data-status="later"`.
- 3-tile row renders: `.timeline-tile-current`, `.timeline-tile-next-action`, `.timeline-tile-deadline`.
- Main blocker placeholder renders with `data-placeholder="blocker"` and the "Open Journal" link.
- AI Nudge placeholder renders with `data-placeholder="ai-nudge"` and the "Open AI chat" link.

**Honest field values:**
- For a project with a phase whose `planned_end_date` is 5 days in the future: deadline tile shows "5 days left" amber.
- For a project with a phase whose `planned_end_date` is 3 days past: deadline tile shows "3 days overdue" red.
- For a project with a phase whose `planned_end_date` is NULL: deadline tile shows "No due date set".
- For a project with `delay is None`: health badge shows "On track".
- For a project with `0 < days_late <= 3`: health badge shows "At Risk".
- For a project with `days_late > 3`: health badge shows "Delayed".
- Owner tile shows the phase.owner string when set; shows "Not assigned" when NULL.

**Phase strip ordering:**
- Phases render in `phase_order` (not insertion order).
- A skipped phase still appears in the strip with skipped icon.

**Action buttons + permissions:**
- Admin sees all 5 buttons (Finish, Adjust, Add Update, Add Blocker disabled, AI Intake).
- PM (with project edit access) sees all 5.
- Viewer sees: 0 buttons except possibly AI Intake if `can_use_ai_intake` allows.
- `[Add Blocker]` button has `disabled` attribute + a tooltip mentioning Build 07.
- `[Finish Current Phase]` link target includes `#phase-row-{current_phase.id}`.
- `[Open AI Intake]` button triggers the existing assistant panel (presence of expected onclick attr or data attribute).

**Detailed Table expand:**
- Existing `timeline-table-v2` table is INSIDE a `<details>` element with summary "Detailed Table".
- The `<details>` is NOT `open` by default.
- Existing per-row Edit / Finish controls inside Detailed Table still render unchanged.

**Routing + URL anchors:**
- GET `/projects/{id}#timeline` opens Timeline tab (Build 01 invariant preserved).
- GET `/projects/{id}#timeline-command-center` opens Timeline tab AND scrolls to Command Center.

**No regressions:**
- i18n parity at 649/649.
- Re-run `test_v13_build01.py`, `test_v13_build05b.py`, `test_build_v121.py`, `test_build30.py`.
- No new migration (verify migrations count unchanged at 5).
- No new AI tool (verify tool count unchanged).

### Real Playwright assertions (not just screenshots)
- Mobile 375px: phase strip overflows-x cleanly (no wrap); 3-tile row stacks to single column.
- Detailed Table summary is click-targetable.

## Explicit Deferrals

- Wiring action buttons to dedicated Command Center routes → Build 07.
- Blocker model + Add Blocker write flow → Build 07 (architecture review required before adding the table).
- AI Nudge generation → Build 07+ (needs rules engine OR LLM call architecture).
- Timeline History view derived from existing records → Build 08.
- Phase health badge as a stored column (instead of derived) → not planned; derivation is correct.
- Replacing the Detailed Table modal with an inline edit → out of scope.
- Phase strip status filter (clicking a phase to filter the table to that phase) → out of scope.
- Templates / Planning Sandbox → Build 09+.

## Rollback / Safety

Rollback is template/CSS/i18n/test only:
- Restore previous `workspace-panel-timeline` markup in `project_detail.html`.
- Remove the Command Center section + Detailed Table `<details>` wrapper.
- Remove Build 06 CSS + i18n keys.
- Remove `test_v13_build06.py`.
- Revert `project_detail` route to its pre-Build-06 context dict (remove `command_center_state`).

Existing routes, services, models, and database rows remain untouched. The Detailed Table's existing controls work both before and after Build 06.

## Acceptance Criteria

- Timeline tab opens to the Command Center section BEFORE the Detailed Table.
- Phase strip clearly indicates Done / Current / Next / Later for every phase.
- 3-tile row shows Current Phase, Next Action (placeholder narrative), and Deadline.
- Health badge color matches the locked-rule output.
- Days left / overdue badge matches today's date arithmetic.
- Main blocker and AI Nudge slots render EXPLICIT placeholders, never fake data.
- Action buttons either link to existing controls OR render as labeled disabled placeholders.
- Detailed Table is hidden behind an expand summary, default closed.
- Viewer cannot mutate anything from this view (action buttons either absent or non-functional).
- Mobile 375px: phase strip horizontally scrolls; tiles stack.
- All Build 01-05B layout markers (`workspace-panel-timeline`, `variant-command-card`, etc.) still pass their tests.
- i18n parity at 649/649.
- No schema change, no service change, no AI tool change.

## What Build 06 Solves From the User's Problem

| User concern (from canonical doc) | Build 06 response |
|---|---|
| "Timeline should not be a passive date list" | Command Center is now first; Detailed Table is collapsed |
| "Should push the project forward" | Phase strip + Current Phase tile + Deadline tile create immediate orientation |
| "Create deadline pressure" | Days-left badge + pressure dots make urgency visible |
| "Remind the PM what needs to happen next" | Next Action tile shows owner + placeholder text pointing at current phase |
| "Reduce mental burden of tracking everything manually" | Pressure rules are deterministic; PM doesn't have to do the math |
| "Do not build UI that backend cannot honestly support" | Blocker + AI Nudge are EXPLICIT placeholders; no fake data |
| "Move slowly; correctness matters more than speed" | Display-only build; Build 07 wires actions with dedicated tests |

## Sketch of Build 07 (next build, not in 06 scope)

For visibility:
- Wire `[Finish Current Phase]` to a Command Center–scoped POST that calls the existing `crud.finish_phase()` service. Adds a confirmation checklist (per doc §5.2).
- Wire `[Adjust Due Date]` to an inline reason-required form that calls the existing `crud.update_phase()` service.
- Wire `[Add Update]` to an inline new-journal-entry form that calls the existing `crud.create_journal_entry()` service with `entry_type` chooser.
- Add Blocker: architecture review first; likely either (a) `project_blockers` table with phase_id FK or (b) reuse `journal.entry_type='blocker'`. Decision in Build 07 plan.
- AI Intake button: integrate existing assistant panel to pre-load project_id context.
- AI Nudge: stays placeholder. Build 07+ might add deterministic-rule nudges only.

## Sketch of Build 08 (after 07)

- Timeline History / Updates section derived from: `project_changes` rows, `phase_plan_changes` rows, `journal_entries` rows, `project_files` uploads.
- Typed event display with filters (Delay / Decision / Blocker / Phase Change / File Uploaded / etc).
- No new event table — pure derivation per the doc §1.4.

---

End of Build 06 execution plan. Implementation begins only after this is reviewed and approved.
