# v1.3 Build 08 Execution Plan — Timeline Updates / History (derived view)

## Status

Plan-only execution gate. No code until this plan is reviewed and approved.

Predecessor: Build 07B shipped at `5dfff4e` (Project Blockers — first-class lifecycle model + Command Center wiring + Pulse cascade integration).

This plan implements the user's `V13_BUILD08_TIMELINE_HISTORY_PLAN.md` canonical doc (committed `71edcdd`). Per masterplan §"Build Sequence" and Feature Design Review Q4 ("Timeline history should derive from Journal/change log/phase changes before adding a new event table"), Build 08 ships **pure derivation** — zero new schema, zero new migration.

## User Problem (from the canonical doc)

> "Create a Timeline Updates / History section that explains what happened and why, using existing records first."

> "Prefer derived aggregation over a new event table unless existing records cannot support the required history."

> "PM can review why the timeline changed without reading raw database rows."

Today the PM can see "what is happening now" (Command Center, Build 06+07A+07B) and "what is planned" (Detailed Table, Build 17). They cannot easily see **"what happened and why"** without scrolling the Detailed Table's per-phase plan_changes accordion + opening Journal + opening Change Log. Build 08 unifies these into one chronological feed at the bottom of the Timeline workspace.

## Architecture Review

Per CLAUDE.md §"Before Changing the Database Schema" — Build 08 makes **no schema change**, but the same discipline applies in reverse: prove that existing tables can honestly support the required history before considering a new event table.

| Question | Answer |
|---|---|
| What problem is this solving? | Surface "what happened and why" derived from existing records. |
| Which tables and service functions affected? | Read-only union over `project_changes`, `phase_plan_changes`, `project_journal_entries`. One new helper `crud.get_timeline_events(db, project_id, limit)`. |
| Should this be a real column / table or handled in existing tables? | **Existing tables.** Each source already stores the WHO / WHAT / WHEN / WHY for its event type. The merge is presentation, not storage. |
| Does it bypass the service layer? | No — read-only helper inside `crud.py`. |
| Does it require change-log recording? | No — Build 08 is display-only. The source records already carry the audit (write_change rows from Builds 13, 14, 17, 07B). |
| Rollback plan? | Remove the helper + remove the template section + remove i18n + remove tests. Zero data risk. |

### Decision: derive, do not add an `events` table

A new `timeline_events` table would let us pre-classify every event (Sample Update vs Packaging Update vs Manual Note) — but the doc explicitly defers "semantic AI classification of all old entries". Pre-classification by hand at write time means every existing writer (`crud.create_journal_entry`, `crud.update_phase`, `crud.update_blocker`, etc.) gains a new column, which is more migration risk than a pure-display change earns back. We derive instead, and a future Build 1X can add the column if PMs report that derived classification feels wrong.

## Scope (strict)

In:
1. New service `crud.get_timeline_events(db, project_id, limit, sensitive_visible) -> list[dict]` that unions and normalizes events from 3 source tables.
2. New `TimelineEvent` shape (Python dict / dataclass) — `occurred_at`, `event_type`, `event_subtype`, `actor`, `title`, `body`, `link_anchor`, `is_sensitive`, `is_ai`, `source_table`.
3. New section `#timeline-history` rendered inside `workspacePanelTimeline`, AFTER the existing `#timeline` Detailed Table section.
4. Filter chips: All / Delays / Decisions / Blockers / Phase Changes / Files+Renderings (6 chips per the doc).
5. Sensitive-event filter for viewer (cost field_updates, factory/engineer field_updates hidden from viewer).
6. AI badge overlay (small `bi-robot` icon) on events where `source_type='ai_chat'` OR `changed_by='ai'`.
7. Pagination affordance: default 50 events, "Show more" button bumps to 200 client-side (events already loaded server-side at limit=200, but UI hides past 50 until clicked).
8. i18n labels for the 11 doc event types + 6 filter chips + status strings.
9. `test_v13_build08.py` (~30 assertions).
10. CHANGELOG + CURRENT_TASK + commit.

Out (explicit):
- No new table.
- No new migration.
- No new AI tool (Build 08 is read-only display).
- No semantic AI classification of old entries.
- No timeline template / sandbox (Build 09 scope).
- No editing of historical events from the History view (source-of-truth tables stay edit-only from their own UIs).
- No cross-project history feed.
- No CSV / PDF export (could be a v1.4+ deliverable).
- No infinite scroll / cursor pagination beyond 200 — if PMs report 200 is too few, Build 1X adds cursor pagination then.

## Wireframe Alignment Check

The canonical Build 08 doc gives an event-type list and filter list but no wireframe. Proposed layout (slots into the existing v1.3 Command Center wireframe §5):

```
─────────────────────────────────────────────────────────────────────
TIMELINE COMMAND CENTER       [phase strip + tiles + actions + tile]

▶ Detailed Table              [collapsed by default — Build 06]

TIMELINE UPDATES / HISTORY    (50 most recent · 'Show more' for 200)

[All] [Delays] [Decisions] [Blockers] [Phase Changes] [Files+Renderings]

┌────────────────────────────────────────────────────────────────────┐
│ ● Jun 4, 2026 · 14:22       [Phase Change] [Sample Update]   🤖    │
│  Sample Dev → done. Mass Production now in progress.               │
│  by alice (admin)                                          → #phase-row-5 │
├────────────────────────────────────────────────────────────────────┤
│ ● Jun 3, 2026 · 09:10       [Delay]                                │
│  Sample Dev planned_end_date shifted +7 days.                      │
│  Reason: Factory pushed sample 1 week.                             │
│  by alice (pm)                                             → #phase-row-3 │
├────────────────────────────────────────────────────────────────────┤
│ ● Jun 3, 2026 · 08:55       [Blocker]                              │
│  Blocker opened: 'Packaging cost is missing' (high)                │
│  by alice (pm)                                  → #timeline-command-center │
├────────────────────────────────────────────────────────────────────┤
│ ● Jun 2, 2026 · 16:30       [Cost Update]                          │
│  target_factory_cost: $7.50 → $8.20                                │
│  by alice (pm)                                                     │
├────────────────────────────────────────────────────────────────────┤
│ ● Jun 2, 2026 · 11:14       [File Uploaded] [Rendering Update]  🤖 │
│  Rendering 'sample-v2.png' uploaded.                               │
│  by ai                                                  → #renderings │
├────────────────────────────────────────────────────────────────────┤
│ ... (45 more, Show more →)                                         │
└────────────────────────────────────────────────────────────────────┘
```

Filter chip behavior: client-side. Clicking a chip toggles `data-filter` on a wrapper; CSS hides rows whose `data-event-type` doesn't match. Server returns the full set (up to limit=200) on every render. Avoids a round-trip per filter click.

## Feature Design Review (11 questions)

1. **Real workflow problem:** PMs forget what changed and why. Detailed Table shows planned vs actual; Journal shows reasoning; Change Log is hidden. None of them answers "what happened to this project in the last week."
2. **Repeated or edge-case:** Repeated daily; this is the post-standup catch-up screen.
3. **Structured data:** Existing — `project_changes`, `phase_plan_changes`, `project_journal_entries`. Zero new structure.
4. **Could live in notes first:** Already does — Journal is one of the source tables. Build 08 just merges it with the other 2 sources.
5. **Intake burden:** Zero new intake — purely derived.
6. **AI role:** AI-created events get a visible 🤖 badge so the PM knows which records came from confirmed AI actions. No AI classification or summarization in Build 08.
7. **Display payoff:** PM lands on Timeline, scrolls past Command Center + Detailed Table, sees unified history. Filters narrow to just delays or just blockers in one click.
8. **Migration impact:** None.
9. **Minimal schema:** Zero new schema.
10. **Minimal UI change:** One new section + 6 filter chips + paginated event list. CSS + i18n only.
11. **Deferred:** New event table, semantic AI classification, cross-project feed, CSV export, infinite scroll, edit-from-history, timeline templates (Build 09).

## Backend Honesty Mapping

Every event type traces to a real row in one of the 3 source tables. No fabricated events; no derivations that hide audit detail.

| Doc event type | Source table | Filter rule | event_subtype | Permission rule | Test coverage |
|---|---|---|---|---|---|
| **Phase Change** | `project_changes` | `change_type='phase_update'` AND summary does NOT match Sample/Packaging rules | (none) | all authenticated | Build 17 covers writes; Build 08 adds rendering test |
| **Decision** | `project_journal_entries` | `entry_type='decision'` | (none) | `can_view_journal` (viewer cannot see Journal entries — same in History) | Build 14 + new |
| **Delay** | `phase_plan_changes` | `new_date > old_date` (forward shift); `old_date` non-null | (none) | all authenticated | Build 17 + new |
| **Blocker** | `project_changes` | `change_type IN ('blocker_opened','blocker_updated','blocker_resolved')` | the change_type itself | all authenticated | Build 07B + new |
| **File Uploaded** | `project_changes` | `change_type='file_upload'` AND linked file's `file_category != 'rendering'` | (none) | all authenticated; sensitive file categories hidden from viewer (factory_feedback, quotation) | Build 13 + new |
| **Rendering Update** | `project_changes` | `change_type='file_upload'` AND linked file's `file_category='rendering'` | (none) | all authenticated | Build 04 + new |
| **Cost Update** | `project_changes` | `change_type='field_update'` AND `field_name IN COST_FIELDS` | the field_name | **viewer HIDDEN** (cost data) | Build 13 + new |
| **Sample Update** | `project_changes` | `change_type='phase_update'` AND phase.phase_type IN ('prototype','review') | (none) | all authenticated | Build 17 + new |
| **Packaging Update** | `project_journal_entries` | `entry_type='packaging'` | (none) | `can_view_journal` (viewer cannot see) | Build 14 + new |
| **AI Intake** | (overlay, not bucket) | `source_type='ai_chat'` OR `changed_by='ai'` | n/a | inherits the underlying event's permission | new |
| **Manual Note** | catch-all | `project_journal_entries.entry_type NOT IN (decision, packaging)` AND `project_changes.change_type='event_note'` | (none) | journal half: `can_view_journal`; event_note half: all authenticated | Build 14 + new |

`COST_FIELDS = {"target_factory_cost", "actual_factory_cost", "target_msrp", "actual_msrp", "packaging_cost"}` (closed allowlist).

### Reading the mapping

- **6 source-driven buckets** + **3 contextual subtypes** (Sample = phase_type-driven, Rendering = file_category-driven, Packaging = entry_type-driven) + **1 overlay badge** (AI Intake) = exactly the doc's 11 event types displayed honestly.
- **No type is fabricated.** Every label has a deterministic filter rule with no fall-through to "I'll guess."
- **Manual Note** is the catch-all for everything that doesn't match the above rules (e.g., `event_note` change-log rows from `create_journal_entry`, `create_variant`, etc.). Keeps the feed honest about its catch-all rather than mis-labeling.

## UI Scope

Touch:
- `app/crud.py` — add `get_timeline_events(db, project_id, limit=200, viewer=False)`, helpers `_event_subtype_for_phase_change`, `_event_subtype_for_file_upload`, `_event_subtype_for_journal_entry`, `_is_sensitive_event`. Plus constant `COST_FIELDS` and `SENSITIVE_FILE_CATEGORIES = {"factory_feedback","quotation"}`.
- `app/routes/projects.py` — `project_detail` view computes `timeline_events = crud.get_timeline_events(db, project_id, limit=200, viewer=(current_user.role=='viewer'))` once per render. No new route.
- `app/templates/project_detail.html` — new `<section id="timeline-history">` inside `workspacePanelTimeline`, after the existing `<section id="timeline">` and before the `<div class="modal" id="phaseModal">` block. Includes filter chips, paginated list (first 50 visible, rest hidden behind `[data-pagination="hidden"]` with `Show more` button), per-event row markup with date, type badges, AI badge overlay, body text, actor, optional link anchor.
- `app/static/css/styles.css` — append `.timeline-history-*` styles (filter chip row, event row, type badge color palette per bucket, AI badge, "Show more" affordance).
- `app/static/js/main.js` — small filter handler (~30 lines): chip click toggles active state + applies a single CSS class on the wrapper that hides non-matching rows via attribute selectors. "Show more" button reveals hidden rows.
- `app/i18n/en.json` + `zh.json` — ~14 new keys (11 event type labels + 6 filter chip labels − overlap; section title + Show more + empty state). Parity target **702/702** (688 + 14).
- `test_v13_build08.py` — new file (target ~30 assertions).
- `CURRENT_TASK.md`, `CHANGELOG.md`.

Do not touch:
- `app/models.py` (no schema change)
- `app/migrations.py` (no migration; count stays at 6)
- AI tool registry
- Existing Detailed Table, Command Center, Pulse template branches, blocker tile
- Existing routes (Build 07A 3 routes + Build 07B 3 routes unchanged)

## Locked Decisions

### Lock 1 — Pure derivation; no `timeline_events` table
Read-only union over `project_changes` + `phase_plan_changes` + `project_journal_entries`. If PMs report classification feels wrong in production, future build can add an explicit `event_type` column. Doc default = derive first.

### Lock 2 — 6 filter chips: All / Delays / Decisions / Blockers / Phase Changes / Files+Renderings
The doc specifies these 6 exactly. The 11 event types map to chip filters as:
- **Delays** → `event_type='delay'`
- **Decisions** → `event_type='decision'`
- **Blockers** → `event_type='blocker'`
- **Phase Changes** → `event_type='phase_change'` OR `event_subtype='sample'` (Sample Update is a phase change)
- **Files+Renderings** → `event_type='file_upload'` (regardless of `rendering` subtype)
- **All** → no filter

Cost Update, Packaging Update, AI Intake overlay, Manual Note: visible under **All** only — they don't get their own filter chip. The doc's 6-chip list is the locked surface.

### Lock 3 — Sensitive-event visibility for viewer
Viewer cannot see:
- Cost Update events (any `field_name IN COST_FIELDS`).
- File Uploaded events whose linked file has `file_category IN SENSITIVE_FILE_CATEGORIES` (factory_feedback, quotation).
- Decision / Packaging Update / Manual Note events from `project_journal_entries` (gated on existing `can_view_journal`, which viewer fails).

Viewer DOES see: Phase Change, Delay, Blocker, File Uploaded (non-sensitive categories), Rendering Update, AI Intake overlay on visible events.

Filtering happens **server-side** in `get_timeline_events` based on `viewer` flag. Defense in depth; UI also won't render hidden buckets.

### Lock 4 — Default visible 50; "Show more" reveals up to 200
Server always returns up to 200 events sorted desc by `occurred_at`. Template renders all 200 but applies `[data-pagination="hidden"]` to events 51-200. "Show more" button (only rendered when count > 50) removes the hidden attribute. Avoids a round-trip and avoids cursor pagination complexity. If PMs hit 200+ in practice, Build 1X adds cursor pagination.

### Lock 5 — Client-side filter chips
Server returns the full set; chips are pure CSS show/hide via `[data-event-type]` selectors on the wrapper. Avoids a round-trip per click. Filter state is local (not in URL hash) — refreshing resets to "All". Matches the Pulse next-action card's stateless render pattern.

### Lock 6 — AI Intake is an overlay badge, NOT a separate bucket
Events where `source_type='ai_chat'` OR `changed_by='ai'` get a small `bi-robot` icon next to the event type badge. They still classify into the appropriate bucket (e.g., an AI-confirmed journal entry is a Decision/Note, not an "AI Intake"). The badge tells the PM *who* did it, the bucket tells them *what* happened.

### Lock 7 — Newest first; merge by `occurred_at`
Single SQL query per source table (3 queries total — none expensive at typical project size). In-memory merge by `occurred_at DESC`. No SQL UNION (avoids fighting SQLite's lack of typed columns across the 3 tables).

### Lock 8 — Anchor links where the original record is reachable
- Phase Change / Delay / Sample Update → `#phase-row-{phase_id}` (auto-expands Detailed Table per Build 06 anchor handler).
- Blocker → `#timeline-command-center` (Command Center tile shows the blocker).
- File Uploaded / Rendering Update → `#files` (Files section).
- Decision / Packaging Update / Manual Note (journal) → `#journal`.
- Cost Update / Manual Note (event_note) → no anchor (the source field has no detail page).

Anchors are honest — clicking them lands on existing UI that already shows the record. No new detail-page route.

### Lock 9 — Scope discipline (carrying Build 07B's Lock 10 pattern)
07B introduced "scope discipline" as a lock type. Carrying forward:

**Out of scope for Build 08, do NOT slip in:**
- AI-generated event summaries.
- Semantic classification beyond the deterministic rules in the Backend Honesty Mapping.
- Edit-from-history (clicking a Cost Update event opens the field for editing).
- A "since I last looked" unread marker.
- Per-event mute / star / pin.
- Export to CSV / PDF.
- Cross-project history.
- Email digest of recent events.
- Date-range picker (we ship limit-based pagination, not date filtering, this build).

If any of these surface during implementation, they stop the work and become a separate plan.

## Permissions

| Element | Visibility |
|---|---|
| `#timeline-history` section | All authenticated |
| Filter chip row | All authenticated |
| Phase Change / Delay / Blocker / File Uploaded (non-sensitive) / Rendering Update events | All authenticated |
| Decision / Packaging Update / Manual Note (journal-sourced) events | `can_view_journal` (admin + PM only) |
| Cost Update events | `can_view_costs` (admin + PM only) |
| File Uploaded events for `factory_feedback` / `quotation` | `can_view_sensitive_fields` (admin + PM only) |
| AI Intake overlay badge | inherits underlying event's permission |
| "Show more" button | All authenticated (only rendered when count > 50) |

Viewer sees a deduplicated, filtered subset — all non-sensitive events. The filter chip row stays full for all roles so the UI shape doesn't shift per role; chips that would yield zero events still render but show "No events match this filter."

## i18n Keys (locked EN + zh, parity-required)

| Key | EN | ZH |
|---|---|---|
| `timeline.history_title` | Timeline Updates / History | 时间线更新 / 历史 |
| `timeline.history_hint` | Latest {n} events (most recent first) | 最近 {n} 条更新 |
| `timeline.history_show_more` | Show more ({n}) | 查看更多（{n}） |
| `timeline.history_empty` | No events yet for this project. | 此项目暂无更新记录。 |
| `timeline.history_empty_filter` | No events match this filter. | 没有符合此筛选条件的更新。 |
| `timeline.history_filter_all` | All | 全部 |
| `timeline.history_filter_delays` | Delays | 延期 |
| `timeline.history_filter_decisions` | Decisions | 决策 |
| `timeline.history_filter_blockers` | Blockers | 阻碍 |
| `timeline.history_filter_phase_changes` | Phase Changes | 阶段变化 |
| `timeline.history_filter_files` | Files + Renderings | 文件 + 渲染图 |
| `timeline.history_event_phase_change` | Phase Change | 阶段变化 |
| `timeline.history_event_decision` | Decision | 决策 |
| `timeline.history_event_delay` | Delay | 延期 |
| `timeline.history_event_blocker` | Blocker | 阻碍 |
| `timeline.history_event_file_uploaded` | File Uploaded | 文件上传 |
| `timeline.history_event_rendering_update` | Rendering Update | 渲染图更新 |
| `timeline.history_event_cost_update` | Cost Update | 成本更新 |
| `timeline.history_event_sample_update` | Sample Update | 样品更新 |
| `timeline.history_event_packaging_update` | Packaging Update | 包装更新 |
| `timeline.history_event_manual_note` | Note | 备注 |
| `timeline.history_ai_badge` | AI | AI |
| `timeline.history_by_actor` | by {actor} | 由 {actor} |
| `timeline.history_anchor_view` | View | 查看 |

24 new keys. Parity target **712/712** (= 688 + 24). Recount confirmed in implementation.

## Tests — test_v13_build08.py

Target ~30 assertions. Mirrors v1.3 test pattern (`requests.Session` + `sqlite3`).

### Helper-level (call `crud.get_timeline_events` directly)
1. Returns empty list for a project with no activity.
2. Returns at least one row of each event type when fixtures cover all 6 buckets.
3. `event_type` field matches Backend Honesty Mapping rules.
4. `event_subtype` correctly set for Sample / Rendering / Packaging contextual cases.
5. `is_ai=True` for events where `source_type='ai_chat'` OR `changed_by='ai'`.
6. Newest first ordering.
7. `viewer=True` filter hides cost-update events from the result.
8. `viewer=True` filter hides journal-sourced events (Decision / Packaging / Manual Note from journal).
9. `viewer=True` filter hides file uploads with `file_category='factory_feedback'`.
10. `viewer=False` (admin/PM) sees everything.
11. `limit=200` ceiling honored.

### Route-level rendering
12. `#timeline-history` section renders inside `workspacePanelTimeline`.
13. After the existing `#timeline` Detailed Table section in document order.
14. Filter chip row has exactly 6 chips with correct `data-filter` attributes.
15. Each rendered event row has `data-event-type` matching its bucket.
16. AI badge (`bi-robot`) renders on events where source is AI.
17. Phase Change event has `href="#phase-row-{id}"` anchor.
18. Blocker event has `href="#timeline-command-center"` anchor.
19. File Uploaded event has `href="#files"` anchor.
20. Journal-sourced event has `href="#journal"` anchor.
21. Default 50 events visible; remainder `[data-pagination="hidden"]`.
22. "Show more" button only renders when total > 50.

### Permissions
23. Viewer page does NOT contain Cost Update event markup.
24. Viewer page does NOT contain `factory_feedback` file event markup.
25. Viewer page does NOT contain journal-sourced events.
26. Admin sees all of the above.
27. PM-owner sees all of the above.

### Filter chip semantics (markup correctness; JS behavior validated manually)
28. Each chip has the right i18n label.
29. "All" chip is active by default.

### Regression
30. i18n parity at 712/712 (or recomputed target if any key was reworded).
31. Migration count still 6 (no schema change).
32. test_v13_build07b 66/66 (Pulse + blocker tile invariants).
33. test_v13_build_v121 19/19 (release-proof baseline).

### Manual browser walkthrough
- Create a project, run through 3 phase finishes + 2 plan adjusts + 1 blocker + resolve + 2 journal entries + 1 file upload. Verify all show up in History, correctly typed, newest first.
- Click each filter chip in turn and verify the row visibility matches the chip's filter rule.
- Login as viewer; verify the filtered-down feed.
- 50+ events: verify "Show more" appears and reveals events 51+.

## Explicit Deferrals

- Cursor pagination beyond 200 → Build 1X if PMs report.
- New `timeline_events` table → Build 1X if classification feels wrong.
- AI summarization of events → not planned for v1.3.
- Edit-from-history → not planned.
- CSV / PDF export → v1.4+ consideration.
- Per-event mute / star / pin → not planned.
- Cross-project history feed → not planned.
- Email digest → not planned.
- Date-range picker → not planned for v1.3 (limit-pagination is the v1.3 surface).
- Semantic AI re-classification of legacy entries → out of scope per doc + Lock 9.
- Timeline templates / sandbox → Build 09 scope.

## Rollback / Safety

Rollback is code/template/i18n/test only:
- Delete `app/crud.py` `get_timeline_events` + 4 sub-helpers + 2 constants.
- Remove `timeline_events` context dict key from `project_detail` view.
- Remove `<section id="timeline-history">` from template.
- Remove `.timeline-history-*` CSS.
- Remove filter chip JS handler (~30 lines).
- Remove 24 i18n keys (both languages).
- Delete `test_v13_build08.py`.

Zero data risk. Source tables unchanged. All existing surfaces (Command Center, Detailed Table, Pulse, Blocker tile) unaffected.

## Acceptance Criteria

- Timeline workspace now has 3 sections (Command Center · Detailed Table collapsed · Timeline Updates / History).
- History feed unifies events from 3 source tables, normalized into the 11 doc event types via deterministic rules.
- Filter chips work client-side; default "All".
- Viewer never sees Cost Update, sensitive-file uploads, or journal-sourced events.
- AI-created events carry a visible badge.
- Each event with a reachable source links back (anchor or Files/Journal section).
- Default 50 visible; "Show more" reveals up to 200.
- i18n parity at 712/712.
- No new schema, no migration, no new AI tool, no service mutation.
- test_v13_build08.py passes; all v1.3 Builds 01-07B + v1.2.1 regression remain green.
- No scope creep per Lock 9.

## What Build 08 Solves From the User's Doc

| Doc acceptance criterion | Build 08 response |
|---|---|
| "Create a Timeline Updates / History section that explains what happened and why, using existing records first." | ✓ New `#timeline-history` section; derived from 3 existing tables; zero new schema. |
| "Prefer derived aggregation over a new event table unless existing records cannot support the required history." | ✓ Architecture Review confirms existing tables sufficient; new table deferred. |
| "Aggregate from existing sources (change log / phase plan changes / journal entries / file uploads / AI events)" | ✓ All 5 sources covered: `project_changes` (covers file uploads + AI events + cost updates + blocker events), `phase_plan_changes` (delays + plan changes), `project_journal_entries` (decisions + packaging + manual notes). |
| "Normalize display into [11] event types" | ✓ Backend Honesty Mapping maps all 11 to deterministic source rules. |
| "Add filters: All / Delays / Decisions / Blockers / Phase Changes / Files+Renderings" | ✓ Lock 2 — 6 chips exactly. |
| "Keep original source records intact and link/anchor back where practical." | ✓ Lock 8 anchors. |
| "PM can review why the timeline changed without reading raw database rows." | ✓ One section, one chronological feed, one-click filters. |
| "History remains derived and auditable from existing source records." | ✓ Pure derivation; rollback is removing code only. |

## Sketch of Build 09 (after 08)

- Planning Sandbox **design doc only** per masterplan §"Non-Negotiable Product Decisions" → "Planning Sandbox is design-only in initial v1.3."
- Documents a future template/dependency sandbox without implementing it.
- Single markdown deliverable, ~1 commit.

## Sketch of Build 10 (after 09)

- v1.3.0 Release Hardening: bump `app/version.py` from `1.2.1` to `1.3.0`, update visible version strings, write `test_v13_build10.py` as the release-proof regression that re-runs v1.3 Builds 01-09 + v1.2.1 baseline.

---

End of Build 08 execution plan. Implementation begins only after this is reviewed and approved.
