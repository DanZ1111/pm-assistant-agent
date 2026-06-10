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
