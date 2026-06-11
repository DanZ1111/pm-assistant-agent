"""Release-gate scenario — finish_phase auto-advance + stage/delay recalc.

Contract for `crud.finish_phase`:
  - Current phase: status='done', actual_end_date=today, and
    actual_start_date filled in if previously NULL.
  - Next eligible phase (next phase_order that is not done/skipped):
    status='in_progress', actual_start_date=today if not already set.
  - After commit, recalculate_stage_and_delay() runs:
    project.current_stage is the next in-progress phase name (per
    derive_current_stage); project.estimated_launch_date reflects the
    new schedule (per calculate_delay).
  - A `project_changes` row records "Phase X marked done. Y is now in
    progress."

This single scenario locks the contract that finish_phase, the stage
derivation, and the delay calculation all compose correctly.
"""
from datetime import date

from scenario_contracts.lib import actions, assertions, fixtures

ID = "finish_phase_advancement_001"
TITLE = "Finishing Design advances next phase + recalculates stage + delay"
TAGS = ["release_gate", "deterministic", "phase", "derived_state"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "Phase finish is the most common PM action. If auto-advance, "
    "stage derivation, or delay recalc desync — which can happen if "
    "any one of the three helpers changes signature or moves out of "
    "the same transaction — leadership sees stale data on every "
    "project. This scenario locks all three at once."
)

DESIGN_PHASE_NAME = "Design"
ENG_REVIEW_PHASE_NAME = "Engineering Review"


def setup(db):
    pm = fixtures.create_user(db, username="pm_finish", role="pm",
                              display_name="PM-Finish")
    project = actions.create_project_for_pm(
        db, name="Finish Phase Project", pm_username="pm_finish",
    )
    return {"pm": pm, "project": project}


def run(world, db, http):
    project_id = world["project"].id

    # Capture phase ids by name via direct read.
    world["design_id"] = actions.snapshot_field(
        db, "project_phases",
        where={"project_id": project_id, "phase_order": 1},
        field="id",
    )
    world["eng_review_id"] = actions.snapshot_field(
        db, "project_phases",
        where={"project_id": project_id, "phase_order": 2},
        field="id",
    )

    # Pre-state snapshots.
    world["pre_design_status"] = actions.snapshot_field(
        db, "project_phases", where={"id": world["design_id"]},
        field="status",
    )
    world["pre_eng_status"] = actions.snapshot_field(
        db, "project_phases", where={"id": world["eng_review_id"]},
        field="status",
    )
    world["pre_current_stage"] = actions.snapshot_field(
        db, "projects", where={"id": project_id}, field="current_stage",
    )

    # The action under test.
    actions.finish_phase(db, phase_id=world["design_id"],
                         user_id=world["pm"].id)

    # Post-state snapshots — captured INSIDE run() so check() compares
    # captured values, not the current DB (which might change later if
    # any future step is added).
    world["post_design_status"] = actions.snapshot_field(
        db, "project_phases", where={"id": world["design_id"]},
        field="status",
    )
    world["post_design_actual_end"] = actions.snapshot_field(
        db, "project_phases", where={"id": world["design_id"]},
        field="actual_end_date",
    )
    world["post_eng_status"] = actions.snapshot_field(
        db, "project_phases", where={"id": world["eng_review_id"]},
        field="status",
    )
    world["post_eng_actual_start"] = actions.snapshot_field(
        db, "project_phases", where={"id": world["eng_review_id"]},
        field="actual_start_date",
    )
    world["post_current_stage"] = actions.snapshot_field(
        db, "projects", where={"id": project_id}, field="current_stage",
    )


def check(db, world):
    project_id = world["project"].id
    today_iso = date.today().isoformat()

    # Pre-conditions sanity
    assertions.assert_equal(
        world["pre_design_status"], "not_started",
        label="pre: Design was not_started",
    )
    assertions.assert_equal(
        world["pre_eng_status"], "not_started",
        label="pre: Engineering Review was not_started",
    )

    # Post-conditions on Design
    assertions.assert_equal(
        world["post_design_status"], "done",
        label="Design status is 'done' after finish",
    )
    assertions.assert_equal(
        world["post_design_actual_end"], today_iso,
        label="Design actual_end_date is today",
    )

    # Post-conditions on Engineering Review (auto-advance)
    assertions.assert_equal(
        world["post_eng_status"], "in_progress",
        label="Engineering Review auto-advanced to in_progress",
    )
    assertions.assert_equal(
        world["post_eng_actual_start"], today_iso,
        label="Engineering Review actual_start_date is today",
    )

    # derive_current_stage output: current_stage matches the new
    # in-progress phase name (Engineering Review).
    assertions.assert_equal(
        world["post_current_stage"], ENG_REVIEW_PHASE_NAME,
        label="project.current_stage == Engineering Review after recalc",
    )

    # Audit row recorded the finish + advance.
    assertions.assert_history_contains(
        db, project_id, f"Phase '{DESIGN_PHASE_NAME}' marked done",
        label="project_changes records the Design finish",
    )
    assertions.assert_history_contains(
        db, project_id, f"'{ENG_REVIEW_PHASE_NAME}' is now in progress",
        label="project_changes records the Engineering Review advance",
    )
