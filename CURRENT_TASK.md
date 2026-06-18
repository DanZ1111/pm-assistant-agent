# CURRENT_TASK.md

Short relay note for the next session (Claude or Codex). For full
history use `git log`. For why decisions were made, see linked plans.

## In flight (2026-06-18)

**Just landed (`fa74c1a`, `0841b9c`):**
- Sandbox follow-ups: Connect button mode, `replace_existing` for the
  template picker, QA hooks for canvas-bypass tests, and the
  **SB-Rescue-03 stay-on-Modules lock** restored after drift.
- QA Build 12: AI prototype-approval confirmation guard + sandbox
  parallel planning + sandbox template/connection scenarios.

**Next up (Step 2 of approved plan
[`~/.claude/plans/can-you-still-find-nested-cook.md`](../../.claude/plans/can-you-still-find-nested-cook.md)):**
1. Extend [FEATURE_DESIGN_PROCESS.md](FEATURE_DESIGN_PROCESS.md) with
   Q12–Q15 (Plan Quality Gate). ≤40 new lines.
2. Add Spec Drift Gate section to [CLAUDE.md](CLAUDE.md) with the
   auto-select-after-add worked example. ≤30 new lines.
3. Back-port the QA-11 vetoes lock and verify Rule 6 has an
   automated check.
4. Commit C: process changes only.

**Then deferred:** Phase 2 markdown audit — produces a report only,
no file moves without approval.

## Lesson Codex must internalize (the reason for Step 2)

The SB-Rescue-03 stay-on-Modules behavior was a 5-line lock buried
inside a 400-line plan. The QA-12 session three days later silently
contradicted it by rewriting `addModule()` to auto-select the new
node — because that made the QA-12 scenario shorter. The regression
surfaced only when `ui_sandbox_add_module` went red in the full suite.

**The lesson is structural, not "be more careful":** prose locks
decay across sessions. Every approved UX/data/permission lock now
must ship with an automated test assertion in the same commit
(regex source-pin for structural locks, behavior test for observable
ones). The Spec Drift Gate in CLAUDE.md (landing in Commit C) makes
this a discipline rule.

## Locks Codex must respect right now

- **SB-Rescue-03 (locked in `fa74c1a`):** `addModule()` in
  [planning_sandbox.js](app/static/js/planning_sandbox.js) ends on
  the Modules tab and does NOT call `selectNode(createdNodeId)`.
  Enforced by `test_sb_rescue_03_stay_on_modules_lock` in
  [test_v14_sandbox_ui_rescue.py](test_v14_sandbox_ui_rescue.py).
- **QA-11 vetoes:** no coverage matrix, no live LLM scenario
  generator, no AI release-gate judge. Documented in
  [QA_BUILD11_EXECUTION_PLAN.md](QA_BUILD11_EXECUTION_PLAN.md) and
  the revised [QA_AI_WORKFLOW_PRD.md](QA_AI_WORKFLOW_PRD.md).
  (Automated lock to be added in Commit C.)
- **Rule 6:** UI scenarios must reach features through real PM
  navigation, not `actions.open_url` only. See
  [SCENARIO_AUTHORING_GUIDE.md](SCENARIO_AUTHORING_GUIDE.md).
- **Cytoscape canvas testability gap:** per-node DOM clicks are
  impossible (canvas-rendered). Scenarios use the
  `window.__planningSandboxQA.*` JS hooks as the documented
  workaround. Real `[data-sandbox-connect-from]` button clicks
  are still required for the connect-mode click path.

## Where to look for context

- `git log` from `2108527` forward — sandbox rescue → QA-12 → drift
  fix.
- `~/.claude/plans/can-you-still-find-nested-cook.md` — approved
  Two-Gate Process plan + locked decisions.
- [V14_SANDBOX_UI_RESCUE_PLAN.md](V14_SANDBOX_UI_RESCUE_PLAN.md) —
  the 400-line plan whose SB-Rescue-03 lock decayed; canonical
  example of why the Spec Drift Gate exists.
- [QA_OPEN_BUGS.md](QA_OPEN_BUGS.md) — curated bug surface; check
  before opening new work.
