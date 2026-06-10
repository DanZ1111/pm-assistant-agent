"""PM actions callable from scenario run() functions.

User lock 9: run() may only call actions.*; no direct route/DB mutation.

QA-01 ships service-layer actions only. QA-03 adds HTTP/Playwright variants.
"""
from __future__ import annotations


def adjust_due_date(db, phase_id, new_end_date, reason, changed_by="user"):
    """Adjust a phase's planned_end_date via the real service helper.

    Writes phase_plan_changes + project_changes rows just like the live
    Timeline Command Center action.
    """
    from app import crud

    return crud.update_phase(
        db,
        phase_id=phase_id,
        data={"planned_end_date": new_end_date},
        changed_by=changed_by,
        reason=reason,
    )


def record_event_note(db, project_id, summary, changed_by="user"):
    """Write a plain event_note row via crud.write_change()."""
    from app import crud

    change = crud.write_change(
        db,
        project_id=project_id,
        change_type="event_note",
        changed_by=changed_by,
        summary=summary,
    )
    db.commit()
    return change
