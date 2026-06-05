# v1.3 Build 07B Execution Plan — Blocker Model + Add Blocker Wiring

## Status

Plan-only execution gate. No code until this plan is reviewed and approved.

Predecessor: Build 07A shipped at `57b48c3` (Finish / Adjust / Add Update wired to dedicated Command Center routes; Add Blocker stayed disabled with tooltip "Coming Build 07B — needs Architecture Review for blocker model").

This plan starts with the **Architecture Review** the user's `V13_BUILD07_TIMELINE_COMMAND_ACTIONS_PLAN.md` and `CLAUDE.md` both require before any blocker-model schema change. The plan resolves the 7 open Architecture Review questions sketched at the end of `V13_BUILD07_EXECUTION_PLAN.md`. Each answer is presented as the **proposed** default; the user can override any item before implementation starts.

## User Problem (from the canonical doc)

> "Add Blocker always requires the pre-build Architecture Review… Default planning assumption: Add Blocker probably needs a first-class `project_blockers` model if it is meant to behave like command-center state instead of a note."

> "Timeline actions move real backend state, refresh derived state, and leave audit/history behind."

> "If a row [in the action mapping] cannot be completed honestly, that action remains placeholder." — Build 07A satisfied this by deferring Add Blocker. Build 07B completes the row.

The Command Center's wireframe in `timeline_command_center_redesign_plan.md` §5.1 shows "Main blocker" as a first-class tile that **drives pressure** ("Packaging cost is still missing. This may delay sample approval."). A blocker is not just a note — it is state that:
- has a lifecycle (active → resolved),
- affects Project Pulse's next-action recommendation (a project with active blockers shouldn't fall through to "no urgent action"),
- can attach to a specific phase or to the project as a whole,
- needs an audit trail (who opened it, when, why, who resolved it).

A free-text journal entry of `entry_type='risk'` cannot do these things — journal entries have no resolve action, no `phase_id` FK, no display on Command Center, no priority for Pulse.

## Architecture Review

### 1. Schema-change checklist (per CLAUDE.md §"Before Changing the Database Schema")

1. **What problem is this solving?** Promote "blocker" from narrative concept (journal entry of type=risk) to first-class state with active/resolved lifecycle, phase association, Command Center display, and Pulse priority.
2. **Which tables and service functions are affected?**
   - New: `project_blockers` table, `crud.create_blocker / update_blocker / resolve_blocker / get_active_blockers_for_project / get_blockers_by_phase`.
   - Touched (read-only): `recalculate_stage_and_delay` is NOT changed (delay is still planned-date driven; blockers are a parallel signal that doesn't change `current_stage`). Project Pulse template gains a blocker branch in its next-action cascade.
3. **Should this be a real column or handled in notes/thesis/change log?** Real table. Notes/journal cannot model lifecycle + foreign keys + filtered queries. Change log is per-event audit, not current-state.
4. **Does this bypass the service layer?** No — all writes go through `crud.*` helpers that call `write_change()` for audit.
5. **Does it require change-log recording?** Yes — every blocker create/update/resolve writes a `project_changes` row (`change_type='blocker_opened|blocker_updated|blocker_resolved'`).
6. **Rollback plan?** Migration 006 is additive (CREATE TABLE IF NOT EXISTS); rollback = drop the table + revert the 3 routes/services/template-section + revert i18n + AI tools. No data loss in other tables.

### 2. Resolution of the 7 open questions from V13_BUILD07_EXECUTION_PLAN.md

| # | Question | Proposed answer | Rationale |
|---|---|---|---|
| 1 | Model choice (final) | **New `project_blockers` table** (not journal extension) | Lifecycle + FK + filtered queries justify first-class state per Build 07A plan default. |
| 2 | Per-phase vs per-project | **Per-project with OPTIONAL `phase_id` FK** | Blockers can pre-date phase creation (e.g., factory hasn't quoted yet at Idea stage); attaching to a phase when known supplies the strip-dot display data without forcing it. |
| 3 | Active/resolved state model | **Status enum stored as String**: `active` / `resolved`. Plus `resolved_at DATETIME NULL`, `resolved_by_user_id INTEGER NULL FK`. **No `archived` state**; admin-only delete is the escape hatch. | Mirrors how `ProjectPhase.status` is modeled (String, not enum type — same migration risk profile). Computing "active" from row absence is fragile when we need history of resolved blockers in Timeline History (Build 08). |
| 4 | Display impact | (a) Command Center "Main blocker" tile flips from placeholder → **newest active blocker** by `created_at desc`; empty state stays honest ("No active blockers"). (b) Project Pulse next-action cascade inserts a **new highest-priority branch** above the existing `delay` branch: if there is at least one active blocker, surface "Resolve blocker: {title}" with link to Command Center. (c) Phase strip block adds a small `bi-shield-exclamation` red dot when that phase has ≥1 active blocker (CSS only; data already in query). | These three surfaces are the user's wireframe; doing fewer is dishonest, doing more (e.g., AI-generated blocker summaries) bloats scope. |
| 5 | Permission model | **Create/update/resolve**: admin (any project) + PM (own projects only). **View**: all authenticated (mirrors Project Pulse / Command Center). **Delete (hard)**: admin only (matches Build 14 journal delete + Build 16 variant delete patterns). PM cannot delete; resolve is the PM-facing close action. | Consistent with the rest of the app's role matrix; no new permission concept. |
| 6 | AI tool registry | Add `create_blocker` + `update_blocker` + `resolve_blocker` to `TOOL_SCHEMAS`. All three added to `CONFIRMATION_TOOLS` (Build 27 confirmation guard required for every chat-driven write). `UPDATE_BLOCKER_ALLOWED = {"title", "description", "severity", "phase_id"}` whitelist. No `delete_blocker` AI tool — admin-only, UI-only (matches `delete_variant` pattern where AI cannot destruct). | Reuses Build 27's centralized confirmation pattern; no new gating concept. |
| 7 | Migration 006 | Additive `_create_project_blockers(engine)` mirroring Build 30A's `_create_project_creation_tokens()` pattern: `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS` on `(project_id, status)` and `(phase_id)`. Idempotent on SQLite + PostgreSQL. | Same pattern proven by Build 30A migration 004; no new migration mechanics needed. |

## Wireframe Alignment Check

User's wireframe §5.1 explicitly shows:

```
Main blocker
Packaging cost is still missing. This may delay sample approval.
```

Build 07B fulfills this by replacing the Build 06 placeholder block with:

```
Main blocker
[title]
[description, truncated to ~2 lines with "more" affordance]
Opened {N} days ago by {author}            [Resolve] [Edit]
+ Add another blocker → opens inline form
```

When there are zero active blockers:

```
Main blocker
No active blockers. [+ Add blocker]
```

The Build 07A inline-form pattern (Lock 1 from the prior plan) carries over: Add Blocker button toggles a 4th panel inside the existing `#cc-action-form` mount. Resolve and Edit on an active blocker use the same mount (slot 5 + slot 6).

Doc compliance per §1.5 (no fake intelligence): every visible field on the new tile traces to a `project_blockers` column. The Pulse next-action and phase-strip red dot are deterministic. No AI generation, no LLM nudge.

## Feature Design Review (11 questions)

1. **Real workflow problem:** PMs lose context on what's holding a project up. Journal entries are searchable but not surfaced; a real blocker tile + Pulse priority + phase dot make the blocker visible everywhere it matters.
2. **Repeated or edge-case:** Repeated — every project has 0–N blockers over its lifecycle; PMs add/resolve them weekly.
3. **Structured data:** New `project_blockers` table.
4. **Could live in notes first:** Journal entries of `entry_type='risk'` exist today but cannot fulfill the wireframe (no resolve action, no Pulse priority, no Command Center display).
5. **Intake burden:** Add Blocker form is 4 fields (title, description, severity, optional phase). Comparable to Add Update.
6. **AI role:** `create_blocker` + `update_blocker` + `resolve_blocker` are proposal-only via Build 27 confirmation. The assistant can suggest a blocker from chat (e.g., "It sounds like packaging cost is blocking sample approval — create a blocker?") and the PM confirms.
7. **Display payoff:** PM lands on Timeline → Command Center → sees Main blocker immediately. Lands on Overview → Pulse "Resolve blocker" badge. Glances at phase strip → red dot on the affected phase.
8. **Migration impact:** Migration 006, additive, idempotent. New table only; no column added to existing tables. Pulse template gains a new branch but the existing branches still fire if no blockers exist (backwards-compatible).
9. **Minimal schema:** 9 columns: `id, project_id, phase_id NULL, title, description, severity, status, created_at, created_by_user_id, resolved_at NULL, resolved_by_user_id NULL`. 11 if we count nullables; this is the minimum for the wireframe + audit + Pulse + phase strip.
10. **Minimal UI change:** Replace 2 placeholder elements in Command Center (the main-blocker block + the disabled `[Add Blocker]` button) with honest equivalents. Add a Pulse cascade branch. Add the phase-strip red dot CSS + data attribute. Add 3 inline form panels (Add / Edit / Resolve) inside the existing `#cc-action-form` mount.
11. **Deferred:** Multi-severity color coding beyond a 3-tier `low/medium/high` (no `critical`); blocker comments / discussion thread; cross-project blocker views; blocker SLA timers; AI-generated blocker summaries; bulk-resolve.

## Schema Design (Migration 006)

```sql
CREATE TABLE IF NOT EXISTS project_blockers (
    id                  INTEGER PRIMARY KEY,                        -- SERIAL on PG; INTEGER PK = AUTOINCREMENT on SQLite
    project_id          INTEGER NOT NULL REFERENCES projects(id),
    phase_id            INTEGER NULL REFERENCES project_phases(id), -- optional; nullable
    title               VARCHAR NOT NULL,                           -- short label, ~80 chars max enforced at form layer
    description         TEXT NULL,                                  -- free-form details
    severity            VARCHAR NOT NULL DEFAULT 'medium',          -- 'low' | 'medium' | 'high'
    status              VARCHAR NOT NULL DEFAULT 'active',          -- 'active' | 'resolved'
    created_at          DATETIME NOT NULL,
    created_by_user_id  INTEGER NULL REFERENCES users(id),
    resolved_at         DATETIME NULL,
    resolved_by_user_id INTEGER NULL REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS ix_pb_project_status ON project_blockers(project_id, status);
CREATE INDEX IF NOT EXISTS ix_pb_phase          ON project_blockers(phase_id);
```

Notes:
- `status` and `severity` stored as String (not SQL ENUM type) to mirror existing `ProjectPhase.status` and `ProjectVariant.status` — keeps PG/SQLite migration symmetric and avoids the migration risk of altering enums later.
- `description` is nullable so the assistant can propose a 1-line blocker without forcing a description body.
- `created_by_user_id` is nullable (matches `PhasePlanChange.changed_by_user_id`) so legacy AI-created blockers in test fixtures don't break the FK.
- Indexes target the two hot queries: "active blockers for this project" (Command Center + Pulse) and "blockers attached to this phase" (phase-strip dot, also used by Timeline History in Build 08).
- No `updated_at` column — updates write a `project_changes` audit row; we do not need cell-level optimistic concurrency.

## Backend Honesty Mapping

| Visible field | Source of truth | Write path | Derived-state rule | Permission rule | Test coverage |
|---|---|---|---|---|---|
| **Main blocker tile — title** | `project_blockers.title` (newest active by `created_at desc`) | `crud.create_blocker` + Command Center POST /command/add-blocker | If no active blocker exists → "No active blockers." empty state with `[+ Add blocker]` | All authenticated to view; `can_edit_project` for create/edit/resolve | New (Build 07B) |
| **Main blocker tile — description** | `project_blockers.description` | same as title | Truncated to 2 lines via CSS `-webkit-line-clamp:2`; full text in a small `<details>` summary that says "more" | All authenticated to view | New |
| **Main blocker tile — opened metadata** | `project_blockers.created_at`, `created_by_user_id` → `users.display_name` | (read-only) | "Opened {N} days ago by {author}" — `N = (today - created_at).days` | All authenticated to view | New |
| **Main blocker tile — [Resolve] button** | n/a — opens inline form | `crud.resolve_blocker(blocker_id, resolved_by_user_id)` via `POST /command/resolve-blocker` | Visible only if `can_edit_project` AND blocker.status == 'active' | `can_edit_project` | New |
| **Main blocker tile — [Edit] button** | n/a — opens inline form | `crud.update_blocker(blocker_id, data)` via `POST /command/edit-blocker` | Visible only if `can_edit_project`; UPDATE_BLOCKER_ALLOWED whitelist enforced on POST | `can_edit_project` | New |
| **[+ Add another blocker] / [+ Add blocker]** | n/a — toggles the Add Blocker form panel in `#cc-action-form` mount | `crud.create_blocker(...)` via `POST /command/add-blocker` | Visible only if `can_edit_project` | `can_edit_project` | New (replaces Build 07A's disabled-button + tooltip) |
| **Pulse next-action — "Resolve blocker"** | Active-blocker count from `get_active_blockers_for_project(project_id)` | (read-only) | Inserted as the FIRST branch in the existing Pulse cascade. Title: "Resolve blocker: {newest active title}". Link target: `/projects/{id}#timeline-command-center`. Falls through to existing delay/thesis/missing-field/inspiration branches when count == 0. | All authenticated to view | New + Pulse regression |
| **Phase strip — red dot on blocker phases** | Active blockers with `phase_id` filtered into `command_center_state.phase_strip` entries | (read-only) | Dot present when `entry.phase` has ≥1 active blocker. CSS class `.timeline-phase-blocker-dot` on the block. | All authenticated to view | New |
| **Severity badge** | `project_blockers.severity` | Edit form | `low` (gray) / `medium` (amber, default) / `high` (red). Color-coded chip in the tile + Pulse cascade text. | All authenticated to view | New |
| **AI proposal cards** | `TOOL_SCHEMAS` + `CONFIRMATION_TOOLS` set | Build 27 proposal system → on confirm calls handler → calls `crud.create_blocker / update_blocker / resolve_blocker` | Standard Build 27 proposal card; admin/PM can confirm | `can_edit_project` (re-validated on confirmation) | New |
| **Audit / history records** | `project_changes` rows of types `blocker_opened`, `blocker_updated`, `blocker_resolved` | Each `crud.*_blocker` writes one via `write_change()` | (none — pure write) | n/a | New |

### Reading the mapping

All 11 surfaces have an honest data source. Zero placeholders introduced by Build 07B.

## UI Scope

Touch:
- `app/models.py` — add `ProjectBlocker` model + relationship from `Project.blockers` (back_populates) and optional `ProjectPhase.blockers` (back_populates).
- `app/migrations.py` — add migration 006 `_create_project_blockers(engine)` mirroring `_create_project_creation_tokens()`.
- `app/crud.py` — add `create_blocker / update_blocker / resolve_blocker / get_active_blockers_for_project / get_blockers_by_phase / get_blockers_by_phase_id_set`. Each mutating function writes a `project_changes` audit row.
- `app/routes/projects.py` — add 3 new POST routes (`/command/add-blocker`, `/command/edit-blocker`, `/command/resolve-blocker`). Mirror Build 07A route shape: re-auth, ownership check, validate, delegate to service, redirect with `?cc_action=...&cc_result=...`.
  - Plus: extend `project_detail` view to pass `active_blockers` (list, newest first) and `blockers_by_phase_id` (dict for phase strip) into the template context.
- `app/templates/project_detail.html` — replace the Build 06 `data-placeholder="blocker"` block with an honest blocker tile. Add 3 new inline form panels inside `#cc-action-form`. Replace the disabled `[Add Blocker]` button with an enabled one (`data-cc-form="add-blocker"`); the Build 06 tooltip is dropped. Pulse template: insert the new "Resolve blocker" branch as the first cascade item. Phase strip: add the red-dot span when `entry.phase.id in blockers_by_phase_id`.
- `app/static/css/styles.css` — append `.timeline-blocker-*` styles (tile, severity chips, [Resolve] / [Edit] / "more" affordances, phase-strip red dot).
- `app/static/js/main.js` — extend `initCommandCenter()` so the new add/edit/resolve buttons populate the form mount the same way Build 07A's Finish/Adjust/Add Update do. Likely <10 lines additional.
- `app/ai/tools.py` — add 3 new tool schemas (`create_blocker`, `update_blocker`, `resolve_blocker`) + handlers; add them to `CONFIRMATION_TOOLS`; add `UPDATE_BLOCKER_ALLOWED` whitelist.
- `app/ai/prompts.py` — add 1-2 sentences guiding the assistant on when to propose a blocker (mirrors the create_idea guidance pattern at app/ai/prompts.py:157).
- `app/i18n/en.json` + `zh.json` — ~22 new keys (tile labels, severity chips, form fields, banner messages, Pulse branch, phase-strip aria). Parity target 688/688.
- `AI_TOOLS_REGISTRY.md` — add a row for the 3 new tools (per CLAUDE.md: "For any feature that creates structured data, add a corresponding tool entry").
- `test_v13_build07b.py` — new file (target ~40 assertions).
- `CURRENT_TASK.md`, `CHANGELOG.md`.

Do not touch:
- `recalculate_stage_and_delay()` — blockers do not affect `current_stage`. Delay is still planned-date driven; a blocker can co-exist with on-track planning.
- Build 07A's 3 routes / forms — unchanged.
- `phase_plan_changes` — irrelevant; blockers are not a date change.
- `ProjectJournalEntry.entry_type='risk'` — preserved for backwards compatibility (PMs can still log risk-type journal entries; we don't auto-convert old risk entries to blockers).

## Locked Decisions

### Lock 1 — Lifecycle: 2 states, not 3
`status` is `active` or `resolved`. No `archived` or `wontfix` — admin-only delete handles "ignore this for good". Keeps the Command Center display rule trivial: "newest active". Resolved blockers stay in the DB for Timeline History (Build 08) but don't render in the tile.

### Lock 2 — Severity is `low | medium | high`, not numeric
Three values cover the visual difference (gray / amber / red). Numeric severity invites scope creep (sort priority math, weighted aging). Default `medium` so omitted-severity creates don't fail.

### Lock 3 — `phase_id` is OPTIONAL
A blocker can attach to any phase OR none. Validation: if `phase_id` provided, it must belong to the same `project_id` (mirrors the existing `_relationship_error` pattern in `app/ai/tools.py:455`). Routes reject mismatched phase_id with `cc_result=not_authorized`.

### Lock 4 — "Main blocker" tile shows ONE blocker at a time (newest active)
Multiple active blockers are summarized as "+ {N-1} more" link that scrolls to a full list rendered below the tile (collapsed by default behind a `<details>` summary, mirroring the Detailed Table pattern from Build 06). Avoids tile sprawl while keeping all blockers reachable.

### Lock 5 — Pulse branch inserted FIRST in the cascade
Active blocker beats delay beats thesis beats missing-field beats inspiration. Rationale: a known active blocker is more actionable than a calculated delay (the blocker may be the *reason* for the delay). Doc-aligned: "what should the PM do next?" — resolve the blocker first.

### Lock 6 — Resolve is a one-click action, NOT a form
[Resolve] button on an active blocker posts directly to `/command/resolve-blocker` with `blocker_id`. No reason field, no confirmation modal — the blocker title + description IS the context. Bulk-resolve and resolution notes are deferred. If PMs want to capture *how* a blocker was resolved, they use Add Update (Build 07A) immediately after.

### Lock 7 — Defense-in-depth permission re-validation per route
Same pattern as Build 07A: each new route independently re-runs `require_auth` + `can_edit_project`. Phase ownership cross-check on Add/Edit. Admin-bypasses do NOT short-circuit phase-belongs-to-project validation.

### Lock 8 — Add Blocker submit-button disable (Lock 7 amendment carried over)
Build 07A's `data-cc-disable-on-submit` JS hook applies to the new Add Blocker form. UX only, not load-bearing. No server-side idempotency token; double-create creates two blockers (cheap, PM can resolve one).

### Lock 9 — AI proposes; user confirms (Build 27 pattern, no exceptions)
`create_blocker`, `update_blocker`, `resolve_blocker` all go through Build 27 confirmation. No silent AI write. `delete_blocker` is NOT exposed as an AI tool (admin-only UI action; matches `delete_variant`).

## Permissions

| Element | Visibility / action |
|---|---|
| Main blocker tile (view) | All authenticated |
| Pulse "Resolve blocker" branch | All authenticated to view; link targets are anchor only — viewer can land on Command Center but cannot mutate |
| Phase strip red dot | All authenticated |
| `[+ Add blocker]` / `[+ Add another blocker]` button | `can_edit_project` |
| `[Edit]` button on active blocker | `can_edit_project` |
| `[Resolve]` button on active blocker | `can_edit_project` |
| Hard delete | Admin only (UI button hidden from PMs; route returns 403 / redirects with `not_authorized` for non-admin) |
| AI `create_blocker / update_blocker / resolve_blocker` | `can_edit_project` (re-validated on confirmation) |

Viewer sees the tile + Pulse branch + phase-strip dot. Viewer cannot create / edit / resolve / delete. Server-side enforcement is load-bearing; UI hides the buttons.

## i18n Keys (locked EN + zh, parity-required)

| Key | EN | ZH |
|---|---|---|
| `timeline.blocker_title` | Main blocker | 主要阻碍 |
| `timeline.blocker_empty` | No active blockers. | 当前没有进行中的阻碍。 |
| `timeline.blocker_more_affordance` | more | 更多 |
| `timeline.blocker_opened_meta` | Opened {n} days ago by {author} | 由 {author} 提出 {n} 天 |
| `timeline.blocker_opened_today` | Opened today by {author} | 今天由 {author} 提出 |
| `timeline.blocker_more_count` | + {n} more | 还有 {n} 条 |
| `timeline.blocker_others_summary` | Other active blockers | 其他进行中的阻碍 |
| `timeline.blocker_severity_low` | Low | 低 |
| `timeline.blocker_severity_medium` | Medium | 中 |
| `timeline.blocker_severity_high` | High | 高 |
| `timeline.btn_add_blocker` | Add Blocker | 添加阻碍 |
| `timeline.btn_add_another_blocker` | + Add another blocker | + 添加另一阻碍 |
| `timeline.btn_resolve_blocker` | Resolve | 标记已解决 |
| `timeline.btn_edit_blocker` | Edit | 编辑 |
| `timeline.cc_blocker_title_label` | Blocker title | 阻碍标题 |
| `timeline.cc_blocker_title_placeholder` | e.g., Packaging cost is missing | 例如：包装成本尚未确定 |
| `timeline.cc_blocker_description_label` | Details (optional) | 详细描述（可选） |
| `timeline.cc_blocker_severity_label` | Severity | 严重程度 |
| `timeline.cc_blocker_phase_label` | Attach to phase (optional) | 关联阶段（可选） |
| `timeline.cc_blocker_phase_none` | — Project-wide — | — 整个项目 — |
| `timeline.cc_result_blocker_resolved` | Blocker resolved. | 阻碍已标记为已解决。 |
| `timeline.cc_result_blocker_empty_title` | Blocker title is required. | 必须填写阻碍标题。 |
| `pulse.blocker_action_title` | Resolve blocker | 解决阻碍 |
| `pulse.blocker_action_copy` | "{title}" is open. Resolve it before continuing. | 「{title}」尚未解决，请先处理。 |
| `pulse.open_command_center` | Open Command Center | 打开指挥中心 |

Total: **25 new keys** (one above the rough ~22 estimate). Parity target 691/691 (= 666 from Build 07A + 25). The Build 07A `timeline.btn_add_blocker_disabled` and `timeline.btn_add_blocker_tooltip` keys are **removed** in 07B since the button is no longer disabled (net = +25, -2 = +23 → 689/689). **Locked target: 689/689.** Plan re-counts during implementation if any key is reworded.

## Tests — test_v13_build07b.py

Target ~40 assertions. Mirrors v1.3 test pattern (requests.Session + sqlite3).

### Migration + schema
1. Migration 006 ran: `project_blockers` table exists with 11 expected columns.
2. Indexes `ix_pb_project_status` + `ix_pb_phase` exist.
3. `ProjectBlocker` model importable; `Project.blockers` relationship resolves; `ProjectPhase.blockers` resolves.

### crud.* services (called directly, not via HTTP)
4. `create_blocker` inserts a row + writes a `blocker_opened` change-log row.
5. `update_blocker` mutates allowlisted fields + writes `blocker_updated` change-log; rejects non-allowlisted fields.
6. `resolve_blocker` sets `status='resolved'`, `resolved_at`, `resolved_by_user_id`; writes `blocker_resolved` change-log.
7. `get_active_blockers_for_project` returns only `status='active'`, newest first.
8. `get_blockers_by_phase` returns blockers with that `phase_id` (and `status='active'` if filter applied).

### Routes — happy paths (admin + PM owner)
9. `POST /command/add-blocker` with valid title + description + severity + phase_id → row created, redirects `cc_result=ok`, banner renders.
10. `POST /command/edit-blocker` with valid fields → row updated, redirect ok.
11. `POST /command/resolve-blocker` → row resolved, redirect ok.

### Routes — validation
12. `POST /command/add-blocker` with empty title → `cc_result=blocker_empty_title`, no row created.
13. `POST /command/add-blocker` with `phase_id` belonging to a different project → `cc_result=not_authorized`, no row.
14. `POST /command/edit-blocker` with non-allowlisted field (e.g., `created_by_user_id=999`) → field IGNORED (whitelisted update), no privilege escalation.

### Routes — permissions
15. Viewer POST to any of the 3 routes → `cc_result=not_authorized`, no DB mutation.
16. Non-owner PM POST → same `not_authorized`.
17. PM cannot hard-delete via UI; route enforces admin-only on delete.

### Template rendering
18. Active blocker present → Command Center tile renders title + description + severity badge + opened-meta line.
19. Severity badge has class `.timeline-blocker-severity-high` (etc).
20. No active blocker → tile renders empty state with `[+ Add blocker]` button.
21. Multiple active blockers → tile shows newest + "+ {N-1} more" + collapsed `<details>` list of others.
22. PM owner sees Edit + Resolve buttons; viewer does NOT see Edit or Resolve.

### Pulse next-action cascade
23. Project with 1+ active blockers: Pulse "attention needed" card shows `pulse.blocker_action_title` (NOT delay / thesis / missing-field).
24. Project with 0 active blockers: existing Build 02 cascade unchanged (regression — delay branch fires if delayed; otherwise thesis; otherwise...).
25. Resolved blockers do NOT trigger the Pulse branch.

### Phase strip red dot
26. Phase 3 has 1 active blocker → that phase's strip block has class `.timeline-phase-blocker-dot` (or similar marker).
27. Other phases do NOT carry the dot.
28. Resolved blockers do NOT trigger the dot.

### AI tool registry
29. `create_blocker`, `update_blocker`, `resolve_blocker` in `TOOL_SCHEMAS`.
30. All 3 in `CONFIRMATION_TOOLS`.
31. `UPDATE_BLOCKER_ALLOWED` contains `title, description, severity, phase_id`.
32. `delete_blocker` NOT in `TOOL_SCHEMAS` (admin-only, UI-only).
33. AI call with `confirmed=False` returns `confirmation_required` for all 3 tools.
34. AI call with `confirmed=True` from PM-owner runs the handler.

### Cross-cutting + regression
35. i18n parity at 689/689.
36. Migrations count = 6.
37. test_v13_build07.py (07A) re-runs green — Add Blocker button is no longer the disabled placeholder; the 07A assertion that checks for the `disabled` attribute on the Add Blocker button is updated to verify the button now exists, is enabled, and has `data-cc-form="add-blocker"`.
38. test_v13_build06.py re-runs green — the placeholder assertion check (`data-placeholder="blocker"`) is updated to verify the honest tile now renders instead. AI Nudge placeholder still present.
39. test_v13_build02.py (Pulse) re-runs green AFTER updating the test to accept the new blocker branch as a valid Pulse output when blockers exist; existing branches still fire when blockers are zero.
40. `test_build_v121.py` 19/19 (release-proof regression).

### Manual browser walkthrough
- Add a blocker via the form; verify it appears in the tile, in Pulse, and as a phase-strip dot.
- Edit the blocker; verify changes render.
- Resolve via the [Resolve] button; verify tile reverts to "No active blockers" empty state, Pulse falls back, phase dot disappears.
- Add 3 blockers; verify the "+ 2 more" affordance + collapsed details list.
- As viewer: verify tile + Pulse branch visible, NO action buttons.
- Via AI assistant: ask "create a blocker for missing packaging cost"; verify proposal card appears; confirm; verify it lands as an active blocker.

## Explicit Deferrals

- Blocker comments / discussion thread → not planned; use Add Update for thread-like updates linked to the blocker title.
- Blocker SLA timers / auto-escalation → not planned.
- Bulk-resolve (one click resolves multiple) → not planned for v1.3.
- AI-generated blocker summaries / proactive blocker detection from chat → Build 07B exposes the tool but does NOT auto-propose. Future builds may add proactive proposal.
- Cross-project blocker dashboard → out of scope.
- Blocker file attachments → out of scope; use Add Update + file uploads on the journal entry instead.
- Renaming `journal.entry_type='risk'` rows to blockers → no auto-migration; existing risk entries stay as journal entries.
- Severity = `critical` (4th level) → 3 levels are enough for visual differentiation; add later if needed.

## Rollback / Safety

Rollback is migration + code + template:
- Drop `project_blockers` table (`DROP TABLE project_blockers`).
- Remove migration 006 entry from `MIGRATIONS` list and the `_create_project_blockers` function.
- Revert `app/models.py` (remove `ProjectBlocker` + relationships).
- Revert the 3 new routes in `app/routes/projects.py`.
- Revert the 6 new `crud.*_blocker` functions.
- Revert template: restore Build 06's `data-placeholder="blocker"` block, restore disabled `[Add Blocker]` button and `timeline.btn_add_blocker_disabled` + `timeline.btn_add_blocker_tooltip` keys.
- Revert Pulse cascade: remove the blocker branch.
- Revert phase-strip dot CSS + data attribute.
- Remove `app/ai/tools.py` blocker entries from `TOOL_SCHEMAS`, `CONFIRMATION_TOOLS`, `UPDATE_BLOCKER_ALLOWED`, and `_HANDLERS`.
- Remove i18n keys.
- Delete `test_v13_build07b.py`.

If migration 006 ran in production before rollback, `DROP TABLE` is the only destructive step. All other reverts are template / code only. The drop is safe because no other table references `project_blockers` (FK direction is `project_blockers → projects/users/phases`, not the reverse).

## Acceptance Criteria

- Migration 006 creates `project_blockers` idempotently on SQLite + PostgreSQL.
- `crud.create_blocker / update_blocker / resolve_blocker` each write a `project_changes` audit row.
- Command Center "Main blocker" tile is honest: shows newest active blocker OR "No active blockers" empty state.
- Pulse "Resolve blocker" branch fires first in the cascade when active blockers exist.
- Phase strip shows red dot only on phases with ≥1 active blocker.
- All 3 routes enforce permissions server-side; viewer + non-owner PM cannot mutate.
- All 3 AI tools require Build 27 confirmation before write.
- `delete_blocker` is not exposed as an AI tool.
- i18n parity at 689/689.
- Build 06 + 07A + 02 (Pulse) regressions all pass after their assertions are updated for the new honest blocker tile.
- Manual browser walkthrough passes (create / edit / resolve / "+ N more" / viewer view / AI propose+confirm).

## What Build 07B Solves From the User's Doc

| User concern (from canonical doc + Build 07 pre-doc) | Build 07B response |
|---|---|
| "Add Blocker always requires the pre-build Architecture Review" | ✓ This plan's Architecture Review section + 7 question table |
| "Wire Add Blocker only if source-of-truth mapping is approved" | ✓ Backend Honesty Mapping table — 11 honest fields, 0 placeholders introduced by 07B |
| "Blockers should drive pulse/timeline blocker display if implemented" | ✓ Pulse cascade branch (Lock 5) + Command Center tile + phase-strip dot |
| "AI confirmation required for every chat-driven write" | ✓ All 3 AI tools in CONFIRMATION_TOOLS (Lock 9) |
| "Timeline actions move real backend state, refresh derived state, and leave audit/history behind" | ✓ Migration 006 + 3 mutating crud helpers + write_change in each + Pulse re-renders on next page load |
| "No action is wired by merely changing frontend text" | ✓ 3 new dedicated routes + a new table + 3 new service functions + 3 new AI tool handlers |

## Open Questions Remaining

- **AI assistant proactive proposal:** should the assistant auto-suggest a blocker when chat contains language like "blocked by", "waiting on", "can't move forward"? **Default answer: NO for Build 07B** — assistant only creates a blocker when explicitly asked. Proactive detection is a future iteration once we see whether PMs actually use the manual form.
- **Resolved-blocker visibility:** should resolved blockers appear in Command Center at all (e.g., a "Recently resolved" small section)? **Default answer: NO for Build 07B** — they appear in Build 08's Timeline History view instead, keeping Command Center focused on "what needs attention now."
- **Pulse branch when blocker exists AND project is also delayed:** which message wins? **Default answer: blocker wins** (Lock 5). The delay branch is suppressed when there's at least one active blocker. PM can still see the delay in the Command Center deadline tile.

These are all "default = NO/conservative" choices; user can override before implementation starts.

---

End of Build 07B execution plan. Implementation begins only after this is reviewed and approved.
