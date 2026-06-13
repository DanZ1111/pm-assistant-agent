"""Golden scenario — designed to FAIL with a structured DB diff.

setup + run succeed normally, but check asserts something the run did NOT
do. The runner must catch the AssertionFailure and report exit 1 with the
expected/actual diff.
"""
from scenario_contracts.lib import actions, assertions, fixtures

ID = "golden_db_fail_001"
TITLE = "DB assertion designed to mismatch — proves failures are visible"
TAGS = ["deterministic", "golden"]
MATURITY = "candidate"
WHY_IT_MATTERS = (
    "If a known-bad assertion does not show up as a failure in the report, "
    "the runner is silently swallowing failures and no scenario can be trusted."
)


def setup(db):
    pm = fixtures.create_user(db, "fail_pm", role="pm")
    project = fixtures.create_project(db, "Fail Project", pm.display_name)
    return {"pm": pm, "project": project}


def run(world, db, http):
    actions.record_event_note(
        db=db,
        project_id=world["project"].id,
        summary="One event note was actually written",
    )


def check(db, world):
    # Deliberately wrong: assert 5 rows when only 1 exists.
    assertions.assert_row_count(
        db, "project_changes", expected=5,
        where={"project_id": world["project"].id},
        label="intentionally-wrong count assertion",
    )
