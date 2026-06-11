"""Release-gate scenario — blocker create / update / resolve lifecycle.

Contract:
  - `crud.create_blocker` writes one project_blockers row (status='active')
    and one project_changes "blocker_opened" row.
  - `crud.update_blocker` (severity bump) writes the change to
    project_blockers AND one project_changes "blocker_updated" row.
  - `crud.resolve_blocker` flips status to 'resolved' AND writes one
    project_changes row recording the resolution.
"""
from scenario_contracts.lib import actions, assertions, fixtures

ID = "blocker_lifecycle_001"
TITLE = "Blocker: create (low) → update (high) → resolve, each step audited"
TAGS = ["release_gate", "deterministic", "blocker"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "Blockers shape leadership prioritization. If any of the three "
    "transitions silently stops writing to project_changes, the "
    "Timeline History stream loses visibility into critical project "
    "events. This scenario locks all three transitions in sequence."
)

INITIAL_TITLE = "Tooling delay: liner steel grade pending"


def setup(db):
    pm = fixtures.create_user(db, username="pm_bl", role="pm",
                              display_name="PM-BL")
    project = actions.create_project_for_pm(
        db, name="Blocker Lifecycle Project", pm_username="pm_bl",
    )
    return {"pm": pm, "project": project}


def run(world, db, http):
    project_id = world["project"].id

    # Step 1: create the blocker at severity=low.
    blocker = actions.create_blocker(
        db, project_id=project_id, title=INITIAL_TITLE,
        description="Initial low-severity blocker",
        severity="low", user_id=world["pm"].id,
    )
    world["blocker_id"] = blocker.id
    world["after_create_active_count"] = actions.snapshot_table_count(
        db, "project_blockers",
        where={"project_id": project_id, "status": "active"})
    world["after_create_change_count"] = actions.snapshot_table_count(
        db, "project_changes",
        where={"project_id": project_id, "change_type": "blocker_opened"})

    # Step 2: bump severity to high.
    actions.update_blocker(
        db, blocker_id=blocker.id, data={"severity": "high"},
        user_id=world["pm"].id,
    )
    world["after_update_severity"] = actions.snapshot_field(
        db, "project_blockers", where={"id": blocker.id}, field="severity",
    )
    world["after_update_change_count"] = actions.snapshot_table_count(
        db, "project_changes",
        where={"project_id": project_id, "change_type": "blocker_updated"})

    # Step 3: resolve the blocker.
    actions.resolve_blocker(
        db, blocker_id=blocker.id, user_id=world["pm"].id,
    )
    world["after_resolve_active_count"] = actions.snapshot_table_count(
        db, "project_blockers",
        where={"project_id": project_id, "status": "active"})
    world["after_resolve_status"] = actions.snapshot_field(
        db, "project_blockers", where={"id": blocker.id}, field="status",
    )
    world["after_resolve_total_change_count"] = actions.snapshot_table_count(
        db, "project_changes", where={"project_id": project_id})


def check(db, world):
    project_id = world["project"].id

    # Step 1 contract
    assertions.assert_equal(
        world["after_create_active_count"], 1,
        label="one active blocker after create",
    )
    assertions.assert_equal(
        world["after_create_change_count"], 1,
        label="one 'blocker_opened' change-log row after create",
    )

    # Step 2 contract
    assertions.assert_equal(
        world["after_update_severity"], "high",
        label="severity bumped to high",
    )
    assertions.assert_equal(
        world["after_update_change_count"], 1,
        label="one 'blocker_updated' change-log row after severity bump",
    )

    # Step 3 contract
    assertions.assert_equal(
        world["after_resolve_active_count"], 0,
        label="zero active blockers after resolve",
    )
    assertions.assert_equal(
        world["after_resolve_status"], "resolved",
        label="blocker status is 'resolved'",
    )
    # The project should now have at least 4 change-log rows:
    # the project-create event_note, blocker_opened, blocker_updated,
    # and the resolve row (whichever change_type that uses).
    # Use >= so we don't lock the exact resolve change_type — that's a
    # separate contract surface the lifecycle scenario shouldn't pin
    # tightly.
    assertions.assert_equal(
        world["after_resolve_total_change_count"] >= 4, True,
        label="at least 4 project_changes rows after the lifecycle",
    )
