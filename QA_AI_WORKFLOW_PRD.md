# PRD — AI-Assisted PM Workflow QA Upgrade

## Summary

The current QA system is valuable, but it does not yet test the product like a
real PM. It runs deterministic build tests and authored scenario contracts, but
it still allowed Planning Sandbox issues to pass because the tested paths did
not fully match the user workflow.

This PRD proposes a QA upgrade where AI helps author and critique realistic PM
workflow scenarios, while deterministic Python/Playwright tests remain the final
release gate. AI should help us discover missing coverage and weak assertions;
it should not become a nondeterministic pass/fail judge.

## Problem

The sandbox failures exposed a coverage gap:

- Existing tests proved routes, services, selectors, and some browser surfaces.
- They did not prove that an unfamiliar PM could enter the sandbox, choose a
  template, see the graph appear, add modules, connect nodes, edit a selected
  node, recover back to the module library, inspect warnings, and understand
  apply status without the canvas jumping.
- The current scenario runner executes authored steps. It does not generate PM
  behavior, infer missing workflows, or decide that a workflow feels broken.

The result is a false sense of confidence: the app can pass tests while a real PM
still cannot complete the intended job.

## Goals

1. Test the system as a PM workflow tool, not only as isolated routes and
   components.
2. Add an explicit QA coverage matrix that maps PRDs, wireframes, user jobs,
   buttons, state changes, and scenario files.
3. Use AI to propose missing scenarios, critique weak tests, and review
   screenshots/reports.
4. Keep final pass/fail deterministic and reproducible.
5. Require critical acceptance journeys to verify UI truth plus at least one of:
   database truth, history/audit truth, or PM comprehension truth.

## Non-Goals

- Do not replace existing build tests.
- Do not make live AI output the release gate.
- Do not allow AI to silently mutate product data during QA.
- Do not build a free-roaming autonomous tester before deterministic scenario
  coverage is strong.
- Do not add product schema migrations for the initial QA upgrade unless a
  later implementation plan proves one is necessary.

## Current QA Behavior

The current QA stack has three useful layers:

- `test_build*.py` and version-specific regressions verify code, service, route,
  migration, i18n, source, and browser contracts.
- `scenario_contracts` can run deterministic DB, UI, and journey scenarios.
- `SCENARIO_AUTHORING_GUIDE.md` already states the right philosophy: acceptance
  journeys should ask whether a real PM would notice if the behavior broke.

The missing part is enforcement and coverage discipline. The runner can execute
good scenarios, but it cannot yet tell us which important PM workflows have no
scenario at all.

## Proposed QA Architecture

### 1. QA Coverage Matrix

Create a reviewable coverage matrix that tracks:

- feature area
- PRD or wireframe reference
- PM workflow/job
- UI entry point
- buttons or controls touched
- expected UI state
- expected DB state
- expected history/audit state
- expected PM comprehension outcome
- scenario file
- status: missing, drafted, automated, passing, failing, deferred

This becomes the source of truth for whether a feature is truly covered.

### 2. PM Workflow Scenario Library

Define business-event scenarios that resemble real PM work, for example:

- Factory returns a prototype and the engineer approves it.
- Supplier delay creates a blocker and pushes a due date.
- Quote received updates pricing context and history.
- Rendering is selected as final and appears in project overview/timeline.
- Sandbox plan runs Design and Engineering in parallel, then gates Prototype
  until both branches are complete.

Each scenario must state what the PM knows, what they do in the UI, and what the
system should show afterward.

### 3. Expanded Deterministic Actions And Assertions

Extend scenario helpers where needed for:

- project-scoped AI intake and confirmation flow
- timeline phase movement
- blocker/update/due-date actions
- sandbox template selection
- sandbox node add/edit/connect/delete
- sandbox graph/layout assertions
- file upload and rendering promotion
- history feed assertions
- no-silent-mutation assertions before user confirmation

Assertions should verify user-visible behavior, not only backend state.

### 4. AI Scenario Authoring Loop

AI reads the relevant PRD, wireframe, coverage matrix, existing tests, and recent
bug reports. It proposes missing scenarios and flags weak assertions.

The output is advisory. Codex, Claude Code, or a human reviewer converts approved
proposals into deterministic scenario files.

### 5. AI Coverage Critic

AI reviews scenario files, screenshots, and test reports and flags issues such
as:

- direct URL navigation without testing the real entry point
- DB-only acceptance journeys
- no rendered UI assertion
- no history/audit assertion where one is expected
- buttons visible but never clicked
- screenshots that show broken layout despite tests passing
- missing PM comprehension checks

### 6. Optional Live AI Draft Generator

A later build may add an environment-gated command that calls a configured LLM
to generate draft scenario proposals. It must only write reviewable draft output
or reports. It must not decide pass/fail and must not mutate app data.

## Example Target Scenario — Prototype Approved Through AI Intake

1. Create or load a project in Prototype Review.
2. PM opens project-scoped AI intake through the real project UI.
3. PM enters: "Factory returned the prototype and the engineer says it is good
   enough."
4. System proposes a journal/update and phase movement, but does not mutate the
   database before confirmation.
5. PM confirms.
6. Database records the update and phase change.
7. Timeline Command Center shows the new current phase and next action.
8. History feed shows a human-readable event.
9. The test fails if any mutation happens before confirmation.

## Example Target Scenario — Sandbox Parallel Planning

1. Navigate from Project Detail to Planning Sandbox through the visible UI.
2. Choose a template and verify the graph appears.
3. Add Design and Engineering modules as parallel branches.
4. Connect both branches into Prototype.
5. Set Design to 5 days and Engineering to 15 days.
6. Verify the visual graph shows parallel work, not a single vertical stack.
7. Verify Prototype starts after both upstream branches are complete.
8. Verify warnings are human-readable and apply status is understandable.

## Proposed Build Breakdown

### QA-v2 Build 01 — Coverage Matrix And Rules

- Add the QA coverage matrix format.
- Add scenario metadata expectations for feature, PRD reference, buttons touched,
  and truth tiers.
- Add a coverage/lint report that identifies uncovered critical workflows.

### QA-v2 Build 02 — PM Workflow Actions

- Expand deterministic scenario helpers for AI intake, timeline actions,
  sandbox interactions, and history assertions.
- Add stable selector requirements where scenarios need them.

### QA-v2 Build 03 — Sandbox Acceptance Journeys

- Add journeys for template use, graph appearance, node connection,
  selected-node recovery, parallel branches, warning comprehension, and apply
  readiness.

### QA-v2 Build 04 — Timeline And AI Intake Journeys

- Add journeys for prototype approval, delay/blocker handling, due-date changes,
  phase advancement, and history visibility.

### QA-v2 Build 05 — AI Reviewer Prompt Pack

- Add prompt templates/instructions for AI scenario generation and coverage
  critique.
- Keep this offline/manual first; no live model dependency required.

### QA-v2 Build 06 — Optional Live AI Draft Generator

- Add an environment-gated draft generator using a configured LLM.
- Output draft scenario proposals and review notes only.
- Do not make model output a release gate.

## Acceptance Criteria

- Every critical feature has at least one PM workflow acceptance scenario.
- Every acceptance scenario enters through the real UI path where practical.
- Every load-bearing scenario checks UI truth plus DB, history, or PM
  comprehension truth.
- Coverage reports show missing workflows before release.
- AI helps find gaps, but deterministic scripts remain the final gate.
- Sandbox and Timeline workflows are tested through realistic PM actions, not
  only route smoke tests.

## Risks

- More acceptance journeys can slow the suite. Use tags such as smoke,
  release-gate, and full.
- Live AI calls can be costly and nondeterministic. Keep them optional and
  advisory.
- Scenario quality depends on stable selectors and honest UI hooks.
- AI scenario proposals can sound plausible while missing implementation facts,
  so every proposal must be converted into deterministic tests before it counts.

## Assumptions

- Scenario files remain Python and build on the existing `scenario_contracts`
  runner.
- Existing `test_build*.py` files continue as regression tests.
- The deterministic runner remains the source of pass/fail truth.
- AI is used to author and critique QA coverage, not to judge releases directly.
- Claude Code should review this PRD before any QA-v2 implementation begins.
