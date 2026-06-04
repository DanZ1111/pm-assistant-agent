# v1.3 Build 02 - Overview Project Pulse v1 (Rules-Based)

## Summary

Add Project Pulse as the first Overview section. It should answer: what is happening now, what needs attention, and what should the PM do next?

This build is Project Pulse v1: a rules-based display layer using existing project state. It is not the final intelligent PM pulse. No new writes.

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
- No conversation-history nudge.
- No time-since-last-update drift detection.
- No velocity comparison against typical phase duration or peer projects.
- No blocker model.
- No command buttons beyond links to existing sections.

## Future Pulse Intelligence

Future builds may make Project Pulse smarter after honest sources and tests exist:

- Project drift detection from time since last update.
- Velocity vs typical phase duration, such as "Design has taken 30 days; similar projects cleared it in 14."
- AI-suggested nudge from assistant conversation history and confirmed project changes.
- Active blocker state if Build 07 approves a first-class blocker source of truth.

## Tests

- Add `test_v13_build02.py`.
- Verify Project Pulse appears before Product Thesis.
- Verify delayed project shows delay action.
- Verify missing-critical project shows missing-field action.
- Verify healthy project shows no urgent action.
- Verify viewer does not see sensitive factory/cost details.
- Verify the section is labeled or documented as rules-based v1 behavior, not final AI intelligence.
- Run `python3 test_build_v121.py`.

## Acceptance Criteria

- PM can open Overview and understand immediate project health before reading details.
- No new database state is introduced.

## Implementation Notes

- Implemented `#project-pulse` as the first Overview section in `project_detail.html`, before Product Thesis.
- Uses existing context only: `project`, `health`, `delay`, `current_phase`, `linked_ideas`, and role visibility flags.
- Action priority is delay, missing Thesis, first remaining critical missing field, early-stage missing inspiration, then no urgent action.
- Sensitive engineer/factory details render only when `can_sensitive` is true; project-level costs are not shown in Pulse.
- Added EN/ZH i18n keys under `pulse.*` and `common.unknown`.
- No schema, route, service, AI tool, or mutating behavior changes.

## Verification

- `env BASE_URL=http://localhost:8001 python3 test_v13_build02.py` — 11/11 passed.
- `env BASE_URL=http://localhost:8001 python3 test_v13_build01.py` — 16/16 passed.
- `python3 test_build_v121.py` — 19/19 passed.
