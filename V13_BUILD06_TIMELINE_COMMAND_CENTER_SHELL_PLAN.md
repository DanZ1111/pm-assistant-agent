# v1.3 Build 06 - Timeline Command Center Shell

## Summary

Replace Timeline's first impression with an execution command center shell. It should create deadline pressure and orient the PM before showing the old detailed table.

This build is mostly display. No behavior change unless existing backend support is already honest and tested.

## Backend Honesty Mapping

Before implementation, fill this table in the PR/build notes:

| Visible field | Source of truth | Write path | Derived-state rule | Permission rule | Test coverage |
|---|---|---|---|---|---|
| Phase strip | project phases | existing phase routes | status/order/current phase | all authenticated can view | build test |
| Current phase | derived from phases | finish/edit phase routes | first in-progress or first unfinished | all authenticated can view | build test |
| Next action | derived/placeholder | none | explicit placeholder unless sourced | all authenticated can view | build test |
| Owner | phase.owner/project PM | edit phase/project | direct field or fallback | all authenticated can view owner text | build test |
| Due date | current phase planned_end | edit phase | overdue if before today and not done/skipped | all authenticated can view | build test |
| Blocker | placeholder until modeled | none | explicit placeholder | all authenticated can view placeholder | build test |
| AI nudge | placeholder until modeled | none | explicit placeholder | PM/admin only if action-oriented | build test |

## Implementation Changes

- Timeline tab first section becomes `Timeline Command Center`.
- Add phase strip at the top.
- Show current phase, owner, due date, days left/overdue, and status using existing data.
- Show next action, blocker, and AI nudge only as honest placeholders unless a reliable source already exists.
- Add action buttons as placeholders or links only:
  - Finish Current Phase
  - Add Update
  - Add Blocker
  - Adjust Due Date
  - AI Intake
- Keep old planned/actual table behind an expandable `Detailed Table`.
- No new schema.

## Explicit Deferrals

- No new blocker write flow.
- No AI-generated nudge.
- No action backend wiring except existing safe routes if mapped.
- No timeline history redesign yet.

## Tests

- Add `test_v13_build06.py`.
- Verify command center appears before detailed table.
- Verify phase strip marks done/current/next/later states.
- Verify overdue/current phase display matches existing delay rules.
- Verify placeholders are explicitly labeled, not fake data.
- Verify detailed table can expand and still contains existing phase actions.
- Verify `#timeline` opens Timeline tab and command center.
- Run `python3 test_build_v121.py`.

## Acceptance Criteria

- Timeline feels like an execution workspace on first view.
- No UI field implies backend intelligence that does not exist.
