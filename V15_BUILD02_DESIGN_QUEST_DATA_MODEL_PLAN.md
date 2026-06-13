# v1.5 Build 02 Plan — Design Quest Data Model

## Status

Implementation plan for review and execution after v1.5 Build 01.

Parent plan:

- `V15_MASTERPLAN.md`

Canonical PRD:

- `V15_DESIGNER_PORTAL_PRD.md`

## Purpose

Create the backend source of truth for design quests before building the PM or
designer workflow UI.

Build 02 should make it possible for later builds to create draft/open quests,
assign designers, attach designer-facing references, and shape designer-safe
responses without exposing PM project pages or internal project data.

## Scope

In:

1. Add additive data models and migration for:
   - `DesignQuest`,
   - `DesignQuestAssignment`,
   - `DesignQuestReference`,
   - `DesignQuestEvent`.
2. Add service helpers in `crud.py` for:
   - creating a draft quest,
   - publishing a quest,
   - closing a quest,
   - assigning designers,
   - linking existing project files as designer-visible references,
   - listing quests visible to a designer,
   - shaping one designer-safe quest payload.
3. Add permission helpers for quest visibility:
   - draft quests are PM/admin-only,
   - open/reviewing/revision states are visible based on quest visibility and
     assignments,
   - designers never receive raw project objects or PM-only fields.
4. Add `AI_TOOLS_REGISTRY.md` planned entries for the future AI surface.
5. Add `test_v15_build02.py` proving schema, service behavior, visibility,
   audit, and no UI scope leak.

Out:

- no PM quest creation UI,
- no Designer Portal quest list/detail UI,
- no designer submission upload,
- no submission upload,
- no revision workflow,
- no final selection,
- no guarded file-serving route yet,
- no project rendering promotion,
- no Timeline/Pulse integration,
- no AI tool handlers or AI write access.

## Feature Design Review

1. Real problem: PMs need design briefs, assignments, references, and status to
   have a durable source of truth before designers can submit work.
2. Repeated: design quests will be used for most projects that need renderings
   or industrial design work.
3. Structured data: yes, status, visibility, assignments, references, and audit
   need filtering and permissions.
4. Notes fallback: a journal entry cannot safely drive designer visibility,
   assignment, deadline, or guarded reference access.
5. Intake burden: Build 02 adds no manual UI yet; later PM UI should keep brief
   creation lightweight.
6. AI role: AI can later draft briefs and suggest assignments, but Build 02 only
   registers planned tools.
7. Display payoff: later builds can show active quest, designer-safe dashboard,
   PM review state, and Timeline/Pulse design pressure.
8. Migration impact: additive tables only; no existing columns renamed or
   removed.
9. Minimal schema: quest, assignment, reference, and event tables; submissions
   and revisions are deferred.
10. Minimal UI change: none in Build 02 beyond no-scope tests.
11. Deferred: UI, uploads, revisions, submissions, final selection, guarded file
    routes, and AI handlers.

## Architecture Review

1. Problem solved: structured design workflow source of truth that preserves
   PM/designer separation.
2. Tables and services affected: new design quest tables, `Project` and `User`
   relationships, migration registry, and design quest helpers in `crud.py`.
3. Real column vs notes: quest status, visibility, assignments, references, and
   audit must be structured because they drive permissions and workflow state.
4. Service layer: all quest mutations go through `crud.py`; routes and future
   AI handlers must call these helpers.
5. Change log: every quest mutation writes a `DesignQuestEvent`; project-level
   `ProjectChange` is optional in later UI builds but not the source of truth.
6. Rollback: drop additive tables and remove model/service imports; no existing
   project data is mutated by Build 02.

## Data Model

### `design_quests`

Source of truth for one design brief/work request.

Fields:

- `id`
- `project_id`
- `title`
- `brief`
- `must_keep`
- `must_avoid`
- `status`: `draft`, `open`, `reviewing`, `revision_needed`, `selected`,
  `closed`, `cancelled`
- `visibility`: `all_active_designers`, `assigned_designers_only`
- `soft_deadline`
- `is_timeline_blocking`
- `linked_phase_id`
- `created_by_user_id`
- `published_at`
- `closed_at`
- `created_at`
- `updated_at`

Constraint:

- partial unique index: at most one active quest per project for statuses
  `draft`, `open`, `reviewing`, `revision_needed`, `selected`.

### `design_quest_assignments`

Designer access/assignment table.

Fields:

- `id`
- `quest_id`
- `designer_user_id`
- `assigned_by_user_id`
- `status`: `assigned`, `removed`
- `created_at`
- `updated_at`

Constraint:

- unique `(quest_id, designer_user_id)`.

### `design_quest_references`

Designer-facing reference links to existing project files.

Fields:

- `id`
- `quest_id`
- `project_file_id`
- `label`
- `visibility`: `designer_visible`, `internal_only`
- `sort_order`
- `added_by_user_id`
- `created_at`

Lock:

- Build 02 links existing `ProjectFile` rows only. It does not expose raw
  `/uploads` links or add guarded file-serving routes yet.

### `design_quest_events`

Audit trail for quest lifecycle and assignment/reference changes.

Fields:

- `id`
- `quest_id`
- `project_id`
- `event_type`
- `actor_user_id`
- `summary`
- `payload_json`
- `created_at`

## Backend Honesty Mapping

| Visible / Service Behavior | Source Of Truth | Write Path | Derived Rule | Permission Rule | Test |
|---|---|---|---|---|---|
| Draft quest exists | `design_quests.status='draft'` | `create_design_quest_draft` | none | admin/PM with project edit access | Build 02 service test |
| Published quest exists | `design_quests.status='open'`, `published_at` | `publish_design_quest` | draft -> open only | admin/PM with project edit access | Build 02 service test |
| Closed quest | `design_quests.status='closed'`, `closed_at` | `close_design_quest` | open/reviewing/etc. -> closed | admin/PM with project edit access | Build 02 service test |
| Assigned designers | `design_quest_assignments` | `assign_designers_to_quest` | removed rows do not grant access | admin/PM with project edit access | Build 02 assignment test |
| Designer-visible references | `design_quest_references.visibility` + `project_files` | `link_design_quest_reference` | only matching project files can link | admin/PM with project edit access | Build 02 reference test |
| Designer-safe payload | quest + filtered references | `shape_design_quest_for_designer` | never include project cost/factory/journal/timeline | quest visible to designer | Build 02 payload test |
| Quest lifecycle audit | `design_quest_events` | every mutating service helper | event per mutation | service writes only | Build 02 audit test |

## Service Plan

Likely new helpers in `app/crud.py`:

- `create_design_quest_draft(db, project_id, user_id, title, brief, ...)`
- `publish_design_quest(db, quest_id, user_id)`
- `close_design_quest(db, quest_id, user_id, reason=None)`
- `assign_designers_to_quest(db, quest_id, designer_user_ids, assigned_by_user_id)`
- `link_design_quest_reference(db, quest_id, project_file_id, added_by_user_id, ...)`
- `get_active_design_quest(db, project_id)`
- `list_design_quests_for_designer(db, designer_user_id)`
- `can_designer_view_quest(user, quest)`
- `shape_design_quest_for_designer(quest, user)`

Mutation helpers must write `DesignQuestEvent`.

## Permission Decisions

- Admin may create/update/read all design quests.
- PM may create/update/read quests only when existing project edit permission
  allows it.
- Designer can read open/published quests only when:
  - visibility is `all_active_designers`, or
  - visibility is `assigned_designers_only` and an active assignment exists.
- Designer cannot see draft quests.
- Designer manager may read portal quest payloads for operations, but Build 02
  does not grant PM Workspace access.
- Designer-safe payload must not include project fields such as factory, cost,
  MSRP, quotation, journal, timeline, PM notes, or raw file paths.

## Migration Plan

Add migration:

- `011_v1_5_create_design_quest_core`

It creates the four tables and indexes idempotently.

No existing table is altered.

## AI Registry Plan

Add planned entries only:

- `draft_design_quest`
- `publish_design_quest`
- `close_design_quest`

All future AI writes require confirmation and must call the same service layer.
No handler is registered in Build 02.

## Testing Plan

Create:

- `test_v15_build02.py`

Required assertions:

1. Build 02 plan and PRD locks exist.
2. Models and migration names exist.
3. Migration creates all four tables and indexes on a temporary DB.
4. Create draft quest writes quest + event.
5. Draft quest is invisible to designer-safe listing.
6. Publish quest writes `published_at` + event.
7. `all_active_designers` open quest is visible to a designer.
8. Assigned-only quest is visible only to assigned designer.
9. References can only link project files from the same project.
10. Designer-safe payload excludes PM/internal fields and raw `file_path`.
11. Close quest removes it from open designer listing and writes event.
12. AI registry lists planned design quest tools without app handlers.
13. Build 02 adds no Designer Portal quest UI or submission model.
14. i18n parity remains exact.

Regression:

- `python3 test_v15_build02.py`
- `python3 test_v15_build01.py`
- `python3 test_build_v121.py`
- `git diff --check`

## Acceptance Criteria

- Additive quest data model exists.
- Mutating quest helpers go through `crud.py` and write audit events.
- Designer-safe read shaping exists and omits PM-only/internal data.
- Draft/open/assigned-only visibility rules are proven by tests.
- No designer submission workflow exists yet.
- No raw public designer file route is exposed.
- Existing PM/admin/viewer/designer shell behavior remains intact.

## Stop Condition

After implementation and tests, commit Build 02 before moving to Build 03.
