# v1.5 Build 07 Plan — Select Final & Promote Rendering

## Status

Implementation plan for v1.5 Build 07 after Build 06 Revision Loop is
committed.

Parent plan:

- `V15_MASTERPLAN.md`

Canonical PRD:

- `V15_DESIGNER_PORTAL_PRD.md`

## Purpose

Allow a PM/admin project editor to select one designer submission version as the
final design and promote that version into the existing project rendering
surface with explicit source metadata.

Build 07 does not mark design complete and does not affect Timeline/Pulse.

## Scope

In:

1. Extend existing `project_files` rendering storage with source metadata for
   designer-portal promotions.
2. Add selected submission/version/user/date fields to design submissions and
   quests where needed for PM display and audit.
3. Add service helper to select a final submission version and create a
   `ProjectFile` rendering row from the immutable submission version.
4. Add PM/admin confirmation form in incoming submission cards.
5. Show the selected/final rendering source in `Renderings & Design`.
6. Add guarded validation so only project editors can promote a version that
   belongs to the project quest/submission.
7. Add audit events for submission selected and rendering promoted.
8. Add exact EN/ZH i18n parity and Build 07 regression coverage.

Out:

- no `Mark Design Complete`,
- no Timeline/Pulse display,
- no automatic phase completion,
- no AI write handlers,
- no designer-facing final selection controls,
- no image annotation,
- no rendering replacement UI beyond selecting a newer promoted submission.

## Feature Design Review

1. Real problem: PMs need the chosen designer result to become the project
   rendering without manual file copying or lost provenance.
2. Repeated: every design quest should end in one selected visual or document.
3. Structured data: yes, final selection and source version metadata must be
   queryable and auditable.
4. Notes fallback: no, notes cannot reliably drive selected/final rendering
   display or prove which submission version was promoted.
5. Intake burden: PM clicks one confirmation action from the existing
   submission card.
6. AI role: none in this build.
7. Display payoff: PM sees the selected rendering in the existing project
   rendering context with source designer/version metadata.
8. Migration impact: additive nullable columns only.
9. Minimal schema: extend current workflow tables and `project_files` rather
   than creating a parallel rendering table.
10. Minimal UI change: one select-final action plus one selected-source summary.
11. Deferred: design-complete, Timeline/Pulse, AI, annotations, design library.

## Architecture Review

1. Problem solved: final designer selection can become a project rendering with
   source provenance.
2. Tables/services affected: `design_quests`, `design_submissions`,
   `design_submission_versions`, `project_files`, `design_quest_events`, and
   `project_changes`.
3. Real column vs notes: real columns are required because selected rendering
   source metadata drives UI and audit behavior.
4. Service layer: selection and promotion write path must live in `crud.py`.
5. Change log: create `DesignQuestEvent` entries and a `ProjectChange`
   file/promote audit row.
6. Rollback: remove Build 07 routes/UI and nullable metadata columns; promoted
   rendering files remain ordinary `project_files` rows.

## Backend Honesty Mapping

| Visible Field / Action | Source Of Truth | Write Path | Derived Rule | Permission Rule | Test |
|---|---|---|---|---|---|
| Select final | `design_submissions.status`, `selected_version_id` | `select_final_design_submission_version` | selected submission becomes `selected`; sibling selected submissions are cleared | PM/admin project editor | Build 07 select test |
| Quest selected state | `design_quests.status` | same service | quest becomes `selected`; not complete | PM/admin project editor | Build 07 quest state test |
| Promoted rendering | `project_files.file_category='rendering'` | same service | rendering row copies immutable version file metadata | PM/admin project editor | Build 07 rendering test |
| Source metadata | `project_files.source_type/source_id/source_metadata` | same service | metadata points to submission/version/designer/selector | PM/admin project editor | Build 07 source test |
| Designer controls | none | none | designers cannot select/promote | no designer project access | Build 07 permission test |

## Data Model Plan

Add nullable columns to `design_quests`:

- `selected_submission_id`
- `selected_version_id`
- `selected_by_user_id`
- `selected_at`
- `promoted_project_file_id`

Add nullable columns to `design_submissions`:

- `selected_version_id`
- `selected_by_user_id`
- `selected_at`

Add nullable columns to `project_files`:

- `source_type`
- `source_id`
- `source_metadata`

For Build 07, promoted designer submissions use:

- `ProjectFile.file_category = "rendering"`
- `ProjectFile.source_type = "design_submission_version"`
- `ProjectFile.source_id = DesignSubmissionVersion.id`
- `ProjectFile.source_metadata` JSON including quest, submission, version,
  designer, selector, and selected timestamp.

## Migration Plan

Add migration:

- `014_v1_5_select_final_promote_rendering`

Indexes:

- `ix_project_files_source`
- `ix_design_quests_selected_version`
- `ix_design_submissions_selected_version`

## Service Plan

Add to `app/crud.py`:

- `select_final_design_submission_version(db, submission_id, version_id, user_id)`
- `get_selected_design_rendering_source(db, project_id)`

Selection behavior:

1. validate submission/version/project/quest match,
2. validate reviewer can edit the project,
3. clear prior selected submission state for the quest,
4. mark the chosen submission `selected`,
5. set quest status `selected`,
6. create a `ProjectFile` rendering row referencing the existing stored file,
7. record source metadata,
8. write `DesignQuestEvent` entries for `submission_selected` and
   `submission_promoted_to_rendering`,
9. write a project change record through existing file upload/change audit path.

## Route Plan

Update `app/routes/projects.py`:

- `POST /projects/{project_id}/design-quests/{quest_id}/submissions/{submission_id}/versions/{version_id}/select-final`

The route redirects back to `#renderings-overview` and reports errors via the
existing `design_quest_error` query parameter.

## Template Plan

Update `app/templates/project_detail.html`:

- add a selected/final rendering source summary above the active quest details
  when present,
- add a select-final confirmation form beside each submission version/action
  where `can_edit` is true,
- label promoted versions in the version history.

## i18n Plan

Add exact EN/ZH parity for Build 07 labels under `design_quest.*` and
`renderings.*`.

Expected new keys: 8-14. Lock exact count in `test_v15_build07.py`.

## Testing Plan

Create:

- `test_v15_build07.py`

Required assertions:

1. Plan locks select-final/promotion scope and excludes design-complete,
   Timeline/Pulse, and AI handlers.
2. Fresh DB has selected metadata and project file source columns/indexes.
3. PM/admin can select a specific submission version as final.
4. Selection creates a project rendering row with source metadata.
5. Quest status becomes `selected`; no phase or Timeline completion occurs.
6. Selecting a second version clears the previous selected submission state and
   creates a newer promoted rendering.
7. Regular designer cannot select/promote.
8. PM page shows selected/final source metadata.
9. Promoted rendering appears in the existing rendering overview/history.
10. i18n parity is exact.
