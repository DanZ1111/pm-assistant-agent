"""v1.4 Build 01 — Planning Sandbox schema + module/template seed proof.

This build creates the Planning Sandbox data foundation only. It must not add
the canvas route, Apply behavior, schedule engine, or any live ProjectPhase
mutation path.
"""
import os
import sys
import tempfile
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = Path(__file__).resolve().parent
PASS, FAIL = [], []


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, reason):
    FAIL.append((name, reason))
    print(f"  ✗  {name}: {reason}")


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def contains_all(label, text_value, needles):
    missing = [needle for needle in needles if needle not in text_value]
    if missing:
        fail(label, f"missing: {missing}")
    else:
        ok(label)


def build_temp_db():
    tmp = tempfile.TemporaryDirectory()
    db_path = Path(tmp.name) / "v14_build01.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    # Match app.main startup order: create tables from models first, then run
    # additive/idempotent migrations and seed data.
    import app.models  # noqa: F401
    from app.database import Base
    from app import migrations

    Base.metadata.create_all(bind=engine)
    migrations.run_pending(engine)
    migrations.run_pending(engine)  # idempotency proof: second run no-ops

    Session = sessionmaker(bind=engine)
    return tmp, engine, Session


def scalar(conn, sql, params=None):
    return conn.execute(text(sql), params or {}).scalar()


def main():
    print("\n── 1. Planning models import ──")
    from app.models import (
        PlanningModule,
        PlanningSandbox,
        PlanningSandboxNode,
        PlanningSandboxEdge,
        PlanningTemplate,
        PlanningTemplateNode,
        PlanningTemplateEdge,
        Project,
    )
    planning_models = [
        PlanningModule, PlanningSandbox, PlanningSandboxNode,
        PlanningSandboxEdge, PlanningTemplate, PlanningTemplateNode,
        PlanningTemplateEdge,
    ]
    if all(model.__tablename__.startswith("planning_") for model in planning_models):
        ok("All 7 v1.4 planning models import with planning_* tables")
    else:
        fail("planning model imports", [m.__tablename__ for m in planning_models])
    if hasattr(Project, "planning_sandboxes"):
        ok("Project.planning_sandboxes relationship exists")
    else:
        fail("Project relationship", "missing planning_sandboxes")

    print("\n── 2. Migration registry ──")
    from app.migrations import MIGRATIONS, PLANNING_MODULE_SEEDS, SYSTEM_TEMPLATE_SEEDS
    migration_names = [name for name, _ in MIGRATIONS]
    contains_all(
        "Migration registry includes v1.4 Build 01 migration names",
        "\n".join(migration_names),
        [
            "007_v1_4_create_planning_sandbox_core",
            "010_v1_4_create_planning_templates",
        ],
    )
    if not any(name.startswith("008_v1_4") for name in migration_names) and "009_v1_4_create_planning_apply_events" in migration_names:
        ok("Migration 008 remains unclaimed; 009 is claimed by Build 07 Apply audit")
    else:
        fail("reserved migration names", migration_names)
    if len(PLANNING_MODULE_SEEDS) >= 20:
        ok(f"Planning module seed list has at least 20 modules ({len(PLANNING_MODULE_SEEDS)})")
    else:
        fail("module seed count", len(PLANNING_MODULE_SEEDS))
    if len(SYSTEM_TEMPLATE_SEEDS) == 6:
        ok("Exactly 6 system template seeds defined")
    else:
        fail("system template seed count", len(SYSTEM_TEMPLATE_SEEDS))

    print("\n── 3. Fresh DB migration + seed proof ──")
    tmp, engine, Session = build_temp_db()
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        expected_tables = {
            "planning_module_library",
            "planning_sandboxes",
            "planning_sandbox_nodes",
            "planning_sandbox_edges",
            "planning_templates",
            "planning_template_nodes",
            "planning_template_edges",
        }
        missing_tables = expected_tables - tables
        if not missing_tables:
            ok("All 7 planning tables exist on a fresh DB")
        else:
            fail("planning tables", f"missing {missing_tables}")
        if "planning_apply_events" in tables:
            ok("planning_apply_events exists after Build 07 migration")
        else:
            fail("planning_apply_events scope", "table should exist once Build 07 is present")

        with engine.connect() as conn:
            active_modules = scalar(conn, "SELECT COUNT(*) FROM planning_module_library WHERE is_active = 1")
            if active_modules >= 20:
                ok(f"Seeded active planning modules >= 20 ({active_modules})")
            else:
                fail("active module count", active_modules)

            categories = {
                row[0] for row in conn.execute(text(
                    "SELECT DISTINCT category FROM planning_module_library"
                )).fetchall()
            }
            expected_categories = {"PRODUCT", "FACTORY", "COMMERCIAL", "ASSET", "COMPLIANCE"}
            if expected_categories.issubset(categories):
                ok(f"Module categories cover product/factory/commercial/asset/compliance ({sorted(categories)})")
            else:
                fail("module categories", sorted(categories))

            template_names = {
                row[0] for row in conn.execute(text(
                    "SELECT name FROM planning_templates WHERE is_system = 1 ORDER BY sort_order"
                )).fetchall()
            }
            expected_templates = {
                "Simple OEM Knife",
                "Standard Folding Knife",
                "New Mechanism Knife",
                "Gift Set / Combo Pack",
                "Packaging-heavy Retail Product",
                "Amazon Launch Product",
            }
            if expected_templates == template_names:
                ok("All 6 named system templates seeded")
            else:
                fail("system template names", sorted(template_names))

            template_nodes = scalar(conn, "SELECT COUNT(*) FROM planning_template_nodes")
            template_edges = scalar(conn, "SELECT COUNT(*) FROM planning_template_edges")
            if template_nodes >= 45 and template_edges >= 40:
                ok(f"Template graph rows seeded (nodes={template_nodes}, edges={template_edges})")
            else:
                fail("template graph rows", f"nodes={template_nodes}, edges={template_edges}")

            duplicate_modules = scalar(conn, """
                SELECT COUNT(*) FROM (
                    SELECT module_key FROM planning_module_library
                    GROUP BY module_key HAVING COUNT(*) > 1
                )
            """)
            duplicate_templates = scalar(conn, """
                SELECT COUNT(*) FROM (
                    SELECT template_key FROM planning_templates
                    GROUP BY template_key HAVING COUNT(*) > 1
                )
            """)
            if duplicate_modules == 0 and duplicate_templates == 0:
                ok("Repeated migration run did not duplicate module/template seeds")
            else:
                fail("seed idempotency", f"modules={duplicate_modules}, templates={duplicate_templates}")

        phase_cols = {col["name"] for col in insp.get_columns("project_phases")}
        expected_phase_cols = {
            "id", "project_id", "phase_name", "phase_type", "phase_order",
            "planned_start_date", "planned_end_date", "actual_start_date",
            "actual_end_date", "owner", "status", "notes", "created_at", "updated_at",
        }
        if phase_cols == expected_phase_cols:
            ok("project_phases schema unchanged by Build 01")
        else:
            fail("project_phases schema drift", sorted(phase_cols ^ expected_phase_cols))
    finally:
        tmp.cleanup()

    print("\n── 4. Read-only service helpers ──")
    tmp, engine, Session = build_temp_db()
    try:
        import app.crud as crud
        db = Session()
        try:
            modules = crud.list_planning_modules(db)
            templates = crud.list_planning_templates(db)
            counts = crud.get_planning_template_counts(db)
            if len(modules) >= 20 and all(m.is_active for m in modules):
                ok("crud.list_planning_modules returns active seeded modules")
            else:
                fail("list_planning_modules", len(modules))
            if len(templates) == 6 and all(t.is_system for t in templates):
                ok("crud.list_planning_templates returns 6 active system templates")
            else:
                fail("list_planning_templates", len(templates))
            if counts and all(v["nodes"] > 0 and v["edges"] > 0 for v in counts.values()):
                ok("crud.get_planning_template_counts returns node/edge counts")
            else:
                fail("template counts", counts)
        finally:
            db.close()
    finally:
        tmp.cleanup()

    print("\n── 5. Admin route/template, no canvas yet ──")
    admin_route = read("app/routes/admin.py")
    base_template = read("app/templates/base.html")
    admin_modules_template = read("app/templates/admin_modules.html")
    contains_all(
        "admin.py exposes admin-only /admin/modules route",
        admin_route,
        [
            '@router.get("/admin/modules"',
            "planning_modules_inspector",
            "require_admin(current_user)",
            "list_planning_modules",
            "list_planning_templates",
            "get_planning_template_counts",
        ],
    )
    contains_all(
        "admin_modules.html renders read-only module/template inventory",
        admin_modules_template,
        [
            "Planning Modules",
            "Module Library",
            "System Templates",
            "Editing arrives in a later sandbox build",
        ],
    )
    if "<form" not in admin_modules_template and "method=\"post\"" not in admin_modules_template:
        ok("admin_modules.html has no mutation form")
    else:
        fail("admin_modules.html read-only", "found a form or POST method")
    if "/admin/modules" in base_template and "bi-diagram-3" in base_template:
        ok("Admin nav links to /admin/modules")
    else:
        fail("admin nav", "missing /admin/modules link")

    from app.main import app
    route_paths = {getattr(route, "path", "") for route in app.routes}
    if "/admin/modules" in route_paths:
        ok("FastAPI route table includes /admin/modules")
    else:
        fail("route table", "/admin/modules missing")
    sandbox_routes = [
        path for path in route_paths
        if path.startswith("/projects/{project_id}/sandbox") or path.startswith("/projects/{id}/sandbox")
    ]
    if not sandbox_routes:
        ok("No project sandbox canvas route exists in pure Build 01 scope")
    elif (ROOT / "V14_BUILD03_EXECUTION_PLAN.md").exists():
        ok("Project sandbox route exists as a later v1.4 Build 03 addition")
    else:
        fail("canvas route scope", sandbox_routes)

    print("\n── Summary ──")
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        print("\nFailures:")
        for name, reason in FAIL:
            print(f" - {name}: {reason}")
        sys.exit(1)


if __name__ == "__main__":
    main()
