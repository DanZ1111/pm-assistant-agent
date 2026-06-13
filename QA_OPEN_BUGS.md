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

### 🐛 Planning Sandbox is not reachable via UI navigation

**Discovered:** 2026-06-13, via blind QA suite run + targeted
discoverability scenario.

**Failing scenario:**
[`scenario_contracts/acceptance/sandbox_is_discoverable_from_project.py`](scenario_contracts/acceptance/sandbox_is_discoverable_from_project.py)

**Failure message:**
```
step 2 (PM looks for a visible link to the Planning Sandbox) check:
project detail page has at least one <a href=*/sandbox> link
(PMs need a clickable entry point to the Planning Sandbox):
expected True, got False
```

**PM-visible symptom:** From the project detail page (`/projects/{id}`)
there is no clickable link, button, or tab that leads to the Planning
Sandbox at `/projects/{id}/sandbox`. The route works and the page
renders if you type the URL, but PMs cannot find the feature through
normal navigation. The user reported it as:

> "I couldn't find the 'sandbox' or editor that has nodes, anywhere on
> this UI. Not a single way I can find out this section."

A grep of `app/templates/` confirms: zero references to `/sandbox`
outside `planning_sandbox.html` itself. The sandbox page has a
"back to project" link, but the project detail page has no
"forward to sandbox" link.

**Why it shipped despite existing UI tests:** every existing UI
scenario (`ui_sandbox_canvas_smoke`, `ui_sandbox_add_module`, the
acceptance journey, etc.) navigates **directly** to
`/projects/{id}/sandbox` via `actions.open_url`. None tests "can a
PM click their way to the sandbox?" The bug is invisible to
URL-driven testing — this is now **Rule 6** in
[SCENARIO_AUTHORING_GUIDE.md](SCENARIO_AUTHORING_GUIDE.md).

**Where the fix lives:** `app/templates/project_detail.html`. Add a
navigation entry to `/projects/{id}/sandbox`. Reasonable placements
(any one is enough to satisfy the regression test):

- A button in the Timeline tab near the phase strip (e.g. next to
  "Open Command Center")
- A third tab in the workspace tabs alongside "Overview" and
  "Timeline" (e.g. "Sandbox" or "Plan")
- A button in the Project Pulse "Attention Needed" card when
  appropriate
- A button in the section header bar somewhere always-visible

The regression test does not lock placement — it only requires that
SOME `<a href*="/projects/{id}/sandbox">` exists on the project
detail page.

**Verification:**
```bash
# Should report PASS: 1 and "3 steps OK" once the fix lands.
python3 -m scenario_contracts.lib.runner \
  scenario_contracts/acceptance/sandbox_is_discoverable_from_project.py

# Suite should be all-green:
bash run_qa_suite.sh
```

**Status:** OPEN — Codex domain (sandbox UI iteration).

**When fixed:** move this entry to "Recently fixed" below with the
commit hash and date.

---

## Recently fixed

(none yet — this file is new as of 2026-06-13)

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
