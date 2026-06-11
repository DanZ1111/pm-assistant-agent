# v1.5 Masterplan — Designer Portal & Rendering Workflow

## Status

Plan-only document for review by the user, Claude Code, ChatGPT, and Codex.

No implementation should begin until this masterplan and the relevant build
execution plan are reviewed and explicitly approved.

Canonical PRD:

- `V15_DESIGNER_PORTAL_PRD.md`

## Product Goal

v1.5 creates a restricted Designer Portal that closes the loop between PM design
briefs, designer submissions, PM review, revision, final selection, and project
renderings.

The product goal is not "make another project management system." The goal is:

```text
PM Workspace remains the project command center.
Designer Portal becomes the restricted submission/revision surface.
Selected design work flows back into project renderings.
Design completion can affect Timeline/Pulse only through explicit PM action.
```

## Non-Negotiable Locks

1. v1.5 is one backend / two experiences:
   - PM Workspace,
   - Designer Portal.
2. Designer Portal must not expose PM Assistant project pages or internal
   project data.
3. Designer-visible files must not use raw public `/uploads` links. They must
   go through guarded file routes.
4. PM-facing and designer-facing API/route response shapes must be separate.
5. `designer_manager` is a portal operations role, not a PM/admin equivalent.
6. Do not merge builds for speed.
7. Do not add AI write access in v1.5.
8. Do not add reward system, design library, champion submissions, or
   Figma-style annotation in v1.5.
9. One active quest per project is acceptable for MVP.
10. Timeline integration must be display/explicit-action only. No automatic
    timeline advancement.

## Scope Boundaries

In v1.5:

- roles and portal shell,
- design quest data model,
- PM-side Renderings & Design workflow,
- Designer Portal quest/submission workflow,
- revision loop,
- final selection and promotion to project rendering,
- explicit design-complete flow,
- hardening and permission tests.

Out of v1.5:

- AI handlers that mutate design quest/submission state,
- rewards/points,
- rankings/leaderboards,
- design asset library,
- champion cycles,
- image annotation/drawing,
- real-time comments,
- external client sharing,
- separate service/mobile app.

## v1.4 Sandbox Status Note

User observed on 2026-06-10 that the Planning Sandbox still feels placeholder
in production, module editing may not be visible/usable enough, and the sandbox
may belong inside the Timeline workspace rather than a separate master tab/route.

This is important, but it is not part of v1.5 Designer Portal.

Before further sandbox work, create a separate v1.4 follow-up review:

- verify what shipped versus what production shows,
- decide whether sandbox entry should live inside Timeline,
- decide whether module editing should be redesigned,
- preserve the sandbox-only-until-Apply invariant.

Do not combine that sandbox correction with Designer Portal builds.

## Build Series

### v1.5 Build 01 — Roles & Portal Shell

Purpose:

- Add designer-specific role foundation without quest workflow.

Scope:

- Add `designer` and `designer_manager` role support.
- Extend invite PIN support for those roles.
- Add `/designer` shell and dashboard placeholder.
- Block designer roles from PM project routes.
- Keep PM/admin/viewer behavior unchanged.

Out:

- no quest tables,
- no design submissions,
- no file upload changes,
- no AI tools,
- no reward/admin override system.

Plan file:

- `V15_BUILD01_ROLES_PORTAL_SHELL_PLAN.md`

### v1.5 Build 02 — Design Quest Data Model

Purpose:

- Add backend source of truth for design quests.

Expected scope:

- `DesignQuest`,
- `DesignQuestAssignment`,
- `DesignQuestReference`,
- service helpers,
- designer-safe read shaping,
- draft/open visibility rules.

Out:

- no full PM UI,
- no designer submission upload yet unless explicitly approved.

### v1.5 Build 03 — PM Renderings & Design Quest MVP

Purpose:

- PM can create, edit, publish, and close one active design quest from project
  `Renderings & Design`.

Expected scope:

- replace placeholder with real PM quest panel,
- create/edit/publish/close quest,
- upload reference files through guarded workflow,
- empty states,
- PM designer preview.

### v1.5 Build 04 — Designer Portal Quest View

Purpose:

- Designers can see safe quest dashboard/detail pages.

Expected scope:

- available quests,
- assigned/open filtering,
- designer-safe quest detail,
- guarded reference file viewing,
- no PM Workspace chrome or project links.

### v1.5 Build 05 — Submissions & Versions

Purpose:

- Designers can submit images and PMs can see incoming submissions.

Expected scope:

- `DesignSubmission`,
- `DesignSubmissionVersion`,
- upload validation,
- PM incoming submission grid,
- version preservation.

### v1.5 Build 06 — Revision Loop & Review Actions

Purpose:

- PM can review submissions and request structured revision.

Expected scope:

- shortlist,
- reject,
- request revision,
- revision checklist,
- designer sees revision request,
- designer uploads revised version,
- PM sees version history.

### v1.5 Build 07 — Select Final & Promote Rendering

Purpose:

- Selected design submission becomes project rendering through confirmation.

Expected scope:

- select final,
- promote selected version to project rendering/source record,
- source metadata (`design_submission`),
- selected/final rendering display.

### v1.5 Build 08 — Design Status In Timeline/Pulse

Purpose:

- PM can understand whether design work is blocking project progress.

Expected scope:

- design quest status in Project Pulse,
- design quest status in Timeline,
- explicit `Mark Design Complete`,
- no automatic phase completion.

### v1.5 Build 09 — Designer Manager Operations

Purpose:

- Portal operations controls for designer-manager role.

Expected scope:

- manage designer accounts/activation where safe,
- assignment assistance,
- extension/unlock/reopen abnormal portal states,
- audit every override.

Out:

- no PM/admin project-data equivalence.

### v1.5 Build 10 — Release Hardening

Purpose:

- Ship v1.5 as reliable internal MVP.

Expected scope:

- version bump,
- docs,
- permissions regression,
- upload validation,
- end-to-end PM/designer workflow tests,
- scenario contract coverage.

## Backend Honesty Requirements

Before each implementation build, write or update that build's plan with:

- visible field,
- source of truth,
- write path,
- derived-state rule,
- permission rule,
- audit/change-log behavior,
- test coverage.

No UI may imply functionality that does not have a backend source or an
explicit "not active yet" state.

## Permission Architecture Locks

Designer routes must have their own permission helpers.

Minimum helper concepts:

- `is_designer_role(user)`,
- `is_designer_manager(user)`,
- `require_designer_portal_user(user)`,
- `can_access_design_quest(user, quest)`,
- `can_access_design_submission(user, submission)`,
- `can_manage_design_portal(user)`,
- `deny_pm_workspace_for_designer_roles(user)`.

Existing PM helpers such as `can_edit_project` must not be casually expanded to
include designer roles.

## File Architecture Locks

The current app has static `/uploads` serving. Designer Portal must not depend
on raw public file URLs for designer-visible assets.

v1.5 should introduce guarded file routes for:

- design quest references,
- design submission versions,
- final selected design source links.

Physical file storage may remain shared, but access must be checked per route.

## AI Locks

AI may be documented as future support, but v1.5 must not add AI tools that
write design quests, submissions, revisions, selections, promotions, rewards,
or timeline state.

Any future AI write path must follow the existing rule:

- AI proposes,
- user confirms,
- service layer writes,
- audit records the change.

## Testing Strategy

Each implementation build should get a dedicated test:

- `test_v15_build01.py`,
- `test_v15_build02.py`,
- etc.

Core regression categories:

- role and route blocking,
- designer-safe response shape,
- guarded file access,
- quest status transitions,
- submission/version preservation,
- revision loop,
- final promotion,
- explicit design completion,
- no PM internal data leakage.

Release hardening must include a scenario contract:

```text
PM creates quest
PM publishes quest
Designer sees safe quest
Designer submits v1
PM requests revision
Designer submits v2
PM selects final
PM promotes rendering
PM marks design complete
Designer never accesses PM project internals
```

## Feature Design Review

1. Real problem: PMs need a structured design-request/review loop without
   exposing internal project management data to designers.
2. Repeated use: every product needing visuals, renders, packaging, or design
   iterations can use this workflow.
3. Structured data: quests, submissions, versions, revisions, and source links
   require structured records.
4. Notes fallback: notes/chat cannot reliably preserve permissions, versions,
   source images, and revision history.
5. Intake burden: PMs enter one designer-facing brief instead of repeatedly
   re-explaining requirements in chat.
6. AI role: AI is deferred and must remain confirmation-only if added later.
7. Display payoff: PMs see design state in the project while designers see only
   the work they need.
8. Migration impact: v1.5 will require additive tables, starting Build 02.
9. Minimal schema: Build 01 has no schema; later builds add isolated workflow
   tables rather than changing core project semantics.
10. Minimal UI change: add the portal shell first, then one workflow surface per
   build.
11. Deferred: rewards, design library, champion submissions, annotation,
   designer social features, and AI write tools.
