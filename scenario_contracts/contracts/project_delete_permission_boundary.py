"""Release-gate scenario — project delete permission boundary.

Contract:
  - Admin can delete any project.
  - PM can delete a project they own IF every phase is still
    `status=not_started` AND `actual_start_date IS NULL`. Once any
    phase has started (status != not_started OR actual_start_date
    is set), the PM is blocked.
  - Viewer can never delete.

Source: `app.dependencies.can_delete_project`. This contract locks
the static permission rule without touching the live DB — same
shape as `viewer_permission_boundaries`.
"""
from datetime import date

from scenario_contracts.lib import actions, assertions, fixtures

ID = "project_delete_permission_boundary_001"
TITLE = "Project delete: admin always; PM only if no phase started; viewer never"
TAGS = ["release_gate", "deterministic", "delete", "permissions"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "Delete is the most destructive PM action. If the permission "
    "boundary slips — PM deleting a project mid-execution, or viewer "
    "deleting at all — there is no undo. This contract locks the four "
    "states (admin / PM-eligible / PM-blocked-by-started-phase / "
    "viewer) at the dependencies.can_delete_project level."
)


def setup(db):
    admin = fixtures.create_user(db, username="root_pb", role="admin")
    pm = fixtures.create_user(db, username="pm_pb", role="pm",
                              display_name="PM-PB")
    other_pm = fixtures.create_user(db, username="pm_pb_other", role="pm",
                                    display_name="Other PM")
    viewer = fixtures.create_user(db, username="guest_pb", role="viewer")

    # Two projects owned by pm_pb. One stays untouched (PM-eligible),
    # one will have a started phase (PM-blocked).
    fresh = actions.create_project_for_pm(
        db, name="Fresh — PM-deletable", pm_username="pm_pb")
    started = actions.create_project_for_pm(
        db, name="Started — PM-blocked", pm_username="pm_pb")
    # Mark the first phase of `started` as in_progress with an
    # actual_start_date so can_delete_project trips.
    from sqlalchemy import text
    db.execute(
        text("""
            UPDATE project_phases
            SET status = 'in_progress', actual_start_date = :today
            WHERE project_id = :pid AND phase_order = 1
        """),
        {"today": date.today(), "pid": started.id},
    )
    db.commit()
    db.refresh(fresh)
    db.refresh(started)

    return {
        "admin": admin, "pm": pm, "other_pm": other_pm, "viewer": viewer,
        "fresh": fresh, "started": started,
    }


def run(world, db, http):
    # No state change. Static permission contract.
    return None


def check(db, world):
    fresh = world["fresh"]
    started = world["started"]

    # 1. Admin can always delete.
    assertions.assert_permission(
        world["admin"], "can_delete_project", expected=True,
        project=fresh,
        label="admin can delete a fresh project",
    )
    assertions.assert_permission(
        world["admin"], "can_delete_project", expected=True,
        project=started,
        label="admin can delete even a started project",
    )

    # 2. PM-owner can delete a fresh project.
    assertions.assert_permission(
        world["pm"], "can_delete_project", expected=True,
        project=fresh,
        label="PM owner can delete a fresh project",
    )

    # 3. PM-owner is BLOCKED on a started project.
    assertions.assert_permission(
        world["pm"], "can_delete_project", expected=False,
        project=started,
        label="PM owner blocked on a project with a started phase",
    )

    # 4. PM who is NOT the owner cannot delete either project.
    assertions.assert_permission(
        world["other_pm"], "can_delete_project", expected=False,
        project=fresh,
        label="non-owner PM cannot delete a fresh project",
    )

    # 5. Viewer is denied on every project.
    assertions.assert_permission(
        world["viewer"], "can_delete_project", expected=False,
        project=fresh,
        label="viewer cannot delete a fresh project",
    )
    assertions.assert_permission(
        world["viewer"], "can_delete_project", expected=False,
        project=started,
        label="viewer cannot delete a started project",
    )
