# v1.5 Build 08 Plan — Design Status In Timeline/Pulse

## Status

Implementation plan for v1.5 Build 08 after Build 07 Select Final & Promote
Rendering is committed.

Parent plan:

- `V15_MASTERPLAN.md`

Canonical PRD:

- `V15_DESIGNER_PORTAL_PRD.md`

## Purpose

Surface design quest progress in Project Pulse and Timeline Command Center, and
let a PM/admin explicitly mark design complete after a final rendering is
selected.

Build 08 does not automatically finish phases or mutate Timeline phase status.

## Scope

In:

1. Add explicit design-complete metadata to design quests.
2. Add a service helper that derives design status for project display.
3. Add a service helper to mark design complete.
4. Show design status in Project Pulse.
5. Show design status in Timeline Command Center.
6. Add a PM/admin `Mark Design Complete` action only after a final rendering is
   selected.
7. Add audit event for design completion.
8. Add exact EN/ZH i18n parity and Build 08 regression coverage.

Out:

- no automatic phase completion,
- no direct mutation of `project_phases`,
- no Planning Sandbox integration,
- no AI write handlers,
- no designer-facing completion controls,
- no new designer-manager operations.

## Feature Design Review

1. Real problem: PMs need design work state visible in execution views without
   manually remembering whether design is blocking progress.
2. Repeated: every project with a design quest needs the same status summary.
3. Structured data: yes, explicit completion metadata must be auditable and
   separate from phase state.
4. Notes fallback: no, notes cannot safely drive Pulse/Timeline status.
5. Intake burden: PM clicks one explicit completion button after final
   selection.
6. AI role: none in this build.
7. Display payoff: Pulse and Timeline show whether design is waiting,
   reviewing, revising, selected, or complete.
8. Migration impact: additive nullable completion columns only.
9. Minimal schema: completion fields on `design_quests`; display status is
   derived.
10. Minimal UI change: one Pulse card line, one Timeline status tile, one
   explicit completion form.
11. Deferred: phase automation, AI handlers, manager operations, release docs.

## Architecture Review

1. Problem solved: design completion becomes explicit workflow state visible in
   execution surfaces.
2. Tables/services affected: `design_quests`, `design_quest_events`, and
   `project_changes`.
3. Real column vs notes: real columns are required for durable completion
   provenance.
4. Service layer: marking complete must live in `crud.py`.
5. Change log: write a design quest event and project change entry; do not
   write phase changes.
6. Rollback: remove Build 08 route/UI and nullable completion columns; selected
   renderings remain intact.

## Backend Honesty Mapping

| Visible Field / Action | Source Of Truth | Write Path | Derived Rule | Permission Rule | Test |
|---|---|---|---|---|---|
| Design status | `design_quests`, submissions, revisions, selected fields | read-only `get_project_design_status` | status label derived from quest workflow | project viewer/editor can see PM page | Build 08 display test |
| Mark Design Complete | `design_quests.design_completed_at/by` | `mark_design_quest_complete` | allowed only after selected version/rendering exists | PM/admin project editor | Build 08 complete test |
| Timeline phase state | `project_phases` | none in Build 08 | unchanged by design completion | no write | Build 08 no-phase-mutation test |
| Pulse action | derived status | route/form calls service | shows completion action only when selected and incomplete | PM/admin project editor | Build 08 UI test |

## Data Model Plan

Add nullable columns to `design_quests`:

- `design_completed_at`
- `design_completed_by_user_id`

Do not add a stored project or phase status. Design status is derived for
display from quest status, selected fields, open revision requests, submissions,
and completion fields.

## Migration Plan

Add migration:

- `015_v1_5_design_status_timeline_pulse`

Indexes:

- `ix_design_quests_completed_at`

## Service Plan

Add to `app/crud.py`:

- `get_project_design_status(db, project_id)`
- `mark_design_quest_complete(db, quest_id, user_id)`

Derived display states:

- `none`: no active design quest.
- `draft`: quest exists but is not published.
- `waiting_for_submissions`: published quest has no submissions.
- `pm_review_needed`: submissions exist and no final is selected.
- `revision_requested`: open revision request exists.
- `final_selected`: selected version exists but completion is not marked.
- `design_complete`: completion metadata exists.
- `closed`: quest is closed/cancelled without completion.

Completion behavior:

1. validate PM/admin project editor,
2. validate selected submission/version and promoted rendering exist,
3. set `design_completed_at/by`,
4. keep `project_phases` unchanged,
5. write `DesignQuestEvent(event_type='design_completed')`,
6. write `ProjectChange(change_type='event_note', source_type='design_quest')`.

## Route Plan

Update `app/routes/projects.py`:

- `POST /projects/{project_id}/design-quest/{quest_id}/mark-complete`

The route redirects to `#timeline-command-center` and reports errors via the
existing `design_quest_error` query parameter.

## Template Plan

Update `app/templates/project_detail.html`:

- Project Pulse shows design status and links to Renderings & Design.
- Timeline Command Center shows a design-status support tile.
- Mark Design Complete button appears only when status is `final_selected` and
  `can_edit` is true.

## i18n Plan

Add exact EN/ZH parity for Build 08 labels under `design_quest.*`, `pulse.*`,
and `timeline.*`.

Expected new keys: 12-18. Lock exact count in `test_v15_build08.py`.

## Testing Plan

Create:

- `test_v15_build08.py`

Required assertions:

1. Plan locks display/explicit-complete scope and excludes phase automation and
   AI handlers.
2. Fresh DB has design-complete metadata and index.
3. Project design status derives waiting/review/revision/selected/complete.
4. Mark Design Complete is rejected before final selection.
5. PM/admin can mark selected design complete.
6. Marking complete writes audit records.
7. Marking complete does not change project phase status or actual dates.
8. Regular designer cannot mark complete.
9. Project Pulse and Timeline render design status.
10. i18n parity is exact.
