# v1.3 Build 01 - Workspace Shell

## Summary

Create the Project Detail workspace boundary. Add Overview/Timeline tabs under the project header, move the existing Timeline section into the Timeline tab, and remove Commercial Snapshot as a promoted first section.

This build is information architecture only. No Timeline behavior redesign yet.

## Implementation Changes

- Add a compact tab control under the project header alerts:
  - `Overview`
  - `Timeline`
- Default tab is Overview.
- If the URL hash is `#timeline`, open the Timeline tab on load.
- Move the existing Timeline section and phase edit modal into the Timeline tab.
- Keep all non-Timeline sections in Overview.
- Remove `#commercial-snapshot` from the rendered page.
- Move created/updated dates into quiet metadata near Change Log.
- Do not promote project-level cost/MSRP as first-screen cards.
- If existing project-level target cost/MSRP must remain visible, render them only as low-priority facts, not as a named first section.
- No schema changes and no route changes.

## Explicit Deferrals

- No Project Pulse yet.
- No Timeline Command Center yet.
- No new Timeline actions.
- No Variant Card redesign.
- No Designer Portal placeholder.

## Tests

- Add `test_v13_build01.py`.
- Verify Overview tab is active by default.
- Verify Timeline content is hidden by default and shown when Timeline tab is clicked.
- Verify `/projects/{id}#timeline` opens Timeline tab.
- Verify no rendered `#commercial-snapshot` exists.
- Verify Product Thesis remains in Overview and is not in Timeline.
- Verify existing phase edit modal still opens from Timeline.
- Run `python3 test_build_v121.py`.
- Run desktop/mobile Playwright screenshots for Project Detail.

## Acceptance Criteria

- PM can clearly see Project Detail as two workspaces.
- No existing timeline route/action is broken.
- The first content section is no longer Commercial Snapshot.
