# CURRENT_TASK.md

## Task
**v1.3.0 SHIPPED.** Build 10 release-hardening complete. Awaiting v1.4-01 (Planning Sandbox Schema + Module Library).

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth.

## What just shipped in this session

- **Build 10** committed as one atomic commit (see latest `git log`). Closes the v1.3 series; v1.3.0 is now the official release.
  - `app/version.py` — `1.2.1` → `1.3.0`. `CURRENT_BUILD_NAME` updated to identify v1.3.0. `LAST_UPDATED = 2026-06-06`.
  - `VERSION.md` — new header (v1.3.0 / 2026-06-06), new `## What's new in v1.3.0` narrative covering all 10 builds + the cross-cutting delete-FK fix, Version Map extended with v1.2.0 / v1.2.1 / v1.3.0 rows. The historic v1.2.0 / v1.2.1 release sections + Version Map back to v0.1.0 preserved.
  - `CHANGELOG.md` — `## Unreleased` reset to empty placeholder. New `## v1.3.0 — Project Detail Command Center` heading dated 2026-06-06, with Build 10's leak-fix entry on top + every prior `## Unreleased` v1.3 entry preserved verbatim underneath.
  - `MASTERPLAN.md` — new `## v1.3.0 — Project Detail Command Center ✓ SHIPPED v1.3.0` section between the v1.2.1 entry and `## Requirements (Build 1)`. Lists all 10 builds + the cross-cutting fix with commit hashes; documents Build 10's hardening scope; sketches the v1.4 Planning Sandbox 9-sub-build sequence as the next milestone.
  - `app/templates/project_detail.html` — 3-line patch around the `#changes` (legacy Change Log) for-loop hides `event_note` rows whose `summary` starts with `"Journal entry added:"` when `not can_view_journal`. Mirrors Build 08's `_is_pc_sensitive` rule for the Timeline History feed. End-to-end smoke-tested: viewer GET on a project with a journal entry no longer surfaces the journal text in the Change Log section; admin/PM continue to see everything.
  - `test_build_v121.py` — `CURRENT_VERSION` assertion relaxed from `startswith("1.2.")` to "anything past v1.2.0". `CURRENT_BUILD_NAME` no longer required to mention v1.2.1. `VERSION.md` assertion drops the `**Current Version:** v1.2.1` literal-string check (since the bump overwrites it) but still asserts `v1.2.1 released` + `## What's new in v1.2.1` markers — the load-bearing v1.2.1 release proof.
  - `test_v13_build10.py` — new file, **51/51 PASS**. Sections: runtime version source on v1.3 line; release docs (v1.3.0 markers in VERSION.md / CHANGELOG.md / MASTERPLAN.md + v1.2.0/v1.2.1 preservation); v1.3 test-file inventory (test_v13_build01..10 + 05b + 07b + cross-cutting tests); i18n parity at 714/714; migration count at 6; Build 10 leak-fix template patch present + end-to-end leak-smoke (viewer page does NOT contain journal text); cross-cutting behavior locks (SQLite FK enforcement, `delete_project` ai_conversations + project_creation_tokens cleanup, Build 08 `get_timeline_events`, Build 07B `get_active_blockers_for_project` / `get_active_phase_blocker_ids` / `ProjectBlocker` model + `Project.blockers` relationship); plan-file regression guard; subprocess invocation of `test_build_v121.py` + `test_delete_project_ai_intake_regression.py` + every `test_v13_build0N.py` (01-09) + `test_v13_build05b.py` + `test_v13_build07b.py`.

## Build 10 — release verification at ship time

- `python3 test_v13_build10.py` — **51/51 PASS**.
- Full v1.3 + cross-cutting + baseline sweep:
  - v1.3 Builds 01-10 (16 + 11 + 20 + 20 + 34 + 42 + 59 + 57 + 66 + 55 + 99 + 51 = **530 assertions**), all green.
  - `test_delete_project_ai_intake_regression.py` 17/17.
  - `test_build_v121.py` 19/19 (relaxed CURRENT_VERSION assertion survives v1.3.0 bump).
  - `test_ai_e2e.py` 15P / 2S / 0F (SKIPs are env-config, not regressions).
- Total: **566 assertions PASSING** across 14 test files.
- i18n parity: **714/714** EN/zh.
- Migration count: **6** (locked at v1.3.0; v1.4 adds 4 more — 007, 008, 009, 010).

## v1.3 Build series — FINAL

| Build | Status | Commit |
|---|---|---|
| 01 — Workspace Shell | shipped | `448364e` |
| 02 — Project Pulse v1 | shipped | `ea0460c` |
| 03 + 04 — Product Concept + Renderings Overview | shipped together | `bc80506` |
| 05 — Variant Command Cards | shipped | `4d8c847` |
| 05B — Structured Variant Specs | shipped | `dd96cf2` |
| 06 — Timeline Command Center Shell | shipped | `4a800d6` |
| 07A — Timeline Command Actions Backend | shipped | `57b48c3` |
| 07B — Project Blockers | shipped | `5dfff4e` |
| 08 — Timeline Updates / History | shipped | `3ab1dc8` |
| Cross-cutting — Project delete FK fix | shipped | `b8a9687` |
| 09 — Planning Sandbox Design (original) | shipped | `fc064a6` |
| 09 amended — Engineering response to PRD | shipped | `fd59cf9` |
| 09 amended again — Codex V14 additions | shipped | `9fce749` |
| **10 — v1.3.0 Release Hardening** | **shipped this session** | latest |

## Next step — v1.4-01 Planning Sandbox Schema + Module Library

Per `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md` §4 (the design lock):

| Sub-build | Scope | Risk |
|---|---|---|
| **v1.4-01** | Migration 007: 4 tables (`planning_module_library`, `planning_sandboxes`, `planning_sandbox_nodes`, `planning_sandbox_edges`). Seed module library with ~20 module rows. Migration 010 ships early so v1.4-03 can render from templates; seed 6 system templates. Admin-only `/admin/modules` read-only list page. NO canvas yet. | Low |
| v1.4-02 | Schedule Engine (pure Python, ~30 fixture assertions, no UI) | Medium |
| v1.4-03 | Static Canvas Renderer (read-only Cytoscape.js render) | Medium |
| v1.4-04 | Module Palette + Add/Edit Nodes | Medium-high |
| v1.4-05 | Connect Nodes (drag handles + cycle detection; property-panel fallback ships either way) | **High** |
| v1.4-06 | Canvas Interaction Hardening (Tidy + duration bins + warning banner + read-only applied snapshots) | Medium |
| v1.4-07 | Apply to Project Plan (10-step transaction; 4 preconditions including active-blocker check) | **High** |
| v1.4-08 | Save as Template + 3 AI tools | Medium |
| v1.4-09 | Release Hardening v1.4.0 + scenario contract runner + AI_TOOLS_REGISTRY.md update | Medium |

Total v1.4 Sandbox surface: 4 migrations (007–010), 7 new tables, ~14 crud helpers, 3 implemented AI tools + 2 deferred, ~170 test assertions across 9 plan-first execution slices.

## Deferred to v1.4 / beyond (carried forward)

- USER_GUIDE.md v1.3.0 Chinese 速览 summary block — needs native-speaker review.
- Native-speaker Chinese review of strings added in v1.3 Builds 01-09.
- AI prompt translation, Help modal body translation, `/admin/*` page translation.
- Full Profit Model implementation.
- Row-level multi-tenancy.
- Bulk delete from the projects list / soft-delete with undo window.
- Auto-provisioning script for Railway (DEPLOYMENT.md runbook is still manual).
- One-time admin cleanup of the original 6 admin-linked duplicates from the Build 30A incident.
- Planning Sandbox implementation (v1.4-01 through v1.4-09 per Build 09 design lock).
- Cursor pagination beyond 200 Timeline History events (per Build 08 Lock 11).
- Recently-resolved blockers section in Command Center (per Build 07B Lock 10).
- Multiple sandbox drafts per project (per Build 09 amended Q9 — v1.5+).
- Append-after-advanced-phases Apply mode (per Build 09 amended Q2 — v1.5+).
- Critical-path highlighting on sandbox canvas (v1.5+).

## v1.3 process pattern (closed — full retrospective)

Every build in the v1.3 series:
- Started with a per-build execution plan (`V13_BUILD0X_EXECUTION_PLAN.md`), committed and reviewed before code.
- Got a Backend Honesty Mapping when display surfaces were introduced (Build 06 onward; Build 09 amended brought it to design-doc level too).
- Got an Architecture Review when schema changed (Build 05B, Build 07B) OR in reverse when schema was deliberately NOT changed (Build 08 — proved existing tables sufficient; Build 09 amended — locked the v1.4 design without touching v1.3 schema).
- Got a "Scope discipline" lock (introduced in Build 07B Lock 10, carried through every later build) — explicit out-of-scope lists prevented feature creep mid-build.
- Got a regression sweep + commit before moving to the next build.

Two new reusable patterns the series established:
1. **Design-doc correction via new commit** (Build 09 + Amendment 1 + Amendment 2) — when a shipped design doc turned out to assume the wrong product after external review, the response was a fresh commit that rewrote the doc + updated the regression test + added a dated Decision log row, NOT a `git commit --amend` or silent rewrite. The pattern is reusable for any future shipped-design-doc correction.
2. **Cross-cutting bug fix between feature builds** (the project-delete FK fix at `b8a9687` between Build 08 and Build 09) — when a user-reported bug surfaces mid-series and is unrelated to the current build, ship it as its own commit with a dedicated regression test file rather than folding it into either adjacent feature build's commit. The pattern is reusable for any future cross-cutting fix.

Both patterns scale to the v1.4 sandbox builds.
