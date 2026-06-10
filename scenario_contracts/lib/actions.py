"""PM actions callable from scenario run() functions.

User lock 9: run() may only call actions.*; no direct route/DB mutation.

QA-01 ships service-layer actions only. QA-03 adds HTTP/Playwright variants.
"""
from __future__ import annotations

from datetime import date


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


def create_project_for_pm(db, name, pm_username, **fields):
    """Create a project owned by the given PM via the real service helper.

    Returns the created Project. The product_manager field is filled with
    the PM's username so get_projects_for_user matches.
    """
    from app import crud

    data = {
        "name": name,
        "product_manager": pm_username,
        "status": "active",
    }
    data.update(fields)
    return crud.create_project(db, data)


def create_variant(db, project_id, variant_name, **fields):
    """Create a project variant via the real service helper."""
    from app import crud

    data = {"variant_name": variant_name}
    data.update(fields)
    return crud.create_variant(db, project_id, data)


def create_sandbox_from_template(db, project_id, template_key, user_id, user_role="pm"):
    """Create a draft sandbox for a project from a seeded template."""
    from app import crud

    return crud.create_sandbox_from_template(
        db, project_id, template_key, user_id, user_role,
    )


def apply_sandbox(db, project_id, sandbox_id, apply_start_date, user_id,
                  update_launch_date=False):
    """Explicitly apply a draft sandbox to the live project plan."""
    from app import crud

    if isinstance(apply_start_date, str):
        apply_start_date = date.fromisoformat(apply_start_date)
    return crud.apply_sandbox_to_project(
        db,
        project_id=project_id,
        sandbox_id=sandbox_id,
        apply_start_date=apply_start_date,
        update_launch_date=update_launch_date,
        user_id=user_id,
    )


def snapshot_table_count(db, table_name, where=None):
    """Read-only COUNT snapshot for use inside run().

    Keeps the discipline boundary: any DB interaction inside run() routes
    through actions.* even when it's a read. Result is typically stashed
    into `world` so check() can assert against it.
    """
    from sqlalchemy import text

    sql = f"SELECT COUNT(*) FROM {table_name}"
    params = {}
    if where:
        clause = " AND ".join(f"{c} = :{c}" for c in where)
        sql += f" WHERE {clause}"
        params = where
    return db.execute(text(sql), params).scalar()
