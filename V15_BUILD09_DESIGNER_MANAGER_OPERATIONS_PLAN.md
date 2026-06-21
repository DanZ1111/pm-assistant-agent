# v1.5 Build 09 Plan — Designer Manager Operations

## Status

Implementation plan for v1.5 Build 09 after Build 08 Design Status in
Timeline/Pulse is committed.

Parent plan:

- `V15_MASTERPLAN.md`

Canonical PRD:

- `V15_DESIGNER_PORTAL_PRD.md`

## Purpose

Give `designer_manager` users narrow Designer Portal operations controls
without turning them into PM/admin project users.

Build 09 does not expose PM Workspace project pages, cost, factory, timeline
editing, project journal, or AI write controls to designer managers.

## Scope

In:

1. Add a Designer Manager operations dashboard under `/designer/manager`.
2. Show designer accounts and safe designer-facing quest information.
3. Allow designer managers to assign designers to active assigned-only design
   quests.
4. Allow designer managers to reopen a mistakenly rejected submission back to
   PM review.
5. Audit every manager operation through design quest events.
6. Add exact EN/ZH i18n parity and Build 09 regression coverage.

Out:

- no PM Workspace access,
- no project cost/factory/supplier/journal exposure,
- no project phase mutation,
- no design-complete controls,
- no AI write handlers,
- no admin invite PIN/user deletion controls,
- no rewards, ranking, or design library.

## Feature Design Review

1. Real problem: portal operators need to help designers access briefs and
   recover obvious portal mistakes without PM/admin access.
2. Repeated: assignment support and rejected-submission recovery are common
   operational tasks.
3. Structured data: yes, assignments and reopen events must remain auditable.
4. Notes fallback: no, notes do not grant quest access or restore workflow
   state.
5. Intake burden: manager chooses a designer from a select and submits one
   action.
6. AI role: none in this build.
7. Display payoff: managers can operate the portal from a safe dashboard.
8. Migration impact: no schema change expected.
9. Minimal schema: reuse `design_quest_assignments`, `design_submissions`, and
   `design_quest_events`.
10. Minimal UI change: one manager-only section in Designer Portal.
11. Deferred: account activation model, invite generation, rewards, library,
   PM-side controls.

## Architecture Review

1. Problem solved: designer-manager can perform narrow portal operations.
2. Tables/services affected: `users`, `design_quests`,
   `design_quest_assignments`, `design_submissions`, `design_quest_events`.
3. Real column vs notes: no new columns are needed for assignment/reopen.
4. Service layer: manager operations must live in `crud.py`.
5. Change log: design quest event is required for assignment and reopen.
6. Rollback: remove manager routes/template/service helpers; existing
   assignments/submissions remain valid.

## Backend Honesty Mapping

| Visible Field / Action | Source Of Truth | Write Path | Derived Rule | Permission Rule | Test |
|---|---|---|---|---|---|
| Manager dashboard | safe shaped quest/user data | read-only helper | excludes PM-only project fields | `designer_manager` only | Build 09 dashboard test |
| Assign designer | `design_quest_assignments` | `manager_assign_designer_to_quest` | active assignment is created/reactivated | `designer_manager` only | Build 09 assign test |
| Reopen rejected submission | `design_submissions.status` | `manager_reopen_design_submission` | rejected -> submitted; quest -> reviewing if needed | `designer_manager` only | Build 09 reopen test |
| Audit | `design_quest_events` | same services | manager operation event per write | service enforced | Build 09 audit test |

## Service Plan

Add to `app/crud.py`:

- `list_designer_manager_operations(db, manager_user_id)`
- `manager_assign_designer_to_quest(db, quest_id, designer_user_id, manager_user_id)`
- `manager_reopen_design_submission(db, submission_id, manager_user_id)`

Rules:

1. Only `designer_manager` users can call these services.
2. Assignment is allowed only for active, assigned-only quests.
3. Assignment targets must be regular `designer` users.
4. Reopen is allowed only for rejected submissions.
5. Reopen does not select final, mark complete, or mutate phases.
6. Every write records a `DesignQuestEvent`.

## Route Plan

Update `app/routes/designer.py`:

- `GET /designer/manager`
- `POST /designer/manager/quests/{quest_id}/assign`
- `POST /designer/manager/submissions/{submission_id}/reopen`

All routes remain under Designer Portal chrome.

## Template Plan

Create:

- `app/templates/designer/manager.html`

Update:

- `app/templates/designer/dashboard.html`

Dashboard shows a manager-only link to operations. The operations page shows:

- designer roster,
- active assigned-only quests with assignment forms,
- rejected submissions with reopen forms.

## i18n Plan

Add exact EN/ZH parity under `designer.manager.*`.

Expected new keys: 12-18. Lock exact count in `test_v15_build09.py`.

## Testing Plan

Create:

- `test_v15_build09.py`

Required assertions:

1. Plan locks designer-manager operations scope and excludes PM/admin/AI scope.
2. Designer manager can open `/designer/manager`; regular designer cannot.
3. Manager dashboard exposes safe portal data and no PM-only fields/routes.
4. Manager can assign a designer to an assigned-only active quest.
5. Assigned designer can then see the quest.
6. Manager can reopen a rejected submission back to PM review.
7. Reopen writes a design quest event and does not mutate phases.
8. Manager can create and publish quests from `/designer/manager` while still
   being unable to access `/projects/:id`.
9. i18n parity is exact.
