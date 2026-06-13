# v1.5 Build 04 Plan — Designer Portal Quest View

## Status

Implementation plan for v1.5 Build 04 after Build 03 PM quest panel is
committed.

Parent plan:

- `V15_MASTERPLAN.md`

Canonical PRD:

- `V15_DESIGNER_PORTAL_PRD.md`

## Purpose

Make published design quests visible inside the restricted Designer Portal
without exposing PM project pages, internal project data, or raw public upload
URLs.

Build 04 is read-only for designers except guarded reference downloads. It does
not add submissions.

## Scope

In:

1. Update `/designer` dashboard to list visible published quests.
2. Add `/designer/quests/{quest_id}` read-only designer-safe quest detail page.
3. Add guarded reference download route:
   - `/designer/quests/{quest_id}/references/{reference_id}/download`
4. Use Build 02 visibility rules and safe payload shaping.
5. Show:
   - quest title,
   - brief,
   - must keep,
   - must avoid,
   - soft deadline,
   - status,
   - safe reference metadata/download buttons.
6. Keep Designer Portal chrome separate from PM Workspace.
7. Add tests for visibility, route blocking, guarded reference access, and no
   raw `/uploads` links.

Out:

- no designer submission upload,
- no submission/version tables,
- no PM review grid,
- no revision workflow,
- no final selection,
- no Timeline/Pulse integration,
- no AI handlers,
- no designer manager operations beyond read visibility already defined.

## Feature Design Review

1. Real problem: designers need a safe place to read published briefs and
   references without being inside PM project pages.
2. Repeated: designers will start every assignment by opening the portal and
   reading the quest.
3. Structured data: yes, visibility, quest status, references, and assignment
   rules already exist in Build 02.
4. Notes fallback: no, a note cannot enforce designer-safe fields or reference
   permissions.
5. Intake burden: none for designers in this build; the portal is read-only.
6. AI role: no AI write/read enhancement in this build.
7. Display payoff: designer sees only the brief and safe references needed to
   begin work.
8. Migration impact: none.
9. Minimal schema: none; reuse Build 02 tables.
10. Minimal UI change: dashboard list plus one detail page.
11. Deferred: uploads/submissions, revisions, final selection, operations tools.

## Architecture Review

1. Problem solved: read-only designer quest access with guarded references.
2. Tables/services affected: `design_quests`, `design_quest_references`,
   `project_files`; `crud.list_design_quests_for_designer`,
   `crud.shape_design_quest_for_designer`, and visibility helper.
3. Real column vs notes: no new schema.
4. Service layer: routes call existing safe-shaping/visibility helpers.
5. Change log: no mutation, so no new audit row.
6. Rollback: remove designer routes/templates/i18n/test; Build 02/03 data is
   unaffected.

## Backend Honesty Mapping

| Visible Field / Action | Source Of Truth | Write Path | Derived Rule | Permission Rule | Test |
|---|---|---|---|---|---|
| Dashboard quest list | `design_quests` | none | `list_design_quests_for_designer` | designer visibility helper | Build 04 dashboard test |
| Quest detail | safe payload dict | none | `shape_design_quest_for_designer` | `can_designer_view_quest` | Build 04 detail test |
| Reference metadata | `design_quest_references` + `project_files` | none | designer-visible references only | visible quest + matching reference | Build 04 reference test |
| Reference download | disk file behind `ProjectFile.file_path` | none | no raw `/uploads` URL exposed | visible quest + reference belongs to quest | Build 04 guarded download test |
| PM route blocking | middleware from Build 01 | none | no PM project route for designers | designer role redirects/forbidden | Build 04 boundary test |

## Route Plan

Update `app/routes/designer.py`:

- `GET /designer`
- `GET /designer/quests/{quest_id}`
- `GET /designer/quests/{quest_id}/references/{reference_id}/download`

Reference download route must:

- require Designer Portal user,
- reject regular PM/viewer users,
- call `can_designer_view_quest`,
- verify the reference belongs to the quest,
- verify `visibility == designer_visible`,
- return `FileResponse` only after checks.

## Template Plan

Update:

- `app/templates/designer/dashboard.html`

Add:

- `app/templates/designer/quest_detail.html`

Design guidance:

- dashboard is operational, not marketing,
- show active/open quest cards,
- detail page should read like a brief,
- no PM project links,
- no raw upload links,
- no raw `/uploads` links,
- no inactive upload/submission form that implies functionality exists.

## i18n Plan

Add exact EN/ZH parity for Build 04 labels under `designer.*`.

Expected new keys: 12.

## Testing Plan

Create:

- `test_v15_build04.py`

Required assertions:

1. Build 04 plan locks read-only designer quest view scope.
2. `/designer` dashboard lists published visible quests.
3. Draft quests do not appear to designers.
4. Assigned-only quest appears to assigned designer only.
5. Quest detail shows designer-safe fields.
6. Detail does not show project factory/cost/MSRP/timeline/journal/PM route
   links.
7. Reference route downloads only when quest/reference are visible to user.
8. Detail page contains guarded reference URL and no `/uploads` URL.
9. Designer still cannot access `/projects/{id}`.
10. No submission upload route/model/UI exists.
11. i18n parity remains exact.

Regression:

- `python3 test_v15_build04.py`
- `python3 test_v15_build03.py`
- `python3 test_v15_build02.py`
- `python3 test_build_v121.py`
- `git diff --check`

## Acceptance Criteria

- Designers can find and open visible published quests in `/designer`.
- Designers see only safe brief/reference fields.
- Designers can download references only through guarded Designer Portal routes.
- Draft and assigned-only visibility rules are enforced server-side.
- PM Workspace pages remain blocked for designer roles.
- No submissions or revision workflow exists yet.

## Stop Condition

Commit Build 04 before starting Build 05 submissions/versioning.
