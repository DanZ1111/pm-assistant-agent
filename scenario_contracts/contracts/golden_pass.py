"""Golden scenario — designed to PASS.

Proves the happy path: a real PM action runs, real audit row exists, the
runner reports success and exits 0.
"""
from scenario_contracts.lib import actions, assertions, fixtures

ID = "golden_pass_001"
TITLE = "Recording an event note writes a project_changes row"
TAGS = ["release_gate", "deterministic", "golden"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "If a deterministic happy-path scenario stops passing, the runner itself "
    "or one of its library helpers is broken — no real scenario can be trusted."
)


def setup(db):
    pm = fixtures.create_user(db, "golden_pm", role="pm")
    project = fixtures.create_project(db, "Golden Project", pm.display_name)
    return {"pm": pm, "project": project}


def run(world, db, http):
    actions.record_event_note(
        db=db,
        project_id=world["project"].id,
        summary="Golden pass scenario fired",
    )


def check(db, world):
    assertions.assert_row_count(
        db, "project_changes", expected=1,
        where={"project_id": world["project"].id},
        label="golden_pass produced exactly one change row",
    )
    assertions.assert_history_contains(
        db, world["project"].id, "Golden pass scenario fired",
        label="golden_pass change summary is searchable",
    )
