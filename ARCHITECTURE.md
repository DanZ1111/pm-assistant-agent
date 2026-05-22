# ARCHITECTURE.md — PM Product Tracker

## 1. What This System Is

An internal product project tracker for a knife/product-development company.

**What it does:**
- Tracks product projects from concept to mass production
- Shows who owns each project, which factory, what the target cost/MSRP is
- Warns when projects are delayed or missing critical information
- Attaches files and renderings to projects
- Records every important change
- Lets the user create/update projects from messy notes via AI

**What it is NOT (yet):**
- A full company brain or truth layer
- A CRM, KOL tracker, or email system
- A multi-agent orchestration system
- A complex permission system
- Jira/Asana

---

## 2. Request/Response Flow

```
Browser
  ↓
FastAPI Routes (thin — handle HTTP only)
  ↓
Service Functions in crud.py (all business logic lives here)
  ↓
SQLAlchemy Models
  ↓
SQLite (local) → PostgreSQL (Railway, v0.2)
```

**Future orchestrator flow (do not build yet):**
```
Company Orchestrator
  ↓
Product Tracker API/Skill
  ↓
Service Layer (crud.py)
  ↓
Database
```

External agents must never write directly to database tables. They must call service functions.

---

## 3. Service Layer Rules

All important database writes go through **named service functions in `crud.py`**.

Routes handle: HTTP parsing, form input, calling service functions, rendering templates, redirects.

Routes do **not** contain business logic or direct DB mutations.

Every mutating service function must call `write_change()`.

**If `crud.py` exceeds ~400 lines**, split into `app/services/`:
- `project_service.py`, `timeline_service.py`, `file_service.py`
- `change_log_service.py`, `health_service.py`, `admin_service.py`

Do not pre-split. Split when it becomes hard to navigate.

---

## 4. Data Model Principles

### Project Status
Allowed values: `active`, `completed`, `archived`, `cancelled`, `paused`

**Never use `delayed` as a project status.** Delay is a calculated condition — a project can be both `active` and delayed simultaneously.

### Delay
Calculated by `calculate_delay(project, phases)`. Source of truth is phases.

A phase is delayed if: `planned_end_date < today` AND `status NOT IN ('done', 'skipped')`.

`estimated_launch_date` may be written back to the project row as a cache.

### Current Stage
Derived by `derive_current_stage(phases)` = first phase where status is not `done` or `skipped`.

Stored on project row as a cache only. **Phases are the source of truth.**

### Needs Info
Calculated by `get_project_health(project, phases, files)`. Never stored.

A project can be `active + delayed + needs_info` simultaneously.

### Field Levels

| Level | Fields | Behavior |
|---|---|---|
| **Hard required** | `name` | Blocks creation if missing |
| **Health critical** | `brand`, `product_manager`, `engineer`, `factory`, `target_factory_cost`, `target_msrp`, `planned_launch_date`, `project_thesis` (≥80 chars), at least one timeline phase | Red warning, does NOT block creation |
| **Recommended** | `sku`, `product_type`, phase owners, at least one file | Yellow warning |

---

## 5. Product Thesis

Product Thesis is **not a normal note**. It is the soul of the project.

It must answer: why this product exists, who it's for, what makes it different, why it fits this brand, the target price logic, and key risks.

- Stored as a single text field (`project_thesis`)
- Treated as incomplete if empty or fewer than 80 characters
- **Always displayed as the first main section on the project detail page**
- Never buried in a miscellaneous notes area

---

## 6. Change Log Rules

Every important change must create a `ProjectChange` record via `write_change()`.

Two types of changes:
1. **Field-level** (`change_type=field_update`): field_name, old_value, new_value
2. **Event-level** (`change_type=event_note`): summary only (e.g. "Factory rejected Prototype 1 because handle tolerance was too tight")

Changes to record: field edits, phase edits, file uploads, archive, AI updates.

`write_change()` is called **inside** service functions. Routes never write change log entries directly.

---

## 7. File Rules

Files are **project evidence**, not just visuals. Categories:
`rendering`, `reference`, `quotation`, `thesis`, `factory_feedback`, `packaging`, `other`

Files must have `file_category` and optionally `source_note` to stay organized over time.

Image files are displayed at **full resolution** in a lightbox — no compression.

---

## 8. AI Rules

**AI proposes. User confirms.**

AI may: extract fields, draft thesis, summarize files, suggest project matches, identify gaps.

AI must not silently overwrite: factory, cost, MSRP, PM, engineer, launch date, phase status, thesis.

All AI writes that matter require explicit user confirmation and must be recorded in the change log with `changed_by="ai"`.

---

## 9. Schema Evolution Rule

Before adding a new column, ask:
- Is this field used frequently enough to warrant structured storage?
- Does it need filtering, sorting, calculation, or reporting?
- Could it live in `project_thesis`, `phase.notes`, `source_note`, or a change log entry instead?

**Prefer free text until repeated usage proves a field needs its own column.**

For any schema change: write a short Architecture Review answering what tables/services/UI/AI behavior are affected (see `CLAUDE.md §Before Changing the Database Schema`).

---

## 10. Build Order

| Build | Scope |
|---|---|
| 1 | Project CRUD, health check, card/table list, detail page, form |
| 1.5 | Database Inspector (`/admin/database`) + this file |
| 2 | Timeline phases, delay calculation, delay badges |
| 3 | File uploads, rendering gallery, lightbox |
| 4 | Full change log (backfill write_change across all builds) |
| 5 | AI text intake |
| 6 | AI file/image intake (PDF, Word, Excel, vision) |
| 7 | AI update existing project (fuzzy match) |
