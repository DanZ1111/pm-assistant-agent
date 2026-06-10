"""Golden scenario — UI-tagged, must be skipped in QA-01.

The runner sees the `ui` tag and skips execution, recording outcome=skip
with a clear "Playwright path lands in QA-03" note. QA-03 will replace
this scenario with a real Playwright failure check.
"""
from scenario_contracts.lib import assertions, fixtures

ID = "golden_ui_fail_001"
TITLE = "UI-tagged scenario must be skipped until QA-03"
TAGS = ["ui", "golden"]
MATURITY = "candidate"
WHY_IT_MATTERS = (
    "QA-01 has no Playwright path. The runner must skip UI-tagged scenarios "
    "instead of crashing or pretending to pass. QA-03 will flip this to a real run."
)


def setup(db):
    pm = fixtures.create_user(db, "ui_pm", role="pm")
    project = fixtures.create_project(db, "UI Project", pm.display_name)
    return {"pm": pm, "project": project}


def run(world, db, http):
    # Body intentionally left empty — runner skips before reaching this.
    raise RuntimeError("ui-tagged scenario should never execute in QA-01")


def check(db, world):
    raise RuntimeError("ui-tagged scenario check should never run in QA-01")
