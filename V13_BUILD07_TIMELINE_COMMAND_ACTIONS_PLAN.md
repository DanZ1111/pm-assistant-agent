# v1.3 Build 07 - Timeline Command Actions Backend

## Summary

Wire real Timeline Command Center actions only after mapping each action to source of truth, service writes, derived-state refresh, permission rule, audit/history, and tests.

This is the highest-risk build in v1.3.

## Pre-Build Blocker Decision Gate

Before implementation begins, write an Architecture Review for Add Blocker and choose the source of truth:

| Option | Choose if | Do not choose if |
|---|---|---|
| `project_blockers` table | Blockers need active/resolved state, owner, due date, severity, cross-phase aggregation, Project Pulse impact, or Timeline Command Center pressure. | Build 07 cannot absorb schema/service/test scope. |
| `ProjectJournalEntry.entry_type = "blocker"` | Blockers are only narrative updates and do not need active state or resolution tracking. | PMs expect blockers to drive health, next action, overdue pressure, or filters. |

Default planning assumption: Add Blocker probably needs a first-class `project_blockers` model if it is meant to behave like command-center state instead of a note.

If this decision is not complete, Build 07 must leave Add Blocker as a placeholder.

## Required Action Mapping

Before implementation, complete this table in the build notes:

| UI action | Route/service | DB write | Derived state refresh | History/audit entry | Test |
|---|---|---|---|---|---|
| Finish Current Phase | existing/new service | phase status + actual end | current_stage recalculated | change log/phase update | required |
| Add Update | journal or timeline event | journal/change/event | command/history refresh | journal/change log | required |
| Add Blocker | blocked until Architecture Review chooses model | `project_blockers` or journal blocker type | pulse/timeline blocker display if implemented | required if implemented | required if implemented |
| Adjust Due Date | phase edit/plan change service | planned date + reason | delay recalculated | phase_plan_changes | required |
| AI Intake | existing assistant confirmation | confirmed tool proposal | target section refresh | AI/change log | required |

If a row cannot be completed honestly, that action remains placeholder.

## Architecture Review Trigger

Add Blocker always requires the pre-build Architecture Review above. Add Update also requires review if it cannot be represented cleanly with existing Project Journal, phase notes, phase plan changes, or change log.

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
