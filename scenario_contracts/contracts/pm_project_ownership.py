"""Release-gate scenario — PM project ownership boundary.

A project created by PM Alice appears in Alice's My Projects, not in PM
Bob's. Admin sees everything. Viewer sees nothing.

This is the load-bearing scope rule for the PM dashboard. If it breaks,
PMs see each other's projects (a privacy violation) or admins lose oversight.
"""
from scenario_contracts.lib import actions, assertions, fixtures

ID = "pm_project_ownership_001"
TITLE = "PM-owned project is visible to owner, hidden from other PMs, visible to admin"
TAGS = ["release_gate", "deterministic", "ownership"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "PMs must only see projects they own. Cross-PM visibility leaks customer "
    "details across teams; admin invisibility breaks oversight. This is the "
    "single contract that defines the PM dashboard scope."
)


def setup(db):
    alice = fixtures.create_user(db, username="alice", role="pm",
                                 display_name="Alice")
    bob = fixtures.create_user(db, username="bob", role="pm",
                               display_name="Bob")
    admin = fixtures.create_user(db, username="root", role="admin",
                                 display_name="Root")
    return {"alice": alice, "bob": bob, "admin": admin}


def run(world, db, http):
    project = actions.create_project_for_pm(
        db, name="Alice's Marine Knife", pm_username="alice",
    )
    world["project_id"] = project.id


def check(db, world):
    project_id = world["project_id"]

    assertions.assert_project_visible_to_user(
        db, world["alice"], project_id,
        label="alice (owner) sees her project",
    )
    assertions.assert_project_not_visible_to_user(
        db, world["bob"], project_id,
        label="bob (other PM) does NOT see alice's project",
    )
    assertions.assert_project_visible_to_user(
        db, world["admin"], project_id,
        label="admin sees alice's project (oversight rule)",
    )
