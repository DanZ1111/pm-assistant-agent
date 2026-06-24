# QA Agent 1.1 Plan — Sandbox Usability Acceptance

## Purpose

QA Agent 1.1 turns the user's Planning Sandbox complaints into deterministic
PM-facing acceptance checks. The goal is not a live AI tester yet. The goal is
to make QA fail when the sandbox route technically works but a PM cannot use
the planner to choose a template, add/connect steps, recover the module
library, and understand warnings.

## Feature Design Review

1. **Real workflow problem:** PMs need to visually plan a timeline without the sandbox feeling like floating disconnected cards and hidden controls.
2. **Repeated or edge-case:** Repeated, because sandbox planning is intended to be the normal pre-timeline planning workflow.
3. **Structured data:** No new product data; this build adds QA scenarios only.
4. **Could live in notes:** No, because the problem is workflow test coverage, not product data capture.
5. **Intake burden:** No added PM intake burden.
6. **AI reduce burden:** Deferred; this build is deterministic QA, not live AI scenario generation.
7. **Display/reminder payoff:** QA will now verify the PM-visible canvas, panel, template, warning, and connection behavior.
8. **Migration impact:** None.
9. **Minimal schema change:** None.
10. **Minimal UI change:** None planned; only add app changes if the new scenario exposes a true bug.
11. **Deferred:** Live LLM critic, screenshot judge, coverage matrix, and broader QA Agent 2.x work.

## Plan Quality Gate

12. **Primary user click-path:** create project via UI → click sandbox link from project detail → choose template → replace template → select node → connect workflow step → recover Modules tab → inspect Issues.
13. **Reference scan:** Skipped because this is an incremental QA build over the existing sandbox and scenario framework.
14. **Locked behaviors:**
- Sandbox acceptance must enter through a project-detail sandbox link, not direct URL only.
- Template chooser must open, close on repeated click, close on outside click, close on Escape, and applying a template must change the graph.
- Default module library must hide advanced/granular modules while preserving an Advanced filter.
- Selecting a canvas node must populate the Selected Node panel and must not show the no-node empty state.
- A visible Connect control plus canvas QA hook must create a dependency edge.
- Back to Modules must restore the module library after node edit/selection.
- Issues must show human-readable warning copy and hide raw warning codes from visible text.
- Warning summaries must live in the action bar/Issues panel, not as giant raw-code canvas blockers.
15. **Automated locks:**
- `test_qa_agent_1_1.py` source-locks the scenario file for project-detail navigation, template toggles, outside/Escape close, module filter checks, connect control, Back to Modules, warning copy, and raw-code absence.
- `sandbox_usability_acceptance.py` browser scenario fails when any locked PM-facing behavior breaks.

## Files Planned

- Add `scenario_contracts/acceptance/sandbox_usability_acceptance.py`.
- Add `test_qa_agent_1_1.py`.
- Update `HUMAN_JOURNAL.md` after the build lands.

## Test Plan

```bash
python3 -m py_compile \
  scenario_contracts/acceptance/sandbox_usability_acceptance.py \
  test_qa_agent_1_1.py

python3 test_qa_agent_1_1.py

BASE_URL=http://127.0.0.1:8001 python3 -m scenario_contracts.lib.runner \
  scenario_contracts/acceptance/sandbox_usability_acceptance.py

python3 test_v14_sandbox_ui_rescue.py
python3 test_qa_build12.py
```

Browser-backed acceptance may skip when the dev server is unreachable, but the
release/manual run must start the app and run it against the live UI.

