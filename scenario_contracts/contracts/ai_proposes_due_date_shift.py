"""Release-gate scenario — AI must propose, not directly write, a phase shift.

CLAUDE.md non-negotiable:
  "AI never writes directly to the database without user confirmation."

The contract for `adjust_phase_plan`:
  - PM/admin dispatch unconfirmed → `confirmation_required`;
    `project_phases.planned_end_date` unchanged; no `phase_plan_changes`
    row.
  - PM/admin dispatch confirmed → phase moved; one `phase_plan_changes`
    row with the reason; one `project_changes` row whose summary
    surfaces the reason.
  - Viewer dispatch → `forbidden`; no DB write.
"""
from datetime import date

from scenario_contracts.lib import actions, assertions, fixtures

ID = "ai_proposes_due_date_shift_001"
TITLE = "AI proposing a phase due-date shift must require confirmation; viewer denied"
TAGS = ["release_gate", "deterministic", "ai_confirmation"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "Phase due-date shifts cascade through the Timeline Command "
    "Center, delay calculations, and Timeline History. AI silently "
    "moving phase dates would manufacture fake delays for leadership "
    "to react to. If adjust_phase_plan is dropped from "
    "CONFIRMATION_TOOLS, this contract catches it."
)

ORIGINAL_END = date(2026, 6, 30)
NEW_END = date(2026, 7, 20)
REASON = "AI-suggested adjustment for supplier holiday window"


def setup(db):
    admin = fixtures.create_user(db, username="root_ai_d", role="admin")
    pm = fixtures.create_user(db, username="pm_ai_d", role="pm",
                              display_name="PM-AI-D")
    viewer = fixtures.create_user(db, username="guest_ai_d", role="viewer")
    project = fixtures.create_project(db, name="AI Due Date Project",
                                      pm_name="pm_ai_d")
    phases = fixtures.seed_phases(
        db, project.id, ["Design", "Sample", "Production"],
        start_date=date(2026, 6, 1), duration_days=10,
    )
    # Pin the Sample phase's planned_end_date so the shift is unambiguous.
    sample = phases[1]
    sample.planned_end_date = ORIGINAL_END
    db.commit()
    db.refresh(sample)
    return {"admin": admin, "pm": pm, "viewer": viewer,
            "project": project, "sample_id": sample.id}


def run(world, db, http):
    project_id = world["project"].id
    args = {
        "project_id": project_id,
        "phase_id": world["sample_id"],
        "planned_end_date": NEW_END.isoformat(),
        "reason": REASON,
    }

    world["pre_plan_change_count"] = actions.snapshot_table_count(
        db, "phase_plan_changes")

    # 1. PM unconfirmed — snapshot planned_end_date AFTER the call so
    # check() can verify the "no write" state without being clobbered
    # by the confirmed path that runs later in this same run().
    world["unconfirmed_result"] = actions.ai_dispatch(
        db, "adjust_phase_plan", args, world["pm"], confirmed=False,
    )
    world["after_unconfirmed_end_date"] = actions.snapshot_field(
        db, "project_phases", where={"id": world["sample_id"]},
        field="planned_end_date",
    )
    world["after_unconfirmed_plan_change_count"] = actions.snapshot_table_count(
        db, "phase_plan_changes")

    # 2. Viewer
    world["viewer_result"] = actions.ai_dispatch(
        db, "adjust_phase_plan", args, world["viewer"], confirmed=False,
    )
    world["after_viewer_end_date"] = actions.snapshot_field(
        db, "project_phases", where={"id": world["sample_id"]},
        field="planned_end_date",
    )
    world["after_viewer_plan_change_count"] = actions.snapshot_table_count(
        db, "phase_plan_changes")

    # 3. PM confirmed
    world["confirmed_result"] = actions.ai_dispatch(
        db, "adjust_phase_plan", args, world["pm"], confirmed=True,
    )


def check(db, world):
    project_id = world["project"].id
    phase_id = world["sample_id"]

    # Unconfirmed path — compare snapshots captured inside run()
    assertions.assert_dispatch_required_confirmation(
        world["unconfirmed_result"], "adjust_phase_plan",
        label="PM unconfirmed dispatch returns confirmation_required",
    )
    assertions.assert_equal(
        world["after_unconfirmed_end_date"], ORIGINAL_END.isoformat(),
        label="phase planned_end_date unchanged after unconfirmed dispatch",
    )
    assertions.assert_equal(
        world["after_unconfirmed_plan_change_count"],
        world["pre_plan_change_count"],
        label="unconfirmed dispatch did NOT write a phase_plan_changes row",
    )

    # Viewer path — compare snapshots captured inside run()
    assertions.assert_dispatch_blocked(
        world["viewer_result"], "forbidden",
        label="viewer dispatch is forbidden",
    )
    assertions.assert_equal(
        world["after_viewer_end_date"], ORIGINAL_END.isoformat(),
        label="phase planned_end_date unchanged after viewer dispatch",
    )
    assertions.assert_equal(
        world["after_viewer_plan_change_count"],
        world["pre_plan_change_count"],
        label="viewer dispatch did NOT write a phase_plan_changes row",
    )

    # Confirmed path
    assertions.assert_dispatch_succeeded(
        world["confirmed_result"],
        label="PM confirmed dispatch succeeded",
    )
    assertions.assert_phase_field(
        db, phase_id, field="planned_end_date",
        expected=NEW_END.isoformat(),
        label="phase planned_end_date moved after confirm",
    )
    assertions.assert_phase_plan_change_recorded(
        db, phase_id, reason_needle=REASON,
        label="phase_plan_changes row records the reason",
    )
    assertions.assert_history_contains(
        db, project_id, REASON,
        label="project_changes summary surfaces the reason",
    )
