# CURRENT_TASK.md

## Task
Post-v1.2.0 project detail layout cleanup — remove the low-value left sidebar.

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder.

## Current state

The project detail sidebar refactor has been prepared as a git checkpoint.
Pre-refactor rollback anchor: `146526527b82b5ef138bf1e8395d5066d26a2cae`.

Implemented:
- Removed the rendered `.detail-sidebar` from `app/templates/project_detail.html`.
- Removed the top-level project Edit link from the header; Archive/Delete remain as whole-project actions.
- Moved Product Manager, Engineer, Factory, Owner, Stage, Planned Launch, and delayed launch into a compact header facts grid under the project title.
- Moved Target Factory Cost / Target MSRP into a full-width `Commercial Snapshot` section near the top of the detail content.
- Kept created/updated timestamps in the Commercial Snapshot for now; they are no longer in a persistent rail.
- Removed dead sidebar CSS and updated responsive rules for the full-width layout.
- Added `section.commercial_snapshot` to both English and Chinese i18n bundles.
- Updated old sidebar expectations in `test_build1.py` and `test_build2.py`.
- Added a static layout contract to `test_build29.py`.

## Verification So Far

- `python3 -m compileall -q app` — PASS.
- `python3 -m json.tool app/i18n/en.json` — PASS.
- `python3 -m json.tool app/i18n/zh.json` — PASS.
- `python3 test_build29.py` — 26/26 PASS.
- Focused desktop Playwright smoke on `/projects/<latest>` — PASS; screenshot: `/private/tmp/project_detail_layout_smoke.png`.
- Focused mobile Playwright smoke on `/projects/<latest>` — PASS; screenshot: `/private/tmp/project_detail_layout_mobile_smoke.png`.

## Known Notes

- `test_build1.py` was attempted but its first anonymous-root assertion is stale for the current auth-gated app, so it timed out before reaching the project detail assertions. The updated assertions were not reached in that legacy suite.
- The existing fixed assistant dock still overlays the lower edge of the viewport on mobile. That predates this sidebar cleanup and should be handled in the assistant workspace/layout build rather than mixed into this narrow refactor.

## Remaining

- If the user asks to undo this layout, revert the layout checkpoint commit or reset back to the pre-refactor anchor above after confirming destructive reset intent.
- The assistant dock mobile overlay remains a separate future layout task.
