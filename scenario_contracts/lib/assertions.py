"""Assertion helpers callable from scenario check() functions.

User lock 9: check() may only call assertions.*; no inline asserts.

Each assertion raises AssertionFailure on mismatch. The runner catches and
records it as a structured failure (not a generic Python AssertionError).
"""
from __future__ import annotations

from datetime import date


class AssertionFailure(Exception):
    """Structured assertion failure with expected/actual context."""

    def __init__(self, label, expected, actual, hint=None):
        self.label = label
        self.expected = expected
        self.actual = actual
        self.hint = hint
        message = f"{label}: expected {expected!r}, got {actual!r}"
        if hint:
            message += f" ({hint})"
        super().__init__(message)


def assert_db_field(db, table_name, where, field, expected, label=None):
    """Assert a single field on a row matched by `where` equals `expected`.

    `where` is a dict of column-name -> value used to find the row.
    """
    from sqlalchemy import text

    where_clause = " AND ".join(f"{col} = :{col}" for col in where)
    sql = f"SELECT {field} FROM {table_name} WHERE {where_clause} LIMIT 1"
    row = db.execute(text(sql), where).fetchone()
    if row is None:
        raise AssertionFailure(
            label or f"{table_name}.{field}",
            expected,
            None,
            hint=f"no row in {table_name} matching {where}",
        )
    actual = row[0]
    if isinstance(actual, date) and isinstance(expected, str):
        actual = actual.isoformat()
    if actual != expected:
        raise AssertionFailure(label or f"{table_name}.{field}", expected, actual)


def assert_history_contains(db, project_id, needle, label=None):
    """Assert that some project_changes row for this project contains `needle`."""
    from sqlalchemy import text

    rows = db.execute(
        text("""
            SELECT summary, reason, new_value
            FROM project_changes
            WHERE project_id = :pid
        """),
        {"pid": project_id},
    ).fetchall()
    for row in rows:
        for cell in row:
            if cell and needle in str(cell):
                return
    raise AssertionFailure(
        label or "history_contains",
        needle,
        f"{len(rows)} rows; no match",
        hint="needle not found in any summary/reason/new_value",
    )


def must_not_mutate(db, table_name, **where):
    """Assert that no row matching `where` has been updated since `setup`.

    QA-01 uses a coarse check: assert that the row matching `where` has
    updated_at equal to created_at (i.e. no UPDATE has been applied).
    """
    from sqlalchemy import text

    where_clause = " AND ".join(f"{col} = :{col}" for col in where)
    sql = (
        f"SELECT created_at, updated_at FROM {table_name} "
        f"WHERE {where_clause} LIMIT 1"
    )
    row = db.execute(text(sql), where).fetchone()
    if row is None:
        raise AssertionFailure(
            f"must_not_mutate {table_name}",
            "row exists",
            None,
            hint=f"no row matching {where}",
        )
    created_at, updated_at = row
    if created_at != updated_at:
        raise AssertionFailure(
            f"must_not_mutate {table_name} {where}",
            "created_at == updated_at",
            f"created_at={created_at}, updated_at={updated_at}",
        )


def assert_row_count(db, table_name, expected, where=None, label=None):
    """Assert that a SELECT COUNT(*) returns `expected`."""
    from sqlalchemy import text

    sql = f"SELECT COUNT(*) FROM {table_name}"
    params = {}
    if where:
        where_clause = " AND ".join(f"{col} = :{col}" for col in where)
        sql += f" WHERE {where_clause}"
        params = where
    actual = db.execute(text(sql), params).scalar()
    if actual != expected:
        raise AssertionFailure(label or f"count({table_name})", expected, actual)


def assert_no_rows(db, table_name, where=None, label=None):
    """Assert that no rows in `table_name` match `where`."""
    assert_row_count(db, table_name, 0, where=where,
                     label=label or f"no rows in {table_name}")


def assert_dispatch_required_confirmation(result, tool_name, label=None):
    """Assert dispatch returned a confirmation_required error for `tool_name`."""
    if not isinstance(result, dict):
        raise AssertionFailure(
            label or "dispatch result shape",
            "dict",
            type(result).__name__,
        )
    if result.get("ok") is not False:
        raise AssertionFailure(
            label or "dispatch confirmation_required",
            "ok=False",
            f"ok={result.get('ok')!r}",
        )
    if result.get("error") != "confirmation_required":
        raise AssertionFailure(
            label or "dispatch confirmation_required error code",
            "confirmation_required",
            result.get("error"),
        )
    if result.get("tool") != tool_name:
        raise AssertionFailure(
            label or "dispatch confirmation_required tool name",
            tool_name,
            result.get("tool"),
        )


def assert_dispatch_succeeded(result, label=None):
    """Assert dispatch returned a success result (ok=True, no error)."""
    if not isinstance(result, dict):
        raise AssertionFailure(
            label or "dispatch result shape",
            "dict",
            type(result).__name__,
        )
    if result.get("ok") is not True:
        raise AssertionFailure(
            label or "dispatch succeeded",
            "ok=True",
            f"ok={result.get('ok')!r}, error={result.get('error')!r}",
        )


def assert_dispatch_blocked(result, expected_error, label=None):
    """Assert dispatch refused with the expected error code (e.g. 'forbidden')."""
    if not isinstance(result, dict):
        raise AssertionFailure(
            label or "dispatch result shape",
            "dict",
            type(result).__name__,
        )
    if result.get("ok") is not False:
        raise AssertionFailure(
            label or f"dispatch blocked ({expected_error})",
            "ok=False",
            f"ok={result.get('ok')!r}",
        )
    if result.get("error") != expected_error:
        raise AssertionFailure(
            label or f"dispatch blocked error code",
            expected_error,
            result.get("error"),
        )


def assert_active_blocker_count(db, project_id, expected, label=None):
    """Assert N project_blockers rows with status='active' for the project."""
    assert_row_count(
        db, "project_blockers", expected=expected,
        where={"project_id": project_id, "status": "active"},
        label=label or f"active blockers on project {project_id}",
    )


def assert_equal(actual, expected, label=None):
    """General equality assertion for values captured in `world`.

    Used when check() needs to compare a pre-run snapshot (captured by an
    actions.* read) against an expected value. Keeps the discipline
    boundary: check() never imports app.* or runs SQL directly.
    """
    if actual != expected:
        raise AssertionFailure(label or "assert_equal", expected, actual)


# ── Browser assertions (QA-03) ──────────────────────────────────────────


def assert_ui_shows(page, selector, label=None):
    """Assert an element exists and is visible on the current page."""
    try:
        locator = page.locator(selector).first
        # is_visible has a default timeout; expose nothing too long.
        visible = locator.is_visible(timeout=2000)
    except Exception as exc:
        raise AssertionFailure(
            label or f"ui shows {selector}",
            "visible element",
            f"locator error: {exc!r}",
        )
    if not visible:
        raise AssertionFailure(
            label or f"ui shows {selector}",
            "visible",
            "not visible (or not present)",
        )


def assert_ui_does_not_show(page, selector, label=None):
    """Assert an element is absent or hidden."""
    try:
        count = page.locator(selector).count()
    except Exception as exc:
        raise AssertionFailure(
            label or f"ui does not show {selector}",
            "absent",
            f"locator error: {exc!r}",
        )
    if count > 0:
        # Element exists; assert it's not visible.
        locator = page.locator(selector).first
        if locator.is_visible(timeout=1000):
            raise AssertionFailure(
                label or f"ui does not show {selector}",
                "absent or hidden",
                "visible",
            )


def assert_url_path(page, expected_path, label=None):
    """Assert the current URL ends with `expected_path` (ignoring query/hash)."""
    from urllib.parse import urlparse

    actual_path = urlparse(page.url).path
    if actual_path != expected_path:
        raise AssertionFailure(
            label or "url path",
            expected_path,
            actual_path,
        )


def assert_canvas_node_count_equals(page, expected, label=None):
    """Assert the sandbox canvas node count matches `expected`."""
    from scenario_contracts.lib.actions import read_sandbox_node_count

    actual = read_sandbox_node_count(page)
    if actual != expected:
        raise AssertionFailure(
            label or "sandbox canvas node count",
            expected,
            actual,
        )


def assert_page_contains(page, needle, label=None):
    """Assert the rendered HTML contains `needle` somewhere."""
    html = page.content()
    if needle not in html:
        raise AssertionFailure(
            label or "page contains",
            f"contains {needle!r}",
            f"absent (page length {len(html)})",
        )


def assert_project_visible_to_user(db, user, project_id, label=None):
    """Assert that get_projects_for_user(user) contains the given project."""
    from app import crud

    projects = crud.get_projects_for_user(db, user)
    project_ids = {p.id for p in projects}
    if project_id not in project_ids:
        raise AssertionFailure(
            label or f"project {project_id} visible to {user.username}",
            "in list",
            f"not in list (visible: {sorted(project_ids)})",
        )


def assert_project_not_visible_to_user(db, user, project_id, label=None):
    """Assert that get_projects_for_user(user) does NOT contain the project."""
    from app import crud

    projects = crud.get_projects_for_user(db, user)
    project_ids = {p.id for p in projects}
    if project_id in project_ids:
        raise AssertionFailure(
            label or f"project {project_id} hidden from {user.username}",
            "absent",
            f"present (visible: {sorted(project_ids)})",
        )


def assert_permission(user, permission_name, expected, project=None, label=None):
    """Assert that a permission helper returns `expected` for `user`.

    `permission_name` is a function name in app.dependencies, e.g.
    "can_edit_project", "can_view_costs", "can_view_journal",
    "can_view_sensitive_fields".

    Some helpers take just (user); others take (user, project). We
    introspect and call appropriately.
    """
    from app import dependencies
    import inspect

    func = getattr(dependencies, permission_name, None)
    if func is None or not callable(func):
        raise AssertionFailure(
            label or f"permission {permission_name}",
            "callable in app.dependencies",
            f"missing or non-callable",
        )
    sig = inspect.signature(func)
    if "project" in sig.parameters and project is not None:
        actual = func(user, project)
    else:
        actual = func(user)
    if bool(actual) != bool(expected):
        raise AssertionFailure(
            label or f"{permission_name}({user.username})",
            expected,
            actual,
        )


def assert_phase_field(db, phase_id, field, expected, label=None):
    """Assert a field on a project_phases row by phase_id."""
    assert_db_field(
        db, "project_phases", where={"id": phase_id},
        field=field, expected=expected, label=label,
    )


def assert_phase_plan_change_recorded(db, phase_id, reason_needle, label=None):
    """Assert a phase_plan_changes row exists for phase_id whose reason
    contains the needle."""
    from sqlalchemy import text

    rows = db.execute(
        text("""
            SELECT field_changed, reason, old_date, new_date
            FROM phase_plan_changes
            WHERE phase_id = :pid
        """),
        {"pid": phase_id},
    ).fetchall()
    for row in rows:
        if row[1] and reason_needle in row[1]:
            return
    raise AssertionFailure(
        label or f"phase_plan_changes reason for phase {phase_id}",
        f"contains {reason_needle!r}",
        f"{len(rows)} rows; reasons: {[r[1] for r in rows]}",
    )
