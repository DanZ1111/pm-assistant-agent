# v1.5 Build 06 Plan — Revision Loop & Review Actions

## Status

Implementation plan for v1.5 Build 06 after Build 05 Submissions & Versions is
committed.

Parent plan:

- `V15_MASTERPLAN.md`

Canonical PRD:

- `V15_DESIGNER_PORTAL_PRD.md`

## Purpose

Allow PM/admin project editors to review incoming designer submissions,
shortlist or reject them, and request structured revisions with checklist
items. Designers must see their own revision requests and upload revised
versions that preserve the request-to-version lineage.

Build 06 does not select a final design or promote anything into project
renderings.

## Scope

In:

1. Add `DesignRevisionRequest` and `DesignRevisionItem` models.
2. Add migration `013_v1_5_create_design_revision_requests`.
3. Add `revision_request_id` to `design_submission_versions` so revised
   uploads can point back to the request they answer.
4. Add service helpers for:
   - shortlisting a submission,
   - rejecting a submission,
   - requesting revision with checklist items,
   - listing open revision requests for a designer submission,
   - linking a revised upload to an open revision request,
   - shaping revision requests for designer and PM views.
5. Add PM action forms in the incoming submission grid:
   - shortlist,
   - reject,
   - request revision with general comment + checklist textarea.
6. Add Designer Portal revision panel:
   - open request summary,
   - checklist items,
   - upload revised version tied to the revision request.
7. Add audit events for shortlist/reject/revision requested/revision uploaded.
8. Add exact EN/ZH i18n parity and Build 06 regression test.

Out:

- no final selection,
- no promotion to project rendering,
- no project rendering source metadata,
- no Timeline/Pulse integration,
- no AI write handlers,
- no image annotation,
- no designer manager override operations.

## Feature Design Review

1. Real problem: PMs need to tell designers what to change without losing the
   connection between feedback and revised files.
2. Repeated: design review/revision is a common repeated loop before sampling.
3. Structured data: yes, revision status, checklist items, and response version
   links must be queryable and auditable.
4. Notes fallback: no, notes cannot reliably show open revision work or prove
   which version answered which request.
5. Intake burden: PM enters a short comment and optional checklist; designer
   uploads one revised file from the existing quest page.
6. AI role: none in this build.
7. Display payoff: PM sees submission state; designer sees exactly what needs
   revision and can submit the response in one place.
8. Migration impact: additive tables plus one nullable version column.
9. Minimal schema: revision request and item tables only; final selection waits.
10. Minimal UI change: action row inside existing PM submission cards and one
   revision panel inside the Designer Portal quest detail.
11. Deferred: final selection, promotion, annotations, AI review suggestions,
   rewards, design library.

## Architecture Review

1. Problem solved: structured PM review and designer revision loop.
2. Tables/services affected: `design_submissions`,
   `design_submission_versions`, `design_revision_requests`,
   `design_revision_items`, `design_quest_events`.
3. Real column vs notes: real tables are required because revision items and
   response versions are workflow state.
4. Service layer: all review writes must live in `crud.py`.
5. Change log: write `DesignQuestEvent` for every review/revision transition.
6. Rollback: remove Build 06 routes/UI and drop revision tables/nullable
   version link; Build 05 submissions remain intact.

## Backend Honesty Mapping

| Visible Field / Action | Source Of Truth | Write Path | Derived Rule | Permission Rule | Test |
|---|---|---|---|---|---|
| Shortlist | `design_submissions.status` | `shortlist_design_submission` | status becomes `shortlisted` | PM/admin project editor | Build 06 shortlist test |
| Reject | `design_submissions.status` | `reject_design_submission` | status becomes `rejected` | PM/admin project editor | Build 06 reject test |
| Request revision | `design_revision_requests/items` | `request_design_revision` | submission status `revision_requested`, quest status `revision_needed` | PM/admin project editor | Build 06 request test |
| Designer revision panel | revision request safe payload | none | open requests for own submission | designer owns submission or manager | Build 06 designer panel test |
| Revised upload | `design_submission_versions.revision_request_id` | Build 05 upload helper with revision id | new version links to open request; request resolved; submission status `revised` | designer owns submission/request | Build 06 revised upload test |

## Data Model Plan

Add to `app/models.py`:

### `DesignRevisionRequest`

- `id`
- `submission_id`
- `quest_id`
- `project_id`
- `requested_by_user_id`
- `status`: `open`, `resolved`, `cancelled`
- `general_comment`
- `created_at`
- `resolved_at`

### `DesignRevisionItem`

- `id`
- `revision_request_id`
- `text`
- `status`: `open`, `resolved`
- `sort_order`
- `created_at`

Add nullable `revision_request_id` to `DesignSubmissionVersion`.

## Migration Plan

Add migration:

- `013_v1_5_create_design_revision_requests`

Tables:

- `design_revision_requests`
- `design_revision_items`

Column:

- `design_submission_versions.revision_request_id`

Indexes:

- `ix_design_revision_requests_submission_status`
- `ix_design_revision_requests_quest_status`
- `ix_design_revision_items_request`
- `ix_design_submission_versions_revision_request`

## Service Plan

Add to `app/crud.py`:

- `shortlist_design_submission(db, submission_id, user_id)`
- `reject_design_submission(db, submission_id, user_id, reason=None)`
- `request_design_revision(db, submission_id, user_id, general_comment, checklist_text)`
- `list_open_revision_requests_for_submission(db, submission_id)`
- `shape_design_revision_request_for_designer(request, user)`
- `shape_design_revision_request_for_pm(request)`

Extend:

- `create_or_append_design_submission_version(..., revision_request_id=None)`

Revision upload behavior:

1. validate the revision request belongs to the designer's submission,
2. validate request status is `open`,
3. append a new immutable version,
4. set request status `resolved`,
5. set checklist items `resolved`,
6. set submission status `revised`,
7. write audit event.

## Route Plan

Update `app/routes/projects.py`:

- `POST /projects/{project_id}/design-quests/{quest_id}/submissions/{submission_id}/shortlist`
- `POST /projects/{project_id}/design-quests/{quest_id}/submissions/{submission_id}/reject`
- `POST /projects/{project_id}/design-quests/{quest_id}/submissions/{submission_id}/request-revision`

Update `app/routes/designer.py`:

- Extend upload route to accept optional `revision_request_id`.

No new file-serving routes are needed beyond Build 05 guarded version download.

## Template Plan

Update:

- `app/templates/project_detail.html`
- `app/templates/designer/quest_detail.html`
- `app/static/css/styles.css`

PM incoming submission cards:

- show status,
- show latest version,
- show version count,
- show action row: Shortlist, Reject, Request Revision,
- request revision uses an inline details/form block to avoid a modal-heavy UI.

Designer quest detail:

- show open revision requests above upload form,
- show checklist items,
- revised upload includes hidden `revision_request_id`.

## i18n Plan

Add exact EN/ZH parity for Build 06 labels under `design_quest.*` and
`designer.*`.

Expected new keys: 16-24. Lock exact count in `test_v15_build06.py`.

## Testing Plan

Create:

- `test_v15_build06.py`

Required assertions:

1. Plan locks revision scope and excludes final selection/promotion.
2. Fresh DB has revision tables, indexes, and version link column.
3. PM/admin can shortlist a submission.
4. PM/admin can reject a submission.
5. PM/admin can request revision with checklist items.
6. Regular designer cannot review another designer's submission.
7. Designer sees only their own open revision request/checklist.
8. Designer uploads revised version tied to revision request.
9. Revised upload resolves request/items and preserves earlier versions.
10. PM sees version history and revision-linked version.
11. No final selection/promotion/AI handler exists.
12. i18n parity remains exact.

Regression:

- `python3 test_v15_build06.py`
- `python3 test_v15_build05.py`
- `python3 test_v15_build04.py`
- `python3 test_build_v121.py`
- `python3 test_v14_build09.py`
- `git diff --check`

## Acceptance Criteria

- PM/admin can shortlist, reject, and request revisions on submitted designs.
- Designers see their own open revision request with checklist items.
- Revised uploads create a new version linked to the request.
- Previous versions remain available.
- Final selection and promotion are still absent.

## Stop Condition

Commit this plan before implementation. After Build 06 implementation is green,
commit it before starting Build 07 Select Final & Promote Rendering.
