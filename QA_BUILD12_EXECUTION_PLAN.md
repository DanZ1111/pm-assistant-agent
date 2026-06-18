# QA Build 12 Execution Plan — PM Workflow Agent Journeys

## Purpose

QA Build 12 applies the lesson from the Planning Sandbox miss: write realistic
PM journeys first, not more QA meta-tooling. The useful "agent" here is the
scenario authoring pattern: a PM narrative is translated into deterministic
steps, predicted system state, and repeatable assertions.

## Scope

In:

- Add one DB-level AI confirmation journey proving AI proposal guards prevent
  silent mutation before user confirmation.
- Add one browser-backed sandbox journey proving a PM can build a parallel plan
  and see dependency edges/timing behavior.
- Add only the helper assertions/actions required by those journeys.
- Add `test_qa_build12.py` to lock the new scenario files and run them.

Out:

- No coverage matrix.
- No live LLM scenario generation.
- No live LLM release gate.
- No product version bump.
- No broad QA framework rewrite.

## Locked Decisions

1. Deterministic scripts remain the release gate.
2. AI is represented through the real `app.ai.tools.dispatch()` confirmation
   contract, not through nondeterministic live model calls.
3. Browser acceptance journeys must enter features through PM-visible UI paths
   when practical.
4. Each journey must catch at least one bug class normal build tests can miss.
5. Helper expansion is bottom-up: add only what the scenario needs.

## Planned Scenarios

### 1. AI Prototype Approval Confirmation

Narrative: the factory returns the prototype and the engineer says it is good
enough. AI proposes recording the update and moving the project forward.

Required proof:

- unconfirmed `create_journal_entry` returns `confirmation_required`;
- journal/history rows do not change before confirmation;
- confirmed journal writes the PM update;
- unconfirmed `finish_phase` returns `confirmation_required`;
- Prototype Review does not move before confirmation;
- confirmed finish moves Prototype Review to done and advances the next phase.

### 2. Sandbox Parallel Planning

Narrative: a PM needs Design and Engineering to run in parallel, then Prototype
can start only after both branches are connected upstream.

Required proof:

- PM reaches sandbox from a real project;
- template/blank draft loads a canvas;
- adding/connecting nodes creates visible edges;
- parallel branches are represented by two upstream nodes connected to one
  downstream prototype node;
- timing behavior reflects the longer upstream branch;
- issues/apply status remain understandable.

## Test Plan

```bash
python3 -m py_compile \
  scenario_contracts/journeys/ai_prototype_approval_confirmation.py \
  scenario_contracts/acceptance/sandbox_parallel_planning_workflow.py \
  test_qa_build12.py

python3 -m scenario_contracts.lib.runner \
  scenario_contracts/journeys/ai_prototype_approval_confirmation.py

python3 -m scenario_contracts.lib.runner \
  scenario_contracts/acceptance/sandbox_parallel_planning_workflow.py

python3 test_qa_build12.py
python3 test_qa_build11.py
python3 test_v14_sandbox_ui_rescue.py
python3 test_build_v121.py
```

Browser-backed acceptance scenarios may skip if the dev server is unreachable;
that skip is acceptable only for local environments where the server is not
running. A full release check should run them against `python run.py`.
