# QA Open Bugs

Bugs the QA system has surfaced that need `app/*` fixes. Each entry is
what Codex (or any contributor) needs to act on.

## How to use this file

If you're picking up work on this project:

1. **At session start**, check this file — it's where the QA system
   surfaces what's currently broken in PM-visible terms.
2. **Run the suite** to see live state:
   ```
   bash run_qa_suite.sh
   ```
3. **Open this file** for the curated list of what's known broken,
   including: which scenario is RED, what the failure message is,
   what the PM-visible symptom is, and where the fix lives.
4. **Pick a bug**, land the fix in `app/*`, then verify the failing
   scenario flips to GREEN:
   ```
   python3 -m scenario_contracts.lib.runner <path-to-scenario>
   ```
5. **Move the entry** from the "Open" section below to the "Recently
   fixed" section and commit. The next contributor will see the
   history and trust that the QA system catches what it claims to.

## Discipline

This file is **curated by humans / handoff agents**, not auto-generated
(yet). Reasons:
- Auto-generation from the suite log would include every flaky run
  and every transient timeout, drowning real signal.
- A human (or claude/codex on handoff) is in the best position to
  distinguish "QA scenario is wrong" from "real bug" before promoting
  to this file.

If the suite goes RED and you cannot tell whether it's a real bug or
a scenario regression, **first investigate**. If it's a real bug,
add an entry here. If it's a scenario bug, fix the scenario.

---

## Open

(none)

---

## Recently fixed

### ✅ SB-Rescue-03 stay-on-Modules lock restored after silent drift

**Discovered:** 2026-06-18, via the full QA suite. `test_qa_build07`
and `release_gate scenarios` both went RED on the same root cause —
`ui_sandbox_add_module` failed because `.sandbox-add-module-btn` was
no longer visible after clicking Add. Investigation revealed
`addModule()` had been silently rewritten in a later session to call
`selectNode(createdNodeId)` instead of `setActiveTab('modules')`,
which contradicted SB-Rescue-03 §3 "Add-module behavior" but matched
the QA-12 scenario's shorter loop. Plan vs. implementation drift
across a session boundary.

**Fixed:** 2026-06-18, commit `fa74c1a`. `addModule()` in
[app/static/js/planning_sandbox.js](app/static/js/planning_sandbox.js)
now always ends on the Modules tab and clears `selectedNodeId`. The
one-shot auto-connect from a pre-Add source node is preserved.

**Automated lock added** (`test_sb_rescue_03_stay_on_modules_lock` in
[test_v14_sandbox_ui_rescue.py](test_v14_sandbox_ui_rescue.py)): the
addModule body must contain `setActiveTab('modules')` and must NOT
contain `selectNode(createdNodeId)`. This prevents the same drift
from happening silently in a future session.

**Larger lesson** (driving the QA-v2 Spec Drift Gate work in flight):
prose locks inside long plans decay across sessions. Every approved
UX/data/permission lock should ship with an automated assertion in
the same commit. See the approved plan
`~/.claude/plans/can-you-still-find-nested-cook.md` and the
forthcoming Spec Drift Gate addition to CLAUDE.md.

**Verification:**
```bash
python3 test_v14_sandbox_ui_rescue.py   # 10/10 PASS (with new lock)
bash run_qa_suite.sh                    # PASS: 15 / FAIL: 0
```

### ✅ Planning Sandbox is reachable via UI navigation

**Discovered:** 2026-06-13, via blind QA suite run + targeted
discoverability scenario.

**Fixed:** 2026-06-13, pending commit.

**Scenario now green:**
[`scenario_contracts/acceptance/sandbox_is_discoverable_from_project.py`](scenario_contracts/acceptance/sandbox_is_discoverable_from_project.py)

**Fix:** `app/templates/project_detail.html` now exposes
`/projects/{id}/sandbox` from the project workspace bar and from the
Timeline Command Center action row. `app/static/css/styles.css` styles
the workspace-bar link so it reads as an intentional project-planning
entry point.

**Verification:**
```bash
env BASE_URL=http://localhost:8001 python3 -m scenario_contracts.lib.runner \
  scenario_contracts/acceptance/sandbox_is_discoverable_from_project.py
```

Result: `PASS: 1 | FAIL: 0 | INVALID: 0 | SKIP: 0`.

---

## Related files

- [SCENARIO_AUTHORING_GUIDE.md](SCENARIO_AUTHORING_GUIDE.md) — the 6
  hard rules for new scenarios; Rule 6 was added the day this file
  was created (and was discovered by the same investigation)
- [UI_TESTABILITY_GAPS.md](UI_TESTABILITY_GAPS.md) — gaps in stable
  selectors that have proposed `app/*` patches; not bugs per se,
  but coverage that's blocked on small template changes
- [STABLE_CREDIBILITY.md](STABLE_CREDIBILITY.md) — promotion rule
  for scenarios; once a fix lands and a scenario stays green across
  10 loop runs, it's eligible for stable promotion
- [QA_ROADMAP.md](QA_ROADMAP.md) — full QA series plan + history
