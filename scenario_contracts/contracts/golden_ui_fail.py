"""Golden scenario — UI failure pipeline proof.

Intentionally asserts that a CSS selector that does NOT exist on the
projects index page is visible. The runner must:
  - exit 1 (assertion failure),
  - capture a screenshot under reports/screenshots/,
  - surface the failure with a clear "ui shows ..." reason.

If this scenario stops failing, the runner's UI failure path is broken
and no real UI scenario can be trusted.

If Playwright is unavailable or the dev server is down, the runner SKIPs
cleanly — that's the right behavior; the test suite verifies it.
"""
from scenario_contracts.lib import actions, assertions

ID = "golden_ui_fail_001"
TITLE = "Intentional UI failure proves the UI failure pipeline catches regressions"
TAGS = ["ui", "golden"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "QA-01 left this scenario as a placeholder skip. QA-03 flips it to "
    "an intentional FAIL so we can prove the browser failure path "
    "(screenshot capture, structured detail, exit 1) actually works. "
    "If this stops failing, the UI runner is silently swallowing failures."
)


def setup(db):
    return {}


def run(world, db, http, page):
    actions.open_url(page, "/projects")


def check(db, world, page):
    # Intentionally wrong: assert a selector that should not exist.
    assertions.assert_ui_shows(
        page,
        "#this-selector-should-never-exist-on-projects-index",
        label="intentionally-wrong UI assertion",
    )
