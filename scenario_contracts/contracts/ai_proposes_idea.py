"""Release-gate scenario — AI must propose, not directly write, an idea + link.

CLAUDE.md non-negotiable:
  "AI never writes directly to the database without user confirmation."

The contract for `create_idea` (with `project_id` set, which also links):
  - PM/admin dispatch unconfirmed → `confirmation_required`;
    `ideas` and `project_ideas` tables unchanged.
  - PM/admin dispatch confirmed → exactly one idea row; one
    project_ideas link row; one project_changes audit row.
  - Viewer dispatch → `forbidden`; no DB write.
"""
from scenario_contracts.lib import actions, assertions, fixtures

ID = "ai_proposes_idea_001"
TITLE = "AI proposing a new idea + project link must require confirmation; viewer denied"
TAGS = ["release_gate", "deterministic", "ai_confirmation"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "Ideas link products together. AI silently creating ideas would "
    "let chat speculation become permanent product backlog. If "
    "create_idea is dropped from CONFIRMATION_TOOLS, this contract "
    "catches it."
)

IDEA_NAME = "AI-proposed: ambidextrous thumb stud"


def setup(db):
    admin = fixtures.create_user(db, username="root_ai_i", role="admin")
    pm = fixtures.create_user(db, username="pm_ai_i", role="pm",
                              display_name="PM-AI-I")
    viewer = fixtures.create_user(db, username="guest_ai_i", role="viewer")
    project = fixtures.create_project(db, name="AI Idea Project",
                                      pm_name="pm_ai_i")
    return {"admin": admin, "pm": pm, "viewer": viewer, "project": project}


def run(world, db, http):
    project_id = world["project"].id
    args = {
        "project_id": project_id,
        "name": IDEA_NAME,
        "description": "AI extracted this from a chat about handle ergonomics.",
        "idea_type": "feature",
        "source": "ai_chat",
    }

    world["pre_idea_count"] = actions.snapshot_table_count(db, "ideas")
    world["pre_link_count"] = actions.snapshot_table_count(
        db, "project_ideas", where={"project_id": project_id})

    # 1. PM unconfirmed
    world["unconfirmed_result"] = actions.ai_dispatch(
        db, "create_idea", args, world["pm"], confirmed=False,
    )
    world["after_unconfirmed_idea_count"] = actions.snapshot_table_count(
        db, "ideas")
    world["after_unconfirmed_link_count"] = actions.snapshot_table_count(
        db, "project_ideas", where={"project_id": project_id})

    # 2. Viewer
    world["viewer_result"] = actions.ai_dispatch(
        db, "create_idea", args, world["viewer"], confirmed=False,
    )
    world["after_viewer_idea_count"] = actions.snapshot_table_count(
        db, "ideas")

    # 3. PM confirmed
    world["confirmed_result"] = actions.ai_dispatch(
        db, "create_idea", args, world["pm"], confirmed=True,
    )


def check(db, world):
    project_id = world["project"].id

    # Unconfirmed path
    assertions.assert_dispatch_required_confirmation(
        world["unconfirmed_result"], "create_idea",
        label="PM unconfirmed dispatch returns confirmation_required",
    )
    assertions.assert_equal(
        world["after_unconfirmed_idea_count"], world["pre_idea_count"],
        label="unconfirmed dispatch did NOT write an idea",
    )
    assertions.assert_equal(
        world["after_unconfirmed_link_count"], world["pre_link_count"],
        label="unconfirmed dispatch did NOT link to project",
    )

    # Viewer path
    assertions.assert_dispatch_blocked(
        world["viewer_result"], "forbidden",
        label="viewer dispatch is forbidden",
    )
    assertions.assert_equal(
        world["after_viewer_idea_count"], world["pre_idea_count"],
        label="viewer dispatch did NOT write an idea",
    )

    # Confirmed path
    assertions.assert_dispatch_succeeded(
        world["confirmed_result"],
        label="PM confirmed dispatch succeeded",
    )
    assertions.assert_row_count(
        db, "ideas", expected=1,
        label="exactly one idea was created",
    )
    assertions.assert_row_count(
        db, "project_ideas", expected=1,
        where={"project_id": project_id},
        label="exactly one project_ideas link row created",
    )
    # link_idea_to_project writes the audit row as
    # "Linked {idea.serial_number} to Inspired By" — not the idea name.
    serial = world["confirmed_result"].get("serial_number")
    assertions.assert_history_contains(
        db, project_id, f"Linked {serial}",
        label="project_changes records the idea serial number",
    )
