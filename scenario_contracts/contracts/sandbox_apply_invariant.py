"""Release-gate scenario — sandbox draft/apply isolation.

Two contracts in one scenario:

  (1) BEFORE Apply: a draft sandbox with nodes leaves project_phases
      untouched. No planning_apply_events row. No plan_applied row.

  (2) AFTER Apply: project_phases is populated from the sandbox nodes,
      exactly one planning_apply_events row exists, and exactly one
      project_changes row with change_type='plan_applied' is recorded.

If either contract breaks, the entire Planning Sandbox value proposition
("draft your plan without disrupting the live timeline") collapses.
"""
from datetime import date

from scenario_contracts.lib import actions, assertions, fixtures

ID = "sandbox_apply_invariant_001"
TITLE = "Sandbox draft does not mutate project_phases; Apply does, with audit"
TAGS = ["release_gate", "deterministic", "sandbox"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "The Planning Sandbox exists so PMs can re-plan without disrupting the "
    "current execution timeline. If draft edits leak into project_phases, "
    "PMs lose the safety of experimentation. If Apply writes no audit, "
    "leadership cannot reconstruct when or why the timeline changed."
)

TEMPLATE_KEY = "simple_oem_knife"
APPLY_START = date(2026, 7, 1)


def setup(db):
    user = fixtures.create_user(db, username="pm_sandbox", role="pm",
                                display_name="PM-Sandbox")
    project = fixtures.create_project(db, name="Sandbox Apply Project",
                                      pm_name="pm_sandbox")
    return {"user": user, "project": project}


def run(world, db, http):
    project_id = world["project"].id
    user_id = world["user"].id

    # 1. Create a draft sandbox from a system template.
    sandbox = actions.create_sandbox_from_template(
        db, project_id=project_id, template_key=TEMPLATE_KEY,
        user_id=user_id, user_role=world["user"].role,
    )
    world["sandbox_id"] = sandbox.id

    # 2. Snapshot the pre-Apply state via read-only actions so check()
    #    can verify the draft-only invariant.
    world["pre_phase_count"] = actions.snapshot_table_count(
        db, "project_phases", where={"project_id": project_id})
    world["pre_apply_event_count"] = actions.snapshot_table_count(
        db, "planning_apply_events", where={"project_id": project_id})
    world["pre_plan_applied_count"] = actions.snapshot_table_count(
        db, "project_changes",
        where={"project_id": project_id, "change_type": "plan_applied"})

    # Sandbox node count drives the expected post-Apply phase count.
    world["sandbox_node_count"] = actions.snapshot_table_count(
        db, "planning_sandbox_nodes", where={"sandbox_id": sandbox.id})

    # 3. Apply the sandbox.
    event = actions.apply_sandbox(
        db, project_id=project_id, sandbox_id=sandbox.id,
        apply_start_date=APPLY_START, user_id=user_id,
    )
    world["apply_event_id"] = event.id


def check(db, world):
    project_id = world["project"].id

    # Pre-Apply invariant: drafting a sandbox did NOT touch project_phases.
    assertions.assert_equal(
        world["pre_phase_count"], 0,
        label="pre-apply project_phases was 0 (draft did not leak)",
    )
    assertions.assert_equal(
        world["pre_apply_event_count"], 0,
        label="pre-apply planning_apply_events was 0",
    )
    assertions.assert_equal(
        world["pre_plan_applied_count"], 0,
        label="pre-apply plan_applied change rows was 0",
    )

    # Post-Apply: project_phases now matches the sandbox node count.
    assertions.assert_row_count(
        db, "project_phases", expected=world["sandbox_node_count"],
        where={"project_id": project_id},
        label="post-Apply project_phases count == sandbox node count",
    )
    # Sanity guard: the template must have been non-empty.
    assertions.assert_equal(
        world["sandbox_node_count"] > 0, True,
        label="simple_oem_knife template is not empty",
    )

    # Post-Apply: exactly one planning_apply_events row for this project.
    assertions.assert_row_count(
        db, "planning_apply_events", expected=1,
        where={"project_id": project_id},
        label="Apply wrote exactly one planning_apply_events row",
    )

    # Post-Apply: exactly one plan_applied change row for this project.
    assertions.assert_row_count(
        db, "project_changes", expected=1,
        where={"project_id": project_id, "change_type": "plan_applied"},
        label="Apply wrote exactly one plan_applied project_changes row",
    )

    # The apply event references our sandbox.
    assertions.assert_db_field(
        db, "planning_apply_events",
        where={"id": world["apply_event_id"]},
        field="sandbox_id", expected=world["sandbox_id"],
        label="planning_apply_events.sandbox_id matches draft sandbox",
    )
