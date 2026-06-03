# v1.3 Build 08 - Timeline History

## Summary

Create a Timeline Updates / History section that explains what happened and why, using existing records first.

Prefer derived aggregation over a new event table unless existing records cannot support the required history.

## Implementation Changes

- Add `Timeline Updates / History` below Timeline Map/Detailed Table.
- Aggregate from existing sources:
  - project change log
  - phase plan changes
  - journal entries
  - file uploads
  - rendering/prototype photo uploads/comments
  - AI intake/change events
- Normalize display into event types:
  - Phase Change
  - Decision
  - Delay
  - Blocker
  - File Uploaded
  - Rendering Update
  - Cost Update
  - Sample Update
  - Packaging Update
  - AI Intake
  - Manual Note
- Add filters:
  - All
  - Delays
  - Decisions
  - Blockers
  - Phase Changes
  - Files/Renderings
- Keep original source records intact and link/anchor back where practical.

## Explicit Deferrals

- No new event table unless aggregation fails architecture review.
- No semantic AI classification of all old entries.
- No timeline template/sandbox.

## Tests

- Add `test_v13_build08.py`.
- Verify phase plan change appears as a timeline history event.
- Verify journal decision/risk entries appear under appropriate filter.
- Verify file/rendering upload appears under Files/Renderings.
- Verify AI intake change appears as AI Intake or Manual Note depending source.
- Verify viewer does not see sensitive cost/factory details.
- Verify filters hide/show expected event classes.
- Run `python3 test_build_v121.py`.

## Acceptance Criteria

- PM can review why the timeline changed without reading raw database rows.
- History remains derived and auditable from existing source records.
