"""
Versioned migration runner for additive schema changes.

New TABLES are handled by SQLAlchemy `Base.metadata.create_all()` in main.py
lifespan — that already does "CREATE TABLE IF NOT EXISTS" semantics on both
SQLite and PostgreSQL.

New COLUMNS on existing tables need explicit ALTER TABLE. This module
provides idempotent helpers + a tracking table (`_migrations`) so each
named migration runs exactly once per database.

Rules:
- Every migration must be idempotent: safe to call again after success.
- `add_column_if_missing()` ONLY swallows "duplicate column" / "already exists"
  errors. Any other failure is logged AND re-raised so half-applied schemas
  are visible immediately rather than silently corrupted.
- Migrations log to stdout so Railway logs show what ran.
"""
import logging
from datetime import datetime
from sqlalchemy import text, inspect
from sqlalchemy.exc import OperationalError, ProgrammingError, IntegrityError

log = logging.getLogger("migrations")
if not log.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("[migrations] %(message)s"))
    log.addHandler(h)
    log.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Tracking table
# ---------------------------------------------------------------------------

_TRACKING_DDL = """
CREATE TABLE IF NOT EXISTS _migrations (
    name TEXT PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL
)
"""


def _ensure_tracking_table(engine):
    with engine.begin() as conn:
        conn.execute(text(_TRACKING_DDL))


def _already_ran(engine, name: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT 1 FROM _migrations WHERE name = :n"), {"n": name}
        ).first()
        return row is not None


def _mark_ran(engine, name: str):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO _migrations (name, applied_at) VALUES (:n, :t)"),
            {"n": name, "t": datetime.utcnow()},
        )


# ---------------------------------------------------------------------------
# Idempotent ALTER TABLE helper
# ---------------------------------------------------------------------------

# Substrings (lowercased) we recognize as "this column already exists" — safe
# to swallow. Anything else is a real failure and must propagate.
_SAFE_ALREADY_EXISTS_HINTS = (
    "duplicate column",     # SQLite + PostgreSQL "duplicate column name"
    "already exists",       # PostgreSQL "column ... already exists"
)


def add_column_if_missing(engine, table: str, column: str, ddl: str):
    """Run ALTER TABLE {table} ADD COLUMN {column} {ddl} safely.
    No-op if the column already exists. Re-raises on any other error.

    `ddl` is the type + constraints fragment, e.g.  "VARCHAR DEFAULT 'en'"
    or "INTEGER".
    """
    # Fast path: check via inspector first (avoids producing alarming
    # exceptions in logs for the common no-op case).
    insp = inspect(engine)
    try:
        existing_cols = {c["name"] for c in insp.get_columns(table)}
    except Exception as e:
        log.error("Could not inspect table %s: %s", table, e)
        raise

    if column in existing_cols:
        log.info("skip ALTER: column %s.%s already exists", table, column)
        return

    sql = f'ALTER TABLE {table} ADD COLUMN {column} {ddl}'
    log.info("running: %s", sql)
    try:
        with engine.begin() as conn:
            conn.execute(text(sql))
        log.info("added column %s.%s", table, column)
    except (OperationalError, ProgrammingError, IntegrityError) as e:
        msg = str(e).lower()
        if any(hint in msg for hint in _SAFE_ALREADY_EXISTS_HINTS):
            log.info("race: column %s.%s already exists (another process)", table, column)
            return
        log.error("FAILED to add column %s.%s: %s", table, column, e)
        raise


# ---------------------------------------------------------------------------
# Migration registry
# ---------------------------------------------------------------------------

MIGRATIONS = [
    (
        "001_v1_1_add_language_to_users",
        lambda eng: add_column_if_missing(eng, "users", "language", "VARCHAR DEFAULT 'en'"),
    ),
    (
        "002_v1_1_add_conversation_id_to_ai_messages",
        lambda eng: add_column_if_missing(eng, "ai_messages", "conversation_id", "INTEGER"),
    ),
]


def run_pending(engine):
    """Run any not-yet-applied migrations in order. Idempotent + logged."""
    _ensure_tracking_table(engine)
    for name, fn in MIGRATIONS:
        if _already_ran(engine, name):
            log.info("skip %s — already applied", name)
            continue
        log.info("applying %s ...", name)
        try:
            fn(engine)
        except Exception:
            log.error("MIGRATION FAILED: %s — leaving _migrations entry absent so it retries next startup", name)
            raise
        _mark_ran(engine, name)
        log.info("applied %s", name)
