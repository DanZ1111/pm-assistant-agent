# v1.3 Build 07 - Timeline Command Actions Backend

## Summary

Wire real Timeline Command Center actions only after mapping each action to source of truth, service writes, derived-state refresh, permission rule, audit/history, and tests.

This is the highest-risk build in v1.3.

## Required Action Mapping

Before implementation, complete this table in the build notes:

| UI action | Route/service | DB write | Derived state refresh | History/audit entry | Test |
|---|---|---|---|---|---|
| Finish Current Phase | existing/new service | phase status + actual end | current_stage recalculated | change log/phase update | required |
| Add Update | journal or timeline event | journal/change/event | command/history refresh | journal/change log | required |
| Add Blocker | journal or new event | TBD after architecture review | pulse/timeline blocker display | required | required |
| Adjust Due Date | phase edit/plan change service | planned date + reason | delay recalculated | phase_plan_changes | required |
| AI Intake | existing assistant confirmation | confirmed tool proposal | target section refresh | AI/change log | required |

If a row cannot be completed honestly, that action remains placeholder.

## Architecture Review Trigger

If Add Blocker or Add Update cannot be represented cleanly with existing Project Journal, phase notes, phase plan changes, or change log, write a schema Architecture Review before adding any new table/column.

## Implementation Changes

- Wire Finish Current Phase from Command Center.
- Wire Adjust Due Date only through a reason-required flow.
- Wire Add Update to a confirmed/auditable record.
- Wire Add Blocker only if source-of-truth mapping is approved.
- Keep AI Intake confirmation-gated; no silent mutation.
- Ensure every action updates derived display after redirect.

## Explicit Deferrals

- No planning sandbox.
- No auto-generated AI nudge writes.
- No hidden phase mutation without user confirmation.

## Tests

- Add `test_v13_build07.py`.
- Verify Finish Current Phase updates phase status, actual end, current stage, phase strip, and history/audit.
- Verify Adjust Due Date requires reason and recalculates overdue state.
- Verify Add Update creates an auditable record and appears in appropriate history.
- Verify Add Blocker affects display only if its source-of-truth mapping is implemented.
- Verify PM can act only on editable projects.
- Verify viewer cannot mutate.
- Verify AI path still requires confirmation before writes.
- Run `python3 test_build_v121.py`.

## Acceptance Criteria

- Timeline actions move real backend state, refresh derived state, and leave audit/history behind.
- No action is wired by merely changing frontend text.
