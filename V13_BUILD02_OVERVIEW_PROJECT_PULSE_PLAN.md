# v1.3 Build 02 - Overview Project Pulse

## Summary

Add Project Pulse as the first Overview section. It should answer: what is happening now, what needs attention, and what should the PM do next?

This build is derived display only. No new writes.

## Implementation Changes

- Add `Project Pulse` as the first section inside Overview.
- Use existing derived/project data only:
  - current stage
  - health / missing critical fields
  - active delay if present
  - PM / owner
  - engineer / factory for PM/admin
  - planned or estimated launch date
  - suggested next PM action from current missing/delay state
- Keep Product Thesis immediately after Project Pulse.
- Use a two-column desktop layout:
  - left: current status
  - right: attention needed / suggested action
- On mobile, stack pulse blocks.
- No schema changes.
- No new mutating routes.

## Suggested Next Action Rules

- If delayed: suggest opening Timeline and resolving the overdue phase.
- If missing critical fields: suggest filling the highest-priority missing field.
- If thesis is missing/too short: suggest completing Product Thesis.
- If no linked ideas: suggest adding inspiration only if the project is still early-stage.
- If no obvious issue: show "No urgent action from existing project data."

## Explicit Deferrals

- No AI-generated nudge yet.
- No blocker model.
- No command buttons beyond links to existing sections.

## Tests

- Add `test_v13_build02.py`.
- Verify Project Pulse appears before Product Thesis.
- Verify delayed project shows delay action.
- Verify missing-critical project shows missing-field action.
- Verify healthy project shows no urgent action.
- Verify viewer does not see sensitive factory/cost details.
- Run `python3 test_build_v121.py`.

## Acceptance Criteria

- PM can open Overview and understand immediate project health before reading details.
- No new database state is introduced.
