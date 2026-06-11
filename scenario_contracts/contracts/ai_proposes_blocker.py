"""Release-gate scenario — AI must propose, not directly write, a blocker.

CLAUDE.md non-negotiable:
  "AI never writes directly to the database without user confirmation."

The contract for `create_blocker`:
  - PM/admin dispatch unconfirmed → `confirmation_required`;
    `project_blockers` table unchanged.
  - PM/admin dispatch confirmed → exactly one blocker row with
    status="active"; one `project_changes` "blocker_opened" row.
  - Viewer dispatch → `forbidden`; no DB write.
"""
from scenario_contracts.lib import actions, assertions, fixtures

ID = "ai_proposes_blocker_001"
TITLE = "AI proposing a blocker must require confirmation; viewer denied"
TAGS = ["release_gate", "deterministic", "ai_confirmation"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "Blockers shape PM and leadership prioritization. AI silently "
    "writing blockers based on free-text would let chat noise "
    "manifest as real project state. If create_blocker is dropped "
    "from CONFIRMATION_TOOLS, this contract catches it."
)

BLOCKER_TITLE = "AI-proposed blocker: factory escalation pending"


def setup(db):
    admin = fixtures.create_user(db, username="root_ai_b", role="admin")
    pm = fixtures.create_user(db, username="pm_ai_b", role="pm",
                              display_name="PM-AI-B")
    viewer = fixtures.create_user(db, username="guest_ai_b", role="viewer")
    project = fixtures.create_project(db, name="AI Blocker Project",
                                      pm_name="pm_ai_b")
    return {"admin": admin, "pm": pm, "viewer": viewer, "project": project}


def run(world, db, http):
    project_id = world["project"].id
    args = {
        "project_id": project_id,
        "title": BLOCKER_TITLE,
        "description": "Discussed in chat; needs review.",
        "severity": "high",
    }

    world["pre_blocker_count"] = actions.snapshot_table_count(
        db, "project_blockers", where={"project_id": project_id})

    # 1. PM unconfirmed
    world["unconfirmed_result"] = actions.ai_dispatch(
        db, "create_blocker", args, world["pm"], confirmed=False,
    )
    world["after_unconfirmed_blocker_count"] = actions.snapshot_table_count(
        db, "project_blockers", where={"project_id": project_id})

    # 2. Viewer
    world["viewer_result"] = actions.ai_dispatch(
        db, "create_blocker", args, world["viewer"], confirmed=False,
    )
    world["after_viewer_blocker_count"] = actions.snapshot_table_count(
        db, "project_blockers", where={"project_id": project_id})

    # 3. PM confirmed
    world["confirmed_result"] = actions.ai_dispatch(
        db, "create_blocker", args, world["pm"], confirmed=True,
    )


def check(db, world):
    project_id = world["project"].id

    # Unconfirmed path
    assertions.assert_dispatch_required_confirmation(
        world["unconfirmed_result"], "create_blocker",
        label="PM unconfirmed dispatch returns confirmation_required",
    )
    assertions.assert_equal(
        world["after_unconfirmed_blocker_count"], world["pre_blocker_count"],
        label="unconfirmed dispatch did NOT write a blocker",
    )

    # Viewer path
    assertions.assert_dispatch_blocked(
        world["viewer_result"], "forbidden",
        label="viewer dispatch is forbidden",
    )
    assertions.assert_equal(
        world["after_viewer_blocker_count"], world["pre_blocker_count"],
        label="viewer dispatch did NOT write a blocker",
    )

    # Confirmed path
    assertions.assert_dispatch_succeeded(
        world["confirmed_result"],
        label="PM confirmed dispatch succeeded",
    )
    assertions.assert_active_blocker_count(
        db, project_id, expected=1,
        label="exactly one active blocker after confirm",
    )
    assertions.assert_history_contains(
        db, project_id, BLOCKER_TITLE,
        label="project_changes records the blocker title",
    )
