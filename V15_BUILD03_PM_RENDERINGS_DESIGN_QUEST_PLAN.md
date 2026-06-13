# v1.5 Build 03 Plan — PM Renderings & Design Quest MVP

## Status

Implementation plan for v1.5 Build 03 after Build 02 data model is committed.

Parent plan:

- `V15_MASTERPLAN.md`

Canonical PRD:

- `V15_DESIGNER_PORTAL_PRD.md`

## Purpose

Turn the Project Detail `Renderings` area from a placeholder into the PM-side
control panel for one active design quest.

Build 03 is still PM Workspace only. Designers do not get quest list/detail UI
until Build 04.

## Scope

In:

1. Rename the PM section display to `Renderings & Design`.
2. Add an Active Design Quest panel inside the existing renderings section.
3. PM/admin users with project edit access can:
   - create a draft quest,
   - publish a draft quest,
   - close an active quest,
   - link existing project files as designer-facing references.
4. PM can preview the designer-safe quest payload as read-only text inside the
   PM panel.
5. Show reference file metadata without raw `/uploads` links in the quest panel.
6. Add routes that call Build 02 service helpers only.
7. Add i18n labels and tests.

Out:

- no Designer Portal quest dashboard/detail pages,
- no designer upload/submissions,
- no revision workflow,
- no final selection,
- no guarded designer file route yet,
- no direct upload-to-quest; PM uploads files through the existing Files area
  first, then links them as references,
- no Timeline/Pulse integration,
- no AI handlers.

## Feature Design Review

1. Real problem: PMs need a clear place to create and publish a design brief
   from the project instead of leaving the Designer Portal placeholder dead.
2. Repeated: every project that needs design/rendering work will use this flow.
3. Structured data: yes, the quest already has structured status, visibility,
   deadline, assignment, and references from Build 02.
4. Notes fallback: no, a note cannot safely publish designer-facing work.
5. Intake burden: limited form fields only; reference files reuse existing
   project uploads.
6. AI role: deferred; AI can later draft the brief but must confirm.
7. Display payoff: PM sees active quest state, publish/close actions, and safe
   preview in the renderings section.
8. Migration impact: none; Build 02 tables are reused.
9. Minimal schema: no schema change.
10. Minimal UI change: one panel inside the existing Renderings section.
11. Deferred: designer quest pages, submissions, revisions, final promotion,
    guarded file serving, and AI tools.

## Architecture Review

1. Problem solved: PM can operate the quest lifecycle against the Build 02
   service layer.
2. Tables/services affected: `design_quests`, `design_quest_references`,
   `design_quest_events`; service helpers in `crud.py`.
3. Real column vs notes: no new columns; existing structured quest state is used.
4. Service layer: routes stay thin and call Build 02 service helpers.
5. Change log: Build 02 `DesignQuestEvent` remains the quest audit source.
6. Rollback: remove routes/template panel/i18n/test; Build 02 data remains safe.

## Backend Honesty Mapping

| Visible Field / Action | Source Of Truth | Write Path | Derived Rule | Permission Rule | Test |
|---|---|---|---|---|---|
| Active quest title/status | `design_quests` | `get_active_design_quest` | first active quest per project | project view allowed | Build 03 UI/source test |
| Create draft | `design_quests.status='draft'` | `create_design_quest_draft` | one active quest guard | `can_edit_project` | Build 03 route test |
| Publish quest | `design_quests.status='open'` | `publish_design_quest` | draft only | `can_edit_project` | Build 03 route test |
| Close quest | `design_quests.status='closed'` | `close_design_quest` | active only | `can_edit_project` | Build 03 route test |
| References | `design_quest_references` + `project_files` | `link_design_quest_reference` | same-project file only | `can_edit_project` | Build 03 route test |
| PM preview | `shape_design_quest_for_designer` | read-only | no raw path, no PM-only fields | PM/admin with project access | Build 03 payload test |

## Route Plan

Add to `app/routes/projects.py`:

- `POST /projects/{project_id}/design-quest/create`
- `POST /projects/{project_id}/design-quest/{quest_id}/publish`
- `POST /projects/{project_id}/design-quest/{quest_id}/close`
- `POST /projects/{project_id}/design-quest/{quest_id}/references`

All routes redirect back to `/projects/{project_id}#renderings-overview`.

## Template Plan

Update `app/templates/project_detail.html`:

- section header says `Renderings & Design`,
- replace the old Designer Portal placeholder card with:
  - no-active-quest empty state,
  - create draft form,
  - active quest status card,
  - publish/close action row,
  - reference-link selector from existing project files,
  - read-only designer-safe preview.

## i18n Plan

Add exact EN/ZH parity for Build 03 labels under `design_quest.*`.

Expected new keys: 22.

## Testing Plan

Create:

- `test_v15_build03.py`

Required assertions:

1. Build 03 plan locks PM-only scope.
2. Routes exist and call Build 02 service helpers.
3. Template replaces the placeholder with Active Design Quest panel.
4. Create draft route creates quest and redirects.
5. Publish route opens quest.
6. Close route closes quest.
7. Reference route links only same-project file.
8. Project detail includes PM quest panel for editor.
9. Designer role still cannot access project page.
10. PM preview does not expose raw file paths or `/uploads`.
11. i18n parity remains exact.

Regression:

- `python3 test_v15_build03.py`
- `python3 test_v15_build02.py`
- `python3 test_v15_build01.py`
- `python3 test_build_v121.py`
- `git diff --check`

## Acceptance Criteria

- PM/admin can create, publish, close, and add references to one active design
  quest from the project.
- The old Designer Portal placeholder is gone from PM Renderings.
- No designer-facing quest UI or file route exists yet.
- Existing project rendering history and file upload behavior still works.

## Stop Condition

Commit Build 03 before starting Designer Portal quest view in Build 04.
