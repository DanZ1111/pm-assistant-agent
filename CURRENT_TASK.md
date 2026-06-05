# CURRENT_TASK.md

## Task
v1.3 Build 08 — Timeline Updates / History (derived view). Implemented + tested. Awaiting push.

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth.

## What just shipped in this session

- **Plan** committed at `3e9a373` (initial draft) + `4796778` (folded ChatGPT amendments — Locks 2/7/10 + source_id + 3 empty states + expanded tests).
- **Build 08 implementation** committed as one atomic commit (see latest `git log`). Locks 1–11 approved 2026-06-06 with ChatGPT amendments; implementation followed plan verbatim.
  - `app/crud.py` — new `get_timeline_events(db, project_id, limit, viewer)` helper + 5 sub-helpers + 2 constants (COST_FIELDS, SENSITIVE_FILE_CATEGORIES, _SAMPLE_PHASE_TYPES, _classify_project_change, _is_pc_sensitive, _journal_bucket_and_subtype) + 5 bucket constants. Pure derivation over `project_changes` + `phase_plan_changes` + `project_journal_entries`. Returns `{events, total_unfiltered_visible, viewer_hidden_count, total}`. Deterministic tiebreaker on `occurred_at` ties: `(source_priority, source_id DESC)`. Viewer filter removes restricted events entirely (cost field_updates, sensitive file_category uploads, journal-mirror event_note rows whose summary begins with "Journal entry added:", and all journal-sourced rows).
  - `app/routes/projects.py` — `project_detail` view passes `timeline_history` + `is_viewer` into template context.
  - `app/templates/project_detail.html` — new `<section id="timeline-history">` inside `workspacePanelTimeline`, AFTER existing `#timeline` Detailed Table section. 6 filter chips (data-filter attrs); event list with bucket badge + optional subtype + optional AI badge + actor + optional View anchor; 3 distinct empty state blocks; Show More button only when total > 50.
  - `app/static/css/styles.css` — `.timeline-history-*` styles: chips, bucket-colored badges (delays red / decisions blue / blockers red / phase_changes green / files purple), subtype + AI badges, row layout, mobile breakpoint at 768px. Filter behavior via attribute selectors on the section's `data-active-filter`.
  - `app/static/js/main.js` — `initTimelineHistory()` IIFE: chip click toggles active state + section's `data-active-filter`; computes filter empty-state across the FULL loaded array (not just visible 50, per Lock 5); Show More reveals rows 51-200 and re-evaluates the active filter.
  - `app/i18n/en.json` + `zh.json` — 26 new `timeline.history_*` keys; parity **714/714**.
  - `test_v13_build08.py` — **55/55 PASS** (helper shape + 3 sources merged + bucket coverage + 6 classification cases + viewer hidden_count + viewer-no-journal + viewer-no-cost + source_id traceability + deterministic ordering + Lock 10 anchor fallback + 14 template markers + 3 empty states + Show More gate + Lock 5 full-array filter + Build 06/07A/07B invariants).

## Build 08 — Confirmed locks (1-11)

1. **Pure derivation**; no `timeline_events` table.
2. **6 filter chips** exactly (All / Delays / Decisions / Blockers / Phase Changes / Files+Renderings); every event has one primary bucket (no orphans).
3. **Viewer permission filtering** removes restricted events entirely — no hidden placeholders.
4. **50 default · 200 ceiling** with Show More; no cursor pagination.
5. **Client-side filter chips** against full 200-event array.
6. **AI overlay badge** (`bi-robot`), not a separate bucket.
7. **Newest first** + deterministic tiebreaker on ties.
8. **Anchor links** where original record is reachable.
9. (skip — was renumbered to 11)
10. **Anchor links best-effort** with graceful fallback (link_anchor=None when target permission-hidden or DOM-missing).
11. **Scope discipline** — out of scope: AI summaries, semantic re-classification, edit-from-history, unread markers, per-event mute/star/pin, CSV export, cross-project feed, date-range picker, cursor pagination beyond 200, email digest.

## Discovered + deferred (per Lock 11)

- **Legacy Change Log (`#changes`) viewer leak**: the Build 13 Change Log section renders journal-mirror `event_note` rows to viewers without filtering. Pre-existing behavior; out of Build 08 scope. Build 08 hides those rows specifically in its new History feed via `_is_pc_sensitive`. If we want to fix the Change Log too, that's its own small build (likely ~10 LOC + 1 assertion).

## Verification at ship time

- `python3 test_v13_build08.py` — **55/55 PASS**.
- Regression sweep all green:
  - `test_v13_build01..07b` — 325 assertions total, all PASS.
  - `test_build_v121` — 19/19.
  - `test_build30` — 23/23.
  - `test_ai_e2e` — 15P/2S/0F (SKIPs are OPENAI key issues, not regressions).
- i18n parity: **714/714**.
- Migration count: **6** (unchanged — no schema change in Build 08).

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
| **08 — Timeline Updates / History** | **shipped this session** | latest |
| 09 — Planning Sandbox (design doc only) | planned | — |
| 10 — v1.3.0 Release Hardening | planned | — |

## Next step

Wait for user direction. Suggested next moves:
1. **Push** to origin (currently 8+ commits ahead of `origin/main`).
2. **Browser walkthrough** of Build 08 — create a project, run through 3 phase finishes + 2 plan adjusts + 1 blocker + resolve + 2 journal entries + 1 file upload + 1 cost change. Verify all show up in History, correctly typed + bucketed, newest first. Click each filter chip; verify viewer's hidden-event count.
3. **Build 09** — Planning Sandbox **design doc only** per masterplan §"Non-Negotiable Product Decisions" → "Planning Sandbox is design-only in initial v1.3." Single markdown deliverable, ~1 commit, no code.
4. **Build 10** — v1.3.0 release hardening: bump `app/version.py` from `1.2.1` to `1.3.0`, update visible version strings, write `test_v13_build10.py` as the release-proof regression that re-runs v1.3 Builds 01-09 + v1.2.1 baseline.
5. **Optional cleanup** — fix the legacy Change Log viewer leak discovered during Build 08 (small standalone build; ~10 LOC + 1 assertion in `test_build14.py` or wherever).

## Deferred to future builds (carried forward)

- Native-speaker Chinese review of strings added in Builds 26-30C + v1.3 Builds 01-08.
- AI prompt translation, Help modal body translation, `/admin/*` page translation.
- Full Profit Model implementation (variant cell shows naive margin; full model is v1.4).
- Row-level multi-tenancy.
- Bulk delete from the projects list / soft-delete with undo window.
- Auto-provisioning script for Railway.
- One-time admin cleanup of the original 6 admin-linked duplicates from the Build 30A incident.
- Cursor pagination beyond 200 events (per Lock 11).
- Semantic AI classification of legacy entries (per Lock 11).
- Timeline templates / sandbox implementation (Build 09 is design-doc only).
- CSV / PDF export of Timeline History (per Lock 11).
- Recently-resolved blockers section in Command Center (per Build 07B Lock 10).

## v1.3 process pattern (continues)

Every build gets a build-specific execution plan before coding. Plan files are committed/reviewed first; ChatGPT + Claude both review; the plan gets amended before code lands. Builds touching schema additionally write an Architecture Review section answering CLAUDE.md's 6 schema questions; Build 08 wrote an Architecture Review **in reverse** (proving existing tables can honestly support the requirement, so no schema change is needed). Locks are resolved in-plan before implementation starts. Build 08 added another reusable lock type: **graceful anchor fallback** (Lock 10) — links omitted when target permission-hidden or DOM-missing rather than rendered as broken. Carries forward to any future build that links across permission-gated sections.
