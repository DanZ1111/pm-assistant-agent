"""Release-gate scenario — timeline delay records the reason.

Adjusting a phase's planned_end_date via the Timeline Command Center must:
  - update the phase's planned_end_date,
  - write a phase_plan_changes row capturing the reason,
  - write a project_changes row whose summary surfaces the new date.

If the reason capture breaks, delays become silent and leadership loses
the audit trail that the v1.3 Timeline Command Center was built for.
"""
from datetime import date, timedelta

from scenario_contracts.lib import actions, assertions, fixtures

ID = "timeline_delay_reason_audit_001"
TITLE = "Phase due-date adjustment writes reason to phase_plan_changes + project_changes"
TAGS = ["release_gate", "deterministic", "timeline"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "Delays without recorded reasons make project retros guesswork. The "
    "Build 17 Timeline 2.0 contract was that every shift in planned dates "
    "must be paired with a free-text reason that lands in two audit tables "
    "and surfaces in Timeline History."
)

ORIGINAL_END = date(2026, 6, 30)
NEW_END = date(2026, 7, 15)
REASON = "Coating supplier late by two weeks"


def setup(db):
    pm = fixtures.create_user(db, username="pm_t", role="pm",
                              display_name="PM-T")
    project = fixtures.create_project(db, name="Marine Knife Timeline",
                                      pm_name="pm_t")
    phases = fixtures.seed_phases(
        db, project.id, ["Design", "Sample", "Production"],
        start_date=date(2026, 6, 1), duration_days=10,
    )
    # Override the Sample phase to a known target end date so the
    # assertion is unambiguous.
    sample = phases[1]
    sample.planned_end_date = ORIGINAL_END
    db.commit()
    db.refresh(sample)
    return {"pm": pm, "project": project, "sample_phase_id": sample.id}


def run(world, db, http):
    actions.adjust_due_date(
        db,
        phase_id=world["sample_phase_id"],
        new_end_date=NEW_END,
        reason=REASON,
    )


def check(db, world):
    project_id = world["project"].id
    phase_id = world["sample_phase_id"]

    # Phase's planned_end_date moved to NEW_END.
    assertions.assert_phase_field(
        db, phase_id, field="planned_end_date", expected=NEW_END.isoformat(),
        label="Sample phase planned_end_date moved to NEW_END",
    )

    # A phase_plan_changes row captured the reason.
    assertions.assert_phase_plan_change_recorded(
        db, phase_id, reason_needle=REASON,
        label="phase_plan_changes row recorded the supplier-late reason",
    )

    # The reason surfaces in a project_changes row too.
    assertions.assert_history_contains(
        db, project_id, REASON,
        label="project_changes summary surfaces the reason",
    )

    # The two other phases were not touched.
    assertions.assert_row_count(
        db, "phase_plan_changes", expected=1,
        label="exactly one phase_plan_changes row was written",
    )
