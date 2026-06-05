# CURRENT_TASK.md

## Task
v1.3 Build 09 — Planning Sandbox Design (design-only). Shipped. Awaiting Build 10 (release hardening).

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth.

## What just shipped in this session

- **Build 09 — Planning Sandbox Design (design-only)**, committed as one atomic commit (see latest `git log`).
  - `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md` (~24 KB) — comprehensive design lock covering all 8 user-specified sections: purpose, 6 template types, module model, dependency/overlap, estimated launch math, save-as-template flow, 6 open schema decisions (with recommendations), and the recommended v1.4 4-sub-build implementation sequence.
  - `test_v13_build09.py` — **31/31 PASS**. Regression-guard: asserts design doc exists, all 8 locked sections present, all 6 template types named, all 6 schema decisions present, 4 v1.4 sub-builds present, AND zero scope drift (no migration drift, no i18n drift, no new tables, no can_overlap/overlap_group columns, no new AI tools).
  - No app code changed. No schema. No migration. No i18n. No AI tools. No routes.

## Build 09 — design lock highlights (for v1.4 reference)

### Schema decisions locked (Q1–Q6)
1. **Templates as DB rows**, not static config (`timeline_templates` + `timeline_template_modules`).
2. **Dependencies in a join table**, not a JSON column (cycle detection + topological sort need queryable edges).
3. **Copy-down module → phase** when applying a template (historical project phases must not mutate when source template evolves).
4. **Persisted sandbox state** on the project itself (no separate `sandbox_drafts` table; every edit flows through `crud.update_phase` and writes a normal `phase_plan_changes` audit row).
5. **AI tool surface**: read + apply tools (confirmation-required), no `create_timeline_template` AI tool (matches `delete_variant` UI-only pattern).
6. **Python DAG, not SQL CTE** for the dependency engine (project scale 8–14 phases doesn't warrant DB-side recursion).

### v1.4 sub-build sequence (locked)
| Sub-build | Scope | Risk |
|---|---|---|
| v1.4 Build 01 | Template tables + seed 6 system templates + admin-only template list page | Low |
| v1.4 Build 02 | "Apply template" flow on New Project form + AI intake confirm | Medium |
| v1.4 Build 03 | Sandbox UI: edit durations + dependencies + overlap + live estimated launch | **High** |
| v1.4 Build 04 | "Save current as template" | Low |

### Out of scope for v1.3 entirely (per Build 09 doc)
Any DB table for templates, any migration, any UI for templates, any route changes, any AI tool addition, any seed data, any change to `PHASE_TEMPLATES`, any cycle-detection / topological-sort code.

## Verification at ship time

- `python3 test_v13_build09.py` — **31/31 PASS**.
- Regression sweep all green:
  - `test_v13_build01..08` — 380 assertions total, all PASS.
  - `test_build_v121` — 19/19.
- i18n parity: **714/714** (unchanged).
- Migration count: **6** (unchanged).
- Code changes outside the new doc + new test file: **zero** (verified by test invariants).

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
| 08 — Timeline Updates / History | shipped | `3ab1dc8` |
| **09 — Planning Sandbox Design (design-only)** | **shipped this session** | latest |
| 10 — v1.3.0 Release Hardening | next | — |

## Next step — Build 10 (v1.3.0 Release Hardening)

Final v1.3 build. Suggested scope (per masterplan §"Testing Standard"):
1. **Version bump**: `app/version.py` `v1.2.0-build30` → `v1.3.0`. Update build name + LAST_UPDATED. Update visible version strings if any exist outside `app/version.py`.
2. **Roll up CHANGELOG**: collapse the Unreleased section's v1.3 Builds 01-09 entries into a single `## v1.3.0` heading with a release narrative + dated.
3. **Update MASTERPLAN.md**: mark all 10 v1.3 builds as ✓ SHIPPED with their commit hashes; add v1.3.0 to the version history table if one exists.
4. **Write `test_v13_build10.py`** as the release-proof regression: re-runs all v1.3 Builds 01-09 + v1.2.1 baseline, asserts the version string, asserts the CHANGELOG has a v1.3.0 entry. Mirrors `test_build29.py`'s shape (which served the same role for v1.2.0).
5. **Address the legacy Change Log viewer leak** discovered during Build 08:
   - **Risk assessment**: low. The leak surfaces `event_note` audit rows whose summary mirrors journal-entry text to viewer in the `#changes` section (line 1497 in `project_detail.html`). Viewer permissions are otherwise correct everywhere else (Build 08's `#timeline-history` already hides these). Severity: information disclosure to a role that already has read access to projects; not a privilege escalation.
   - **Recommendation**: include the fix in Build 10 — it's small (~10 LOC in the template's `change-log` for-loop to also skip `event_note` rows whose summary starts with "Journal entry added:" when `not can_view_journal`). Add a single assertion in `test_v13_build10.py` to lock the fix. Avoids shipping v1.3.0 with a known viewer-visibility bug.
   - **Alternative**: ship v1.3.0 first, fix as v1.3.1 patch. Defensible if the rest of the release is critical and we want the change set to be exactly Builds 01-09. **My vote: include in Build 10** because the fix is trivial and shipping a known leak in a release flagged as "release-hardening" reads poorly.

## Deferred to future builds (carried forward)

- Native-speaker Chinese review of strings added in Builds 26-30C + v1.3 Builds 01-09.
- AI prompt translation, Help modal body translation, `/admin/*` page translation.
- Full Profit Model implementation (v1.4).
- Row-level multi-tenancy.
- Bulk delete from the projects list / soft-delete with undo window.
- Auto-provisioning script for Railway.
- One-time admin cleanup of the original 6 admin-linked duplicates from the Build 30A incident.
- **Planning Sandbox implementation** — design locked in Build 09; implementation is v1.4 Builds 01-04 per the sequence in `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md` §8.
- Cursor pagination beyond 200 Timeline History events (per Build 08 Lock 11).
- Recently-resolved blockers section in Command Center (per Build 07B Lock 10).

## v1.3 process pattern (closing the series)

Every build in this series:
- Started with a per-build execution plan (`V13_BUILD0X_EXECUTION_PLAN.md`), committed and reviewed before code.
- Got a Backend Honesty Mapping when display surfaces were introduced.
- Got an Architecture Review when schema changed (Build 07B, Build 05B) OR in reverse when schema was deliberately NOT changed (Build 08 — proved existing tables sufficient; Build 09 — locked the design for v1.4).
- Got a "Scope discipline" lock (introduced in Build 07B Lock 10, carried through Builds 08 and 09) — an explicit out-of-scope list to prevent feature creep mid-build.
- Got a regression sweep + commit before moving to the next build.

This pattern scales. v1.4 Sandbox builds should reuse it verbatim.
