# v1.5 PRD — Designer Portal & Rendering Workflow MVP

## Status

Product requirements document for review.

This is a plan-only artifact. No code, schema, route, migration, or test
implementation is included in this PRD commit.

## Product Summary

v1.5 adds a lightweight Designer Portal inside the existing PM Assistant
codebase. It is not a second product and not a full designer management
system.

The product model is:

- PMs work inside the existing Project Detail page, primarily through
  `Renderings & Design`.
- Designers work inside a restricted `/designer` portal.
- Both experiences share backend data and file storage.
- The two experiences must not share UI or permission surfaces.

Core workflow:

```text
PM publishes design quest
-> designer views restricted brief/references
-> designer submits image
-> PM reviews in project Renderings & Design
-> PM requests revision or selects final
-> designer submits revised version
-> PM promotes selected image to project rendering
-> PM explicitly marks design complete
```

## Problem

The current rendering workflow relies on informal messages, manual file
collection, and hand-maintained rendering sections. This creates several
business problems:

1. PM design briefs, references, deadlines, and revision feedback scatter
   across chat.
2. Designer submissions are not automatically linked to the project.
3. Multi-designer review, shortlist, rejection, and revision loops are hard to
   track.
4. Final selected images must be manually copied into project renderings.
5. Design completion does not naturally appear in project execution status.
6. Designers should not see project timeline, cost, MSRP, factory, supplier,
   quotation, PM journal, or internal PM data.

## Product Principle

One backend, two experiences:

```text
PM Workspace       -> internal project command center
Designer Portal   -> restricted brief/submission workflow
Shared Backend    -> quests, submissions, versions, revisions, files, audit
```

Designer Portal is a controlled submission surface, not a full project
management system for designers.

## Roles

### PM

PMs remain inside the PM Workspace. They can:

- create, edit, publish, and close design quests for their projects,
- upload designer-facing reference files,
- set soft deadlines,
- choose open-to-all-designers or assigned-designer visibility,
- review all submissions for their project quest,
- shortlist, reject, request revision, and select final submissions,
- promote selected submissions to project renderings,
- explicitly mark design complete.

### Designer

Designers use only the Designer Portal. They can:

- view available or assigned quests,
- view designer-facing brief fields and references,
- upload design submissions,
- add notes to PM,
- view their own submission status,
- view PM revision requests for their own submissions,
- upload revised versions.

Designers must not see:

- `/projects/:id` pages,
- timeline,
- cost/MSRP,
- factory/supplier/quotation,
- PM journal,
- internal project metadata,
- other designers' private submissions or feedback.

### Designer Manager

Designer manager is a portal operations role, not a PM/admin equivalent.

Designer managers may eventually:

- manage designer accounts,
- assign designers to quests,
- archive/delete abnormal portal-only content,
- grant extension/unlock exceptions,
- reopen or administratively adjust submission/revision states when needed.

Designer managers must not receive broad PM Workspace access by default and
must not see PM-only project data unless a later reviewed build explicitly
grants a narrow, designer-safe view.

### Admin

Admins remain system administrators and can manage all data. Admin behavior
should be explicit in each implementation build.

## MVP Scope

In scope:

- `Renderings & Design` PM-side project section.
- Designer-facing quest brief and references.
- Soft deadline.
- Publish/close quest.
- Designer dashboard and quest detail.
- Designer upload submission.
- Submission versions.
- PM review actions:
  - shortlist,
  - reject,
  - request revision,
  - select final,
  - promote to project rendering.
- Structured revision checklist.
- Permission-filtered Designer Portal.
- Guarded file routes for designer-visible files.
- Explicit design-complete action that can affect Timeline/Pulse display.

Out of scope for v1.5:

- AI write access to design quest/submission state.
- Reward points.
- Leaderboards.
- Design library / unused asset library.
- Champion submission cycles.
- Figma-style image annotation.
- Real-time commenting.
- External client sharing.
- Separate service/mobile app.
- Designer social features.
- Complex copyright or contract management.

## PM-Side Requirements

The project rendering section becomes `Renderings & Design`.

PM-side layout should contain:

1. Selected / Final Renderings.
2. Active Design Quest.
3. Incoming Submissions.
4. Revision Requests.

### Selected / Final Renderings

Requirements:

- Show selected rendering if present.
- If selected rendering comes from a design submission, show source
  submission, designer, selected by, and selected date.
- PM can replace selected rendering.
- PM can manually upload renderings as fallback.
- Selected rendering remains visible in normal project rendering context.

### Active Design Quest

Requirements:

- One active quest per project is acceptable for MVP.
- Quest supports draft and published states.
- Designers cannot see draft quests.
- PM can edit published quest; `updated_at` must change.
- Brief version history is preferred if cheap, but not required for MVP.
- PM can close quest to stop new submissions.
- PM can preview the designer-safe view.

Fields:

- title,
- designer-facing brief,
- must keep,
- must avoid,
- reference files,
- soft deadline,
- visibility type,
- assigned designers if assignment ships in that build.

### Incoming Submissions

Requirements:

- PM sees all submissions for the quest.
- PM can filter by status.
- PM can open large preview.
- PM sees designer note and version history.
- PM can shortlist, reject, request revision, or select final.
- Selecting final must ask for confirmation before promotion.

### Revision Requests

Requirements:

- Revision request can contain multiple checklist items.
- Designer sees revision request for their own submission.
- Designer can upload a new version in response.
- PM can see which revision request caused which version.
- MVP does not require image annotation.

## Designer Portal Requirements

### Dashboard

Requirements:

- Route family: `/designer`.
- Designer sees only quests they can access.
- Dashboard has available/open quests, own submissions, and needs-revision
  states.
- No full project page links or PM Workspace chrome.

### Quest Detail

Requirements:

- Show only designer-facing fields:
  - quest title,
  - brief,
  - must keep,
  - must avoid,
  - reference files,
  - soft deadline,
  - quest status.
- Designer can upload image submissions while quest allows submission.
- Closed quests disable upload but allow the designer to view prior relevant
  submissions.
- Upload validates file type and size.

### Submission Detail

Requirements:

- Designer sees their own current version.
- Designer sees PM revision checklist and general comment.
- Designer can upload revised version.
- Old versions are preserved.
- Designer cannot mutate old submitted files directly.

## Data Model Requirements

The implementation should add structured design workflow tables instead of
overloading `project_files` alone.

Likely tables:

- `design_quests`
- `design_quest_assignments`
- `design_quest_references`
- `design_submissions`
- `design_submission_versions`
- `design_revision_requests`
- `design_revision_items`
- `project_renderings` or equivalent source metadata if existing rendering
  storage is extended

Important fields:

- Quest status: `draft`, `open`, `reviewing`, `revision_needed`, `selected`,
  `closed`, `cancelled`.
- Submission status: `submitted`, `shortlisted`, `revision_requested`,
  `revised`, `selected`, `rejected`, `archived`.
- Revision status: `open`, `partially_resolved`, `resolved`, `cancelled`.
- Quest visibility: `all_active_designers` or `assigned_designers_only`.
- Timeline integration fields: `is_timeline_blocking`, `linked_phase_id`.

## File Requirements

Accepted MVP types:

- jpg,
- jpeg,
- png,
- webp,
- pdf optional.

Recommended MVP file size limit:

- 20 MB per file.

File handling lock:

- Designer-visible files must not use raw public `/uploads/...` links.
- Designer-visible files must be served through guarded routes that check the
  current user, quest visibility, and submission ownership.
- Existing physical file storage may be reused, but design workflow source
  links must be explicit.

## Permission Requirements

Server-side enforcement is mandatory.

Designer quest access:

- user role must be `designer` or `designer_manager` as appropriate,
- quest must be visible to that designer,
- draft quests are invisible to regular designers,
- response shape must include designer-safe fields only.

Designer submission access:

- regular designer can access only their own submissions,
- designer manager access must be explicitly scoped to portal operations.

PM project submission access:

- PM/admin must pass existing project access checks.

Project page block:

- `designer` and `designer_manager` must not access PM project pages in Build
  01.

## Timeline Integration

Timeline integration must be display/explicit-action only.

Rules:

- Quest may be marked timeline-blocking.
- Pulse/Timeline may display design status:
  - waiting for submissions,
  - PM review needed,
  - revision requested,
  - final selected,
  - design complete.
- Selecting a final submission must not automatically finish a phase.
- PM must explicitly click `Mark Design Complete`.
- Any later phase update must go through existing timeline service rules and
  audit behavior.

## Audit Requirements

MVP should record important events:

- quest created,
- quest published,
- quest edited,
- quest closed,
- submission uploaded,
- submission shortlisted,
- revision requested,
- revised version uploaded,
- submission selected,
- submission rejected,
- submission promoted to project rendering,
- quest marked complete.

Whether these appear in Timeline History can be staged later, but backend
records must exist before relying on them.

## Acceptance Criteria

1. PM can create a draft quest and designers cannot see it.
2. PM can publish a quest and allowed designers can see it.
3. Designer sees only designer-facing fields.
4. Designer can submit a valid image.
5. PM can see the submission in Renderings & Design.
6. PM can request revision with checklist items.
7. Designer can upload a revised version linked to the revision request.
8. PM can select final and promote it to project rendering.
9. PM can explicitly mark design complete.
10. Designer attempts to access `/projects/:project_id` are blocked
    server-side.

## Future Extensions

Deferred beyond v1.5:

- design asset library,
- champion submission cycles,
- reward points,
- manual reward adjustments,
- designer ranking,
- image annotation,
- side-by-side visual diff,
- real-time comments,
- external client review.

## Final Product Decision

Designer Portal should be built inside PM Assistant as a separate restricted
portal. PM review stays in the project. Designers submit and revise in the
portal. Selected designs flow into project renderings. Design completion can
unblock timeline only through explicit PM action.
