# CURRENT_TASK.md

## Task
Build 30C — PM draft delete. Complete. **Awaiting user authorization to commit + push.**

After this lands, the natural next move is **v1.2.1 release-hardening** to roll up all 7 unreleased patches.

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth.

## What changed in Build 30C

### Backend
- New `can_delete_project(user, project)` helper in `app/dependencies.py`:
  - Admin: always True (preserves pre-30C behavior).
  - PM: True if (a) project's `product_manager` matches their username OR display_name (via `can_edit_project`), AND (b) every phase is `status='not_started'` with `actual_start_date is None`. "Until first phase advance" workflow-tied policy.
  - Viewer: always False.
  - None user: False (defense in depth).
- `POST /projects/{id}/delete` in `app/routes/projects.py`: permission expanded from `require_admin` to `can_delete_project`. Returns 403 with a clear "use Archive instead" message when refused, rather than the previous silent redirect.

### Frontend
- `app/templates/project_detail.html`: Delete button visibility changed from `current_user.role == 'admin'` to `can_delete` (new context var). PM sees a helpful tooltip explaining the draft-state condition.
- `app/routes/projects.py:project_detail` exposes `can_delete = can_delete_project(current_user, project)` in template context.

### Tests
- New `test_build30c.py` — **23/23 PASS**. Six role × draft-state combinations:
  - admin + fresh draft → can delete ✓
  - admin + advanced project → can delete ✓
  - PM + own fresh draft → can delete ✓
  - PM + own advanced project → CANNOT delete (403) ✓
  - PM + another PM's project → CANNOT delete (403) ✓
  - Viewer + any → CANNOT delete (403) ✓
  - Helper unit tests against fresh + advanced fixtures
- HTTP-level + template-render + DB-persistence assertions.

### Docs
- `CHANGELOG.md` — Build 30C entry added to `## Unreleased` (top of patch list).
- `MASTERPLAN.md` — Build 30C detail section above 30B.

No schema change. No new dependencies.

## Pre-existing assumption verified
- The Design phase does NOT auto-start on project creation. Checked 5 recent projects: all have `advanced_phases=0`, `started_phases=0`. The "Stage: Design" label is `project.current_stage` (a cached string showing the first not-started phase's NAME) — not an indication the phase has started.

## Verification at this point

- `python3 test_build30c.py` — **23/23**.
- `python3 test_build30b.py` — 19/19 (unchanged).
- `python3 test_build30.py` — 23/23 (unchanged).
- `python3 test_build29.py` — 26/26 (unchanged).
- `python3 test_ai_e2e.py` — 15P/2S/0F (unchanged).
- Manual smoke: log in as PM, create a fresh project (no phases advanced) → Delete button visible → click → project gone. Repeat with a phase manually set to in_progress → no Delete button.

## v1.2 patch series (queued for v1.2.1 release-hardening)

Now 7 patches on `## Unreleased` against `v1.2.0`:
1. IME composer fix v2 (`7d56198`)
2. Nixpacks Python-only (`2bd82bf`)
3. Price strings (`1465265`)
4. Layout refactor (`36a787e`)
5. Build 30A — project creation safety (`cab8884`)
6. Build 30B — Excel batch intake (`1d811b9`)
7. Build 30C — PM draft delete (this commit, pending)

## Next step

Awaiting commit/push authorization. After that: **v1.2.1 release-hardening** (per user direction: "After [30C] we can do release hardening all together"). That build will:
- Bump `app/version.py` from `1.2.0` → `1.2.1`.
- Write `test_build_v121.py` mirroring `test_build29.py`'s release-proof pattern.
- Update VERSION.md / CHANGELOG.md / MASTERPLAN.md / USER_GUIDE.md with the rollup release notes.
- Full regression sweep across all v1.0+ builds.
- Loosen any strict version assertions in the post-30 test files for the bump.
