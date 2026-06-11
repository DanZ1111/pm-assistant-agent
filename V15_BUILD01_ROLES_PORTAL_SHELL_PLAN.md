# v1.5 Build 01 Plan — Roles & Designer Portal Shell

## Status

Plan-only document for review.

Do not implement Build 01 until this plan is approved.

Parent plan:

- `V15_MASTERPLAN.md`

Canonical PRD:

- `V15_DESIGNER_PORTAL_PRD.md`

## Purpose

Create the role and route boundary for Designer Portal without adding any quest
workflow yet.

Build 01 should make it impossible to accidentally treat designers as PMs while
giving designer users a clean, restricted place to land.

## Scope

In:

1. Add role support for:
   - `designer`,
   - `designer_manager`.
2. Extend admin invite-PIN generation to support those roles.
3. Add a minimal `/designer` portal shell:
   - designer dashboard route,
   - designer-manager/admin visible shell behavior if needed,
   - intentional empty state explaining no design quests yet.
4. Add route blocking so designer roles cannot access PM project routes.
5. Add navigation behavior:
   - designer roles should land in Designer Portal,
   - PM Workspace chrome should not expose normal project nav to designer
     roles.
6. Add tests proving route boundaries.

Out:

- no `DesignQuest` table,
- no submission model,
- no reference upload,
- no file route changes yet,
- no PM `Renderings & Design` workflow,
- no designer quest dashboard data,
- no designer-manager operational tools,
- no AI tools,
- no rewards,
- no design library,
- no champion submissions,
- no annotation.

## Product Locks

- v1.5 is one backend / two experiences: PM Workspace and Designer Portal.
- Designer Portal must not expose PM Assistant project pages or internal project
  data.
- PM-facing and designer-facing response shapes must remain separate.
- `designer_manager` is a portal operations role, not a PM/admin equivalent.
- Build 01 must only add roles, invite support, `/designer` shell, and route
  blocking.
- Do not merge Build 01 with quest workflow for speed.

## Architecture Review

1. Problem solved: establish a safe account and route boundary before any
   designer-facing project data exists.
2. Tables affected: existing `users` and `invite_pins` role values only; no new
   table required.
3. Real column vs notes: role values already live in `users.role` and
   `invite_pins.role`; no schema change is needed for Build 01.
4. Service layer: no business data writes beyond existing invite/user creation
   flows.
5. Change log: no project change-log entry needed because no project data
   changes.
6. Rollback: remove role options and `/designer` routes/templates; existing
   admin/pm/viewer roles continue to work.

## Backend Honesty Mapping

| Visible Field / Behavior | Source Of Truth | Write Path | Derived Rule | Permission Rule | Test |
|---|---|---|---|---|---|
| Designer role | `users.role` | existing registration via invite PIN | none | role value exactly `designer` | Build 01 role test |
| Designer manager role | `users.role` | existing registration via invite PIN | none | role value exactly `designer_manager` | Build 01 role test |
| Invite role choices | `invite_pins.role` | admin users route | generated PIN stores selected role | admin only | admin template/source test |
| `/designer` shell | authenticated user | read-only route | shell displays empty state until quests exist | designer/designer_manager/admin allowed; PM optional redirect TBD | route test |
| Designer blocked from `/projects` | authenticated user role | no write | designer roles redirected or forbidden | designer/designer_manager cannot enter PM project pages | route test |
| Existing PM access | existing project permissions | unchanged | unchanged | admin/pm/viewer behavior preserved | baseline regression |

## Permission Decisions To Lock

### Designer role

Regular designers:

- can access `/designer`,
- cannot access `/projects`,
- cannot access project detail, project list, my projects, calendar, database,
  ideas, admin pages, or PM AI workspace unless later reviewed,
- cannot use PM project edit/write routes.

### Designer manager role

Designer managers:

- can access `/designer`,
- may later receive portal operations controls,
- cannot automatically access PM project pages,
- cannot be treated as `admin`,
- cannot be treated as `pm`,
- should not see cost, supplier, timeline, quotation, PM journal, or internal
  project data in Build 01.

### Admin role

Admins:

- can generate designer/designer-manager invite PINs,
- may access `/designer` for inspection/support if useful,
- keep current PM Workspace access.

### PM role

PMs:

- should not need Designer Portal for daily work,
- may be allowed to preview `/designer` later through a quest-specific preview,
  but Build 01 does not need that.

## Route Plan

Likely new route module:

- `app/routes/designer.py`

Likely routes:

- `GET /designer`

Possible auth redirects:

- After login, if role is `designer` or `designer_manager`, redirect to
  `/designer` instead of `/projects`.
- If designer role requests `/projects` or `/projects/{id}`, redirect to
  `/designer` or return 403. Pick one in implementation; prefer redirect for
  page GETs and 403/303 for mutating POSTs.

No quest routes in Build 01.

## Template Plan

Likely new template:

- `app/templates/designer/dashboard.html`

Design guidance:

- This is a real portal shell, not a marketing page.
- First screen should show the operational empty state:
  - "No design quests yet."
  - "When a PM publishes a quest for you, it will appear here."
- Do not show PM nav items to designer roles.
- Keep layout restrained and work-focused.

## Invite/Admin Plan

Likely files:

- `app/routes/admin_users.py`
- `app/templates/admin/users.html`
- `app/i18n/en.json`
- `app/i18n/zh.json`

Changes:

- Role selector includes:
  - PM,
  - Viewer,
  - Designer,
  - Designer Manager.
- PIN prefixes should remain readable and distinct. Example:
  - `DS-` for designer,
  - `DM-` for designer manager.
- Existing PM/viewer invite behavior must remain unchanged.

## i18n Plan

Add exact EN/ZH parity for Build 01 labels.

Likely keys:

- `nav.designer_portal`
- `designer.title`
- `designer.subtitle`
- `designer.empty_title`
- `designer.empty_body`
- `designer.role_designer`
- `designer.role_designer_manager`
- `admin.role_pm`
- `admin.role_viewer`
- `admin.role_designer`
- `admin.role_designer_manager`

Implementation plan should lock final key list before coding.

## Testing Plan

Create:

- `test_v15_build01.py`

Required assertions:

1. New role strings are recognized in invite PIN creation.
2. Admin can generate designer invite PIN.
3. Admin can generate designer-manager invite PIN.
4. Registration with designer PIN creates `users.role == "designer"`.
5. Registration with designer-manager PIN creates
   `users.role == "designer_manager"`.
6. Designer login redirects/lands at `/designer`.
7. Designer cannot access `/projects`.
8. Designer cannot access `/projects/{id}`.
9. Designer manager cannot access `/projects`.
10. Existing admin/pm/viewer access behavior is not broken.
11. `/designer` renders a real empty portal shell.
12. EN/ZH i18n parity remains exact.

Regression:

- `python3 test_v15_build01.py`
- `python3 test_build_v121.py`
- one auth/admin regression if available
- `git diff --check`

## Acceptance Criteria

- Build 01 adds no design quest workflow.
- `designer` and `designer_manager` users can exist.
- Designer roles have a restricted `/designer` landing page.
- Designer roles are server-blocked from PM Workspace project routes.
- Admin can create invite PINs for designer roles.
- Existing admin/pm/viewer flows still work.
- No new migrations are required.
- No AI behavior changes.
- No project data exposure to designer roles.

## Stop Condition

After implementation and tests, stop for review before Build 02.

Do not continue into design quest data model in the same coding session unless
the user explicitly approves Build 02.
