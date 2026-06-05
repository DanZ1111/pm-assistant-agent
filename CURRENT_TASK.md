# CURRENT_TASK.md

## Task
v1.3 Build 07B — Project Blockers (first-class lifecycle model + Command Center wiring). Implemented + tested. Awaiting push.

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth.

## What just shipped in this session

- **Build 07B implementation** committed as one atomic commit (see latest `git log`). Locks 1–10 approved 2026-06-05; implementation followed plan verbatim.
  - `app/models.py` — `ProjectBlocker` model (11 columns), `Project.blockers` + `ProjectPhase.blockers` relationships.
  - `app/migrations.py` — Migration 006 `_create_project_blockers(engine)`, idempotent `CREATE TABLE IF NOT EXISTS` + `ix_pb_project_status` + `ix_pb_phase` indexes (mirrors Build 30A's migration 004 pattern).
  - `app/crud.py` — 6 helpers: `create_blocker / update_blocker / resolve_blocker / get_active_blockers_for_project / get_blockers_by_phase / get_active_phase_blocker_ids` + `UPDATE_BLOCKER_ALLOWED` whitelist. Each mutating helper writes a `project_changes` audit row.
  - `app/routes/projects.py` — 3 new POST routes (`/command/add-blocker`, `/command/edit-blocker`, `/command/resolve-blocker`); `command_center_state` now includes `active_blockers`, `active_blocker_count`, `newest_active_blocker`, `blocker_phase_ids`.
  - `app/templates/project_detail.html` — Build 06 `data-placeholder="blocker"` block replaced with honest `timeline-blocker-tile`; phase-strip blocks gain `timeline-phase-blocker-dot` for phase-linked blockers; Pulse cascade gets a new FIRST branch (Lock 5) — active blocker beats delay/thesis/missing-field; `[Add Blocker]` button promoted from disabled placeholder to enabled `data-cc-form="add-blocker"`; two new inline form panels (Add Blocker + Edit Blocker) inside `#cc-action-form`; new `cc_result` codes (`blocker_empty_title` error, `blocker_resolved` success).
  - `app/static/css/styles.css` — `.timeline-blocker-*` styles (tile, severity chips low/medium/high, count badge, phase-strip dot).
  - `app/static/js/main.js` — `initCommandCenter()` extended with `populateEditBlocker()` that pre-fills the Edit form from the [Edit] button's `data-blocker-*` attrs.
  - `app/ai/tools.py` — 3 new schemas (`create_blocker`, `update_blocker`, `resolve_blocker`), `UPDATE_BLOCKER_ALLOWED`, all 3 added to `CONFIRMATION_TOOLS` (Lock 9). Relationship checks reject wrong-project blocker_id (forbidden) + wrong-project phase_id (phase_not_found). 3 handler functions registered in `_HANDLERS`. `delete_blocker` NOT in `TOOL_SCHEMAS` (matches `delete_variant` admin-only pattern).
  - `app/ai/prompts.py` — 1-sentence guidance: create_blocker only when user explicitly asks; do NOT proactively propose.
  - `AI_TOOLS_REGISTRY.md` — 4 new rows (3 implemented + 1 "not registered — by design").
  - `app/i18n/en.json` + `zh.json` — 24 new keys − 2 removed = net +22; parity 688/688.
  - `test_v13_build07b.py` — **66/66 PASS** (migration + model + i18n parity + crud helpers + audit + Lock 3 phase mismatch + query helpers + template active state + empty state + phase-strip dot + project-level blocker doesn't light up phase + routes happy/empty/cross-project/viewer/wrong-project rejections + Pulse cascade Lock 5 + resolved blockers don't trigger phase dots + AI tool schemas + confirmation gating + no delete_blocker + Build 06/07A invariants).
  - `test_v13_build06.py` + `test_v13_build07.py` — updated for honest tile + enabled Add Blocker button + key churn (planned regression test updates).
  - `test_ai_e2e.py` — TOOL_SCHEMAS count loosened from `== 20` to `>= 20` (Build 07B adds 3 → 23).

## Build 07B — Confirmed locks (1-10)

1. **Real `project_blockers` table** — not journal extension.
2. **2-state lifecycle** (active / resolved); admin-only hard delete is the escape hatch (no UI surface yet).
3. **`phase_id` OPTIONAL + same-project validation**; phase-strip red dot fires ONLY for phase-linked blockers (project-level blockers do not light up any phase block).
4. **Tile shows newest active + active-count badge** (`+N more active` text); `+N more` expanded list DEFERRED to Build 08 Timeline History.
5. **Pulse blocker branch goes FIRST**; beats delay/thesis/missing-field. Behavior change for Build 02 cascade; test_v13_build02 still 11/11 (existing branches still fire when count == 0).
6. **Resolve is one-click** + audit explicit: `crud.resolve_blocker` sets `status`, `resolved_at`, `resolved_by_user_id` AND writes `blocker_resolved` change-log row.
7. **Defense-in-depth permission re-validation** per route + phase-belongs-to-project check on every blocker write.
8. **Add Blocker form** carries `data-cc-disable-on-submit` (Lock 7 amendment from Build 07A carried over).
9. **AI tools confirmation-gated** (all 3 in `CONFIRMATION_TOOLS`); no `delete_blocker` AI tool.
10. **Scope discipline**: NO project health engine, NO SLA timers, NO proactive AI blocker proposal, NO recently-resolved section, NO `+N more` expanded list, NO blocker comments, NO file attachments, NO journal `risk` auto-migration.

## Verification at ship time

- `python3 test_v13_build07b.py` — **66/66 PASS**.
- Regression: `test_v13_build01..07` all green (Build 06 + 07 had planned assertion updates for the new honest tile + enabled button + tooltip key removal); `test_build_v121` 19/19; `test_build30` 23/23; `test_ai_e2e` 15P/2S/0F.
- i18n parity: **688/688**.
- Migration 006 applied successfully on dev sqlite; idempotent on both SQLite + PostgreSQL.

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
| **07B — Project Blockers (model + Command Center wiring)** | **shipped this session** | latest |
| 08 — Timeline History (derived from change-log + journal + plan_changes + files) | planned | — |
| 09 — Planning Sandbox (design-only doc) | planned | — |
| 10 — v1.3.0 Release Hardening (version bump + release-proof regression) | planned | — |

## Next step

Wait for user direction. Suggested next moves:
1. **Push** to origin (currently several commits ahead of `origin/main`).
2. **Browser walkthrough** of Build 07B — add a project-level blocker; verify Pulse branch fires + tile renders + no phase dots; add a phase-linked blocker on phase 3; verify phase 3 gets a red dot + count badge says "+1 more active"; edit one; resolve one; verify tile flips to empty state + Pulse falls through to delay/thesis branch.
3. **Build 08 plan** — Timeline History view derived from `project_changes` + `phase_plan_changes` + `project_journal_entries` + uploaded files + (new) `blocker_opened` / `blocker_resolved` change-log rows. No new table per the doc; "the data already exists." Per the user's V13_MASTERPLAN.md.
4. **Native-speaker Chinese review** of strings added in v1.3 Builds 01-07B (carried-forward deferral).

## Deferred to future builds (carried forward)

- Native-speaker Chinese review of strings added in Builds 26-30C + v1.3 Builds 01-07B.
- AI prompt translation, Help modal body translation, `/admin/*` page translation.
- Full Profit Model implementation (variant cell shows naive margin; full model is v1.4).
- Row-level multi-tenancy (`Organization` table + `org_id` everywhere). Deployment-level isolation (Build 25) remains the answer for ≤3 departments.
- Bulk delete from the projects list / soft-delete with undo window.
- Auto-provisioning script for Railway (the DEPLOYMENT.md runbook is still manual).
- One-time admin cleanup of the original 6 admin-linked duplicates from the Build 30A incident.
- Recently-resolved blockers section in Command Center (per Lock 10 — out of scope for 07B; Build 08 Timeline History will surface them in history view).
- `+N more` expanded blocker list (per Lock 4 — Build 08 will provide the list).
- Proactive AI blocker proposal from chat heuristics (per Lock 10 — manual-only this build).
- Blocker comments / discussion thread, file attachments, SLA timers (per Lock 10 — out of scope).

## v1.3 process pattern (continues)

Every build gets a build-specific execution plan before coding. Plan files are committed/reviewed first. Builds touching schema additionally write an Architecture Review section answering CLAUDE.md's 6 schema questions + any build-specific gates (Build 07B answered both the 6 schema questions and the 7 Add Blocker open questions sketched at the end of V13_BUILD07_EXECUTION_PLAN.md). Locks are resolved in-plan before implementation starts; ChatGPT + Claude both review and the plan gets amended before code lands. Build 07B added Lock 10 (scope discipline) as a new lock type — explicitly forbids "while we're here" feature creep when a build's surface area could naturally expand.
