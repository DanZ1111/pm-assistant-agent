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
    (
        "003_v1_2_add_price_text_fields",
        lambda eng: _add_project_price_text_fields(eng),
    ),
    (
        "004_v1_2_add_project_creation_tokens",
        lambda eng: _create_project_creation_tokens(eng),
    ),
    (
        "005_v1_3_add_variant_structured_specs",
        lambda eng: _add_variant_structured_specs(eng),
    ),
]


def _add_variant_structured_specs(engine):
    """Build 05B — six new optional columns on project_variants matching the
    wireframe's structured spec grouping. All nullable; existing rows keep
    NULL and naturally show the section's empty state until edited."""
    add_column_if_missing(engine, "project_variants", "sales_format", "VARCHAR")
    add_column_if_missing(engine, "project_variants", "packaging_cost", "REAL")
    add_column_if_missing(engine, "project_variants", "blade_summary", "TEXT")
    add_column_if_missing(engine, "project_variants", "handle_summary", "TEXT")
    add_column_if_missing(engine, "project_variants", "mechanism_summary", "TEXT")
    add_column_if_missing(engine, "project_variants", "dimensions_summary", "TEXT")


def _create_project_creation_tokens(engine):
    """Build 30A — additive table for project-create idempotency tokens.

    Idempotent: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
    Works on both SQLite (live dev) and PostgreSQL (Railway prod).
    """
    inspector = inspect(engine)
    if "project_creation_tokens" in inspector.get_table_names():
        log.info("project_creation_tokens table already present — skip create")
    else:
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE project_creation_tokens ("
                "  token VARCHAR PRIMARY KEY,"
                "  user_id INTEGER NOT NULL REFERENCES users(id),"
                "  created_at DATETIME NOT NULL,"
                "  claimed_at DATETIME NULL,"
                "  project_id INTEGER NULL REFERENCES projects(id)"
                ")"
            ))
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_pct_user_created "
            "ON project_creation_tokens(user_id, created_at)"
        ))


def _add_project_price_text_fields(engine):
    add_column_if_missing(engine, "projects", "target_factory_cost_text", "VARCHAR")
    add_column_if_missing(engine, "projects", "target_msrp_text", "VARCHAR")
    with engine.begin() as conn:
        conn.execute(text(
            "UPDATE projects SET target_factory_cost_text = CAST(target_factory_cost AS TEXT) "
            "WHERE target_factory_cost_text IS NULL AND target_factory_cost IS NOT NULL"
        ))
        conn.execute(text(
            "UPDATE projects SET target_msrp_text = CAST(target_msrp AS TEXT) "
            "WHERE target_msrp_text IS NULL AND target_msrp IS NOT NULL"
        ))


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
