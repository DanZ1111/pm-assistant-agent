# v1.3 UI Rework Expectation Reset

## Status

v1.4 Planning Sandbox work is paused. The shipped v1.3 Project Detail UI does not meet the original product expectation for a PM command center.

This document is not an implementation plan yet. It is a reset document to realign Codex, Claude Code, and ChatGPT on what the user expected before any repair build starts.

## Source Documents Read

- `/Users/Mordred5687/Downloads/project_overview_redesign_plan.md`
- `/Users/Mordred5687/Downloads/timeline_command_center_redesign_plan.md`
- `V13_MASTERPLAN.md`
- `V13_BUILD06_TIMELINE_COMMAND_CENTER_SHELL_PLAN.md`
- Current `app/templates/project_detail.html`
- Current `app/static/css/styles.css`
- Current `app/templates/base.html`

## User Feedback Trigger

The production v1.3 Timeline screenshot at `/projects/7#timeline` looks raw and unfinished:

- Phase strip renders as a vertical list instead of a designed lifecycle strip.
- Command Center text appears uncontained, with almost no visual grouping.
- Timeline History filter chips look like default browser buttons.
- The bottom AI composer overlays Timeline actions and hides content.
- The page feels like raw HTML plus scattered buttons, not a PM execution workspace.
- The result is visually far below the user's expectation and should not be treated as a successful UI release.

## Critical Technical Finding

`base.html` loads static assets without versioning:

```html
<link href="/static/css/styles.css" rel="stylesheet">
<script type="module" src="/static/js/main.js"></script>
```

This creates a realistic production failure mode:

- HTML updates to v1.3 markup.
- Browser/CDN keeps an older cached `styles.css`.
- New v1.3 classes such as `.timeline-phase-strip`, `.timeline-history-chip`, and `.timeline-command-center` render with default browser styling.

The screenshot strongly resembles this cache/stale-asset mismatch: navbar styling exists, but new v1.3 Timeline-specific styling appears absent.

This does not excuse the design failure. It means the repair work needs both:

1. asset cache-busting/deploy verification, and
2. actual UI redesign quality improvements.

## Original Product Expectation

The original Timeline PRD says the Timeline tab should be a PM execution command center, not a passive table or raw progress display.

The PM should usually be able to complete daily timeline work from the first section:

```text
Open Timeline
See current phase and next action
Record update / add blocker / adjust due date / finish phase
Leave
```

The intended page hierarchy is:

1. Timeline Command Center
2. Timeline Map / Phase Overview
3. Timeline Updates / History
4. Future Planning Sandbox / Templates

The current v1.3 implementation technically contains some of these labels, but it does not communicate the hierarchy visually.

## What The Timeline First Fold Should Feel Like

The first Timeline screen should feel like a compact operating dashboard for one project.

Required first-fold visual structure:

```text
TIMELINE COMMAND CENTER

[Phase strip: Done -> Done -> Current -> Next -> Later]

[Current Phase]       [Next Action]             [Deadline]
Sample Development    Confirm sample status     Due Jun 12
Health: At Risk       Owner: Factory / PM       3 days left

[Main Blocker]                         [AI Nudge]
Packaging cost missing                 Ask factory for quote today

[Add Update] [Add Blocker] [Adjust Due Date] [Finish Current Phase] [AI Intake]
```

This should be one visually coherent command card, not scattered independent blocks.

## What The Current Implementation Got Wrong

### 1. Backend honesty was treated as enough

The v1.3 plan correctly required honest backend sources. But the implementation treated "honest fields exist" as sufficient. The PRD also required a polished PM workflow surface.

The result is accurate-ish data in a poor interface.

### 2. The phase strip is not a usable phase strip

Expectation:

- one horizontal lifecycle strip,
- compact phase nodes,
- done/current/next/later states,
- instant global position awareness.

Current failure:

- screenshot shows a vertical list of icons and phase names,
- arrows appear on separate lines,
- no professional lifecycle-track composition.

### 3. Command Center is not visually contained

Expectation:

- one top-level command center container,
- internal 3-card summary,
- blocker and AI nudge as subordinate areas,
- action buttons grouped at the bottom of the command center.

Current failure:

- fields appear as loose text,
- sections do not feel related,
- actions sit under/behind the AI composer.

### 4. Timeline Map is still basically a table wrapper

Expectation:

- "Timeline Map / Phase Overview" should be an overview surface,
- current phase expanded,
- old planned/actual table hidden behind an expand control.

Current failure:

- user sees a large "Timeline" heading and "Detailed Table" control,
- no useful phase-map overview exists between Command Center and table.

### 5. Timeline History is too raw

Expectation:

- review/audit feed with typed, readable event cards,
- filter chips that look like app controls,
- events that are scannable.

Current failure:

- chips look like default buttons when CSS is absent,
- even with CSS, history is more like a formatted list than a polished event feed.

### 6. The assistant dock conflicts with Timeline actions

Expectation:

- assistant is a separate workspace assistant,
- it should never hide critical project actions.
- PMs can collapse the bottom composer out of the way and re-expand it quickly when they need AI.

Current failure:

- bottom composer overlays the Timeline action row.
- this makes the main workspace feel broken and cheap.
- the dock is expanded by default and has no explicit "get out of my way" collapsed state.

### 7. Tests did not protect visual quality

The v1.3 tests largely verified:

- routes exist,
- markup exists,
- data sources are honest,
- state transitions work.

They did not sufficiently fail when:

- CSS is stale/missing,
- buttons render as default browser controls,
- major sections collapse into raw text,
- the assistant composer overlaps important actions,
- desktop/mobile screenshots look unacceptable.

## Reset Principles

1. Do not continue v1.4 UI work until v1.3 Project Detail is repaired.
2. Separate emergency production styling fixes from deeper UX redesign.
3. Treat the original PRDs as the source of product expectation.
4. The Timeline first fold must look like an execution dashboard, not a list.
5. The Overview first fold must look like a product understanding dashboard, not a database record.
6. Asset cache-busting is mandatory before any future UI release.
7. Playwright screenshot checks must become release-blocking for these UI surfaces.
8. User-facing placeholder labels should be reduced. If something is future-only, it should read naturally, not like an engineering artifact.
9. The assistant composer must not cover core project actions.
10. The assistant composer must be manually collapsible to a small, easy-to-restore affordance.
11. No new feature scope should be added during the rescue unless it directly fixes the PM workflow.

## Proposed Repair Sequence

### Repair Build 0 - Production CSS and Asset Sanity

Goal: make sure deployed pages actually load current CSS/JS.

Scope:

- Add versioned static asset URLs, for example `styles.css?v={{ APP_VERSION }}` or a stronger build hash.
- Verify production page includes v1.3 CSS selectors in the loaded stylesheet.
- Add a simple smoke test that opens Project Detail Timeline and asserts:
  - `.timeline-phase-strip` computed display is `flex`,
  - `.timeline-history-chip` border radius is not default,
  - `.timeline-tiles-grid` computed display is `grid`,
  - AI composer does not overlap the Command Center action row.

No product redesign yet. This is a deployment/styling correctness fix.

### UI-R2 - Timeline Command Dashboard

Goal: make Timeline match the original PRD first.

Scope:

- Rename the first section visually to "Timeline Command Center."
- Wrap the full first fold in one strong command-center container.
- Redesign phase strip as a real horizontal lifecycle track.
- Redesign Current Phase / Next Action / Deadline as equal dashboard cards.
- Put Main Blocker and AI Nudge into a second row inside the same command center.
- Put actions in a stable action bar inside the command center.
- Replace "AI Nudge Placeholder" wording with user-facing language such as "AI Suggestion coming later" or hide the nudge block until it has real value.

No new backend logic unless needed for layout-safe data.

### UI-R3 - AI Composer Overlap + Collapse Control

Goal: make the assistant composer feel like a useful companion, not a permanent obstruction.

Scope:

- Ensure the bottom AI composer never covers Timeline Command Center actions.
- Add a clear collapse control on or near the composer.
- Default state remains expanded, preserving current ChatGPT-like availability.
- Collapsed state should move the composer out of the workspace, preferably below the screen edge or to a compact side/bottom affordance.
- Collapsed state should leave only a small, professional re-open button that is easy to find and does not cover primary project actions.
- Re-expanded state restores the previous composer mode, scope, and drafted text where practical.
- The assistant side panel can remain separate, but the bottom dock should not fight the main project workspace.
- Add Playwright bounding-box checks proving `.timeline-action-row` is not overlapped when the composer is expanded and when collapsed.
- Add screenshot proof for expanded and collapsed states on desktop and a narrow viewport.

No new AI behavior, routes, model calls, or database changes.

### UI-R4 - Timeline History Visual Rescue

Goal: make history feel like a typed audit feed.

Scope:

- Redesign filter chips as polished segmented controls.
- Render event rows as compact cards with timestamp/type/summary/meta.
- Reduce default visual noise.
- Keep filters and derived event logic unchanged unless bugs appear.

### Later - Timeline Map / Phase Overview

Goal: create the missing middle layer between Command Center and detailed table, after the rescue stabilizes.

Scope:

- Add a dedicated "Timeline Map / Phase Overview" section.
- Reuse phase data to show a larger phase overview.
- Expand the current phase card by default.
- Keep the old planned/actual table behind an explicit "Detailed planned vs actual table" expand control.
- Move Add Phase into the detailed/table area, not the main command center.

### Repair Build 4 - Overview Visual Review

Goal: review whether Overview also failed the PRD before adding new features.

Scope:

- Compare current Overview against the overview PRD.
- Verify Project Pulse, Product Concept, Renderings, Variants, Files, Metadata hierarchy.
- Fix only visual hierarchy and section placement unless data bugs are found.

## What Not To Do

- Do not continue v1.4 drag/drop sandbox work yet.
- Do not add new planning sandbox UI until Project Detail v1.3 is acceptable.
- Do not treat backend correctness tests as proof that the UI is good.
- Do not ship another UI build without screenshots.
- Do not rely on the user to hard-refresh browser cache to see a release.

## Acceptance Standard For The Rescue

Before v1.3 Project Detail is considered repaired:

- Desktop Timeline screenshot should visually resemble the PRD wireframe in structure.
- Mobile Timeline screenshot should stack cleanly without overlap.
- Production deployment should load fresh CSS/JS without manual cache clearing.
- Bottom AI composer should not cover project actions.
- Timeline Command Center should complete the normal PM daily workflow from the first section.
- Detailed table should feel secondary.
- History should look like an audit feed, not raw controls.

## Open Questions For User Review

1. Should the immediate next task be Repair Build 0 only, so production stops showing raw CSS?
2. Should Repair Build 1 redesign Timeline first, before Overview?
3. Should the AI Nudge block be hidden until it has real backend/AI value, instead of showing placeholder text?
4. Should the bottom assistant composer collapse automatically on Timeline when it overlaps action rows?
5. Should v1.4 uncommitted work be parked in a commit/branch before the rescue work starts?
