# Scenario Authoring Guide

This document locks the rules for writing new QA scenarios (by Codex,
Claude, the user, or anyone else). Authoring is the load-bearing
output of the QA system; if scenarios slip toward "test what the code
obviously does," the system loses its value. The rules below are the
fence.

The guide assumes you've already read [STABLE_CREDIBILITY.md](STABLE_CREDIBILITY.md)
(the promotion rule) and [QA_BUILD11_EXECUTION_PLAN.md](QA_BUILD11_EXECUTION_PLAN.md)
(why the acceptance tier exists).

---

## The one question that decides whether a scenario belongs

> **Would a real PM, using the system to ship a real project,
> notice if this scenario broke?**

If the answer is "no" (the regression is invisible to PMs because
it's a developer-facing concern), the scenario probably belongs in a
per-build `test.py`, not in `scenario_contracts/`.

If the answer is "yes" — and you can name a specific way a PM would
notice (UI showing wrong state, Timeline missing the WHY,
Variant page out of sync with Overview, viewer seeing a forbidden
field, 10 steps in PM confused about next action) — the scenario
belongs here, and the rest of this guide applies.

---

## The four kinds of truth

Every load-bearing scenario step must check at least one of these
four kinds of truth. **DB truth alone is no longer enough.**

| Truth tier | What it means | Examples in the library |
|---|---|---|
| **DB truth** | Did the right rows get written? | `assertions.assert_db_field`, `assert_row_count`, `assert_history_contains` (text in `project_changes`) |
| **UI truth** | Does what the PM sees match the DB? | `pm_views.assert_variant_card_present`, `assert_project_findable_on_index_and_detail` |
| **History truth** | Can someone reconstruct *why* the state changed? | `pm_views.assert_history_row_with_type_contains` |
| **PM comprehension** | Could a real PM look at the page and know what to do next? | `pm_views.assert_command_center_current_phase`, `assert_command_center_next_action`, `assert_command_center_health_band`, `assert_active_blocker_count_on_phase_strip` |

Contract scenarios under `contracts/` typically check DB + maybe
history truth. Journey scenarios under `journeys/` chain those.
**Acceptance journeys under `acceptance/` MUST exercise UI truth and
at least one of {history truth, PM comprehension} per load-bearing
step.**

---

## The 6 hard rules

### Rule 1: No DB-only acceptance journeys

`acceptance/<journey>.py` must call at least one `pm_views.assert_*`
function per load-bearing step. If you find yourself writing
`assertions.assert_*` for every `check_*` function in an acceptance
journey, you're writing a `journey/`, not an `acceptance/`. Move it.

### Rule 2: Concrete PM comprehension assertions, not "page exists"

✗ Bad:
```python
def check_after_blocker(db, world, page):
    assertions.assert_page_contains(page, "blocker")
```

✓ Good:
```python
def check_after_blocker(db, world, page):
    pm_views.assert_active_blocker_count_on_phase_strip(
        page, world["project_id"], expected=1,
        label="phase strip flags the blocked phase",
    )
    pm_views.assert_history_row_with_type_contains(
        page, world["project_id"],
        event_type="blockers", needle="Coating Supplier A",
        label="Timeline History blocker row mentions the supplier",
    )
```

The first version passes even if the blocker is buried in fine print.
The second version asserts the PM-visible state explicitly.

### Rule 3: At least one cross-page consistency check per acceptance journey

When the same data is rendered in two places, a regression can
de-sync them. The `pm_views.assert_project_findable_on_index_and_detail`
function is the v1 cross-page check (project name on `/projects` AND
`/projects/{id}`); future scenarios should add stronger versions
(current_stage on both, costs on both, etc.) as the UI exposes the
stable selectors needed.

### Rule 4: Viewer privacy checks must hit the actual rendered HTML

The existing `viewer_permission_boundaries` contract verifies that
`can_view_costs(viewer)` returns False. That's the *helper* contract.
Acceptance journeys are responsible for the *rendered HTML* contract:
log in as viewer, navigate to the page, assert the protected element
is absent or hidden from the DOM. Use
`pm_views.assert_viewer_cannot_see_variant_costs` and similar.

### Rule 5: Stable selectors only — no fragile text-grep workarounds

If the UI does not expose a stable `data-*` attribute (or a
load-bearing semantic class like `.timeline-tile-current
.timeline-tile-primary`) for the value you need to assert on:

1. Do **NOT** add a `page.locator("text=...")` or
   `page.locator(".some-class:nth-of-type(2)")` workaround. These
   are i18n-fragile or position-fragile and would silently break
   when copy or structure changes.
2. Document the gap in [UI_TESTABILITY_GAPS.md](UI_TESTABILITY_GAPS.md)
   with a proposed minimal template patch (typically 1-3 lines
   adding a `data-*` attribute).
3. Skip that assertion until the user reviews and approves the
   patch.
4. Ship the journey with fewer assertions — that's the right
   outcome. The user lock 9 success criterion is "catches at least
   one class of bug per-build `test.py` would miss," not "asserts
   every imaginable thing."

### Rule 6: Test navigation, not just routes

**Discovered the hard way: 2026-06-13.** The user reported they
couldn't find the Planning Sandbox anywhere in the UI. The route
worked. The page rendered. Every UI test we'd written passed because
every UI test navigated **directly to `/projects/{id}/sandbox`** via
`actions.open_url`. No test asked "could a PM click their way to
this feature?" The answer was no — there was no `<a>` element on the
project detail page or anywhere else that linked to the sandbox.
The feature was unreachable; QA was blind to it because every
scenario bypassed the navigation question.

**The rule:** every UI scenario that asserts a feature works must
include at least one step that **reaches the feature through the
navigation a real PM would use** — clicking a link from `/projects`,
from a project detail page, or from a home page. `actions.open_url`
is permitted for setup/teardown but cannot be the only path to the
feature under test.

✗ Bad (URL-driven only — invisible to discoverability bugs):
```python
def do_open_sandbox(world, db, http, page):
    actions.open_url(page, f"/projects/{world['project_id']}/sandbox")
```

✓ Good (clicks the way a PM would):
```python
def do_navigate_to_sandbox(world, db, http, page):
    actions.open_url(page, f"/projects/{world['project_id']}")
    # The PM looks for a link to the sandbox and follows it.
    page.locator(
        f'a[href*="/projects/{world["project_id"]}/sandbox"]'
    ).first.click()
    page.wait_for_load_state("networkidle")

def check_after_navigate(db, world, page):
    # Asserts both that a link existed AND that following it landed
    # on the sandbox.
    assertions.assert_url_path(
        page, f"/projects/{world['project_id']}/sandbox",
        label="clicking the project's sandbox link lands on the sandbox",
    )
```

A scenario that ONLY navigates by URL is testing the **route**, not
the **feature**. Most regressions PMs hit are navigation-class:
"the route still works but the link is gone." A test that doesn't
click is blind to that class.

The canonical example of this rule in practice is
[scenario_contracts/acceptance/sandbox_is_discoverable_from_project.py](scenario_contracts/acceptance/sandbox_is_discoverable_from_project.py)
— a scenario that exists specifically to fail until the navigation
link gets added back to the project detail page. When the bug fix
lands, the scenario turns green; if anyone ever removes the link
again, it goes red.

---

## Choosing the right scenario tier

| Tier | Location | When to use |
|---|---|---|
| **Contract** | `scenario_contracts/contracts/` | Atomic "if X then Y". A single CRUD function or permission rule. ~30-100 LOC. DB-truth-only is acceptable. |
| **Journey** | `scenario_contracts/journeys/` | Multi-step PM workflow chained via the `STEPS=[Step(...)]` shape. Disruptions + AI proposals + cumulative state. DB-truth-only is acceptable but UI-aware journeys can opt in to the acceptance branch by adding the `acceptance` tag. |
| **Acceptance** | `scenario_contracts/acceptance/` | Realistic full PM lifecycle. Tests four kinds of truth. Each load-bearing step uses `pm_views.*`. Tagged `acceptance` so the runner provides a Playwright `page`. |

If you're unsure, default to **journey** for now and add
`acceptance` later when you have stable selectors for the UI checks.

---

## Discipline boundary recap

For every scenario:

- `setup(db)` — fixtures only (or empty if the scenario uses the live
  dev DB for acceptance)
- `do_*(world, db, http[, page])` — actions and disruptions only
- `check_*(db, world[, page])` — assertions and pm_views only

No raw `app.*` imports anywhere in scenario code. The
`test_qa_buildNN.py` regression files regex-check this on every
function body; CI fails on violations.

---

## Realistic product data

When the scenario needs a project name / variant name / supplier
name / etc., use **plausible synthetic data** drawn from the product
domain. The football_knife_asd_lifecycle journey uses:

- `ASD Football Folder` — plausible brand + product
- `Single Knife` and `Combo Pack` — variant lifecycle
- `Coating Supplier A` — supplier delay narrative
- `Premium gift box with embossed display sleeve` — packaging upgrade

These read like real PM notes. They are NOT real customer / supplier
names, so no leakage risk. Avoid placeholder strings like "test
project" or "lorem ipsum" — they degrade the journey's value because
they don't read like real PM work.

---

## How to draft a new acceptance journey via AI

1. **Run the gap analyzer:**
   ```
   python3 scenario_contracts/coverage.py
   ```
   This shows uncovered CRUD functions and AI tools.
2. **Read [QA_BUILD11_EXECUTION_PLAN.md](QA_BUILD11_EXECUTION_PLAN.md) + this guide.**
3. **Read [football_knife_asd_lifecycle.py](scenario_contracts/acceptance/football_knife_asd_lifecycle.py)**
   as a template.
4. **Read [UI_TESTABILITY_GAPS.md](UI_TESTABILITY_GAPS.md)** to know
   what assertions are NOT testable yet.
5. **Draft via your AI of choice** (Claude, Codex, ChatGPT). Save
   into `scenario_contracts/candidates/<name>.py`.
6. **Review the draft** against the 5 rules above. The most common
   AI miss is Rule 2 (concrete comprehension) — AI tends to write
   `assert_page_contains(page, "blocker")` because it's simpler.
   Reject and re-prompt.
7. **Run via the runner:**
   ```
   python3 -m scenario_contracts.lib.runner scenario_contracts/candidates/<name>.py
   ```
8. **Move to `acceptance/`** after at least one green run and human
   review. Tag `MATURITY="candidate"` initially; promote to `stable`
   after 10 consecutive green runs per [STABLE_CREDIBILITY.md](STABLE_CREDIBILITY.md).

---

## What the QA system rejects

The promotion-rule linter in `test_qa_build10.py` rejects any
scenario tagged `MATURITY="stable"` that lacks `release_gate` in
TAGS or has `WHY_IT_MATTERS` shorter than 80 characters. Don't try
to shortcut by drafting a stable scenario with placeholder
`WHY_IT_MATTERS = "Important."` — CI fails on commit.

The discipline-boundary regex check in each `test_qa_buildNN.py`
rejects scenarios that import from `app.*` directly. Don't try to
shortcut by writing `from app.crud import update_project` inside a
`check_*` function — CI fails on commit.

---

## Cross-references

- [QA_ROADMAP.md](QA_ROADMAP.md) — the full QA series + decision log
- [STABLE_CREDIBILITY.md](STABLE_CREDIBILITY.md) — promotion rule
- [UI_TESTABILITY_GAPS.md](UI_TESTABILITY_GAPS.md) — gaps + proposed
  app/* patches
- [scenario_contracts/lib/pm_views.py](scenario_contracts/lib/pm_views.py)
  — the PM-facing assertion library
- [scenario_contracts/acceptance/football_knife_asd_lifecycle.py](scenario_contracts/acceptance/football_knife_asd_lifecycle.py)
  — the canonical acceptance journey example
