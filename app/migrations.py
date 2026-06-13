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
    (
        "006_v1_3_add_project_blockers",
        lambda eng: _create_project_blockers(eng),
    ),
    (
        "007_v1_4_create_planning_sandbox_core",
        lambda eng: _create_planning_sandbox_core(eng),
    ),
    (
        "009_v1_4_create_planning_apply_events",
        lambda eng: _create_planning_apply_events(eng),
    ),
    (
        "010_v1_4_create_planning_templates",
        lambda eng: _create_planning_templates(eng),
    ),
    (
        "011_v1_5_create_design_quest_core",
        lambda eng: _create_design_quest_core(eng),
    ),
    (
        "012_v1_5_create_design_submissions",
        lambda eng: _create_design_submissions(eng),
    ),
    (
        "013_v1_5_create_design_revision_requests",
        lambda eng: _create_design_revision_requests(eng),
    ),
]


PLANNING_MODULE_SEEDS = [
    ("project_brief", "Project Brief", "PRODUCT", "design", 2, "pm",
     "Clear project requirements and constraints",
     "PM confirms scope, target user, target price, and must-have constraints",
     "Initial commercial and product framing.", 10),
    ("product_concept", "Product Concept", "PRODUCT", "design", 5, "pm",
     "Product thesis and positioning",
     "Concept explains who it is for, why it exists, and what makes it different",
     "Strategic concept before design work starts.", 20),
    ("industrial_design", "Industrial Design", "PRODUCT", "design", 14, "designer",
     "Sketches, CAD direction, and form language",
     "PM approves the design direction for sampling",
     "Visual and ergonomic design work.", 30),
    ("mechanical_engineering", "Mechanical Engineering", "PRODUCT", "engineering", 10, "engineer",
     "Mechanism and construction review",
     "Engineer signs off that the design is buildable",
     "Mechanism, lock, tolerance, and structural review.", 40),
    ("blade_steel_validation", "Blade Steel Validation", "FACTORY", "review", 10, "engineer",
     "Steel suitability review",
     "Steel choice is compatible with performance, cost, and factory process",
     "Material validation for blade steel choices.", 50),
    ("handle_material_validation", "Handle Material Validation", "FACTORY", "review", 7, "engineer",
     "Handle material suitability review",
     "Material risk and finish expectations are understood",
     "Validation for handle material and finish risk.", 60),
    ("rendering", "Rendering", "ASSET", "asset", 7, "designer",
     "Product rendering or visual reference",
     "Rendering is approved for internal alignment",
     "Visual asset creation before or during sampling.", 70),
    ("prototype_sample", "Prototype Sample", "FACTORY", "prototype", 21, "factory",
     "Physical prototype sample",
     "Sample arrives and is ready for PM review",
     "Factory prototype or first sample round.", 80),
    ("sample_review", "Sample Review", "PRODUCT", "review", 5, "pm",
     "Sample feedback and decision",
     "PM records approval, revision request, or rejection",
     "Hands-on review of physical sample.", 90),
    ("factory_feedback", "Factory Feedback", "FACTORY", "review", 7, "factory",
     "Factory comments and feasibility notes",
     "Factory confirms constraints, risks, and next changes",
     "Factory response to sample/design feedback.", 100),
    ("quotation", "Quotation", "COMMERCIAL", "review", 5, "factory",
     "Factory quotation",
     "Factory provides cost, MOQ, lead time, and terms",
     "Commercial quote collection.", 110),
    ("cost_review", "Cost Review", "COMMERCIAL", "review", 3, "pm",
     "Cost and MSRP review",
     "PM confirms whether the product still fits the target price architecture",
     "PM price/cost decision point.", 120),
    ("packaging_design", "Packaging Design", "ASSET", "packaging", 10, "designer",
     "Packaging structure and artwork direction",
     "Packaging direction is ready for quote or sample",
     "Packaging creative and structural planning.", 130),
    ("packaging_quote", "Packaging Quote", "COMMERCIAL", "packaging", 5, "factory",
     "Packaging cost quote",
     "Packaging cost and MOQ are known",
     "Packaging cost validation.", 140),
    ("compliance_review", "Compliance Review", "COMPLIANCE", "compliance", 7, "pm",
     "Compliance and market-readiness checklist",
     "Known compliance risks are accepted or resolved",
     "Market, labeling, safety, or retail compliance check.", 150),
    ("tooling", "Tooling", "FACTORY", "production", 21, "factory",
     "Tooling or fixture preparation",
     "Factory confirms tooling is complete",
     "Tooling work before pre-production.", 160),
    ("pre_production_sample", "Pre-production Sample", "FACTORY", "production", 14, "factory",
     "Pre-production sample",
     "PM approves pre-production sample",
     "Final sample before mass production.", 170),
    ("mass_production", "Mass Production", "FACTORY", "production", 30, "factory",
     "Mass production run",
     "Production is complete and ready for QC/shipping",
     "Production execution.", 180),
    ("quality_control", "Quality Control", "FACTORY", "review", 5, "factory",
     "QC report or inspection result",
     "QC result is accepted or issues are documented",
     "Inspection and quality gate.", 190),
    ("product_photography", "Product Photography", "ASSET", "asset", 5, "designer",
     "Photo assets",
     "Assets are ready for sales/listing use",
     "Photo or marketing image production.", 200),
    ("amazon_listing", "Amazon Listing Prep", "COMMERCIAL", "launch", 7, "pm",
     "Amazon listing content",
     "Listing copy, images, keywords, and pricing are ready",
     "Marketplace launch preparation.", 210),
    ("launch_prep", "Launch Prep", "COMMERCIAL", "launch", 7, "pm",
     "Launch checklist",
     "Launch tasks are ready for release",
     "Final launch coordination.", 220),
    ("launch_review", "Launch Review", "COMMERCIAL", "review", 3, "pm",
     "Launch readiness review",
     "PM confirms go/no-go",
     "Final commercial review before launch.", 230),
    ("launch", "Launch", "COMMERCIAL", "launch", 1, "pm",
     "Product launched",
     "Product is live or handed off to sales channel",
     "Launch milestone.", 240),
]


SYSTEM_TEMPLATE_SEEDS = [
    {
        "key": "simple_oem_knife",
        "name": "Simple OEM Knife",
        "description": "Fast linear OEM knife workflow with light design risk.",
        "sort": 10,
        "nodes": [
            ("brief", "project_brief", "Project Brief", 2, "pm", 0, 0),
            ("design", "industrial_design", "Design Direction", 10, "designer", 0, 120),
            ("sample", "prototype_sample", "Factory Sample", 18, "factory", 0, 260),
            ("quote", "quotation", "Quotation", 5, "factory", 0, 430),
            ("production", "mass_production", "Mass Production", 28, "factory", 0, 560),
            ("launch", "launch", "Launch", 1, "pm", 0, 740),
        ],
        "edges": [("brief", "design"), ("design", "sample"), ("sample", "quote"),
                  ("quote", "production"), ("production", "launch")],
    },
    {
        "key": "standard_folding_knife",
        "name": "Standard Folding Knife",
        "description": "Balanced folding-knife workflow with design, engineering, sample, packaging, and launch gates.",
        "sort": 20,
        "nodes": [
            ("concept", "product_concept", "Product Concept", 5, "pm", 0, 0),
            ("design", "industrial_design", "Industrial Design", 14, "designer", -140, 130),
            ("engineering", "mechanical_engineering", "Engineering Review", 10, "engineer", 140, 130),
            ("sample", "prototype_sample", "Prototype Sample", 21, "factory", 0, 300),
            ("review", "sample_review", "Sample Review", 5, "pm", 0, 490),
            ("quote", "quotation", "Quotation", 5, "factory", -120, 620),
            ("packaging", "packaging_design", "Packaging Design", 10, "designer", 120, 620),
            ("pps", "pre_production_sample", "Pre-production Sample", 14, "factory", 0, 780),
            ("production", "mass_production", "Mass Production", 30, "factory", 0, 950),
            ("launch", "launch", "Launch", 1, "pm", 0, 1140),
        ],
        "edges": [("concept", "design"), ("concept", "engineering"), ("design", "sample"),
                  ("engineering", "sample"), ("sample", "review"), ("review", "quote"),
                  ("review", "packaging"), ("quote", "pps"), ("packaging", "pps"),
                  ("pps", "production"), ("production", "launch")],
    },
    {
        "key": "new_mechanism_knife",
        "name": "New Mechanism Knife",
        "description": "Higher-risk mechanism workflow with extra engineering and second sample loop.",
        "sort": 30,
        "nodes": [
            ("concept", "product_concept", "Product Concept", 5, "pm", 0, 0),
            ("engineering", "mechanical_engineering", "Mechanism Engineering", 14, "engineer", 0, 130),
            ("steel", "blade_steel_validation", "Steel Validation", 10, "engineer", -150, 280),
            ("proto1", "prototype_sample", "Prototype 1", 21, "factory", 150, 280),
            ("review1", "sample_review", "Prototype 1 Review", 5, "pm", 0, 470),
            ("feedback", "factory_feedback", "Factory Revision Feedback", 7, "factory", 0, 610),
            ("proto2", "prototype_sample", "Prototype 2", 18, "factory", 0, 750),
            ("quote", "quotation", "Quotation", 5, "factory", 0, 920),
            ("pps", "pre_production_sample", "Pre-production Sample", 14, "factory", 0, 1060),
            ("production", "mass_production", "Mass Production", 30, "factory", 0, 1230),
            ("launch", "launch", "Launch", 1, "pm", 0, 1420),
        ],
        "edges": [("concept", "engineering"), ("engineering", "steel"), ("engineering", "proto1"),
                  ("steel", "review1"), ("proto1", "review1"), ("review1", "feedback"),
                  ("feedback", "proto2"), ("proto2", "quote"), ("quote", "pps"),
                  ("pps", "production"), ("production", "launch")],
    },
    {
        "key": "gift_set_combo_pack",
        "name": "Gift Set / Combo Pack",
        "description": "Combo workflow with product, accessory, and packaging branches converging before production.",
        "sort": 40,
        "nodes": [
            ("concept", "product_concept", "Set Concept", 5, "pm", 0, 0),
            ("knife_design", "industrial_design", "Knife Design", 12, "designer", -180, 140),
            ("packaging", "packaging_design", "Gift Packaging Design", 14, "designer", 180, 140),
            ("sample", "prototype_sample", "Set Sample", 21, "factory", 0, 330),
            ("pack_quote", "packaging_quote", "Packaging Quote", 5, "factory", 180, 500),
            ("quote", "quotation", "Product Quotation", 5, "factory", -180, 500),
            ("cost", "cost_review", "Commercial Review", 3, "pm", 0, 640),
            ("production", "mass_production", "Mass Production", 30, "factory", 0, 790),
            ("launch", "launch", "Launch", 1, "pm", 0, 980),
        ],
        "edges": [("concept", "knife_design"), ("concept", "packaging"),
                  ("knife_design", "sample"), ("packaging", "sample"),
                  ("packaging", "pack_quote"), ("sample", "quote"),
                  ("pack_quote", "cost"), ("quote", "cost"),
                  ("cost", "production"), ("production", "launch")],
    },
    {
        "key": "packaging_heavy_retail",
        "name": "Packaging-heavy Retail Product",
        "description": "Retail workflow where packaging, compliance, and photography are first-class branches.",
        "sort": 50,
        "nodes": [
            ("brief", "project_brief", "Retail Brief", 3, "pm", 0, 0),
            ("design", "industrial_design", "Product Design", 12, "designer", -200, 140),
            ("packaging", "packaging_design", "Retail Packaging", 16, "designer", 120, 140),
            ("compliance", "compliance_review", "Compliance Review", 7, "pm", 320, 140),
            ("sample", "prototype_sample", "Retail Sample", 21, "factory", 0, 340),
            ("photo", "product_photography", "Product Photography", 5, "designer", 220, 520),
            ("quote", "quotation", "Final Quote", 5, "factory", -120, 520),
            ("production", "mass_production", "Mass Production", 30, "factory", 0, 700),
            ("launch", "launch", "Launch", 1, "pm", 0, 900),
        ],
        "edges": [("brief", "design"), ("brief", "packaging"), ("brief", "compliance"),
                  ("design", "sample"), ("packaging", "sample"), ("compliance", "sample"),
                  ("sample", "photo"), ("sample", "quote"), ("photo", "production"),
                  ("quote", "production"), ("production", "launch")],
    },
    {
        "key": "amazon_launch_product",
        "name": "Amazon Launch Product",
        "description": "Workflow optimized for marketplace assets, listing prep, QC, and launch readiness.",
        "sort": 60,
        "nodes": [
            ("concept", "product_concept", "Amazon Product Concept", 5, "pm", 0, 0),
            ("design", "industrial_design", "Design", 12, "designer", -120, 140),
            ("sample", "prototype_sample", "Sample", 18, "factory", -120, 310),
            ("photo", "product_photography", "Photography", 5, "designer", 120, 310),
            ("listing", "amazon_listing", "Amazon Listing Prep", 7, "pm", 120, 470),
            ("qc", "quality_control", "Quality Control", 5, "factory", -120, 470),
            ("launch_review", "launch_review", "Launch Readiness Review", 3, "pm", 0, 620),
            ("launch", "launch", "Launch", 1, "pm", 0, 760),
        ],
        "edges": [("concept", "design"), ("design", "sample"), ("design", "photo"),
                  ("photo", "listing"), ("sample", "qc"), ("listing", "launch_review"),
                  ("qc", "launch_review"), ("launch_review", "launch")],
    },
]


def _create_planning_sandbox_core(engine):
    """v1.4 Build 01 — Planning Sandbox core graph tables + module seeds.

    Idempotent and isolated. These tables are draft planning storage only; no
    project_phases writes happen in this build.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "planning_module_library" not in tables:
            conn.execute(text(
                "CREATE TABLE planning_module_library ("
                "  module_key VARCHAR PRIMARY KEY,"
                "  title VARCHAR NOT NULL,"
                "  category VARCHAR NOT NULL,"
                "  phase_type VARCHAR NOT NULL,"
                "  default_duration_days INTEGER NOT NULL,"
                "  default_owner_role VARCHAR NULL,"
                "  default_deliverable TEXT NULL,"
                "  default_exit_criteria TEXT NULL,"
                "  description TEXT NULL,"
                "  is_active BOOLEAN NOT NULL DEFAULT TRUE,"
                "  sort_order INTEGER NOT NULL DEFAULT 0,"
                "  created_at TIMESTAMP NOT NULL,"
                "  updated_at TIMESTAMP NOT NULL"
                ")"
            ))
        if "planning_sandboxes" not in tables:
            conn.execute(text(
                "CREATE TABLE planning_sandboxes ("
                "  id INTEGER PRIMARY KEY,"
                "  project_id INTEGER NOT NULL REFERENCES projects(id),"
                "  name VARCHAR NOT NULL,"
                "  status VARCHAR NOT NULL DEFAULT 'draft',"
                "  base_template_key VARCHAR NULL,"
                "  created_by_user_id INTEGER NULL REFERENCES users(id),"
                "  created_at TIMESTAMP NOT NULL,"
                "  updated_at TIMESTAMP NOT NULL,"
                "  applied_at TIMESTAMP NULL,"
                "  applied_by_user_id INTEGER NULL REFERENCES users(id),"
                "  last_computed_total_days INTEGER NULL"
                ")"
            ))
        if "planning_sandbox_nodes" not in tables:
            conn.execute(text(
                "CREATE TABLE planning_sandbox_nodes ("
                "  id INTEGER PRIMARY KEY,"
                "  sandbox_id INTEGER NOT NULL REFERENCES planning_sandboxes(id),"
                "  module_key VARCHAR NULL REFERENCES planning_module_library(module_key),"
                "  title VARCHAR NOT NULL,"
                "  category VARCHAR NULL,"
                "  phase_type VARCHAR NOT NULL,"
                "  duration_days INTEGER NOT NULL,"
                "  owner_role VARCHAR NULL,"
                "  deliverable TEXT NULL,"
                "  exit_criteria TEXT NULL,"
                "  x_position REAL NOT NULL DEFAULT 0,"
                "  y_position REAL NOT NULL DEFAULT 0,"
                "  sort_order INTEGER NOT NULL DEFAULT 0,"
                "  created_at TIMESTAMP NOT NULL,"
                "  updated_at TIMESTAMP NOT NULL"
                ")"
            ))
        if "planning_sandbox_edges" not in tables:
            conn.execute(text(
                "CREATE TABLE planning_sandbox_edges ("
                "  id INTEGER PRIMARY KEY,"
                "  sandbox_id INTEGER NOT NULL REFERENCES planning_sandboxes(id),"
                "  from_node_id INTEGER NOT NULL REFERENCES planning_sandbox_nodes(id),"
                "  to_node_id INTEGER NOT NULL REFERENCES planning_sandbox_nodes(id),"
                "  dependency_type VARCHAR NOT NULL DEFAULT 'finish_to_start',"
                "  created_at TIMESTAMP NOT NULL,"
                "  UNIQUE (from_node_id, to_node_id)"
                ")"
            ))

        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_planning_sandboxes_one_draft "
            "ON planning_sandboxes(project_id) WHERE status = 'draft'"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_planning_sandboxes_project "
            "ON planning_sandboxes(project_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_planning_sandbox_nodes_sandbox "
            "ON planning_sandbox_nodes(sandbox_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_planning_sandbox_edges_sandbox "
            "ON planning_sandbox_edges(sandbox_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_planning_sandbox_edges_to "
            "ON planning_sandbox_edges(to_node_id)"
        ))

    _seed_planning_modules(engine)


def _create_planning_templates(engine):
    """v1.4 Build 01 — template tables + 6 system workflow templates.

    Ships early so v1.4 Build 03 can render from templates without another
    schema pass.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "planning_templates" not in tables:
            conn.execute(text(
                "CREATE TABLE planning_templates ("
                "  id INTEGER PRIMARY KEY,"
                "  template_key VARCHAR UNIQUE NOT NULL,"
                "  name VARCHAR NOT NULL,"
                "  description TEXT NULL,"
                "  is_system BOOLEAN NOT NULL DEFAULT FALSE,"
                "  created_by_user_id INTEGER NULL REFERENCES users(id),"
                "  is_active BOOLEAN NOT NULL DEFAULT TRUE,"
                "  created_at TIMESTAMP NOT NULL,"
                "  updated_at TIMESTAMP NOT NULL,"
                "  sort_order INTEGER NOT NULL DEFAULT 0"
                ")"
            ))
        if "planning_template_nodes" not in tables:
            conn.execute(text(
                "CREATE TABLE planning_template_nodes ("
                "  id INTEGER PRIMARY KEY,"
                "  template_id INTEGER NOT NULL REFERENCES planning_templates(id),"
                "  module_key VARCHAR NULL REFERENCES planning_module_library(module_key),"
                "  title VARCHAR NOT NULL,"
                "  duration_days INTEGER NOT NULL,"
                "  owner_role VARCHAR NULL,"
                "  deliverable TEXT NULL,"
                "  exit_criteria TEXT NULL,"
                "  x_position REAL NOT NULL DEFAULT 0,"
                "  y_position REAL NOT NULL DEFAULT 0,"
                "  sort_order INTEGER NOT NULL DEFAULT 0,"
                "  created_at TIMESTAMP NOT NULL,"
                "  updated_at TIMESTAMP NOT NULL"
                ")"
            ))
        if "planning_template_edges" not in tables:
            conn.execute(text(
                "CREATE TABLE planning_template_edges ("
                "  id INTEGER PRIMARY KEY,"
                "  template_id INTEGER NOT NULL REFERENCES planning_templates(id),"
                "  from_node_id INTEGER NOT NULL REFERENCES planning_template_nodes(id),"
                "  to_node_id INTEGER NOT NULL REFERENCES planning_template_nodes(id),"
                "  dependency_type VARCHAR NOT NULL DEFAULT 'finish_to_start',"
                "  created_at TIMESTAMP NOT NULL,"
                "  UNIQUE (from_node_id, to_node_id)"
                ")"
            ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_planning_templates_active "
            "ON planning_templates(is_active, is_system, sort_order)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_planning_template_nodes_template "
            "ON planning_template_nodes(template_id)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_planning_template_edges_template "
            "ON planning_template_edges(template_id)"
        ))

    _seed_system_planning_templates(engine)


def _create_planning_apply_events(engine):
    """v1.4 Build 07 — structured audit for sandbox Apply operations."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "planning_apply_events" not in tables:
            conn.execute(text(
                "CREATE TABLE planning_apply_events ("
                "  id INTEGER PRIMARY KEY,"
                "  project_id INTEGER NOT NULL REFERENCES projects(id),"
                "  sandbox_id INTEGER NOT NULL REFERENCES planning_sandboxes(id),"
                "  applied_at TIMESTAMP NOT NULL,"
                "  applied_by_user_id INTEGER NULL REFERENCES users(id),"
                "  snapshot_json JSON NOT NULL,"
                "  node_count INTEGER NOT NULL DEFAULT 0,"
                "  total_days INTEGER NOT NULL DEFAULT 0,"
                "  planned_start_date DATE NOT NULL,"
                "  computed_end_date DATE NOT NULL,"
                "  updated_project_planned_launch_date BOOLEAN NOT NULL DEFAULT FALSE,"
                "  phases_created INTEGER NOT NULL DEFAULT 0,"
                "  phases_updated INTEGER NOT NULL DEFAULT 0,"
                "  phases_deleted INTEGER NOT NULL DEFAULT 0"
                ")"
            ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_planning_apply_events_project "
            "ON planning_apply_events(project_id, applied_at DESC)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_planning_apply_events_sandbox "
            "ON planning_apply_events(sandbox_id)"
        ))


def _create_design_quest_core(engine):
    """v1.5 Build 02 — Designer Portal quest source-of-truth tables."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "design_quests" not in tables:
            conn.execute(text(
                "CREATE TABLE design_quests ("
                "  id INTEGER PRIMARY KEY,"
                "  project_id INTEGER NOT NULL REFERENCES projects(id),"
                "  title VARCHAR NOT NULL,"
                "  brief TEXT NOT NULL,"
                "  must_keep TEXT NULL,"
                "  must_avoid TEXT NULL,"
                "  status VARCHAR NOT NULL DEFAULT 'draft',"
                "  visibility VARCHAR NOT NULL DEFAULT 'all_active_designers',"
                "  soft_deadline DATE NULL,"
                "  is_timeline_blocking BOOLEAN NOT NULL DEFAULT FALSE,"
                "  linked_phase_id INTEGER NULL REFERENCES project_phases(id),"
                "  created_by_user_id INTEGER NULL REFERENCES users(id),"
                "  published_at TIMESTAMP NULL,"
                "  closed_at TIMESTAMP NULL,"
                "  created_at TIMESTAMP NOT NULL,"
                "  updated_at TIMESTAMP NOT NULL"
                ")"
            ))
        if "design_quest_assignments" not in tables:
            conn.execute(text(
                "CREATE TABLE design_quest_assignments ("
                "  id INTEGER PRIMARY KEY,"
                "  quest_id INTEGER NOT NULL REFERENCES design_quests(id),"
                "  designer_user_id INTEGER NOT NULL REFERENCES users(id),"
                "  assigned_by_user_id INTEGER NULL REFERENCES users(id),"
                "  status VARCHAR NOT NULL DEFAULT 'assigned',"
                "  created_at TIMESTAMP NOT NULL,"
                "  updated_at TIMESTAMP NOT NULL,"
                "  UNIQUE (quest_id, designer_user_id)"
                ")"
            ))
        if "design_quest_references" not in tables:
            conn.execute(text(
                "CREATE TABLE design_quest_references ("
                "  id INTEGER PRIMARY KEY,"
                "  quest_id INTEGER NOT NULL REFERENCES design_quests(id),"
                "  project_file_id INTEGER NOT NULL REFERENCES project_files(id),"
                "  label VARCHAR NULL,"
                "  visibility VARCHAR NOT NULL DEFAULT 'designer_visible',"
                "  sort_order INTEGER NOT NULL DEFAULT 0,"
                "  added_by_user_id INTEGER NULL REFERENCES users(id),"
                "  created_at TIMESTAMP NOT NULL"
                ")"
            ))
        if "design_quest_events" not in tables:
            conn.execute(text(
                "CREATE TABLE design_quest_events ("
                "  id INTEGER PRIMARY KEY,"
                "  quest_id INTEGER NOT NULL REFERENCES design_quests(id),"
                "  project_id INTEGER NOT NULL REFERENCES projects(id),"
                "  event_type VARCHAR NOT NULL,"
                "  actor_user_id INTEGER NULL REFERENCES users(id),"
                "  summary TEXT NULL,"
                "  payload_json JSON NULL,"
                "  created_at TIMESTAMP NOT NULL"
                ")"
            ))

        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_design_quests_one_active "
            "ON design_quests(project_id) "
            "WHERE status IN ('draft', 'open', 'reviewing', 'revision_needed', 'selected')"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_design_quests_project_status "
            "ON design_quests(project_id, status)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_design_quest_assignments_designer "
            "ON design_quest_assignments(designer_user_id, status)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_design_quest_references_quest "
            "ON design_quest_references(quest_id, sort_order)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_design_quest_events_quest "
            "ON design_quest_events(quest_id, created_at)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_design_quest_events_project "
            "ON design_quest_events(project_id, created_at)"
        ))


def _create_design_submissions(engine):
    """v1.5 Build 05 — Designer submission and immutable version tables."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "design_submissions" not in tables:
            conn.execute(text(
                "CREATE TABLE design_submissions ("
                "  id INTEGER PRIMARY KEY,"
                "  quest_id INTEGER NOT NULL REFERENCES design_quests(id),"
                "  project_id INTEGER NOT NULL REFERENCES projects(id),"
                "  designer_user_id INTEGER NOT NULL REFERENCES users(id),"
                "  status VARCHAR NOT NULL DEFAULT 'submitted',"
                "  title VARCHAR NULL,"
                "  designer_note TEXT NULL,"
                "  created_at TIMESTAMP NOT NULL,"
                "  updated_at TIMESTAMP NOT NULL"
                ")"
            ))
        if "design_submission_versions" not in tables:
            conn.execute(text(
                "CREATE TABLE design_submission_versions ("
                "  id INTEGER PRIMARY KEY,"
                "  submission_id INTEGER NOT NULL REFERENCES design_submissions(id),"
                "  quest_id INTEGER NOT NULL REFERENCES design_quests(id),"
                "  project_id INTEGER NOT NULL REFERENCES projects(id),"
                "  version_number INTEGER NOT NULL,"
                "  filename VARCHAR NOT NULL,"
                "  original_filename VARCHAR NOT NULL,"
                "  file_type VARCHAR NOT NULL,"
                "  file_size INTEGER NOT NULL,"
                "  designer_note TEXT NULL,"
                "  uploaded_by_user_id INTEGER NULL REFERENCES users(id),"
                "  created_at TIMESTAMP NOT NULL"
                ")"
            ))

        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_design_submissions_active_designer "
            "ON design_submissions(quest_id, designer_user_id) "
            "WHERE status != 'archived'"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_design_submissions_quest_status "
            "ON design_submissions(quest_id, status)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_design_submissions_designer_status "
            "ON design_submissions(designer_user_id, status)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_design_submission_versions_submission "
            "ON design_submission_versions(submission_id, version_number)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_design_submission_versions_quest "
            "ON design_submission_versions(quest_id, created_at)"
        ))


def _create_design_revision_requests(engine):
    """v1.5 Build 06 — PM revision requests and checklist items."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    columns_by_table = {
        table: {col["name"] for col in inspector.get_columns(table)}
        for table in tables
    }
    with engine.begin() as conn:
        if "design_revision_requests" not in tables:
            conn.execute(text(
                "CREATE TABLE design_revision_requests ("
                "  id INTEGER PRIMARY KEY,"
                "  submission_id INTEGER NOT NULL REFERENCES design_submissions(id),"
                "  quest_id INTEGER NOT NULL REFERENCES design_quests(id),"
                "  project_id INTEGER NOT NULL REFERENCES projects(id),"
                "  requested_by_user_id INTEGER NULL REFERENCES users(id),"
                "  status VARCHAR NOT NULL DEFAULT 'open',"
                "  general_comment TEXT NULL,"
                "  created_at TIMESTAMP NOT NULL,"
                "  resolved_at TIMESTAMP NULL"
                ")"
            ))
        if "design_revision_items" not in tables:
            conn.execute(text(
                "CREATE TABLE design_revision_items ("
                "  id INTEGER PRIMARY KEY,"
                "  revision_request_id INTEGER NOT NULL REFERENCES design_revision_requests(id),"
                "  text TEXT NOT NULL,"
                "  status VARCHAR NOT NULL DEFAULT 'open',"
                "  sort_order INTEGER NOT NULL DEFAULT 0,"
                "  created_at TIMESTAMP NOT NULL"
                ")"
            ))
        if (
            "design_submission_versions" in tables
            and "revision_request_id" not in columns_by_table.get("design_submission_versions", set())
        ):
            conn.execute(text(
                "ALTER TABLE design_submission_versions "
                "ADD COLUMN revision_request_id INTEGER NULL REFERENCES design_revision_requests(id)"
            ))

        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_design_revision_requests_submission_status "
            "ON design_revision_requests(submission_id, status)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_design_revision_requests_quest_status "
            "ON design_revision_requests(quest_id, status)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_design_revision_items_request "
            "ON design_revision_items(revision_request_id, sort_order)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_design_submission_versions_revision_request "
            "ON design_submission_versions(revision_request_id)"
        ))


def _seed_planning_modules(engine):
    now = datetime.utcnow()
    with engine.begin() as conn:
        for (
            module_key, title, category, phase_type, duration, owner_role,
            deliverable, exit_criteria, description, sort_order,
        ) in PLANNING_MODULE_SEEDS:
            exists = conn.execute(
                text("SELECT 1 FROM planning_module_library WHERE module_key = :module_key"),
                {"module_key": module_key},
            ).first()
            if exists:
                continue
            conn.execute(text(
                "INSERT INTO planning_module_library ("
                "module_key, title, category, phase_type, default_duration_days, "
                "default_owner_role, default_deliverable, default_exit_criteria, "
                "description, is_active, sort_order, created_at, updated_at"
                ") VALUES ("
                ":module_key, :title, :category, :phase_type, :duration, "
                ":owner_role, :deliverable, :exit_criteria, :description, "
                ":is_active, :sort_order, :created_at, :updated_at)"
            ), {
                "module_key": module_key,
                "title": title,
                "category": category,
                "phase_type": phase_type,
                "duration": duration,
                "owner_role": owner_role,
                "deliverable": deliverable,
                "exit_criteria": exit_criteria,
                "description": description,
                "is_active": True,
                "sort_order": sort_order,
                "created_at": now,
                "updated_at": now,
            })


def _seed_system_planning_templates(engine):
    now = datetime.utcnow()
    with engine.begin() as conn:
        for template in SYSTEM_TEMPLATE_SEEDS:
            row = conn.execute(
                text("SELECT id FROM planning_templates WHERE template_key = :template_key"),
                {"template_key": template["key"]},
            ).first()
            if row is None:
                conn.execute(text(
                    "INSERT INTO planning_templates ("
                    "template_key, name, description, is_system, created_by_user_id, "
                    "is_active, created_at, updated_at, sort_order"
                    ") VALUES ("
                    ":template_key, :name, :description, :is_system, NULL, "
                    ":is_active, :created_at, :updated_at, :sort_order)"
                ), {
                    "template_key": template["key"],
                    "name": template["name"],
                    "description": template["description"],
                    "is_system": True,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                    "sort_order": template["sort"],
                })
                row = conn.execute(
                    text("SELECT id FROM planning_templates WHERE template_key = :template_key"),
                    {"template_key": template["key"]},
                ).first()

            template_id = row[0]
            node_count = conn.execute(
                text("SELECT COUNT(*) FROM planning_template_nodes WHERE template_id = :template_id"),
                {"template_id": template_id},
            ).scalar()
            if node_count:
                continue

            node_ids = {}
            for sort_order, (local_key, module_key, title, duration, owner_role, x_pos, y_pos) in enumerate(template["nodes"], 1):
                module = conn.execute(text(
                    "SELECT default_deliverable, default_exit_criteria "
                    "FROM planning_module_library WHERE module_key = :module_key"
                ), {"module_key": module_key}).first()
                deliverable = module[0] if module else None
                exit_criteria = module[1] if module else None
                conn.execute(text(
                    "INSERT INTO planning_template_nodes ("
                    "template_id, module_key, title, duration_days, owner_role, "
                    "deliverable, exit_criteria, x_position, y_position, sort_order, "
                    "created_at, updated_at"
                    ") VALUES ("
                    ":template_id, :module_key, :title, :duration_days, :owner_role, "
                    ":deliverable, :exit_criteria, :x_position, :y_position, :sort_order, "
                    ":created_at, :updated_at)"
                ), {
                    "template_id": template_id,
                    "module_key": module_key,
                    "title": title,
                    "duration_days": duration,
                    "owner_role": owner_role,
                    "deliverable": deliverable,
                    "exit_criteria": exit_criteria,
                    "x_position": x_pos,
                    "y_position": y_pos,
                    "sort_order": sort_order,
                    "created_at": now,
                    "updated_at": now,
                })
                node_row = conn.execute(text(
                    "SELECT id FROM planning_template_nodes "
                    "WHERE template_id = :template_id AND sort_order = :sort_order"
                ), {"template_id": template_id, "sort_order": sort_order}).first()
                node_ids[local_key] = node_row[0]

            for from_key, to_key in template["edges"]:
                conn.execute(text(
                    "INSERT INTO planning_template_edges ("
                    "template_id, from_node_id, to_node_id, dependency_type, created_at"
                    ") VALUES ("
                    ":template_id, :from_node_id, :to_node_id, 'finish_to_start', :created_at)"
                ), {
                    "template_id": template_id,
                    "from_node_id": node_ids[from_key],
                    "to_node_id": node_ids[to_key],
                    "created_at": now,
                })


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


def _create_project_blockers(engine):
    """v1.3 Build 07B — first-class blocker model with active/resolved
    lifecycle. Per V13_BUILD07B_EXECUTION_PLAN.md.

    Idempotent: CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
    Works on both SQLite (live dev) and PostgreSQL (Railway prod).
    Mirrors Build 30A's _create_project_creation_tokens() pattern.
    """
    inspector = inspect(engine)
    if "project_blockers" in inspector.get_table_names():
        log.info("project_blockers table already present — skip create")
    else:
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE project_blockers ("
                "  id INTEGER PRIMARY KEY,"
                "  project_id INTEGER NOT NULL REFERENCES projects(id),"
                "  phase_id INTEGER NULL REFERENCES project_phases(id),"
                "  title VARCHAR NOT NULL,"
                "  description TEXT NULL,"
                "  severity VARCHAR NOT NULL DEFAULT 'medium',"
                "  status VARCHAR NOT NULL DEFAULT 'active',"
                "  created_at DATETIME NOT NULL,"
                "  created_by_user_id INTEGER NULL REFERENCES users(id),"
                "  resolved_at DATETIME NULL,"
                "  resolved_by_user_id INTEGER NULL REFERENCES users(id)"
                ")"
            ))
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_pb_project_status "
            "ON project_blockers(project_id, status)"
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_pb_phase "
            "ON project_blockers(phase_id)"
        ))


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
