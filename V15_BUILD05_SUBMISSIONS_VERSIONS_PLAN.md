# v1.5 Build 05 Plan — Submissions & Versions

## Status

Implementation plan for v1.5 Build 05 after Build 04 Designer Portal Quest
View is committed.

Parent plan:

- `V15_MASTERPLAN.md`

Canonical PRD:

- `V15_DESIGNER_PORTAL_PRD.md`

## Purpose

Allow designers to submit design files for open quests and allow PM/admin
project editors to see incoming submissions from the Project Detail Renderings
& Design panel.

Build 05 adds the submission/version data backbone and the first upload/review
surface. It does not add review decisions, revision requests, final selection,
promotion to project renderings, Timeline integration, or AI handlers.

## Scope

In:

1. Add `DesignSubmission` and `DesignSubmissionVersion` models.
2. Add migration `012_v1_5_create_design_submissions`.
3. Add service-layer helpers for:
   - creating a submission when a designer uploads the first version,
   - appending a new immutable version to an existing designer submission,
   - listing designer-owned submissions for the portal,
   - listing PM-visible submissions for a project quest,
   - shaping designer-safe submission payloads,
   - guarded submission-version file access.
4. Add designer upload form on `/designer/quests/{quest_id}` when:
   - quest is open/reviewing/revision_needed,
   - current user can view the quest,
   - current user is a regular designer or designer_manager acting as portal
     user.
5. Add guarded designer file download route:
   - `/designer/quests/{quest_id}/submissions/{submission_id}/versions/{version_id}/download`
6. Add guarded PM file download route:
   - `/projects/{project_id}/design-quests/{quest_id}/submissions/{submission_id}/versions/{version_id}/download`
7. Add PM incoming submission grid in Renderings & Design.
8. Validate uploads:
   - allowed extensions: `jpg`, `jpeg`, `png`, `webp`, `pdf`,
   - max size: 20 MB,
   - empty filename/content rejected.
9. Preserve every uploaded version as a new row; never overwrite old files.
10. Add exact EN/ZH i18n parity and Build 05 regression test.

Out:

- no shortlist/reject/request-revision actions,
- no revision request/checklist tables,
- no final selection,
- no promotion to `project_files` rendering category,
- no Timeline/Pulse status integration,
- no AI write handlers,
- no designer manager operations beyond existing visibility,
- no raw `/uploads` links in designer-facing or PM submission UI.

## Feature Design Review

1. Real problem: designers need a controlled place to submit renderings, and
   PMs need to see submitted design work without hunting through chat/files.
2. Repeated: submission upload and PM review are repeated on every design quest.
3. Structured data: yes, submissions and immutable versions need structured
   rows for ownership, status, file access, and later revision history.
4. Notes fallback: no, notes cannot enforce designer-owned file access or
   preserve version lineage.
5. Intake burden: designers add one upload plus optional note; PMs review a
   compact incoming grid.
6. AI role: none in this build; AI write access remains locked out.
7. Display payoff: PM can see who submitted what and when; designer can see
   their own submitted versions.
8. Migration impact: one additive migration for two tables and indexes.
9. Minimal schema: only submission and version tables; revision/final metadata
   waits for later builds.
10. Minimal UI change: upload form on quest detail and submission grid in the
   existing Renderings & Design panel.
11. Deferred: revision loop, final selection, source promotion, annotations,
   rewards, and design library.

## Architecture Review

1. Problem solved: controlled submission/version storage with role-safe access.
2. Tables/services affected: `design_quests`, new `design_submissions`, new
   `design_submission_versions`, `design_quest_events`, `project_files` only as
   existing references.
3. Real column vs notes: real tables are required because file ownership,
   version preservation, and review state are first-class workflow state.
4. Service layer: routes must call `crud.py`; no direct route-side database
   writes except file bytes saved before service creation.
5. Change log: design quest audit events should record submission/version
   uploads; project `write_change` is optional only if the PM-facing project
   history needs a visible file event.
6. Rollback: drop the two tables/indexes and remove Build 05 routes/templates;
   quest data from Builds 02-04 remains usable.

## Backend Honesty Mapping

| Visible Field / Action | Source Of Truth | Write Path | Derived Rule | Permission Rule | Test |
|---|---|---|---|---|---|
| Upload submission | `design_submissions` + version row | `create_or_append_design_submission_version` | first upload creates submission, later uploads append version | designer can view quest and quest accepts submissions | Build 05 upload test |
| Submission status | `design_submissions.status` | service helper | initial status `submitted` | designer sees own; PM sees project quest | Build 05 status test |
| Version number | `design_submission_versions.version_number` | service helper | max existing version + 1 | same as submission access | Build 05 preservation test |
| Designer detail version list | safe payload | none | list own submission versions newest/ascending by version | owner or designer_manager | Build 05 designer detail test |
| PM incoming grid | `design_submissions` | none | list all submissions for active quest | PM/admin project edit/view access | Build 05 PM grid test |
| Version download | disk file behind stored filename | none | no raw `/uploads` URL exposed | guarded submission access | Build 05 guarded download test |

## Data Model Plan

Add to `app/models.py`:

### `DesignSubmission`

- `id`
- `quest_id` -> `design_quests.id`, required
- `project_id` -> `projects.id`, required for PM queries
- `designer_user_id` -> `users.id`, required
- `status`: default `submitted`
- `title`: optional designer-provided title
- `designer_note`: optional
- `created_at`
- `updated_at`
- relationships: quest, designer, versions

Initial statuses allowed in Build 05:

- `submitted`
- `archived` only for future compatibility; no route writes it yet.

Unique MVP lock:

- one active submission row per `(quest_id, designer_user_id)`.
- multiple file uploads become versions under that row.

### `DesignSubmissionVersion`

- `id`
- `submission_id` -> `design_submissions.id`, required
- `quest_id` -> `design_quests.id`, required
- `project_id` -> `projects.id`, required
- `version_number`, required
- `filename`, stored internal unique filename
- `original_filename`
- `file_type`
- `file_size`
- `designer_note`
- `uploaded_by_user_id`
- `created_at`

No raw public URL column is required. Routes build guarded download URLs from
IDs, not from file paths.

## Migration Plan

Add migration:

- `012_v1_5_create_design_submissions`

Tables:

- `design_submissions`
- `design_submission_versions`

Indexes:

- unique active submission per quest/designer,
- `ix_design_submissions_quest_status`,
- `ix_design_submissions_designer_status`,
- `ix_design_submission_versions_submission`,
- `ix_design_submission_versions_quest`.

## Service Plan

Add to `app/crud.py`:

- `can_access_design_submission(user, submission)`
- `list_design_submissions_for_quest(db, quest_id)`
- `list_design_submissions_for_designer(db, designer_user_id)`
- `shape_design_submission_for_designer(submission, user)`
- `shape_design_submission_for_pm(submission)`
- `create_or_append_design_submission_version(...)`
- `get_design_submission_version_for_download(...)`

The create/append helper must:

1. validate quest exists and status accepts submissions,
2. validate designer can view quest,
3. validate file extension and size,
4. create or reuse the designer's active submission for the quest,
5. write a new immutable version with next version number,
6. update submission timestamp/status,
7. write a design quest event.

## Route Plan

Update `app/routes/designer.py`:

- `POST /designer/quests/{quest_id}/submissions/upload`
- `GET /designer/quests/{quest_id}/submissions/{submission_id}/versions/{version_id}/download`

Update `app/routes/projects.py`:

- `GET /projects/{project_id}/design-quests/{quest_id}/submissions/{submission_id}/versions/{version_id}/download`

All file-serving routes must check database permissions before returning
`FileResponse`.

## Template Plan

Update:

- `app/templates/designer/quest_detail.html`
- `app/templates/project_detail.html`
- `app/static/css/styles.css`

Designer quest detail:

- show upload form only when quest accepts submissions,
- show own submission/version history,
- show upload validation errors as intentional portal messages,
- closed quests hide upload but keep prior versions visible.

PM Renderings & Design panel:

- show incoming submissions grouped by designer,
- show latest version metadata and download button,
- keep review actions visually absent until Build 06.

## i18n Plan

Add exact EN/ZH parity for Build 05 labels under `designer.*` and
`design_quest.*`.

Expected new keys: 18-26. Lock the exact count in `test_v15_build05.py` after
implementation.

## Testing Plan

Create:

- `test_v15_build05.py`

Required assertions:

1. Plan locks submissions/version scope and excludes revisions/final selection.
2. Migration creates both tables and indexes on a fresh DB.
3. Designer can upload allowed file to open visible quest.
4. Upload creates one submission and version 1.
5. Second upload creates version 2 under same submission, preserving version 1.
6. Invalid extension and oversize upload are rejected.
7. Designer sees own submission/version list on quest detail.
8. Designer cannot see or download another designer's private submission.
9. Designer manager can inspect portal submissions if explicitly allowed.
10. PM/admin project page shows incoming submission grid.
11. PM/admin can download submission versions through guarded route.
12. PM-facing and designer-facing HTML contain no raw `/uploads` links.
13. Build 05 adds no revision request/final selection/AI handlers.
14. i18n parity remains exact.

Regression:

- `python3 test_v15_build05.py`
- `python3 test_v15_build04.py`
- `python3 test_v15_build03.py`
- `python3 test_v15_build02.py`
- `python3 test_build_v121.py`
- `python3 test_v14_build09.py`
- `git diff --check`

## Acceptance Criteria

- Designers can upload a submission file from the Designer Portal quest detail.
- Each upload is preserved as an immutable version.
- Designer-facing pages show only that designer's own submission history.
- PM/admin project editors can see incoming submissions in Renderings & Design.
- PM/admin and designers download files only through guarded routes.
- No raw `/uploads` links appear in Designer Portal or PM submission UI.
- No revision/review/final selection feature exists yet.

## Stop Condition

Commit this plan before implementation. After Build 05 implementation is green,
commit it before starting Build 06 Revision Loop & Review Actions.
