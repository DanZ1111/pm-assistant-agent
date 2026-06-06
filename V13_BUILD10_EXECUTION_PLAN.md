# v1.3 Build 10 Execution Plan — v1.3.0 Release Hardening

## Status

Plan-only execution gate. Approved 2026-06-06. Implementation runs this session.

Predecessor: Build 09 Amendment 2 shipped at `9fce749` (Planning Sandbox engineering design with Codex's V14 additions folded in).

Successor: v1.4 series begins after this commit (first build = v1.4-01 Schema + Module Library per the Build 09 design lock).

## Purpose

Roll up all v1.3 work + four post-v1.2.1 unreleased patches into a single tagged release `v1.3.0`. Ship a release-proof regression file that future patches must keep green. Fix the one outstanding bug that surfaced during Build 08 (the legacy Change Log viewer leak) so v1.3.0 doesn't ship with a known viewer-visibility defect.

Mirrors the shape of Build 29 (the v1.2.0 release proof) and the unreleased `test_build_v121.py` rollup that closed v1.2.1.

## Scope (strict)

In:
1. **Version bump:** `app/version.py` from `1.2.1` → `1.3.0`. Update `CURRENT_BUILD_NAME` + `LAST_UPDATED`.
2. **VERSION.md:** add `v1.3.0` header + "What's new in v1.3.0" narrative covering Builds 01–09.
3. **CHANGELOG.md:** roll up the `## Unreleased` section's v1.3 entries (Builds 01–09 + the project-delete FK fix) into a single `## v1.3.0` heading with date. Preserve every per-build narrative under the new heading.
4. **MASTERPLAN.md:** mark all 10 v1.3 builds ✓ SHIPPED with commit hashes.
5. **Legacy Change Log viewer leak fix** (~10 LOC in `project_detail.html` template; one assertion in `test_v13_build10.py`).
6. **test_v13_build10.py** — release-proof regression. Modeled on `test_build_v121.py`. Asserts runtime version, doc rollup, regression inventory (all `test_v13_buildNN.py` present), i18n parity locked at 714/714, the Change Log leak fix in place, full v1.3 + v1.2.1 + delete-fix test runs all PASS when invoked from this file via subprocess.
7. **Relax `test_build_v121.py` `CURRENT_VERSION` assertion** so it survives the v1.3.0 bump (currently asserts `startswith("1.2.")` — needs to be tolerant of any future major-line version that still preserves the v1.2.1 release proof markers).
8. **CURRENT_TASK.md:** mark Build 10 + v1.3.0 shipped; point to v1.4-01 as next step.

Out (explicit):
- USER_GUIDE.md v1.3.0 native-speaker Chinese summary block. Carried forward as a deferred polish item (the existing v1.2.1 Chinese block stays; no Chinese expert in this session). `test_v13_build10.py` does NOT assert a Chinese summary so the bump isn't blocked on it.
- Migration test count change. v1.3 added migrations 005 (Build 05B) and 006 (Build 07B); migration count locks at 6 in test_v13_build10.
- Cosmetic CHANGELOG re-formatting. The rollup preserves each build's narrative verbatim under the new `## v1.3.0` heading; no rewriting.
- AI_TOOLS_REGISTRY.md update for v1.4 sandbox tools. Per Build 09 Amendment 2, that's a v1.4-09 deliverable, NOT v1.3.0.
- Native-speaker review of any new strings added in v1.3 Builds 01–09. Carried forward (it was carried forward from v1.2.1 too).
- Planning Sandbox implementation. Locked as v1.4 in Build 09 design doc.

## Root cause + fix for the legacy Change Log viewer leak

Discovered during Build 08 (Timeline History viewer-permission audit). The leak:

- `app/templates/project_detail.html:1497` renders `#changes` (the Build 13 Change Log section) by iterating `changes` (= `project_changes` rows for this project).
- The loop's only role-filter is at line 1503: `{% set sensitive_fields = ['factory', 'engineer', 'target_factory_cost'] %}` + a check at 1506 that hides `field_update` changes for those fields from non-`can_sensitive` users.
- **It does NOT filter `event_note` rows.** When `crud.create_journal_entry()` is called, it writes a `project_changes` row of type `event_note` with summary `"Journal entry added: '{snippet}'"`. The viewer cannot see the source journal entry (gated on `can_view_journal`) but the audit-mirror row's summary leaks the journal body text via the Change Log section.

Build 08 fixed this *in its own History feed* (added the journal-mirror filter to `crud._is_pc_sensitive`), but explicitly deferred the legacy Change Log fix per Lock 11 scope discipline. Build 10 finishes the job.

**Fix:** in `project_detail.html` line 1504 `for c in changes` loop, additionally skip rows where `c.change_type == 'event_note'` AND `c.summary` starts with `"Journal entry added:"` AND `not can_view_journal`. Mirror the Build 08 rule.

```jinja2
{% for c in changes %}
{# Build 10 — hide journal-mirror event_notes from viewers, parity with Build 08 history. #}
{% if c.change_type == 'event_note' and not can_view_journal and c.summary and c.summary.startswith('Journal entry added:') %}
{% else %}
{# Hide sensitive field changes from viewers — existing behavior #}
{% if c.change_type == 'field_update' and c.field_name in sensitive_fields and not can_sensitive %}
{% else %}
   ... existing render ...
{% endif %}
{% endif %}
{% endfor %}
```

Lines changed: ~3 (the new `{% if %}{% else %}` wrap around the existing `{% if %}{% else %}` block).

Risk: very low. The fix only hides rows from viewers; admin and PM continue to see everything. Reversing the fix is one Edit. No data risk.

## Critical files

Read (already inspected for this plan):
- [app/version.py](app/version.py) — 3 constants to bump.
- [VERSION.md](VERSION.md) — current header + "What's new" sections.
- [CHANGELOG.md](CHANGELOG.md) — `## Unreleased` block to roll up.
- [MASTERPLAN.md](MASTERPLAN.md) — v1.3 build entries to mark shipped.
- [test_build_v121.py](test_build_v121.py) — pattern to mirror; `CURRENT_VERSION` assertion to relax.
- [app/templates/project_detail.html:1497](app/templates/project_detail.html#L1497) — Change Log section to patch.

Modify:
- `app/version.py` — 3 constants.
- `VERSION.md` — header + new v1.3.0 section.
- `CHANGELOG.md` — collapse `## Unreleased` v1.3 entries into `## v1.3.0`.
- `MASTERPLAN.md` — v1.3 build ship status.
- `app/templates/project_detail.html` — Change Log viewer-leak patch (~3 lines).
- `test_build_v121.py` — relax `CURRENT_VERSION` assertion to tolerate v1.3+ (1 line edit).
- `CURRENT_TASK.md` — Build 10 + v1.3.0 shipped status.

Create:
- `V13_BUILD10_EXECUTION_PLAN.md` — this file.
- `test_v13_build10.py` — release-proof regression.

## test_v13_build10.py — locked test surface

Modeled on `test_build_v121.py`. Target ~30 assertions.

### Runtime version source
1. `app.version.CURRENT_VERSION` starts with `"1.3."`.
2. `CURRENT_BUILD_NAME` references `"v1.3.0"` or `"1.3.0"`.
3. `LAST_UPDATED` is ISO date format.

### Release docs
4. `VERSION.md` contains `"**Current Version:** v1.3.0"`, `"v1.3.0 released"`, `"## What's new in v1.3.0"`.
5. `CHANGELOG.md` contains `"## v1.3.0"` heading + a date marker.
6. `CHANGELOG.md` v1.3.0 entry references all 10 v1.3 builds (Workspace Shell / Project Pulse / Product Concept / Renderings / Variant Command Cards / Structured Variant Specs / Timeline Command Center / Command Actions / Project Blockers / Timeline History / Planning Sandbox Design).
7. `CHANGELOG.md` v1.3.0 entry mentions the project-delete FK fix (cross-cutting bug shipped between Builds 08 and 09).
8. `MASTERPLAN.md` contains `"### v1.3.0 — "` heading marking the series shipped.
9. `VERSION.md` still preserves the v1.2.1 release proof (`"v1.2.1 released"`) — backward-compat invariant.

### Test inventory
10. All v1.3 test files exist: `test_v13_build01.py` through `test_v13_build09.py`.
11. `test_v13_build10.py` (this file) exists.
12. `test_build_v121.py` exists (release-baseline carried forward).
13. `test_delete_project_ai_intake_regression.py` exists (Build 09-adjacent cross-cutting fix).

### i18n parity locked
14. en.json == zh.json key set.
15. Key count >= 714 (no regression below v1.3 final lock).

### Migration count locked
16. `MIGRATIONS` is 6 entries (additions 005 + 006 from v1.3).

### Change Log viewer leak fix
17. `project_detail.html` template contains the new journal-mirror filter (`"Journal entry added:"` + `can_view_journal` check).
18. End-to-end: GET as viewer on a project with a journal entry → the resulting page's Change Log section does NOT contain the journal entry text.

### Cross-cutting behavior locks (cheap, module-level)
19. `app/database.py` has the FK enforcement event listener (`PRAGMA foreign_keys = ON` for SQLite connections).
20. `crud.delete_project` explicitly handles `ai_conversations` + `project_creation_tokens` cleanup (regression guard against the AI-intake delete bug fixed at `b8a9687`).
21. `crud.get_timeline_events` exists (Build 08 helper).
22. `crud.get_active_blockers_for_project` exists (Build 07B helper).
23. `crud.get_active_phase_blocker_ids` exists (Build 07B helper).
24. `ProjectBlocker` model importable (Build 07B model).
25. `Project.blockers` relationship resolves (Build 07B back-populates).

### Regression baseline (subprocess)
26. Subprocess invocation of `test_build_v121.py` exits 0.
27. Subprocess invocation of each `test_v13_buildNN.py` (01–09) exits 0. Aggregates pass/fail per child.
28. Subprocess invocation of `test_delete_project_ai_intake_regression.py` exits 0.

### Acceptance
29. Build 10 acceptance criteria documented in the v1.3.0 CHANGELOG entry.
30. Build 10's `V13_BUILD10_EXECUTION_PLAN.md` file exists (regression guard against accidental deletion during future cleanup).

## Verification

After implementing the changes above, automated:

```bash
# 1. Build 10 release proof
python3 test_v13_build10.py
# Expect: PASSED: 30 / 30

# 2. v1.2.1 baseline survives (assertion-relaxation must not break it)
python3 test_build_v121.py
# Expect: PASSED: 19 / FAILED: 0 (or similar, depending on how the
#         relaxed assertion is structured; main contract: still green)

# 3. Full v1.3 sweep
for t in test_v13_build*.py; do
  python3 "$t" 2>&1 | grep -E "^PASSED:|^FAILED:"
done

# 4. Delete-fix regression
python3 test_delete_project_ai_intake_regression.py

# 5. AI e2e for completeness
python3 test_ai_e2e.py
# Expect: 15P / 2S / 0F (SKIPs are OPENAI key issues, not regressions)
```

Manual verification:
- Log into local dev app as viewer; open a project that has at least one journal entry. Confirm the Change Log section at the bottom of the project page does NOT show "Journal entry added: '{entry text}'" — only field updates, file uploads, phase updates, etc.
- Log in as admin or PM on the same project — Change Log still shows everything including the journal-added audit row (admin/PM `can_view_journal` is True).
- Navigate to home page; confirm version badge (if present) reads "v1.3.0".

## Risk / rollback

| Risk | Likelihood | Mitigation |
|---|---|---|
| Version bump breaks test_build_v121 strict version check | High (known) | Relax that assertion in this build (planned in §Scope). Test stays green. |
| Change Log viewer-leak fix accidentally hides admin/PM audit rows | Very low | Fix gates strictly on `not can_view_journal`. Admin/PM `can_view_journal` is True → no rows hidden from them. |
| MASTERPLAN.md formatting drift breaks search-based assertions in older test files | Low | Add the new "### v1.3.0 — " section AFTER existing v1.2.x sections; don't restructure existing content. |
| CHANGELOG rollup loses content from per-build entries | Medium | Rollup is mechanical: every `## Unreleased`-block bullet copies verbatim under `## v1.3.0`. No editorial rewriting. |
| Subprocess invocation in test_v13_build10 hangs or times out | Low | Each subprocess gets a 60 s timeout. Failures roll up as `subprocess_NN_failed` test rows. |

Rollback: every change in this build is reversible by a single Edit. Version constants, doc rollup, template patch, test file — all atomic. No DB state involved.

## What I am NOT doing in this build

- USER_GUIDE.md v1.3.0 Chinese summary block (carried forward; needs native review).
- Re-organizing the existing CHANGELOG structure beyond moving Unreleased → v1.3.0.
- Touching any v1.3 app code other than the Change Log template patch.
- Bumping migration count.
- Adding any AI tools, i18n keys, schema, or routes.
- Updating Codex's `V14_PLANNING_SANDBOX_IMPLEMENTATION_PLAN.md` to reflect Build 09 amendments — Codex's plan stands as their independent reference.
- Anything that would re-trigger plan-mode (no design decisions; this is execution-only).

## Open questions

None remaining. Version-string format follows the v1.2.1 precedent verbatim.
