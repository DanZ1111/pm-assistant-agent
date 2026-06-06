# v1.4 Build 01 Execution Plan — Planning Sandbox Schema + Module Library

## Status

Execution plan for the first v1.4 Planning Sandbox implementation build.

Predecessor: v1.3.0 release hardening shipped at `79c0b07`.

Successor: v1.4 Build 02 — Schedule Engine.

## Purpose

Create the database foundation for the visual Planning Sandbox without adding the canvas UI yet.

This build makes the module library, sandbox graph tables, and system template tables real. It also gives admins a read-only way to inspect seeded planning modules and templates.

## Scope

In:

1. Add SQLAlchemy models for:
   - `PlanningModule`
   - `PlanningSandbox`
   - `PlanningSandboxNode`
   - `PlanningSandboxEdge`
   - `PlanningTemplate`
   - `PlanningTemplateNode`
   - `PlanningTemplateEdge`
2. Add additive idempotent migrations:
   - `007_v1_4_create_planning_sandbox_core`
   - `010_v1_4_create_planning_templates`
3. Migration 007 creates:
   - `planning_module_library`
   - `planning_sandboxes`
   - `planning_sandbox_nodes`
   - `planning_sandbox_edges`
   - seed module rows
4. Migration 010 creates:
   - `planning_templates`
   - `planning_template_nodes`
   - `planning_template_edges`
   - seed 6 system templates
5. Add read-only service helpers:
   - `list_planning_modules`
   - `list_planning_templates`
   - `get_planning_template_counts`
6. Add admin-only read-only route:
   - `GET /admin/modules`
7. Add `app/templates/admin_modules.html`.
8. Add `test_v14_build01.py`.
9. Relax v1.3 regression migration-count assertions so they preserve the v1.3 migration inventory while allowing v1.4 additive migrations.

Out:

- No canvas page.
- No `/projects/{id}/sandbox` route.
- No schedule engine.
- No Apply behavior.
- No AI tools.
- No i18n expansion for admin-only labels.
- No mutation UI for modules/templates.
- No changes to existing `ProjectPhase` behavior.
- No change to v1.3 release docs except forward-compatible test assertions.

## Architecture Review

1. Problem solved: Planning Sandbox needs structured graph/template storage before visual editing or schedule computation can be safely implemented.
2. Tables/services affected: new planning tables only; read-only list helpers in `crud.py`; admin route/template for inspection.
3. Why real tables: modules, templates, nodes, and edges are reusable structured graph data; notes would make schedule calculation and template reuse brittle.
4. Service layer: routes read through `crud.py`; no direct write route is introduced in this build.
5. Change log: no project change log writes because this build does not mutate projects.
6. Rollback: tables are isolated; removing admin route/template leaves existing project behavior unchanged.

## Backend Honesty Mapping

| Visible UI | Source Of Truth | Write Path | Derived Rule | Permission | Test |
|---|---|---|---|---|---|
| Admin module list | `planning_module_library` | Seed migration only | active/inactive counts from rows | admin-only | `test_v14_build01.py` route + content checks |
| Admin template list | `planning_templates` + child rows | Seed migration only | node/edge counts from rows | admin-only | template count checks |
| Module category badge | `planning_module_library.category` | Seed migration only | direct render | admin-only | category assertions |
| Template system badge | `planning_templates.is_system` | Seed migration only | direct render | admin-only | all 6 system templates present |

## Implementation Notes

- Migration helpers use `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`.
- Seed helpers use lookup-by-key before insert so repeated startup does not duplicate rows.
- SQLite cannot reliably enforce partial unique indexes across all environments the same way PostgreSQL can; create the partial draft index where supported and keep the service-layer guard for v1.4-03.
- Migrations 008 and 009 remain unclaimed for later v1.4 builds; do not add no-op entries.
- Migration 010 ships in Build 01 so the Static Canvas Renderer can start from seeded templates in Build 03.

## Test Plan

Run:

```bash
python3 test_v14_build01.py
python3 test_v13_build10.py
python3 test_build_v121.py
```

`test_v14_build01.py` must assert:

- all 7 planning models import
- migration names 007 and 010 exist; 008 and 009 remain unclaimed
- migrations are idempotent on a fresh SQLite database
- all 7 planning tables are created
- module library has at least 20 active seeded modules
- 6 named system templates are seeded
- template node/edge rows exist
- admin `/admin/modules` route exists and is admin-only
- viewer cannot access `/admin/modules`
- no `/projects/{id}/sandbox` canvas route exists yet
- `project_phases` schema is unchanged by this build

## Acceptance Criteria

- Build 01 creates the planning data foundation only.
- No live project/timeline behavior changes.
- No project data is mutated by admin module inspection.
- All tests above pass.
