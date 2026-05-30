# PM Product Tracker — Complete Rebuild Plan

## Plan Changelog

| Version | Changes |
|---|---|
| v1 | Initial plan: M1-M7, Build 1 included timeline + files + change log together |
| v2 | Split milestones: Build 1 = CRUD only, separate builds for timeline/files/log/AI. Added `phase_type`, `file_category`, `change_type`, two-kind change log. Removed `delayed` as primary status. `current_stage` derived from phases. Product Thesis as first-class section. Card + table toggle view. Phase edit via modal not inline. Service layer boundary principle. |
| v3 | Added: Project Health Check system (replaces scattered "missing fields" logic). Added: Database Inspector page (Build 1.5). Added: `get_project_health()` service function. Added: field levels (hard required / health critical / recommended). Added: `project_thesis` completeness check (< 80 chars = incomplete). Expanded "Needs Attention" section. Added: ARCHITECTURE.md requirement. Added: crud.py split path for future. Added plan changelog. |
| v4 (current) | Build 4 plan: Change Log verification. All backend plumbing already complete (write_change called in all 8 service functions, template renders Section 4, route passes changes). Build 4 = create test_build4.py + fix any UI gaps found during testing. |

---

## Context

The previous PM Assistant was a chat-only entity/record system. It's being replaced with a structured product project tracker for a knife/product-development company — manage projects from concept to mass production, with timeline tracking, rendering uploads, delay warnings, and AI intake from messy notes or files.

**Keep:** `.env` (OPENAI_API_KEY), `.gitignore`
**Delete everything else** and create a clean new structure.
**Database:** SQLite locally (Railway PostgreSQL at v0.2)
**Auth:** None — internal tool, single user for now

---

## New App Structure

```
/Users/Mordred5687/Dev Projects/PM Assistant Agent/
  app/
    __init__.py
    main.py              # FastAPI app, route mounting, lifespan
    database.py          # SQLAlchemy engine + get_db()
    models.py            # All ORM models
    schemas.py           # Pydantic schemas
    crud.py              # Service functions — split into services/ if it grows too large
    ai/
      __init__.py
      parser.py
      prompts.py
      matching.py
    routes/
      __init__.py
      projects.py
      intake.py
      files.py
      admin.py           # Database Inspector
    templates/
      base.html
      projects_list.html
      project_detail.html
      project_form.html
      intake.html
      admin_db.html      # Database Inspector page
    static/
      css/styles.css
      js/main.js
    uploads/
  ARCHITECTURE.md        # Living architecture principles document
  requirements.txt
  .env
  .gitignore
  run.py
```

**Future crud.py split path** (when it grows too large):
```
app/services/
  project_service.py
  timeline_service.py
  file_service.py
  change_log_service.py
  health_service.py
  admin_service.py
```
Do not pre-split now. Split when crud.py exceeds ~400 lines.

---

## Database Schema

### `projects`

| Field | Type | Notes |
|---|---|---|
| id | Integer PK | |
| name | String | **only hard-required field** |
| sku | String | nullable |
| brand | String | nullable — health critical |
| status | String | active / completed / archived / cancelled / paused — **never "delayed"** |
| current_stage | String | nullable — **cached, derived from phases** |
| product_type | String | nullable |
| project_owner | String | nullable |
| product_manager | String | nullable — health critical |
| engineer | String | nullable — health critical |
| factory | String | nullable — health critical |
| target_factory_cost | Float | nullable — health critical |
| target_msrp | Float | nullable — health critical |
| planned_launch_date | Date | nullable — health critical |
| estimated_launch_date | Date | nullable — auto-calculated |
| project_thesis | Text | nullable — health critical (and must be ≥ 80 chars to count as complete) |
| created_at | DateTime | |
| updated_at | DateTime | |
| archived_at | DateTime | nullable |

**Delay** — calculated condition, never a status field. Derived in `calculate_delay()`.
**`current_stage`** — cached from phases. Rule: first phase where `status NOT IN ('done', 'skipped')`. Recalculated on any phase change.
**`needs_info`** — calculated from `get_project_health()`. Never stored.

### `project_phases`

| Field | Type | Notes |
|---|---|---|
| id | Integer PK | |
| project_id | FK → projects | |
| phase_name | String | |
| phase_type | String | design / engineering / prototype / review / production / launch |
| phase_order | Integer | |
| planned_start_date | Date | nullable |
| planned_end_date | Date | nullable — health critical for active phase |
| actual_start_date | Date | nullable |
| actual_end_date | Date | nullable |
| owner | String | nullable — recommended |
| status | String | not_started / in_progress / done / delayed / skipped |
| notes | Text | nullable |
| created_at | DateTime | |
| updated_at | DateTime | |

### `project_files`

| Field | Type | Notes |
|---|---|---|
| id | Integer PK | |
| project_id | FK → projects | |
| filename | String | saved name on disk |
| original_filename | String | user's filename |
| file_path | String | relative path under uploads/ |
| file_type | String | image / pdf / word / excel / other |
| file_category | String | rendering / reference / quotation / thesis / factory_feedback / packaging / other |
| file_size | Integer | bytes |
| ai_summary | Text | nullable |
| source_note | Text | nullable |
| uploaded_at | DateTime | |

### `project_changes`

| Field | Type | Notes |
|---|---|---|
| id | Integer PK | |
| project_id | FK → projects | |
| changed_at | DateTime | |
| changed_by | String | user / ai |
| change_type | String | field_update / event_note / phase_update / file_upload / ai_update |
| field_name | String | nullable — for field_update |
| old_value | Text | nullable |
| new_value | Text | nullable |
| summary | Text | human-readable description |
| reason | Text | nullable |
| delay_impact_days | Integer | nullable |
| source_type | String | manual_edit / ai_chat / file_upload / timeline_update |

Two kinds of changes:
1. **Field-level:** `change_type=field_update`, `field_name`, `old_value`, `new_value`
2. **Event-level:** `change_type=event_note`, `summary` only

### `ai_messages`

| Field | Type | Notes |
|---|---|---|
| id | Integer PK | |
| project_id | Integer | nullable FK |
| role | String | user / assistant / system |
| message | Text | |
| created_at | DateTime | |
| metadata_json | JSON | parsed fields, confidence, match result |

---

## Field Levels

| Level | Fields | Behavior |
|---|---|---|
| **Hard required** | `name` | Cannot create without it |
| **Health critical** | `brand`, `product_manager`, `engineer`, `factory`, `target_factory_cost`, `target_msrp`, `planned_launch_date`, `project_thesis` (≥80 chars), at least one phase, active phase has `planned_end_date` | Red warning if missing — does NOT block creation |
| **Recommended** | `sku`, `product_type`, phase owners, at least one uploaded file, `estimated_launch_date` | Yellow warning if missing |

`project_thesis` with fewer than 80 characters is treated as incomplete (same as missing).

---

## Project Health Check

Service function in `crud.py`:

```python
def get_project_health(project, phases, files) -> dict:
    critical_missing = []
    recommended_missing = []

    if not project.brand: critical_missing.append("brand")
    if not project.product_manager: critical_missing.append("product_manager")
    if not project.engineer: critical_missing.append("engineer")
    if not project.factory: critical_missing.append("factory")
    if not project.target_factory_cost: critical_missing.append("target_factory_cost")
    if not project.target_msrp: critical_missing.append("target_msrp")
    if not project.planned_launch_date: critical_missing.append("planned_launch_date")
    if not project.project_thesis or len(project.project_thesis) < 80:
        critical_missing.append("project_thesis")
    if not phases: critical_missing.append("timeline_phases")
    else:
        active_phase = next((p for p in phases if p.status not in ("done","skipped")), None)
        if active_phase and not active_phase.planned_end_date:
            critical_missing.append("active_phase_planned_end_date")

    if not project.sku: recommended_missing.append("sku")
    if not project.product_type: recommended_missing.append("product_type")
    if not files: recommended_missing.append("at_least_one_file")
    # phase owner check
    for p in phases:
        if not p.owner:
            recommended_missing.append("phase_owners")
            break

    return {
        "needs_info": len(critical_missing) > 0,
        "critical_missing": critical_missing,
        "recommended_missing": recommended_missing,
    }
```

**Rules:**
- Never stored as a project status field
- Called in routes when rendering project list and project detail
- AI intake also calls it after extraction to show what's missing before confirmation

---

## Delay Calculation

```python
def calculate_delay(project, phases) -> dict | None:
    today = date.today()
    delayed = [
        p for p in phases
        if p.planned_end_date
        and p.planned_end_date < today
        and p.status not in ("done", "skipped")
    ]
    if not delayed:
        return None
    worst = max(delayed, key=lambda p: (today - p.planned_end_date).days)
    delay_days = (today - worst.planned_end_date).days
    estimated_launch = (
        project.planned_launch_date + timedelta(days=delay_days)
        if project.planned_launch_date else None
    )
    return {"blocking_phase": worst.phase_name, "days_late": delay_days, "estimated_launch": estimated_launch}
```

Writes `estimated_launch_date` back to project row. Called after any phase change.

---

## Default Phase Templates

**Single prototype** (8 phases, `phase_order` 1–8):
Design → Engineering Review → Prototype 1 → Prototype Review → Pre-production Sample → Mass Production → Launch Prep → Launch

**Double prototype** (10 phases):
Design → Engineering Review → Prototype 1 → Prototype 1 Review → Prototype 2 → Prototype 2 Review → Pre-production Sample → Mass Production → Launch Prep → Launch

Applied at project creation. User can add/remove/reorder on detail page.

---

## UI / UX

### All Projects Page

- **Default: Card grid** (3 cols desktop, 2 tablet, 1 mobile)
- **Toggle: Table view** — for comparing cost, factory, PM, dates side-by-side
- **Filters:** All / Active / Delayed / Needs Info / Completed / Archived + Brand, PM, Stage dropdowns

**"Needs Attention" section at top:**
- Delayed projects (red) + days late
- Projects missing critical info (orange) + count of missing fields
- Phases due this week

**Card shows:** name, brand, SKU, stage, PM, factory cost, MSRP, planned launch
**Badges:** red "X days late" if delayed, orange "N missing fields" if `needs_info`

### Project Detail Page

```
[Top bar]  Project Name  |  Brand  |  Status badge
           [DELAYED — X days, est. launch Aug 27]  ← red banner if delayed
           [Missing Info: factory, target_cost, ...]  ← orange banner if needs_info

[Left sidebar]           [Main content, scrollable]
  Brand                   1. PRODUCT THESIS  ← first section, prominent
  SKU                        Why this product exists
  Status                     Customer / Use Case
  PM                         Core Problem
  Engineer                   Product Bet
  Factory                    Differentiation
  Target Cost                Brand Fit
  Target MSRP                Target Price Logic
  Planned Launch             Risks / Unknowns
  Est. Launch
  [Edit button]           2. TIMELINE
                             Phase table, planned/actual dates, status badges
                             Edit each phase via modal (not inline — too buggy for MVP)
                             Add/remove phases
                             Delay summary if applicable

                          3. FILES & RENDERINGS
                             Category filter tabs (All / Renderings / Quotations / etc.)
                             Image gallery: 200px thumbnails → full-res lightbox
                             Non-image files: icon + download link
                             Drag-drop upload zone

                          4. CHANGE LOG
                             Newest first, field updates and event notes
```

### Rendering Lightbox
- Click → full-screen overlay
- `max-width: 95vw; max-height: 90vh; object-fit: contain` — no compression
- Left/right arrows to navigate within project
- Close on Escape or click outside

### Phase Edit
- Each phase has **Edit** button → modal form → submit → refresh (no inline editing)

### AI Intake Page
- Split panel: left = text input + file drop, right = extracted fields + health check warnings + confirm

---

## Database Inspector (Build 1.5)

Route: `GET /admin/database`
Template: `admin_db.html`
**Read-only — no editing from this page.**

**Section 1: Table Overview**
For each table: row count, `created_at` of newest row, `updated_at` of newest row

**Section 2: Field Usage Report**
For each table, for each nullable field:
- field name
- non-empty count / total rows
- usage percentage
- unique value count (where reasonable)

Example display:
```
projects.target_factory_cost   3 / 28   10.7%
projects.project_thesis        22 / 28  78.5%
project_files.file_category    5 / 40   12.5%
```

**Section 3: Project Health Summary**
Count of active projects missing each critical field:
```
factory              missing in 8 / 20 active projects
target_factory_cost  missing in 12 / 20 active projects
project_thesis       incomplete in 5 / 20 active projects
```
+ list of specific project names for each missing field

**Section 4: Recent Changes Feed**
Latest 50 `project_changes` rows:
- project name, changed_at, change_type, field_name, old_value, new_value, summary, changed_by

---

## Service Layer Boundary Rules

All encoded in `ARCHITECTURE.md`:

1. **Routes never mutate DB directly.** All writes go through named service functions in `crud.py`.
2. **All mutating service functions call `write_change()`.** Routes never write change log directly.
3. **Delay is calculated, not stored as status.** `calculate_delay()` is the single source.
4. **`current_stage` is derived from phases, not manually maintained.**
5. **Health check is calculated, not stored.** `get_project_health()` is the single source.
6. **AI proposes, user confirms.** AI never silently overwrites important fields.
7. **Schema evolution rule:** Do not add new columns casually. Prefer `notes` / `project_thesis` / change log free text until a field proves repeated use. Use Database Inspector to verify field usage before promoting to a hard column.
8. **Before any schema change or major feature addition:** write a short Architecture Review answering: what tables/services/UI/AI behavior are affected? Does this bypass the service layer? Is this field likely to be used often?

---

## Build Milestones

### Build 1 — Project CRUD Skeleton

- Clean file structure
- `database.py` (SQLite), `models.py` (all 5 tables), `crud.py` skeleton
- `get_project_health()` service function
- All Projects page: card grid + table toggle + filters + "Needs Attention" section
- "Needs Info" and delay badges on cards
- Create Project form (`name` required, all other fields optional with helper text)
- Edit Project page
- Archive/delete
- Project Detail: sidebar + Product Thesis section (prominent) + health warning banners + placeholder sections for Timeline/Files/Log

**Done when:** Create, view, edit, archive. Product Thesis visible. Needs Info badge works. Card + table view both render.

---

### Build 1.5 — Database Inspector + ARCHITECTURE.md

- `GET /admin/database` → `admin_db.html`
- Table overview, field usage report, project health summary, recent changes feed (reads `project_changes`, which is empty until Build 4 — show gracefully)
- Create `ARCHITECTURE.md` with all service-layer rules and schema evolution principles

**Done when:** `/admin/database` loads, shows field usage %, shows which projects are missing critical fields.

---

### Build 2 — Timeline + Delay

- `project_phases` CRUD in `crud.py`
- Phase templates at project creation (single/double prototype selection on create form)
- Phase edit modal on detail page
- `recalculate_stage_and_delay()` called on every phase change
- Delay banner on detail page, delay badge on cards
- "Needs Attention" section populated with delayed projects + phases due this week

**Done when:** 10-phase project auto-created, set Prototype 1 `planned_end_date` to last week with status `in_progress` → red badge on list + delay summary on detail.

---

### Build 3 — File Uploads + Rendering Gallery

- `project_files` CRUD
- File upload endpoint, drag-drop UI, `uploads/` storage
- Serve files at `/uploads/{filename}`
- Image gallery with category filter tabs
- Full-res lightbox (left/right navigation, no compression)
- Non-image file list with download
- Delete file
- `file_category` selector on upload

**Done when:** Upload PNG rendering → gallery → full-res lightbox. Upload PDF → downloadable. File upload recorded in change log (even though Build 4 comes later — write the change log call now, it will write to the table).

---

### Build 4 — Change Log ✓ SHIPPED v0.4.0

#### Status: Backend complete, test file needed

**What's already done (verified by Explore agent):**
- `write_change()` defined and called in all 8 mutating service functions:
  - `create_project()` — event_note on creation
  - `update_project()` — field_update per changed field (field_name, old_value, new_value)
  - `archive_project()` — field_update status → archived
  - `add_phase()`, `update_phase()`, `delete_phase()` — phase_update
  - `upload_file()` — file_upload with original_filename + category
  - `delete_file()` — file_upload change_type with "deleted" summary
- `project_detail.html` Section 4 renders change log with:
  - field_update: "Field Name: old → new" format
  - event_note / phase_update / file_upload: summary text
  - Timestamp + changed_by
  - Empty state: "No changes recorded yet."
- Route `GET /projects/{id}` passes `changes` = last 30, sorted newest-first

**What Build 4 does:**
1. Create `test_build4.py` (Playwright) covering all 4 TESTING_RULES.md flows:
   - Edit MSRP → change log entry shows field_name="target_msrp", old → new values
   - Edit a phase (e.g. status or end date) → change log shows phase_update entry
   - Upload a file → change log shows file_upload entry with filename
   - Archive a project → change log shows "Project archived." entry
2. Run tests against live server; fix any failures found
3. Add change log count to section header (e.g. "Change Log (5)")

**Critical files:**
- `test_build4.py` — new file to create
- `app/templates/project_detail.html` lines 457–486 — change log section (minor header update only)
- `app/crud.py` — no changes expected (all write_change calls verified present)
- `app/routes/projects.py` — no changes expected

**CSS classes in use (styles.css):**
- `.change-log`, `.change-entry`, `.change-field`, `.change-old`, `.change-new`, `.change-time`, `.change-by`
- `.change-field_update`, `.change-phase_update`, `.change-file_upload`, `.change-event_note` — for per-type color accent

**Verification:** `python3 test_build4.py` — all tests pass

**Done when:** Edit MSRP → change log shows old/new. Upload file → file upload entry. Archive → archive entry. test_build4.py passes.

---

### Build 5 — AI Text Intake ✓ SHIPPED v0.5.0

#### Status: Greenfield — only AIMessage DB model exists

**What's already in place:**
- `AIMessage` ORM model in `models.py` (lines 94–104): id, project_id (nullable FK), role, message, created_at, metadata_json
- `Project.ai_messages` relationship defined
- `AIMessage` imported in `crud.py` (line 5) but unused
- `app/ai/__init__.py` exists (empty)
- Nav link in `base.html` (lines 22–24): disabled, href="#", tooltip "Coming in Build 5"
- `write_change()` supports `changed_by="ai"` and `source_type="ai_chat"`
- OPENAI_API_KEY set in `.env`, `openai` package in requirements.txt (unpinned)

**What Build 5 creates (8 files):**

1. **`app/ai/prompts.py`** — extraction system prompt (constant string)
   - Instructs GPT-4o to extract: name, brand, sku, product_type, product_manager, engineer, factory, target_factory_cost, target_msrp, planned_launch_date, project_thesis
   - Instructs: omit fields not in text, never invent values, return JSON only

2. **`app/ai/parser.py`** — GPT-4o extraction function
   ```python
   def extract_project_fields(raw_text: str) -> dict
   ```
   - Uses `openai.OpenAI` client, `gpt-4o` model, `response_format={"type": "json_object"}`, `temperature=0.1`
   - Lazy-initializes client (calls `load_dotenv()` on first use)
   - Returns dict of extracted fields; on any exception returns `{"_error": str(e)}`

3. **`app/crud.py`** — add `save_ai_message()` service function
   ```python
   def save_ai_message(db, project_id, role, message, metadata) -> AIMessage
   ```

4. **`app/routes/intake.py`** — three routes
   - `GET /ai/intake` → renders intake.html with `proposed=None`
   - `POST /ai/intake/extract` → calls `extract_project_fields()`, runs health check via `SimpleNamespace`, saves ai_messages (project_id=None), renders intake.html with `proposed` dict + `health`
   - `POST /ai/intake/confirm` → accepts all fields as form data (user may edit), calls `crud.create_project()`, saves ai_messages tied to new project.id, calls `write_change(changed_by="ai")`, redirects to `/projects/{id}`
   - Define `_parse_float()` and `_parse_date()` locally (same logic as projects.py) to avoid cross-route imports

5. **`app/templates/intake.html`** — two-state template
   - **State 1** (`proposed is None`): centered textarea + "Extract Fields" button + minimal instructions
   - **State 2** (`proposed is not None`): two-column layout
     - Left col: original text (read-only reference, collapsible)
     - Right col: proposed fields pre-filled in edit form + health check warnings (critical missing = red, recommended = yellow) + "Confirm & Create Project" button + prototype_rounds radio
   - Error alert at top if `error` is set
   - All proposed values passed as `value="{{ proposed.get('field', '') or '' }}"` — user can edit before confirming
   - `raw_text` passed as hidden field in confirm form

6. **`app/main.py`** — import and mount intake router

7. **`app/templates/base.html`** — enable AI Intake nav link:
   - Remove `nav-link-disabled` class
   - Change `href="#"` to `href="/ai/intake"`
   - Remove `title="Coming in Build 5"`

8. **`test_build5.py`** — Playwright tests:
   - Intake page loads (GET /ai/intake → 200, textarea visible)
   - POST extract with real text → proposed fields form appears (real OpenAI call; short timeout-robust input used)
   - No project created yet after extract-only (DB count unchanged)
   - POST confirm with known values → redirects to project detail (200)
   - Project detail shows AI-sourced change log entry
   - No server errors

**Health check in extract route** — uses `types.SimpleNamespace` duck-typing:
```python
proj_ns = types.SimpleNamespace(
    brand=extracted.get("brand"), product_manager=extracted.get("product_manager"),
    engineer=extracted.get("engineer"), factory=extracted.get("factory"),
    target_factory_cost=extracted.get("target_factory_cost"), target_msrp=extracted.get("target_msrp"),
    planned_launch_date=extracted.get("planned_launch_date"),
    project_thesis=extracted.get("project_thesis"), sku=extracted.get("sku"),
    product_type=extracted.get("product_type"),
)
health = crud.get_project_health(proj_ns, [], [])
```

**AI rules enforced:**
- Extraction route does NOT write to projects table — only ai_messages
- Confirm route requires user to POST the fields (they see and can edit them)
- Change log records `changed_by="ai"`, `source_type="ai_chat"` on the creation event_note

**Critical files to modify:**
- `app/crud.py` — add `save_ai_message()` (lines after existing CRUD functions)
- `app/main.py` — add intake router import + `app.include_router(intake_router)`
- `app/templates/base.html` — lines 22–24 (enable nav link)

**Critical files to create:**
- `app/ai/prompts.py`
- `app/ai/parser.py`
- `app/routes/intake.py`
- `app/templates/intake.html`
- `test_build5.py`

**Verification:** `python3 test_build5.py` — all tests pass

**Done when:** Type messy product notes → AI extracts fields → health check shown → user confirms → project created, ai_messages stored, change log shows AI source.

---

### Build 6 — AI File/Image Intake ✓ SHIPPED v0.6.0

#### Status: Greenfield — builds on top of Build 5 intake flow

**What's already in place (Build 5):**
- `app/ai/parser.py`: `extract_project_fields(raw_text)` — GPT-5.4 JSON mode for text
- `app/routes/intake.py`: GET `/ai/intake`, POST `/ai/intake/extract`, POST `/ai/intake/confirm`
- `app/templates/intake.html`: State 1 (textarea) → State 2 (proposed fields + health check + confirm form)
- `crud.upload_file()` — saves file record to DB (no `ai_summary` param yet)
- `UPLOAD_DIR` defined in `crud.py`, used by `files.py`
- `project_files.ai_summary` column exists in ORM model

**What Build 6 adds (7 changes):**

1. **`requirements.txt`** — add `pypdf` for PDF text extraction

2. **`app/ai/parser.py`** — add two new functions:
   - `extract_from_pdf(file_path: str) -> dict`
     - Uses `pypdf.PdfReader` to extract text page by page (max 10 pages)
     - Passes combined text to existing `extract_project_fields()` for field extraction
     - Returns `{"extracted": dict, "raw_text": str}`
   - `extract_from_image(file_path: str) -> dict`
     - Reads image as base64
     - Single vision API call with JSON mode: returns both extracted fields AND `"ai_summary"` string
     - System prompt instructs: extract known fields, plus write `ai_summary` = 2-3 sentence product description
     - Returns `{"extracted": dict, "ai_summary": str}`

3. **`app/crud.py`** — add `ai_summary: str = None` param to `upload_file()` signature and DB write

4. **`app/routes/intake.py`** — add one new route + modify confirm:
   - `POST /ai/intake/extract-file` — new route:
     - Accepts `UploadFile`, `file_category: str = Form("reference")`
     - Saves file to `UPLOAD_DIR` with UUID name (reuses `files.py` pattern)
     - Detects file type; calls `extract_from_pdf()` or `extract_from_image()` based on type
     - Saves ai_messages (project_id=None)
     - Returns State 2 with `proposed`, `health`, and extra context vars: `uploaded_filename`, `uploaded_original_filename`, `uploaded_file_type`, `uploaded_file_category`, `uploaded_ai_summary`
   - `POST /ai/intake/confirm` — add hidden file params:
     - `uploaded_filename: str = Form("")`, `uploaded_original_filename: str = Form("")`, `uploaded_file_type: str = Form("")`, `uploaded_file_category: str = Form("reference")`, `uploaded_ai_summary: str = Form("")`
     - After `create_project()`, if `uploaded_filename` is set: call `crud.upload_file(..., ai_summary=uploaded_ai_summary)` to attach file to project

5. **`app/templates/intake.html`** — modify State 1 + State 2:
   - State 1: Add a file upload section below textarea with an OR divider. Two separate forms with their own submit buttons:
     - Form 1 (existing): textarea → POST `/ai/intake/extract`
     - Form 2 (new): file input + category select → POST `/ai/intake/extract-file` (`enctype="multipart/form-data"`)
   - State 2: Add hidden fields for uploaded file info so confirm route can attach the file. Show collapsible "AI Summary" if `uploaded_ai_summary` is present.

6. **`test_build6.py`** — Playwright + requests tests:
   - Test: GET `/ai/intake` → file input visible on page
   - Test: POST PDF to `/ai/intake/extract-file` → State 2 appears with proposed fields
   - Test: POST image to `/ai/intake/extract-file` → ai_summary generated and shown
   - Test: POST `/ai/intake/confirm` with `uploaded_filename` → project_files row exists with ai_summary
   - Test: No server errors

**For unsupported file types** (not PDF or image): return an error message on State 1.

**Critical files to modify:**
- `requirements.txt` — add `pypdf`
- `app/ai/parser.py` — add `extract_from_pdf()`, `extract_from_image()`
- `app/crud.py` — add `ai_summary` param to `upload_file()`
- `app/routes/intake.py` — new `extract-file` route + modify confirm
- `app/templates/intake.html` — add file form to State 1, hidden fields to State 2

**Critical files to create:**
- `test_build6.py`

**Verification:** `python3 test_build6.py` — all tests pass, project_files row with ai_summary confirmed.

---

### Help AI Assistant ← CURRENT TASK (between Build 6 and Build 7)

#### Context
The Help/Version modal was added with an "Ask AI" tab that is currently a disabled placeholder. The user wants to wire it up so team members can ask how to use the software and get answers grounded in `USER_GUIDE.md` and `CHANGELOG.md`.

**What's already in place:**
- `base.html` lines 219–235: `#pane-ai` tab with disabled textarea + disabled button + placeholder alert
- `USER_GUIDE.md` (~7,600 chars), `CHANGELOG.md` (~3,200 chars) in project root
- `_get_client()` in `app/ai/parser.py` — reusable OpenAI singleton (gpt-5.4, timeout=120s)
- `crud.save_ai_message()` for audit trail

**What this task adds (4 changes):**

1. **`app/ai/parser.py`** — add `answer_help_question(question: str) -> str`:
   - Reads `USER_GUIDE.md` and `CHANGELOG.md` from project root (cap at 8,000 chars each)
   - System prompt: "You are a help assistant for PM Product Tracker. Answer based only on the docs below. Be concise (under 200 words). Use numbered steps for how-to. Never invent features."
   - Call `gpt-5.4`, **no JSON mode** (natural language answer), `temperature=0.2`, `max_completion_tokens=600`
   - Returns answer string; on exception returns `"Sorry, I couldn't answer that right now: {error}"`

2. **`app/routes/help.py`** — new file, one route:
   - `POST /ai/help/ask` — accepts JSON `{"question": "..."}`, calls `answer_help_question()`, saves Q&A to `ai_messages` (project_id=None), returns `{"answer": "..."}`

3. **`app/main.py`** — import and mount `help_router`

4. **`app/templates/base.html`** — update `#pane-ai`:
   - Add `id="helpAskTextarea"` to textarea, remove `disabled`
   - Add `id="helpAskBtn"` to button, remove `disabled`
   - Add `id="helpAskResponse"` div below button for displaying answer
   - Remove "coming soon" placeholder alert
   - Add JS `fetch` block (inline in modal area): POST to `/ai/help/ask`, show "Thinking…" while waiting, render response with line breaks

**Response rendering in JS:**
```javascript
response.answer.replace(/\n/g, '<br>')
```
Renders newlines as breaks so numbered lists and bullets display correctly.

**Critical files:**
- `app/ai/parser.py` — add `answer_help_question()`
- `app/routes/help.py` — new
- `app/main.py` — add help_router
- `app/templates/base.html` — enable Ask AI tab + JS wiring

**Verification:**
- `curl -s -X POST http://localhost:8000/ai/help/ask -H "Content-Type: application/json" -d '{"question":"What does Needs Info mean?"}' | python3 -m json.tool`
- Playwright: open modal → Ask AI tab → type question → click Ask → response appears (non-empty)

---

### Build 7 — AI Update Existing Project ✓ SHIPPED v0.7.0

#### Status: Greenfield — matching module doesn't exist yet

**What's already in place:**
- `crud.update_project(db, project_id, data, changed_by="user")` — already supports `changed_by="ai"`, writes per-field change log entries
- `crud.get_projects()` — has `.ilike()` search pattern reusable for candidate filtering
- `app/routes/intake.py` — extract routes return State 2 with `proposed` dict; confirm route creates projects
- `app/templates/intake.html` — State 2 confirm form; hidden fields pattern already in use
- `write_change()` fully supports `changed_by="ai"` and `source_type="ai_chat"`
- TESTING_RULES Build 7: fuzzy match suggests match, user confirms update (no duplicate), change log shows `changed_by=ai`

**What Build 7 adds (4 changes):**

1. **`app/ai/matching.py`** — new file:
   ```python
   import difflib
   MATCH_THRESHOLD = 0.65

   def find_best_match(candidate_name: str, projects: list) -> tuple[Any, float]:
   ```
   - Case-insensitive exact match → score 1.0
   - Substring containment → score 0.85
   - `difflib.SequenceMatcher` ratio for everything else
   - Returns `(best_project, best_score)` — `(None, 0.0)` if no candidate name or no projects

2. **`app/routes/intake.py`** — three targeted changes:
   - **In `intake_extract` and `intake_extract_file`:** after extraction, fetch all non-archived projects, call `find_best_match(extracted.get("name",""), projects)`, pass `matched_project` and `match_score` to template (None/0.0 if below threshold)
   - **In `intake_confirm`:** add `project_id: str = Form("")` and `action: str = Form("create")` params. If `action == "update"` and project_id: call `crud.update_project(db, int(project_id), update_data, changed_by="ai")` + `write_change(event_note, changed_by="ai", source_type="ai_chat")` + `db.commit()` → redirect to existing project. For update, filter `update_data` to only non-None fields (don't blank existing data). If `action == "create"`: existing flow unchanged.

3. **`app/templates/intake.html`** — two additions to State 2:
   - **Match banner** (between health check alerts and proposed fields form): `{% if matched_project %}` → info alert showing project name, brand, match %, short description of choice
   - **In confirm form:** add `<input type="hidden" name="project_id" value="{{ matched_project.id if matched_project else '' }}">`. Below existing "Confirm & Create Project" button, add `{% if matched_project %}` → warning-styled "Update '{{ matched_project.name }}'" submit button with `name="action" value="update"`. Existing create button gets `name="action" value="create"`.

4. **`test_build7.py`** — three flows per TESTING_RULES:
   - **Test 1 (fuzzy match suggests match):** Create project "XYZ Unique Blade B7"; POST extract with text clearly naming "XYZ Unique Blade B7"; check response HTML shows match banner with project name
   - **Test 2 (update, no duplicate):** Count projects before; POST `/ai/intake/confirm` with `action=update`, known `project_id`, field values including updated MSRP; count projects after (same); visit project → MSRP updated
   - **Test 3 (change log AI attribution):** After update confirm → visit project detail → `.change-log` contains `changed_by=ai` entry

**Key constraint — update filters fields:**
```python
update_data = {k: v for k, v in data.items() if v is not None and k != "status"}
```
Only fields that were actually extracted (non-empty) are applied. Existing fields not mentioned in the input are preserved.

**Critical files to create:**
- `app/ai/matching.py`
- `test_build7.py`

**Critical files to modify:**
- `app/routes/intake.py` — matching call in two extract routes + action/project_id in confirm
- `app/templates/intake.html` — match banner + second submit button

**Verification:** `python3 test_build7.py` — all tests pass

---

---

### Build 8 — Multi-Role Auth ✓ SHIPPED v0.8.0

#### Context
Team needs login before Railway deploy. No User model exists. Adding username/password auth with three roles (admin/pm/viewer), invite-PIN registration, and field-level permissions (factory + engineer hidden from viewers).

#### Permission Matrix

| Action | Admin | PM | Viewer |
|---|---|---|---|
| View all projects | ✓ | ✓ | ✓ |
| Create project | ✓ | ✓ | ✗ |
| Edit project (their own) | ✓ | ✓ | ✗ |
| Edit any project | ✓ | ✗ | ✗ |
| Archive / delete | ✓ | own only | ✗ |
| See factory field | ✓ | ✓ | ✗ |
| See engineer field | ✓ | ✓ | ✗ |
| Upload / delete files | ✓ | own only | ✗ |
| AI Intake | ✓ | ✓ | ✗ |
| Admin DB inspector | ✓ | ✗ | ✗ |
| User management / PINs | ✓ | ✗ | ✗ |
| Help modal / Ask AI | ✓ | ✓ | ✓ |

**"Own project"** = `project.project_manager` (case-insensitive) matches user's `username` OR `display_name`.

#### New Database Tables

**`users`**
| Field | Type |
|---|---|
| id | Integer PK |
| username | String, unique, not null |
| display_name | String, nullable |
| hashed_password | String, not null |
| role | String — admin / pm / viewer |
| created_at | DateTime |
| last_login | DateTime, nullable |

**`invite_pins`**
| Field | Type |
|---|---|
| id | Integer PK |
| pin | String, unique (8-char alphanumeric, uppercase) |
| role | String — pm / viewer |
| created_by_user_id | FK → users |
| used_by_user_id | FK → users, nullable |
| used_at | DateTime, nullable |
| created_at | DateTime |

**`user_sessions`**
| Field | Type |
|---|---|
| id | Integer PK |
| token | String, unique (UUID hex) |
| user_id | FK → users |
| created_at | DateTime |
| expires_at | DateTime (7 days) |

#### New Files

**`app/dependencies.py`** — shared auth helpers:
```python
def get_current_user(request, db) -> User | None  # reads session cookie → DB lookup
def require_auth(user) -> User                     # raises 401 redirect to /auth/login
def require_admin(user) -> User                    # raises 403 if not admin
def can_edit_project(user, project) -> bool        # admin OR pm with name match
```

**`app/routes/auth.py`** — 4 routes:
- `GET /auth/login` → login form
- `POST /auth/login` → validate → set cookie → redirect
- `GET /auth/register` → register form (requires invite PIN)
- `POST /auth/register` → validate PIN → create user → redirect to login
- `POST /auth/logout` → delete session → redirect to login

**`app/routes/admin_users.py`** — user management:
- `GET /admin/users` → list users + unused PINs
- `POST /admin/users/generate-pin` → generate PIN for a given role → store → show

**`app/templates/auth/login.html`** — login form
**`app/templates/auth/register.html`** — register form (username, display_name, password, confirm_password, PIN)
**`app/templates/admin/users.html`** — user list + PIN generator

#### Changes to Existing Files

**`app/models.py`** — add User, InvitePin, UserSession models

**`app/main.py`** — mount auth_router, admin_users_router

**`requirements.txt`** — add `passlib[bcrypt]`

**`app/templates/base.html`** — show logged-in user + logout button in navbar; hide AI Intake from viewers

**Every route in projects.py, files.py, intake.py, admin.py, help.py:**
- Inject `current_user = Depends(get_current_user)`
- Guard write operations with `can_edit_project()` or `require_admin()`
- Pass `current_user` to all template responses

**`app/templates/project_detail.html`:**
- Wrap factory + engineer display in `{% if current_user.role in ('admin','pm') %}`
- Wrap Edit/Archive/Delete buttons in `{% if can_edit %}`

**`app/templates/project_form.html`** — redirect viewers to detail page (enforced in route)

**`app/templates/projects_list.html`** — hide "New Project" button from viewers

**`app/templates/admin_db.html`** — admin-only (enforced in route, no template change needed)

#### Auth Flow Details

**Login:** POST creds → verify password → create `user_sessions` row → set HTTP-only cookie `pm_session=<token>` → redirect to `/projects`

**Register:** POST form → validate PIN exists + unused → create user → mark PIN used → redirect `/auth/login`

**Session cookie:** `pm_session` — HTTP-only, SameSite=Lax, 7-day expiry

**PIN generation:** Admin clicks "Generate PIN" with role selected → random 8-char uppercase alphanumeric (e.g. `X7KP2QMN`) → stored in `invite_pins` → shown once

**Ownership check:**
```python
def can_edit_project(user, project) -> bool:
    if user.role == "admin": return True
    if user.role == "pm":
        pm = (project.project_manager or "").lower().strip()
        return pm == user.username.lower() or pm == (user.display_name or "").lower()
    return False
```

#### Admin Bootstrap
First admin user without a PIN — one-time CLI script `create_admin.py`:
- Does NOT accept `--password` via CLI argument (stays in shell history)
- Uses `getpass.getpass()` for hidden password prompt
- If admin already exists: exit with message (no duplicate creation)
- `python3 create_admin.py --username admin`

#### AI Permission Guard (critical addition)

AI must respect the same role permissions as the UI — AI cannot be used as a permission bypass.

**Role-aware context builder** in `app/dependencies.py`:
```python
FORBIDDEN_AI_TOPICS = [
    ".env", "api key", "openai_api_key", "database_url", "secret_key",
    "password hash", "session token", "cookie", "system prompt",
    "model name", "what model", "tool call", "internal tool",
    "implementation", "source code", "database credential",
]

def sanitize_project_for_user(project, user) -> dict:
    # Returns only allowed project fields as a plain dict
    # Viewer: exclude factory, engineer, target_factory_cost, source_note
    # PM/Admin: all fields
    # NEVER include raw DB internals

def is_forbidden_ai_question(user, message: str) -> bool:
    # Returns True if message asks for role-inappropriate info
    # Everyone: blocks raw secrets (.env, API keys, passwords, session tokens)
    # Viewer: also blocks factory, engineer, supplier, quotation questions
```

**AI access rules:**
| | Admin | PM | Viewer |
|---|---|---|---|
| Project fields (name, brand, status…) | ✓ | ✓ | ✓ |
| Factory, engineer, supplier fields | ✓ | ✓ | ✗ |
| Role/permission explanations | ✓ | ✓ | ✓ |
| System internals (.env, model, tools) | ✗ | ✗ | ✗ |
| Raw secrets (API keys, passwords, tokens) | ✗ | ✗ | ✗ |

**If forbidden topic requested:** AI responds briefly: "I'm not able to provide that information based on your current access level."

**Applies to:** Help/Ask AI modal, AI Intake, any future AI Q&A

**Implementation:** `answer_help_question()` in `parser.py` receives `user` and filters system prompt / adds refusal rule. Never pass raw DB objects or `.env` values into any AI prompt.

#### Architecture Note (to add to ARCHITECTURE.md)
```
## AI Permission / Data Access Rules
- AI context must be built through role-aware helper functions
- Never pass raw SQLAlchemy objects, .env values, settings, system prompts,
  tool names, session tokens, or password hashes into AI context
- Viewer AI context excludes factory, engineer, supplier, quotation fields
- PM AI context may include factory/engineer but not system internals
- Admin AI context includes full project fields but never raw secrets
- AI is not a permission bypass
```

#### Session Security
- Session token: `secrets.token_urlsafe(32)` (not UUID)
- Cookie name: `pm_session`, HTTP-only, SameSite=Lax, 7-day expiry
- No JWT — store token in `user_sessions` DB table, look up per request

#### Ownership Note (document as temporary)
Name matching (`project_manager` text == username or display_name) is MVP-only. Document in ARCHITECTURE.md: "Future version should migrate to `product_manager_user_id` FK."

#### Checkpoints (implement and verify one at a time)
- **8A:** User/InvitePin/UserSession models + `passlib` + `create_admin.py`
- **8B:** Login / logout / session routes + login.html template
- **8C:** Invite PIN registration + admin user management page
- **8D:** Route guards across all existing routes (auth inject + permission checks)
- **8E:** Field visibility (factory/engineer) in templates + AI Permission Guard
- **8F:** `test_build8.py` — all role restriction + AI permission tests

#### Files to Create
- `app/dependencies.py`
- `app/routes/auth.py`
- `app/routes/admin_users.py`
- `app/templates/auth/login.html`
- `app/templates/auth/register.html`
- `app/templates/admin/users.html`
- `create_admin.py`
- `test_build8.py`

#### Files to Modify
- `app/models.py` — add User, InvitePin, UserSession
- `app/main.py` — mount auth_router, admin_users_router
- `app/ai/parser.py` — `answer_help_question()` receives user, filters context
- `requirements.txt` — add `passlib[bcrypt]`
- `ARCHITECTURE.md` — add AI Permission Rules section
- `app/templates/base.html` — nav user info + logout
- `app/templates/project_detail.html` — field visibility + edit guards
- `app/templates/projects_list.html` — hide New Project from viewers
- `app/routes/projects.py` — auth inject + permission checks
- `app/routes/files.py` — auth inject + permission checks
- `app/routes/intake.py` — auth inject (pm+ only)
- `app/routes/admin.py` — require_admin
- `app/routes/help.py` — auth inject (all roles allowed)

**Verification:** `python3 test_build8.py` — login, register, role restrictions, field visibility, AI permission refusals

---

### Build 9 — Railway Deploy ✓ SHIPPED v0.8.0

#### Context
All app functionality is complete through Build 8 (auth, roles, AI features, change log, etc.). The codebase is currently dev-only:
- SQLite hardcoded in `app/database.py`
- `run.py` always runs with `reload=True` on port 8000
- No `railway.toml` / Procfile / runtime pin
- Uploads stored on local filesystem (ephemeral on Railway)
- Admin bootstrap requires interactive `getpass()` — can't run on Railway

Build 9 hardens the app for production deploy on Railway without changing any business logic.

#### What's Already in Place
- `bcrypt<4` pinned in requirements.txt (passlib compatibility — verified Build 8)
- `.gitignore` excludes `.env`, `*.db`, `app/uploads/*` ✓
- All routes auth-protected (Build 8)
- Sessions stored in DB (persist across container restarts as long as DB persists)
- App binds to `0.0.0.0` (already Railway-compatible)
- `python-dotenv` already in requirements (for local `.env` loading)

#### What Build 9 Changes (8 files)

**1. `requirements.txt`** — add PostgreSQL adapter:
```
psycopg2-binary
```

**2. `app/database.py`** — env-driven DB URL with `postgres://` normalization:
```python
import os
_DEFAULT_SQLITE = f"sqlite:///{os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pm_tracker.db')}"
url = os.environ.get("DATABASE_URL", _DEFAULT_SQLITE)
# Railway/Heroku use the legacy "postgres://" scheme; SQLAlchemy 2.x requires "postgresql://"
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql://", 1)
SQLALCHEMY_DATABASE_URL = url
# check_same_thread is SQLite-only
connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
```

**3. `run.py`** — honor `$PORT`, disable reload in production:
```python
import os, uvicorn
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    # Reload only in local dev — Railway sets RAILWAY_ENVIRONMENT
    reload = (os.environ.get("RAILWAY_ENVIRONMENT") is None
              and os.environ.get("DISABLE_RELOAD") != "1")
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=reload)
```

**4. `app/main.py`** — extend lifespan with one-time admin bootstrap from env vars:
```python
# In lifespan, after create_all + makedirs:
initial_user = os.environ.get("INITIAL_ADMIN_USERNAME")
initial_pass = os.environ.get("INITIAL_ADMIN_PASSWORD")
if initial_user and initial_pass:
    from app.database import SessionLocal
    from app.models import User
    from passlib.context import CryptContext
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.role == "admin").first():
            pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
            admin = User(
                username=initial_user.lower().strip(),
                display_name=initial_user,
                role="admin",
                hashed_password=pwd_ctx.hash(initial_pass),
            )
            db.add(admin); db.commit()
            print(f"[bootstrap] Admin '{admin.username}' created from env vars")
        else:
            print("[bootstrap] Admin already exists — skipping env-var bootstrap")
    finally:
        db.close()
```
**After first deploy, user deletes the `INITIAL_ADMIN_*` env vars from Railway dashboard for security.** The bootstrap is idempotent — it never overwrites an existing admin.

Also add a tiny health endpoint for Railway's healthcheck:
```python
@app.get("/healthz")
def healthz():
    return {"status": "ok"}
```

**5. `railway.toml`** — service config:
```toml
[build]
builder = "NIXPACKS"

[deploy]
startCommand = "python3 run.py"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
healthcheckPath = "/healthz"
healthcheckTimeout = 30
```

**6. `runtime.txt`** — pin Python version for nixpacks:
```
python-3.12
```

**7. `.env.example`** — documentation of env vars (committed to repo):
```
# Required
OPENAI_API_KEY=sk-...
# Railway auto-provides DATABASE_URL when you attach a PostgreSQL plugin
DATABASE_URL=postgresql://user:pass@host:port/dbname

# One-time admin bootstrap — DELETE these after first successful login
INITIAL_ADMIN_USERNAME=youradmin
INITIAL_ADMIN_PASSWORD=yourstrongpassword

# Optional
DISABLE_RELOAD=1    # set to disable uvicorn reload locally if you want
```

**8. `USER_GUIDE.md` + `CHANGELOG.md` + `VERSION.md`** — add deploy walkthrough, bump to v0.8.0

#### Railway Volume Setup (Manual, Documented in USER_GUIDE)

Railway's container filesystem is ephemeral — without a volume, every redeploy wipes uploaded files. Required dashboard steps:

1. Railway dashboard → service → Settings → Volumes → New Volume
2. **Mount path:** `/app/app/uploads` (matches the in-container upload directory)
3. **Size:** 1 GB to start (can scale up later)

Without this volume: all file uploads silently lost on next deploy. WARN this in USER_GUIDE.

#### Deploy Walkthrough (added to USER_GUIDE)

1. Push code to a GitHub repo (any visibility)
2. Railway → New Project → Deploy from GitHub repo
3. Add the **PostgreSQL** plugin → it auto-injects `DATABASE_URL`
4. Set service env vars in Railway:
   - `OPENAI_API_KEY` = your key
   - `INITIAL_ADMIN_USERNAME` = your admin username
   - `INITIAL_ADMIN_PASSWORD` = your admin password
5. Settings → Volumes → mount at `/app/app/uploads`
6. Deploy → first startup creates tables + admin
7. Log in once → click **Users** → generate PINs for team
8. **Delete `INITIAL_ADMIN_USERNAME` and `INITIAL_ADMIN_PASSWORD` env vars** (no longer needed)

#### Checkpoints (verify each before next)
- **9A:** `database.py` — env URL + `postgres://` normalization + conditional `connect_args`
- **9B:** `run.py` — `PORT` env + conditional reload
- **9C:** `railway.toml` + `runtime.txt` + `.env.example` + add `psycopg2-binary` to requirements
- **9D:** `main.py` — admin bootstrap lifespan hook + `/healthz` endpoint
- **9E:** USER_GUIDE deploy section + CHANGELOG v0.8.0 + VERSION bump
- **9F:** Local verification + final test_build8.py run to ensure nothing regressed

#### Verification (local only — actual Railway deploy is user-driven)
- `DATABASE_URL=sqlite:///test_v9.db python3 run.py` — uses env-supplied URL, creates `test_v9.db`
- `PORT=9000 python3 run.py` — server binds to 9000 (verify with `curl localhost:9000/healthz`)
- `curl http://localhost:8000/healthz` → `{"status":"ok"}`
- Fresh DB + env-var bootstrap: delete `pm_tracker.db`, then `INITIAL_ADMIN_USERNAME=foo INITIAL_ADMIN_PASSWORD=barpass123 python3 run.py` — server starts, admin row created in DB
- Re-run with env vars set — bootstrap skips ("Admin already exists")
- `python3 test_build8.py` — must still pass 35/35 (no regression from refactor)
- `pip3 install -r requirements.txt` — `psycopg2-binary` installs cleanly

#### Out of Scope (deferred / not needed for MVP)
- S3 / CDN file storage (Railway volume is sufficient)
- Custom domain setup (auto Railway URL is fine)
- CI/CD pipeline (manual Railway deploy is fine for internal tool)
- Health monitoring beyond Railway's built-in restart policy
- DB backups (PostgreSQL plugin on paid Railway tier has auto-backups)
- Multi-region / load balancing
- SECRET_KEY env var (sessions are DB-backed; not used by current code)

#### Files to Modify
- `app/database.py` — env-driven URL + postgres normalization
- `app/main.py` — admin bootstrap + `/healthz`
- `run.py` — `PORT` + reload toggle
- `requirements.txt` — add `psycopg2-binary`
- `USER_GUIDE.md` — deploy walkthrough section
- `CHANGELOG.md` — v0.8.0 entry
- `VERSION.md` — bump to v0.8.0
- `app/templates/base.html` — `v0.7 Help` → `v0.8 Help` button label

#### Files to Create
- `railway.toml`
- `runtime.txt`
- `.env.example`

**Done when:** All checkpoints verified locally, test_build8.py still 35/35, deploy walkthrough committed to USER_GUIDE. (Actual Railway deploy is user-driven from there.)

---

### Build 10 — Calendar View + Admin Nav Hardening ✓ SHIPPED v0.9.0

#### Context
Two requests bundled into a v0.9 release:

1. **Admin-nav hardening:** explicitly verify that "Database" and "Users" navbar links are admin-only and cannot leak to PMs or viewers (route-level guard + template-level visibility). The current code in `base.html` lines 27-34 already wraps both in `{% if current_user and current_user.role == 'admin' %}`, but we want a regression test that locks this in.

2. **Calendar view:** a new page showing which projects are scheduled to launch in each month of a year, plus which projects actually launched in each month. Not a full date-grid calendar — just a month list with planned vs. actual project rosters per month.

#### Permission Model
- **Calendar:** all authenticated users (admin / pm / viewer). Only shows non-sensitive fields (SKU, name, brand, status, dates). Factory/engineer are NOT shown.
- **Database / Users nav:** admin only — already in place, will be regression-tested.

#### What Build 10 Adds (5 changes)

**1. `app/crud.py`** — two new helpers:

```python
def get_actual_launch_date(project) -> date | None:
    """Returns the actual launch date based on the project's Launch phase.
    Looks for the phase with the highest phase_order (which is 'Launch' in
    both default templates) AND requires status='done' AND actual_end_date set.
    Returns None if not yet launched.
    """
    if not project.phases:
        return None
    candidates = [p for p in project.phases
                  if (p.phase_name or '').lower() == 'launch'
                  and p.status == 'done' and p.actual_end_date]
    if candidates:
        return max(p.actual_end_date for p in candidates)
    # Fallback for projects without a 'Launch'-named phase: use the
    # highest-order done phase if project is completed
    if project.status == 'completed':
        done = [p for p in project.phases if p.status == 'done' and p.actual_end_date]
        if done:
            return max(done, key=lambda p: p.phase_order).actual_end_date
    return None


def get_calendar_data(db: Session, year: int) -> dict:
    """Build {month: {'planned': [...], 'actual': [...]}} for the given year.
    Only includes non-archived projects. Each project entry is a plain dict
    containing id, name, sku, brand, status, planned_launch_date, actual_launch_date.
    """
    projects = db.query(Project).filter(Project.status != 'archived').all()
    months = {m: {'planned': [], 'actual': []} for m in range(1, 13)}
    for p in projects:
        entry = {
            'id': p.id, 'name': p.name, 'sku': p.sku, 'brand': p.brand,
            'status': p.status, 'current_stage': p.current_stage,
            'planned_launch_date': p.planned_launch_date,
            'actual_launch_date': get_actual_launch_date(p),
        }
        if p.planned_launch_date and p.planned_launch_date.year == year:
            months[p.planned_launch_date.month]['planned'].append(entry)
        actual = entry['actual_launch_date']
        if actual and actual.year == year:
            months[actual.month]['actual'].append(entry)
    return months
```

**2. `app/routes/calendar.py`** — new file, single route:

```python
@router.get('/calendar', response_class=HTMLResponse)
def calendar_view(request, year: int = None, month: int = None, db = Depends(get_db)):
    current_user = get_current_user(request, db)
    try: require_auth(current_user)
    except _RedirectException as e: return e.response

    today = date.today()
    year = year or today.year
    month = month or today.month  # selected month for the right panel
    if not 1 <= month <= 12: month = today.month

    months_data = crud.get_calendar_data(db, year)
    return templates.TemplateResponse(request, 'calendar.html', {
        'current_user': current_user,
        'year': year, 'selected_month': month, 'today': today,
        'months_data': months_data,
    })
```

**3. `app/templates/calendar.html`** — new template:

Layout (two columns, Bootstrap grid):

```
[Year nav: ◀ 2026 ▶]

┌─ col-lg-4 ──────────────┐  ┌─ col-lg-8 ──────────────────────┐
│ Months                  │  │  June 2026                       │
│ ─────────────────       │  │  ──────────────────              │
│ Jan 2026 · 2 planned    │  │  Planned (3)                     │
│ Feb 2026 · 1 planned    │  │  ┌──────────────────────────┐   │
│ Mar 2026 · 3 planned    │  │  │ RB-001  Damascus Chef Knf│   │
│ Apr 2026 · 2 planned    │  │  │ Brand: Rblack            │   │
│ May 2026 · 1 planned    │  │  │ Planned: Jun 15, 2026    │   │
│ ► Jun 2026 · 3 + 1 done │  │  │ Status: in_progress      │   │
│ Jul 2026 · 0 planned    │  │  └──────────────────────────┘   │
│ Aug 2026 · 1 planned    │  │  ...                             │
│ ...                     │  │                                  │
│                         │  │  Actually Launched (1)           │
│                         │  │  ┌──────────────────────────┐   │
│                         │  │  │ XY-100  Old Project      │   │
│                         │  │  │ Planned: Apr 15, 2026    │   │
│                         │  │  │ Actual:  Jun 3, 2026     │   │
│                         │  │  │ 49 days late             │   │
│                         │  │  └──────────────────────────┘   │
└─────────────────────────┘  └──────────────────────────────────┘
```

Each project row links to `/projects/{id}`. Selected month uses `?year=Y&month=M` URL params. Year nav uses `?year=Y±1`. Pure server-side rendering, no JS.

**4. `app/main.py`** — mount calendar router.

**5. `app/templates/base.html`** — add Calendar nav link (between Projects and AI Intake, visible to ALL authenticated users):

```html
{% if current_user %}
<a class="nav-link px-3 {% if request.url.path.startswith('/calendar') %}active{% endif %}" href="/calendar">
  <i class="bi bi-calendar3 me-1"></i>Calendar
</a>
{% endif %}
```

Also bump Help button label from `v0.8 Help` → `v0.9 Help`.

#### Documentation Updates
- **`USER_GUIDE.md`** — add "Calendar" section explaining: how to read it, what counts as "planned", what counts as "actually launched" (Launch phase done + actual_end_date set), year navigation
- **`CHANGELOG.md`** — v0.9.0 entry covering calendar + nav hardening
- **`VERSION.md`** — bump to v0.9.0
- **Help modal** in base.html — update version badge + add Calendar bullet to feature list + add v0.9.0 entry to changelog tab

#### What This Does NOT Change
- No schema migration. "Actual launch date" is derived at read-time from the existing Launch phase's `actual_end_date` field — no new columns. Documented in ARCHITECTURE.md "do not add columns casually" principle.
- No change to the existing admin route guards. `require_admin()` already protects `/admin/database` and `/admin/users` routes; the nav link visibility is the only template-side concern, and it's already correct.

#### Checkpoints
- **10A:** `app/crud.py` — add `get_actual_launch_date()` and `get_calendar_data()` helpers
- **10B:** `app/routes/calendar.py` + mount in `main.py` + `app/templates/calendar.html`
- **10C:** `app/templates/base.html` — Calendar nav link + Help label `v0.8` → `v0.9`
- **10D:** Help modal content update (current version + changelog tab)
- **10E:** USER_GUIDE Calendar section + CHANGELOG v0.9.0 + VERSION bump
- **10F:** Verification — manual test + admin-nav regression test in test_build8.py

#### Verification
- Playwright: log in as admin → navbar shows Database, Users, Calendar ✓
- Playwright: log in as PM → navbar shows Calendar (no Database, no Users) ✓
- Playwright: log in as viewer → navbar shows Calendar (no Database, no Users, no AI Intake) ✓
- Playwright: viewer hits `/admin/database` directly → redirected ✓ (existing test)
- Playwright: viewer hits `/admin/users` directly → redirected ✓ (new test)
- Manual: create 2-3 projects with `planned_launch_date` in different months of 2026 → visit `/calendar` → projects appear in correct months
- Manual: mark Launch phase done with `actual_end_date` for one project → "Actually Launched" section populates
- Manual: year nav `?year=2025` and `?year=2027` works
- `python3 test_build8.py` — still 35/35

#### Critical Files
- **Create:** `app/routes/calendar.py`, `app/templates/calendar.html`
- **Modify:** `app/crud.py`, `app/main.py`, `app/templates/base.html`, `USER_GUIDE.md`, `CHANGELOG.md`, `VERSION.md`, `test_build8.py` (add admin-nav regression test)

**Done when:** Calendar route renders correctly with a sample dataset, Database/Users hidden from non-admins (verified by test), v0.9.0 documented.

---

### Build 11 — Good Ideas + Project Linkage + AI Dual-Mode Intake ✓ SHIPPED v1.0.0

#### Context
Team members across roles (engineer, ops, sales) come across materials, structures, features, and aesthetic ideas that aren't projects yet but should be collected for future combination into products. Need:
1. A board to log ideas categorized by type
2. Many-to-many linkage between Projects and Ideas (record which ideas a project derives from)
3. AI intake that detects "this is an idea" vs "this is a project" and routes accordingly

#### Permission Model (Ideas — looser than projects)
| Action | Admin | PM | Viewer |
|---|---|---|---|
| View ideas board | ✓ | ✓ | ✓ |
| Create idea | ✓ | ✓ | ✓ |
| Edit any idea | ✓ | ✓ | ✗ |
| Delete idea | ✓ | ✗ | ✗ |
| Link idea to project | ✓ | own projects | ✗ |

Rationale: ideas come from everywhere in the org (ops noticed an Amazon listing, factory rep brought a material sample) — viewers MUST be able to create ideas. Editing requires PM+ to prevent accidental data loss after submission.

#### New Database Tables

**`ideas`** — additive, no migration of existing tables
| Field | Type | Notes |
|---|---|---|
| id | Integer PK | |
| name | String, not null | Short label |
| description | Text, nullable | Longer detail |
| idea_type | String, not null | material / structure / feature / aesthetic / manufacturing / other |
| source | String, not null | factory / tradeshow / internet / customer / team / competitor / other |
| source_detail | String, nullable | Specific factory name, URL, etc. |
| contributor | String, nullable | Free-text submitter name |
| contributor_user_id | Integer FK nullable | If logged-in user submitted |
| status | String | open / in_use / archived |
| notes | Text, nullable | |
| created_at / updated_at | DateTime | |

Serial number for display is derived: `f"IDEA-{id:03d}"` (no separate column).

**`project_ideas`** — many-to-many association
| Field | Type |
|---|---|
| project_id | Integer FK, PK |
| idea_id | Integer FK, PK |
| linked_at | DateTime |
| linked_by_user_id | Integer FK nullable |
| note | String nullable — how this idea was used |

Both tables are additive — `Base.metadata.create_all()` creates them without touching existing tables. Safe on both local SQLite and Railway PostgreSQL.

#### Predefined Enums

**Idea types** (these become the columns on the board): material · structure · feature · aesthetic · manufacturing · other

**Sources:** factory · tradeshow · internet · customer · team · competitor · other

#### UI Sketches

**Ideas Board (`/ideas`)** — CSS grid, one column per type:
```
[+ New Idea]      [Source filter: All ▾]      [Sort: newest ▾]

┌── Materials (5) ─┐ ┌── Structures (3) ┐ ┌── Features (4) ──┐ ...
│ IDEA-007         │ │ IDEA-002         │ │ IDEA-001          │
│ Forged Damascus  │ │ Tri-fold balisong│ │ Magnetic sheath   │
│ source: factory  │ │ source: internet │ │ source: team      │
│ Sarah · May 23   │ │ Mike · Apr 12    │ │ Used in: KT-100   │
│ [edit] [×admin]  │ │ ...              │ │ ...               │
└──────────────────┘ └──────────────────┘ └───────────────────┘
```

**Project Detail — "Inspired by" section** (new, between Product Thesis and Timeline):
```
## INSPIRED BY (3 ideas)         [+ Link existing idea]
· IDEA-007 — Forged Damascus (material) — added by Sarah  [×]
· IDEA-002 — Tri-fold mechanism (structure) — added by Mike  [×]
· IDEA-001 — Magnetic close (feature) — added by AI  [×]
```

"Link existing idea" opens a Bootstrap modal with a searchable list of all open ideas.

#### AI Dual-Mode Intake

The prompt is updated to classify first, then extract:
```json
{
  "classification": "project" | "idea",
  "project_fields": {...existing...},
  "idea_fields": {
    "name": "...", "description": "...",
    "idea_type": "material|structure|feature|aesthetic|manufacturing|other",
    "source": "factory|tradeshow|internet|customer|team|competitor|other",
    "source_detail": "...", "contributor": "..."
  }
}
```

Classification heuristics (in prompt):
- Specific product to develop, with launch/cost/factory → project
- "Cool material I saw" / "new mechanism on Amazon" / "engineer brought back" → idea
- **Ambiguous → default to idea** (low-friction capture; user can toggle to project if AI got it wrong)

State 2 (review) conditionally renders one of two forms based on `classification`. User can toggle ("Actually this is an idea / a project") if AI got it wrong. Same `/ai/intake/extract` and `/ai/intake/extract-file` routes; new `/ai/intake/confirm-idea` for the idea path.

#### Files to Create
- `app/routes/ideas.py` — CRUD routes + link routes
- `app/templates/ideas_board.html`
- `app/templates/idea_form.html` (create/edit)
- `test_build11.py`

#### Files to Modify
- `app/models.py` — add Idea + project_ideas table + relationships on Project
- `app/main.py` — mount ideas_router
- `app/crud.py` — `create_idea`, `update_idea`, `delete_idea`, `get_ideas_grouped(db, source=None)`, `link_idea_to_project`, `unlink_idea_from_project`
- `app/templates/base.html` — "💡 Good Ideas" nav link (all roles), Help label v0.9 → v0.10
- `app/routes/projects.py` — pass linked ideas to detail template; route to link/unlink
- `app/templates/project_detail.html` — new "Inspired By" section
- `app/ai/prompts.py` — new DUAL_MODE_INTAKE_PROMPT
- `app/ai/parser.py` — refactor `extract_project_fields` → `extract_intake` returning classification
- `app/routes/intake.py` — handle both classifications; add `confirm-idea` action
- `app/templates/intake.html` — conditional rendering of project vs idea confirm form
- `USER_GUIDE.md`, `CHANGELOG.md`, `VERSION.md`, base.html help modal

#### Checkpoints (smaller per the timeout discussion)
- **11A:** Idea model + project_ideas link table + CRUD helpers in `crud.py`. Smoke-test with Python REPL.
- **11B:** Ideas board route + template + nav link. Manual verify the board renders.
- **11C:** Project ↔ Idea link UI on project detail + project_detail.html "Inspired By" section.
- **11D:** AI dual-mode prompt + parser refactor + intake template branching.
- **11E:** Docs (USER_GUIDE, CHANGELOG, VERSION, help modal). Tests in test_build11.py. Final test_build8.py regression.

After each checkpoint, I'll stop and report so you can verify before I continue — minimizes work lost to stream timeouts.

#### Verification (test_build11.py)
- Create idea → appears on board in correct column
- Update idea → fields updated
- Delete idea blocked for PM (admin only)
- Link idea to project → appears in project detail
- Unlink idea → removed from project detail
- AI intake: project text → project flow (existing)
- AI intake: idea text ("saw a cool Damascus material at SHOT Show") → idea flow + idea created on confirm
- Viewer can create idea + view board
- **Viewer CANNOT edit existing idea** (form/route both block)
- PM can edit any idea
- test_build8.py — still 40/40

#### Out of Scope (deferred)
- Visual line-drawing between idea columns (users combine ideas mentally; explicit lines is a big lift)
- File attachments to ideas (use description)
- Idea voting / scoring
- Brand-type ideas (merged into "other" for now)

**Done when:** 5 checkpoints verified, /ideas board renders, project↔idea links work, AI correctly classifies project vs idea, v0.10.0 documented.

---

## v1.1.0 — Roadmap (Loose Blueprint)

**Approach:** v1.1.0 is too big for one build. Break it into ~13 small-to-medium builds. This roadmap lists all of them with 1-paragraph scope. **Each build gets its own detailed plan-mode session when we start it** — not all up-front. This avoids over-planning, makes ChatGPT-style scope creep visible, and lets each build ship safely.

**Direction (carried from product discussion):**
"Static project DB → product development workspace." Reduce intake burden, increase display/reminder power, give AI more interpretation work, preserve raw inputs forever for future re-parsing.

**Cross-cutting design notes (incorporate into every build that touches these):**
- **Viewers cannot see Project Journal entries** (likely contains factory/cost/strategy info — more sensitive than the existing factory field)
- **AI never silently writes** — always preview → user confirm → write. Especially for `project_thesis` from business plan extraction
- **Calendar must NOT aggregate MSRP across variants** — show variant count instead
- **Variants need `is_primary`** so the project has a clear "main SKU" until full variant UX
- **Finish Phase** sets current phase `actual_end_date=today, status=done` AND next phase `actual_start_date=today, status=in_progress`
- **Migration logic lives in `app/migrations.py` or `scripts/migrate_*.py`** — NOT in `main.py`. Idempotent + logged. main.py only calls it
- **For v1.1, only `create_journal_entry` is a real AI write tool.** Other tools are schemas/stubs. Confirmation UI ships in a later build
- **AI Permission Guard must be updated** when new sensitive sources arrive (journal, business plan, quotation, variants). Viewer AI context must not include these
- **i18n: thoughtful Chinese for visible UI.** Deep docs (USER_GUIDE, CHANGELOG, ARCHITECTURE) stay English

### Build List

| # | Name | Size | One-paragraph scope |
|---|---|---|---|
| **12** | Bug fixes + canonical version + governance docs | S | Fix the 3 bugs (rendering submit, timeline edit, footer v0.6). Create `app/version.py` as runtime version source and remove every hardcoded version literal. Create `PRODUCT_DEVELOPMENT_PHILOSOPHY.md`, `FEATURE_DESIGN_PROCESS.md`, `AI_TOOLS_REGISTRY.md`. Update `CLAUDE.md`. Foundational — must land first. |
| **13** | Migration infrastructure + v1.1 schema additions | S | Move schema migration out of `main.py` lifespan into `app/migrations.py` (idempotent helpers). Add 5 new tables (`project_journal_entries`, `project_variants`, `project_variant_components`, `phase_plan_changes`, `ai_conversations`) and 2 new columns (`users.language`, `ai_messages.conversation_id`). All purely additive. |
| **14** | Project Journal | M | New section on project detail (between Thesis and Inspired By). Manual entry create + chronological display. AI summary on demand. **Viewer cannot see**. Entry has `title` (AI-generated short summary), `visibility=internal` default. Raw `entry_text` always preserved. |
| **15** | Business Plan upload + Thesis extraction (preview-confirm) | M | Add business plan upload to Create Project. After upload, AI extracts thesis → preview screen → user confirms → write to `project_thesis`. Fixed-height scrollable thesis box on detail. Edit-on-click (PM+admin only). Detect inspirations → suggest linking or creating ideas. |
| **16** | Multi-SKU Variants + Packaging + Quotation + Profit Model placeholder | M | Variants section with CRUD (`is_primary` flag; project-level cost/msrp stay as fallback). Packaging & Accessories section (per-project or per-variant). Quotation section reuses `project_files`. Profit Model = UI placeholder only with intent doc. |
| **17** | Timeline 2.0 (Plan / Reality split) | L | Split each phase row into Plan + Reality columns. Plan date changes require a reason → `phase_plan_changes` row → `*` marker on date. Finish Phase button sets current phase done + advances next phase to in_progress (both `actual_*` timestamps from server). Update `current_stage` + `calculate_delay`. |
| **18** | Rendering History + Prototype Photos | S | Two dedicated sections, chronological with per-upload comments. Comments inline-editable (PM+admin). Latest rendering thumbnail on project card right side. Reuse `project_files` with `file_category="rendering"` and new `file_category="prototype_photo"`. |
| **19** | My Projects tab + Attention banner cleanup + Project state preservation | S | New `/my-projects` route (admin/pm only, hidden from viewer), wide row-per-project layout. Remove Needs-Info from attention banner (keep card badge + filter tab). localStorage `pm_last_project_id` so clicking Projects nav returns to last opened project (double-click to clear). |
| **20** | AI Tools Architecture + Permission Guard update | M | Create `app/ai/tools.py` with JSON schemas for all 16 tools. **Only `create_journal_entry` is wired in v1.1.** Others are schemas with TODO handlers. Update `AI_TOOLS_REGISTRY.md`. Extend `is_forbidden_ai_question` and `sanitize_project_for_user` to filter journal entries, business plans, quotations, variant costs, packaging costs for viewers. |
| **21** | Bottom AI Chat + Side Panel + Conversation History | L | Fixed-position bottom chat input on every authenticated page. Input grows vertically as user types (ChatGPT-style). Files/images drag-droppable into same box. Submit → right-side panel slides open with response. Panel has: Ask/Intake mode toggle, Project/Global scope toggle, conversation history, archive button. `ai_conversations` table stores grouping. Wire `create_journal_entry` as the v1.1 working Intake tool. |
| **22** | AI-Assisted Create Project (remove AI Intake from nav) | M | Create Project page gets two tabs: Manual Form / AI-Assisted. AI-Assisted is the new home for the unified text+file intake. Remove `/ai/intake` from navbar but keep the route (redirect to Create Project AI tab). |
| **23** | Chinese i18n | L | `app/i18n.py` + `app/i18n/zh.json`. `t(key)` Jinja2 global. Translate all nav, page titles, section headers, button labels, badges, status labels, form labels. Thoughtful translations (not raw translate). Language switcher in navbar. User preference persisted to `users.language` and a cookie fallback. Deep docs stay English. |
| **24** | v1.1.0 release tests + USER_GUIDE update + bump | S | New test files per build above. Final regression. USER_GUIDE: short Chinese summary section + English sections for all new features + intended Profit Model formula. CHANGELOG v1.1.0 mega entry. VERSION bump. |

**Total estimate:** 6 small + 5 medium + 3 large = roughly 13 builds. Hopefully each ships within a single session.

**When we start each build**, I'll re-enter plan mode and produce a detailed Feature Design Review for that build only (per `FEATURE_DESIGN_PROCESS.md` once it exists).

---

### Build 12 — Bug Fixes + Canonical Version + Governance Docs ✓ SHIPPED v1.0.1

#### Context
Foundation for v1.1.0. Three known bugs are blocking real use of the app; the canonical version refactor unblocks every future release; the governance docs encode the product philosophy and AI-tool discipline so every later build follows the same rules.

#### Scope (Build 12 only — NOT v1.1 in full)

This build is **only**:
1. Fix the 3 known bugs
2. Create `app/version.py` as runtime version source + remove every hardcoded version literal
3. Create 3 governance docs + update `CLAUDE.md`

Everything else from the v1.1.0 blueprint waits for its own build.

#### Bug 1 — Rendering upload doesn't submit
Investigate first (likely culprits): upload form `enctype="multipart/form-data"` missing on the rendering-specific form, file input `name` mismatch, route auth blocking PMs, file_category not reaching the route, UPLOAD_DIR resolution under the new working directory. Read `app/templates/project_detail.html` upload form, `app/routes/files.py`, browser dev tools (or curl) to confirm what's POSTed. Fix root cause + add regression test: POST a PNG with `file_category=rendering`, verify file appears in gallery + on disk.

#### Bug 2 — Timeline can't be changed / doesn't display normally
Investigate first: phase-edit modal field IDs vs route `Form()` names (they must match exactly), date parsing for empty strings, status enum mismatch between template options and route validation, `current_stage` recalc trigger after edit. Read `app/templates/project_detail.html` phase modal, `app/routes/projects.py` phase routes. Fix root cause + add regression test: POST a phase edit, verify the new dates display.

**Do NOT redesign timeline here.** That's Build 17 (Timeline 2.0). Build 12 just restores basic edit functionality.

#### Bug 3 — Footer shows v0.6
Root cause confirmed: hardcoded literals in `app/templates/base.html` line 172 (changelog entry — legitimate, that's the v0.6 release entry) and line 312 (modal footer "PM Product Tracker v0.6.0" — wrong, never bumped).

**Permanent fix:**
- Create `app/version.py` with constants: `CURRENT_VERSION`, `CURRENT_BUILD_NAME`, `LAST_UPDATED`
- Register them as Jinja2 globals in `app/main.py` (one-line: `templates.env.globals.update(...)`)
- Replace every hardcoded version literal in `base.html` with the global (modal title, footer, help button label)
- `VERSION.md` stays as the canonical human-readable doc; `app/version.py` is the runtime truth
- Add a tiny test: GET `/projects` while logged in, assert page HTML contains current version string

#### Governance Documents (kept concise — not long essays)

**`PRODUCT_DEVELOPMENT_PHILOSOPHY.md`** — 10 principles (≤ 1 line each):
1. Data must be migratable (raw inputs/files/relationships/decisions survive schema changes)
2. Intake burden should be minimized
3. Display and reminders should be richer than intake
4. LLM carries interpretation work — AI proposes, user confirms
5. Change Log is mandatory but not sufficient (Journal records reasoning)
6. Projects are evolving hypotheses, not static forms
7. Support options and scenarios (don't lock one project to one path early)
8. User mental flow drives iteration (discoveries, tradeoffs, decisions)
9. Preserve raw inputs forever (text/files/images) for future re-parsing
10. Manual forms are fallback — unified text/file/image intake is the long-term ideal

**`FEATURE_DESIGN_PROCESS.md`** — 11-question Feature Design Review template (real workflow problem? repeated or edge? needs structured data? could live in Journal/notes/metadata? increases intake burden? AI can reduce it? what display/reminder? affects migration? minimal schema change? minimal UI change? what to defer?)

**`AI_TOOLS_REGISTRY.md`** — definitive registry of AI tools, their parameters, permission requirements, and confirmation rules. Every new feature MUST add a corresponding tool entry. Sections:
- Current tools (with full JSON schemas)
- Tools planned for future features
- Permission/confirmation rules
- How to add a new tool (3-step checklist)

**Update `CLAUDE.md`** — add one new section: "Before designing any new feature or schema change, read `PRODUCT_DEVELOPMENT_PHILOSOPHY.md` and `FEATURE_DESIGN_PROCESS.md`, then produce a Feature Design Review. For any new feature that creates structured data, add a corresponding AI tool entry to `AI_TOOLS_REGISTRY.md`."

Keep all three docs short and scannable. The point is to encode rules for future builds — not to write a manifesto.

#### Files to Create
- `app/version.py`
- `PRODUCT_DEVELOPMENT_PHILOSOPHY.md`
- `FEATURE_DESIGN_PROCESS.md`
- `AI_TOOLS_REGISTRY.md`

#### Files to Modify
- `app/main.py` — register Jinja2 globals for version
- `app/templates/base.html` — replace hardcoded version literals
- `app/templates/project_detail.html` — fix rendering upload form (Bug 1) + phase edit modal (Bug 2)
- `app/routes/files.py` and/or `app/routes/projects.py` — fix server-side bug (whichever turns out to be the cause)
- `CLAUDE.md` — reference governance docs

#### Verification
- POST a PNG to `/projects/{id}/files` with `file_category=rendering` via curl + check it appears
- Edit a phase via the modal in Playwright + check the new dates render
- GET `/projects` while logged in → page HTML contains the version string from `app/version.py` and does NOT contain `v0.6.0` anywhere in the modal footer
- `test_build8.py` 40/40 + `test_build11.py` 20/20 (no regression)
- Optionally: tiny `test_build12.py` with the 3 bug-fix regression cases

#### Done When
- All 3 bugs reproduced + fixed + regression-tested
- `app/version.py` is the only place a runtime version string lives
- 3 governance docs committed
- `CLAUDE.md` references them
- Pushed to GitHub

---

### Build 13 — Migration Infrastructure + v1.1 Schema Additions ✓ SHIPPED v1.1.0-build13

#### Feature Design Review (per FEATURE_DESIGN_PROCESS.md)

1. **Real workflow problem?** Builds 14–23 need new tables and columns. v1.0 used `Base.metadata.create_all()` in `main.py` lifespan, which works for new tables but can't add columns to existing tables. ChatGPT correctly flagged "main.py as schema migrator" as an anti-pattern before it grows worse.
2. **Repeated or edge?** Repeated — every feature build from here adds schema.
3. **Structured data?** Yes — 5 new entity tables.
4. **Could it live in notes?** No — they're distinct entities with their own relationships.
5. **Increases intake burden?** No — backend only.
6. **AI reduce intake?** N/A — backend foundation.
7. **Display/reminder?** None in this build.
8. **Affects migration?** This IS the migration build.
9. **Minimal schema change?** Add 5 nullable-default tables + 2 nullable-default columns. Pure additive — zero risk to existing data.
10. **Minimal UI change?** None.
11. **Defer?** Nothing — this is the smallest foundation for Builds 14–23.

#### Architecture

**`app/migrations.py`** — versioned migration runner:

```python
# _migrations tracking table:
#   name          TEXT PRIMARY KEY
#   applied_at    TIMESTAMP
# Created on first call via CREATE TABLE IF NOT EXISTS.

MIGRATIONS = [
    ("001_v1_1_add_language_to_users",
     lambda eng: add_column_if_missing(eng, "users", "language", "VARCHAR DEFAULT 'en'")),
    ("002_v1_1_add_conversation_id_to_ai_messages",
     lambda eng: add_column_if_missing(eng, "ai_messages", "conversation_id", "INTEGER")),
]

def run_pending(engine): ...                                    # logs each step
def add_column_if_missing(engine, table, column, ddl): ...      # see error handling below
```

**Lifespan order in `main.py`:**
1. `Base.metadata.create_all(bind=engine)` — creates new tables (5 new ones get picked up because we add their models)
2. `migrations.run_pending(engine)` — handles ALTER TABLE for the 2 new columns
3. `_bootstrap_admin_from_env()`

#### Error handling (per ChatGPT correction #2 — do not swallow real failures)

`add_column_if_missing` MUST only catch the specific "column already exists" / "duplicate column" error messages from SQLite + PostgreSQL. Any other exception must be **logged AND re-raised** so a half-applied schema on Railway becomes visible immediately, not silently corrupted.

```python
SAFE_ERRORS = (
    "duplicate column",         # SQLite + PostgreSQL
    "already exists",           # PostgreSQL variant
)
# In try/except: if str(e).lower() contains any SAFE_ERRORS substring → log "skipped" and return.
# Otherwise: log error + re-raise.
```

#### JSON field type choice (per correction #3)

For `extracted_updates_json`, `open_questions_json`, `decisions_json`, `options_json` on `project_journal_entries`:
- Use SQLAlchemy `JSON` type (already used successfully on `ai_messages.metadata_json` in v1.0). Works on both SQLite (as TEXT) and PostgreSQL (as native JSONB).
- Future service-layer code must always read/write through ORM — never parse JSON in templates.

#### users.language fallback (per correction #4)

Migration sets `DEFAULT 'en'` but DEFAULTs don't always populate existing rows uniformly across SQLite/PostgreSQL versions. **All service-layer reads must use `user.language or "en"`** as a defensive fallback. Document this convention in `ARCHITECTURE.md` when Build 23 (i18n) lands.

#### is_primary uniqueness (per correction #5)

`project_variants.is_primary` is a plain `Boolean default False`. **No DB unique constraint** — too risky to enforce at the DB level (would block partial migrations or legitimate edge cases). Build 16 service-layer note: setting `is_primary=True` on one variant must `UPDATE` other variants in the same project to `is_primary=False` first. Add a comment in the model definition flagging this.

#### SQLite FK note (per correction #6 secondary point)

SQLite doesn't enforce FK constraints unless `PRAGMA foreign_keys=ON` is set per connection. The project hasn't enforced this and the smoke test only needs imports + queries to work, so leaving it as-is. Documented for future hardening.

#### Schema Additions (5 new tables, all additive)

| Table | Key columns |
|---|---|
| `project_journal_entries` | id PK · project_id FK · entry_text TEXT not null · entry_type (general/factory_discussion/cost_discovery/design_feedback/decision/risk/packaging/variant/other) · **title** (AI-generated short summary) · **visibility** (internal/public, default internal) · author_user_id FK · ai_summary · extracted_updates_json · open_questions_json · decisions_json · options_json · linked_file_id FK nullable · created_at · updated_at |
| `project_variants` | id PK · project_id FK · variant_name not null · sku · status (idea/evaluating/selected/rejected/launched) · **is_primary** Boolean default False · target_factory_cost · actual_factory_cost · target_msrp · material_summary · size_color_summary · packaging_summary · notes · created_at · updated_at |
| `project_variant_components` | id PK · project_id FK · variant_id FK nullable (null = applies to all variants) · component_type (packaging/accessory) · name not null · target_cost · actual_cost · notes · created_at · updated_at |
| `phase_plan_changes` | id PK · phase_id FK · field_changed (e.g. 'planned_end_date') · old_date · new_date · **reason** TEXT not null · changed_by_user_id FK · changed_at |
| `ai_conversations` | id PK · user_id FK · project_id FK nullable (null = global chat) · title · status (active/archived, default active) · created_at · updated_at |

#### Existing-Table Column Additions

| Table | Column | DDL |
|---|---|---|
| `users` | `language` | `VARCHAR DEFAULT 'en'` (en or zh) |
| `ai_messages` | `conversation_id` | `INTEGER` (FK to ai_conversations, nullable for backward compat with v1.0 messages) |

#### Cross-Cutting Design Notes (from v1.1.0 blueprint)

- `is_primary` on variants is enforced at app level (convention), not as a unique DB constraint. Migration risk too high otherwise.
- Journal `visibility` default is `internal` — viewer filtering happens in Build 14 routes, not here.
- `ai_conversations.project_id` nullable so global chats (Build 21) work without dummy projects.

#### Files to Create
- `app/migrations.py` — migration runner + helpers

#### Files to Modify
- `app/models.py` — 5 new model classes + 2 new columns + relationships
- `app/main.py` — call `migrations.run_pending(engine)` in lifespan, after `create_all`

#### Verification

**Step 0 — Always back up the local DB before any migration smoke test:**
```bash
cp pm_tracker.db pm_tracker.backup_before_build13.db
```

**Smoke tests:**
1. **Existing-DB path:** with the backed-up v1.0 DB in place, restart server, verify migrations log only the genuinely-pending steps, only new tables + new columns added, no existing rows touched. Confirm user count and project count are unchanged before/after.
2. **Fresh-DB path:** move the DB aside, restart, all 8 + 5 = 13 tables present + both new columns on users/ai_messages from scratch. Bootstrap admin still works.
3. **Idempotent path:** restart again on top of the migrated DB — every migration logs "skipping (already applied)", nothing re-runs.
4. **Smoke query:** Python REPL — `db.query(ProjectVariant).all()` returns `[]`, not an error.
5. **Regression:** `test_build8.py` 40/40, `test_build11.py` 20/20, `test_build12.py` 13/13.

After verification, restore the backed-up DB only if the smoke test corrupted anything (it shouldn't).

#### Out of Scope
- CRUD endpoints for any of the 5 new tables (Builds 14–17)
- Routes, templates, UI
- Permission logic
- AI tools (Build 20)
- Tests beyond import + smoke (CRUD tests land per-feature)

**Done when:** new tables and columns exist on both fresh and existing DBs, no test regression, committed.

---

### Build 14 — Project Journal ✓ SHIPPED v1.1.0-build14

#### Feature Design Review

1. **Workflow problem?** Real product development is reasoning evolution (factory tells us X, we abandon Y, we discover Z). Change Log records WHAT changed; Journal records WHY thinking shifted. Currently nowhere to capture "today the factory said carbon fiber will make the knife ugly so we may pivot to smooth-opening as the thesis."
2. **Repeated or edge?** Repeated — every active project has multiple "we learned X" moments per week.
3. **Structured data?** Lightly — just enough to display chronologically with type/author. Heavy structuring (extracted updates) is deferred to Build 20.
4. **Could it live in notes/files?** Could be a free-text note but loses chronology, author, type filtering, AI summary potential, and the "raw input preserved forever" principle. Worth its own table (already created in Build 13).
5. **Intake burden?** Low — one textarea + type dropdown + "Add" button. No required fields besides the text itself.
6. **AI reduce intake?** Yes — AI generates a `title` (short summary) and `ai_summary` (paragraph) on demand from the raw text. User just types stream-of-consciousness.
7. **Display/reminder?** Section on project detail showing entries newest-first. No reminder/notification in this build (Build 21 bottom-chat will surface unanswered open questions later).
8. **Affects migration?** No — table already created in Build 13.
9. **Minimal schema change?** None.
10. **Minimal UI change?** One new section on project_detail between Thesis and Inspired By; one collapsible add form; one entry card layout.
11. **Defer?** `extracted_updates_json` / `open_questions_json` / `decisions_json` / `options_json` extraction (Build 20 with the tool architecture). `visibility=public` toggle UI (no use case yet — all internal by default).

#### Permission Matrix (per the cross-cutting rule "Viewers cannot see Project Journal")

| Action | Admin | PM | Viewer |
|---|---|---|---|
| See reveal button / Journal section at all | ✓ | ✓ | **✗ — button + section completely hidden** |
| Create entry | ✓ (any project) | ✓ (own projects only — `can_edit_project`) | ✗ |
| Edit entry | ✓ (any entry) | ✓ ONLY their own entries AND only on projects they can edit | ✗ |
| Delete entry | ✓ | ✗ (preserves reasoning history) | ✗ |
| Generate AI summary | ✓ | ✓ (own projects) | ✗ |

`can_view_journal(user)` helper added to `app/dependencies.py`: returns `user.role in ("admin", "pm")`.

**PM edit guard (explicit):** the edit route must check `entry.author_user_id == current_user.id` in addition to `can_edit_project(current_user, project)`. Admin bypasses the author check.

#### AI Permission Guard update (per blueprint rule)

Journal entries are a new sensitive source. Add `journal` / `internal note` to `_VIEWER_FORBIDDEN` in `app/dependencies.py` so a viewer using bottom chat (when Build 21 ships) cannot extract journal content via AI either.

#### UI Design

**Section placement:** between Section 1 (Product Thesis) and Section 1b (Inspired By).

**Easter-egg / hidden-by-default UX (per user requirement):**
The Journal section is dense reasoning content that not every viewer of a project wants to see. So the section is **collapsed by default**. Only a slim reveal button appears between Thesis and Inspired By:

```
   ↓ Show Project Journal (5 entries)
```

Clicking expands the full section in place. Clicking again (now labeled "Hide Project Journal") collapses it. Pure JS toggle (no page reload, no localStorage — refresh resets to collapsed; the section is intentionally low-friction-to-hide).

**Expanded layout (after reveal click):**
```
↑ Hide Project Journal (5 entries)        [+ Add Project Update]
─────────────────────────────────────────
[General · Sarah · May 25, 14:32]
  Title: Factory discussion shifted product direction        ← AI-generated
  "Today the factory said carbon fiber will make the knife
   ugly. We may pivot to smooth-opening as the thesis..."     ← raw entry_text
  AI summary: The factory pushed back on carbon fiber...      ← if present
                                              [Summarize] [✎] [✕(admin)]

[Factory discussion · Mike · May 24, 09:15]
  Title: (not yet summarized)
  "Engineer's preference: aluminum, not titanium..."
                                              [Summarize] [✎] [✕(admin)]
```

**Reveal button is also gated by `can_view_journal`** — for viewers, even the button doesn't render.

**Add form (collapsible inline, like Add Phase):**
- Type dropdown: General · Factory Discussion · Cost Discovery · Design Feedback · Decision · Risk · Packaging · Variant · Other
- Text area (no length limit; placeholder asks for stream-of-consciousness)
- [Save] [Cancel]

**Edit:** click ✎ → entry text becomes a textarea with [Save] [Cancel]. Type dropdown also editable. Raw `entry_text` is overwritten. **Every edit writes a `project_changes` row** (`change_type=event_note`, `summary="Journal entry edited: {first 60 chars of old text}... → {first 60 chars of new text}..."`, `changed_by=user`) so the audit trail records the change even though per-edit text history isn't kept. Per-edit text history is flagged as a future improvement.

**Generate AI summary:** click [Summarize] → POST → AI call returns `{title, summary}`.
- **On success:** the entry is updated and page re-renders showing both fields. Idempotent (clicking again regenerates from the latest raw text).
- **On AI failure:** existing `title` / `ai_summary` are NOT touched. The route redirects with `?journal_error=summarize_failed&entry_id=N` and the template renders a flash banner above the affected entry: "AI summary failed — try again later."

#### Routes (new file `app/routes/journal.py`)

- `POST /projects/{project_id}/journal` — create entry (auth + `can_edit_project`)
- `POST /projects/{project_id}/journal/{entry_id}/edit` — edit entry (auth + `can_edit_project` + author-or-admin check)
- `POST /projects/{project_id}/journal/{entry_id}/delete` — delete entry (admin only)
- `POST /projects/{project_id}/journal/{entry_id}/summarize` — call AI to fill `title` + `ai_summary` (auth + `can_edit_project`)

All routes redirect to `/projects/{id}#journal` on success.

#### CRUD helpers (added to `app/crud.py`)

- `create_journal_entry(db, project_id, entry_text, entry_type, author_user_id) -> ProjectJournalEntry`
- `update_journal_entry(db, entry_id, entry_text, entry_type) -> entry | None`
- `delete_journal_entry(db, entry_id) -> bool`
- `get_journal_entries_for_project(db, project_id) -> list[ProjectJournalEntry]`  (already accessible via `project.journal_entries` relationship — this is a typed accessor)
- `apply_ai_summary(db, entry_id, title, summary) -> entry | None`

#### AI parser (added to `app/ai/parser.py`)

```python
def summarize_journal_entry(entry_text: str) -> dict:
    """Returns {'title': str, 'summary': str} or {'_error': str}.
    Title is short (~6-10 words). Summary is 2-3 sentences."""
    # Uses existing _get_client(), gpt-5.4, JSON mode
    # System prompt: extract a short title + 2-3 sentence summary
    # from a product development journal entry. No invention.
```

New system prompt constant `JOURNAL_SUMMARY_PROMPT` in `app/ai/prompts.py`.

#### AI_TOOLS_REGISTRY update

`create_journal_entry` and `summarize_journal_entry` get added to the registry as `status: implemented (HTTP route only; AI bottom-chat tool wiring lands in Build 20)`.

#### Files to Create
- `app/routes/journal.py`
- `app/templates/components/journal_section.html` (partial included from project_detail)
- `test_build14.py`

#### Files to Modify
- `app/crud.py` — 5 new helpers
- `app/ai/parser.py` — `summarize_journal_entry()`
- `app/ai/prompts.py` — `JOURNAL_SUMMARY_PROMPT`
- `app/dependencies.py` — `can_view_journal()` + extend `_VIEWER_FORBIDDEN`
- `app/main.py` — mount `journal_router`
- `app/routes/projects.py` — pass `journal_entries` + `can_view_journal` to detail template (PM/admin only)
- `app/templates/project_detail.html` — include the journal_section partial between Section 1 and 1b
- `app/static/css/styles.css` — Journal entry card + add-form styles
- `AI_TOOLS_REGISTRY.md` — flip the two journal tools to implemented (route-level only)

#### Verification (`test_build14.py`)
- Admin creates entry on any project → appears on detail
- PM creates entry on own project → appears
- PM tries to POST entry on someone else's project → redirected, no row created
- Viewer GET /projects/{id} → reveal button + Journal section NOT in HTML at all
- Viewer POST → redirected, no row created
- AI summarize → entry has `title` and `ai_summary` populated
- AI summarize when AI errors → entry unchanged, error banner shown via `?journal_error=...` param
- PM edits their OWN entry on their OWN project → raw `entry_text` updated AND project_changes row recorded
- **PM tries to edit ANOTHER PM's entry on a project they both can edit → blocked (per author check)**
- **PM tries to edit any entry on a project they don't own → blocked (per project edit check)**
- Admin can edit any entry on any project
- Admin deletes entry → gone
- PM tries to delete → blocked
- Viewer cannot use bottom AI to ask about journal content (covered when Build 21 bottom-chat ships; for Build 14 just confirm `_VIEWER_FORBIDDEN` includes `journal` / `internal note`)
- `test_build8.py` 40/40, `test_build11.py` 20/20, `test_build12.py` 13/13 — no regression

#### Out of Scope
- `extracted_updates_json` / `open_questions_json` / `decisions_json` / `options_json` AI extraction (Build 20)
- Per-edit history (entry text is mutable; raw saved-once)
- File attachment to journal entry (schema has `linked_file_id` but no UI)
- Visibility=public toggle (deferred — all entries internal in v1.1)

**Done when:** Journal section appears on project detail for admin/PM, completely hidden from viewer, AI summarize works end-to-end, all permissions enforced, tests green, committed.

---

### Build 15 — Business Plan Upload + Thesis Extraction (preview-confirm) ✓ SHIPPED v1.1.0-build15

#### Context
Currently the only way to get a Product Thesis onto a project is to type it manually into the form. Real input is often a multi-page business plan PDF that already contains the thesis, target customer, differentiation, price logic, and risks — buried in prose. Today the PM has to re-type the gist into the 80-char-minimum textarea. Build 15 lets the PM upload the plan once and have AI extract the thesis (and any inspirations worth becoming Ideas), then preview and confirm before anything writes to the DB.

This is the first v1.1.0 build that exercises the cross-cutting rule "AI never silently writes important fields — always preview → confirm → write."

#### Feature Design Review (per FEATURE_DESIGN_PROCESS.md)

1. **Real workflow problem?** Yes — PMs currently retype thesis content that already exists in a business plan doc.
2. **Repeated or edge?** Repeated — every new project starts from some kind of brief or plan.
3. **Structured data?** Lightly — writes to existing `project_thesis` column + optionally creates `ideas` rows + creates one `project_files` row (`file_category="business_plan"`).
4. **Could it live in notes/files?** No — thesis already has a column; ideas already have a table. We're just lowering the friction to populate them.
5. **Intake burden?** Lower than today (upload file once vs retype). Preview adds one extra click but removes the 80-char-minimum hurdle.
6. **AI reduce intake?** Yes — entire reason for the build.
7. **Display/reminder?** Fixed-height scrollable thesis box on detail + inline edit (PM+admin only). No reminders.
8. **Affects migration?** No new tables, no new columns. `project_files.file_category` is a free-string column.
9. **Minimal schema change?** None.
10. **Minimal UI change?** Optional file input on Create Project form; thesis section on detail page becomes scrollable + inline-editable; new preview template.
11. **Defer?** Versioning history of multiple uploaded business plans. Bulk-import many plans. (PDF, DOCX, DOC, and image are all in scope — see File-Format Support below.)

#### Permission Matrix

| Action | Admin | PM | Viewer |
|---|---|---|---|
| Upload business plan at create time | ✓ | ✓ | ✗ (cannot create) |
| Trigger thesis extraction on existing project | ✓ (any) | ✓ (own only — `can_edit_project`) | ✗ |
| See preview screen | extractor only | extractor only | n/a |
| Confirm extraction (writes thesis + ideas) | ✓ (any) | ✓ (own only) | ✗ |
| Inline-edit thesis on detail page | ✓ (any) | ✓ (own only) | ✗ |
| See thesis on detail page | ✓ | ✓ | ✓ (thesis already public) |
| Download the business plan file | ✓ | ✓ | ✓ (already a project file) |

**Sensitivity note:** business plan content can contain pricing strategy / margin targets. Per AI Permission Guard rules, viewer bottom-chat (when Build 21 ships) must not be able to AI-summarize the business plan. Extend `_VIEWER_FORBIDDEN` with: `"business plan"`, `"thesis extraction"`, `"margin target"`, `"pricing strategy"`. The plan file itself stays visible in the file list (consistent with existing behavior; viewer can already see filenames of every uploaded file today).

#### UI / UX

**Entry point 1 — Create Project form** (`app/templates/project_form.html`):
- New optional file input above the Product Thesis section: "📄 Business Plan (PDF, Word, or image) — optional. If uploaded, AI will extract a thesis draft for you to review before saving."
- Form submit handling: route `POST /projects/new` accepts an optional `business_plan: UploadFile`. If present:
  1. Create project as normal (thesis stays whatever the user typed, possibly empty)
  2. Save file via `crud.upload_file()` with `file_category="business_plan"`
  3. **Run AI extraction once synchronously**, persist the result as an `AIMessage` row with `metadata_json` containing the full extraction (see Persistence below)
  4. 302-redirect to `/projects/{id}/thesis/preview?extraction_id={ai_message.id}`
- If no file: existing behavior unchanged.

**Entry point 2 — Project Detail page** (Thesis section):
- Two cases:
  - **No thesis yet OR thesis < 80 chars:** existing red empty-state stays, PLUS a new "📄 Extract from Business Plan" button next to "Add it now"
  - **Thesis present:** existing display, PLUS a "🔄 Re-extract from Business Plan" button (only shown if a business plan file is attached) next to Edit
- Clicking either button opens a small upload modal (file input + Submit). Submit POSTs to `/projects/{id}/thesis/extract-upload` (multipart) which:
  1. Saves the file as `file_category="business_plan"`
  2. Runs AI extraction once
  3. Persists the result as an `AIMessage` row
  4. 302-redirects to `/projects/{id}/thesis/preview?extraction_id=N`

**Preview page** (`app/templates/thesis_preview.html` — new):
```
─────────────────────────────────────────
  Review Thesis Extraction
─────────────────────────────────────────
  Source: business_plan_v3.pdf · 4 pages · extracted in 8.2s

  ┌─ Proposed Thesis ────────────────┐  ┌─ Detected Inspirations (2) ──┐
  │ <textarea, 12 rows, pre-filled>  │  │ ☑ Magnetic sheath close       │
  │ "This product exists because..." │  │   Type: feature · Source: team│
  │                                  │  │   ⓘ Looks similar to existing │
  │                                  │  │     IDEA-005 (87% match) →    │
  │ 320 / 80 char minimum  ✓         │  │     [Link existing] [Create   │
  │                                  │  │      new anyway]              │
  │                                  │  │                               │
  │                                  │  │ ☑ Forged Damascus material    │
  │                                  │  │   Type: material · Source:    │
  │                                  │  │   tradeshow                   │
  │                                  │  │   [Create new]                │
  └──────────────────────────────────┘  └───────────────────────────────┘

  [Cancel] [Confirm — Write Thesis + Selected Ideas]
─────────────────────────────────────────
```

User can edit the proposed thesis directly in the textarea, uncheck inspirations they don't want, choose link-vs-create for each fuzzy-matched one. Confirm POSTs everything in one transaction.

**Detail page Thesis section after Build 15:**
```html
<section class="detail-section">
  <div class="section-header">
    <h2>Product Thesis</h2>
    {% if can_edit %}
      <button onclick="toggleThesisEdit()">Edit</button>
      {% if business_plan_file %}
        <a href="/projects/{id}/thesis/extract?file_id={bp.id}">Re-extract</a>
      {% endif %}
    {% endif %}
  </div>
  <div id="thesisDisplay" class="thesis-box thesis-scrollable">  ← max-height + overflow-y:auto
    <p class="thesis-text">{{ project.project_thesis }}</p>
  </div>
  {% if can_edit %}
  <form id="thesisEditForm" method="post" action="/projects/{id}/thesis/inline-edit" class="d-none">
    <textarea name="project_thesis" rows="10">{{ project.project_thesis }}</textarea>
    <button type="submit">Save</button>
    <button type="button" onclick="toggleThesisEdit()">Cancel</button>
  </form>
  {% endif %}
</section>
```

CSS adds: `.thesis-scrollable { max-height: 220px; overflow-y: auto; padding-right: 8px; }`.

**Inline-edit on detail page** is its own separate route (`POST /projects/{id}/thesis/inline-edit`) so it only requires `project_thesis` — distinct from the full edit page. Writes through `crud.update_project()` so the change log is automatic.

#### Routes (added to `app/routes/projects.py`)

**Critical principle (per user correction):** AI extraction is a one-time POST action. The preview page is a pure GET render of saved data — refreshing it must never re-trigger the AI call.

| Route | Method | Purpose | Calls AI? | Auth |
|---|---|---|---|---|
| `/projects/new` | POST (modified) | Accept optional `business_plan: UploadFile`. If present, after project creation: save file, run AI extraction once, persist as AIMessage, then 302 to `/projects/{id}/thesis/preview?extraction_id={ai_message.id}`. | YES (once) | existing |
| `/projects/{id}/thesis/extract-upload` | POST (multipart) | Save uploaded file as `file_category="business_plan"`, run AI extraction once, persist as AIMessage, 302 to `/thesis/preview?extraction_id=N`. | YES (once) | `can_edit_project` |
| `/projects/{id}/thesis/preview` | GET (`extraction_id=N` query param) | Load the saved AIMessage by id. Verify it belongs to this project. Render `thesis_preview.html` with the stored extraction. Compute fuzzy matches against current ideas at render time (cheap, no AI). | **NO** | `can_edit_project` |
| `/projects/{id}/thesis/confirm` | POST | Receives `extraction_id` (hidden field) + edited `project_thesis` + lists `inspiration_action_N` (create/link/skip) + `inspiration_idea_id_N` (for link). Loads saved extraction by id for audit context. Writes thesis through `crud.update_project()`. Creates/links ideas. Updates AIMessage metadata with `confirmed_at` + the user's final selections. Redirects to `/projects/{id}#thesis`. | NO | `can_edit_project` |
| `/projects/{id}/thesis/inline-edit` | POST | Inline-edit form on detail page. Writes thesis via `crud.update_project()`. Redirects to `/projects/{id}#thesis`. | NO | `can_edit_project` |

On extraction failure (during the POST extract-upload step): the AIMessage is still saved with `metadata_json={"_error": "..."}` so the failure is auditable; the preview page renders a flash banner ("Extraction failed — try again or fill thesis manually") and the textarea empty. The user's project + file are preserved; existing thesis is never touched until Confirm.

#### Persistence of extraction results (per user correction)

Reuse the existing `ai_messages` table — no new schema. Each extraction stores one row:

| Column | Value |
|---|---|
| `project_id` | the project the extraction is for |
| `role` | `"assistant"` |
| `message` | `"thesis_extraction"` (sentinel string for filtering) |
| `metadata_json` | full extraction payload (see below) |
| `created_at` | auto |

`metadata_json` shape:
```json
{
  "kind": "thesis_extraction",
  "source_file_id": 42,
  "source_filename": "business_plan_v3.pdf",
  "source_file_type": "pdf",
  "duration_seconds": 8.2,
  "thesis": "...extracted prose...",
  "inspirations": [
    {"name": "...", "description": "...", "idea_type": "feature",
     "source": "team", "source_detail": "..."}
  ],
  "raw_text_preview": "first 600 chars for audit",
  "model": "gpt-5.4",
  "confirmed_at": null,                       // set on confirm
  "confirmed_thesis": null,                   // user's final edited thesis
  "confirmed_inspirations": null              // user's final per-item actions
}
```

The preview route loads by `ai_messages.id`. Refreshing the preview only re-reads the row — zero AI cost.

If JSON.metadata is stored as `JSON` SQLAlchemy type (it is — verified for `AIMessage`), no migration needed. **No new tables; no new columns.**

#### File-Format Support (per user correction)

Build 15 must support **PDF, DOCX, DOC, and image**. Forcing PDF export is a friction tax against PRODUCT_DEVELOPMENT_PHILOSOPHY principle 2 ("intake burden must be minimized").

| Format | Strategy |
|---|---|
| `.pdf` | existing `_extract_pdf_text()` via `pypdf` (refactored out of `extract_from_pdf`) |
| `.docx` | new `_extract_docx_text()` using `python-docx` — iterate `document.paragraphs`, join with `\n\n`; also include text from tables |
| `.doc` (legacy Word) | try LibreOffice conversion: `subprocess.run(["soffice", "--headless", "--convert-to", "docx", file_path, "--outdir", tmpdir], timeout=60)`. If exit 0 and output exists, run docx path. If `soffice` not on PATH or conversion fails, return `{"_error": "DOC format requires LibreOffice; please save as DOCX or PDF and re-upload."}` — the upload UI still accepts `.doc` so the user discovers this gracefully rather than being silently blocked. |
| image (jpg/png/webp) | existing vision-call pattern from `extract_from_image` (single multimodal request to gpt-5.4) |
| anything else | `{"_error": "Unsupported file type. Use PDF, Word, or image."}` |

Updated `extract_thesis_and_inspirations(file_path: str, file_type: str)` accepts `file_type` in `{"pdf", "docx", "doc", "image"}` and dispatches. The file_type is determined by extension at upload time (lowercased) — extend `files.py` `_get_file_type()` to map `.docx → "docx"`, `.doc → "doc"`.

#### AI extractor (added to `app/ai/parser.py`)

```python
def extract_thesis_and_inspirations(file_path: str, file_type: str) -> dict:
    """Dispatches to pdf/docx/doc/image text extraction, then one gpt-5.4
    JSON-mode call with BUSINESS_PLAN_EXTRACT_PROMPT.

    Returns:
       {
         "thesis": str,
         "inspirations": [
           {"name": str, "description": str, "idea_type": str,
            "source": str, "source_detail": str}
         ],
         "raw_text_preview": str,         # first 600 chars
         "duration_seconds": float,
         "model": str,
       }
       or {"_error": str} on any failure (including .doc without soffice).
    """
```

New helpers in the same file:
- `_extract_pdf_text(file_path, max_pages=10)` — refactored out of existing `extract_from_pdf`
- `_extract_docx_text(file_path)` — `python-docx` paragraphs + table cells
- `_extract_doc_text(file_path)` — LibreOffice conversion → docx → reuse `_extract_docx_text`; returns `None` (caller treats as error) if `soffice` missing
- `_extract_image_text_via_vision(file_path)` — extracts via the vision API into a normalized {extracted, raw_text} shape similar to existing `extract_from_image`

New prompt constant `BUSINESS_PLAN_EXTRACT_PROMPT` in `app/ai/prompts.py` — see existing section above for content; unchanged from the prior revision.

#### AI extractor (added to `app/ai/parser.py`)

```python
def extract_thesis_and_inspirations(file_path: str, file_type: str) -> dict:
    """Returns:
       {
         "thesis": str,                   # extracted prose, may be empty
         "inspirations": [
           {"name": str, "description": str, "idea_type": str, "source": str,
            "source_detail": str}
         ],
         "raw_text_preview": str,         # first 600 chars for audit
       }
       or {"_error": str} on failure.

       file_type: "pdf" or "image" — anything else returns _error
       (matches existing parser.py supported types).
    """
```

Internally:
1. Refactor `_extract_pdf_text(file_path, max_pages=10)` out of existing `extract_from_pdf` so both can reuse it.
2. For images: reuse the vision-call pattern from `extract_from_image` (single multimodal request).
3. Single gpt-5.4 call with JSON mode, `temperature=0.2`, new prompt `BUSINESS_PLAN_EXTRACT_PROMPT`.

New prompt constant `BUSINESS_PLAN_EXTRACT_PROMPT` in `app/ai/prompts.py` — instructs:
- Extract a complete product thesis covering: why this exists, target customer, core problem, differentiation, brand fit, price logic, risks
- The thesis MUST be 1-3 paragraphs (concrete; never bullet lists)
- Separately extract any concrete "inspirations" mentioned: materials, structures/mechanisms, features, aesthetic references, manufacturing techniques. Each inspiration must have name + description + idea_type (material/structure/feature/aesthetic/manufacturing/other) + source (factory/tradeshow/internet/customer/team/competitor/other)
- Never invent. If a section isn't covered in the source, return shorter prose. Don't pad
- Return JSON object — never markdown, never code fences

#### Fuzzy-match inspirations to existing ideas

Reuse and generalize `find_best_match()` in `app/ai/matching.py` so it can match on either Project.name or Idea.name (add a `key=` callable, default `lambda x: x.name`). Use it to attach `matched_idea` + `match_score` (None/0.0 if below threshold) to each AI-detected inspiration for the preview template to show "Link to IDEA-005 (87%)" vs "Create new".

#### CRUD helpers (added to `app/crud.py`)

```python
def save_thesis_extraction(db, project_id, extraction_payload) -> AIMessage:
    """Persist a one-time AI extraction as an ai_messages row.
       extraction_payload is the dict returned by extract_thesis_and_inspirations()
       (or {'_error': '...'} on failure — still saved for audit).
       Returns the AIMessage so caller has the id for the redirect."""

def get_thesis_extraction(db, extraction_id, project_id) -> AIMessage | None:
    """Load a saved extraction by id, verifying it belongs to project_id.
       Returns None if not found / wrong project / not a thesis_extraction row.
       The preview route uses this; refreshing the preview just re-reads."""

def apply_thesis_extraction(db, project_id, extraction_id, new_thesis, inspirations, user):
    """Single-transaction write on Confirm:
       1. update_project(..., {"project_thesis": new_thesis}, changed_by=user.role)
       2. For each inspiration with action='create':
          new_idea = create_idea(db, {...}, contributor_user_id=user.id)
          link_idea_to_project(db, project_id, new_idea.id, user.id, note="From business plan extraction")
       3. For each with action='link':
          link_idea_to_project(db, project_id, existing_idea_id, user.id, note="From business plan extraction")
       4. write_change(event_note, "Thesis extracted from business plan",
                       changed_by="ai", source_type="ai_chat")
       5. Mark the AIMessage with confirmed_at + confirmed_thesis + confirmed_inspirations
          so the audit trail captures what the user actually accepted vs what AI proposed.
       Returns summary {thesis_updated: bool, ideas_created: int, ideas_linked: int}.
    """
```

Per-field change log for thesis is automatically recorded by `update_project()`. The summary event_note marks the AI source. The before/after on the AIMessage row gives a complete audit (what AI proposed vs what the human kept).

#### AI Permission Guard update

Add to `app/dependencies.py` `_VIEWER_FORBIDDEN`:
```python
"business plan", "thesis extraction", "margin target", "pricing strategy",
```

#### AI_TOOLS_REGISTRY update

New row added under Current Tools:
| `extract_thesis_from_business_plan` (HTTP route) | project_id, file_id | auth + `can_edit_project` | YES — preview screen before write | **route implemented (Build 15)**; bottom-chat tool wiring lands in Build 20/21 |

The corresponding row in "Planned for v1.1.0" gets removed (rolled into Current Tools).

#### Files to Create
- `app/templates/thesis_preview.html`
- `test_build15.py`

#### Files to Modify
- `app/routes/projects.py` — 4 new routes + modified `POST /projects/new` (extraction is one-time POST; preview is no-AI GET)
- `app/routes/files.py` — extend `_get_file_type()` to map `.docx → "docx"`, `.doc → "doc"`
- `app/templates/project_form.html` — optional business-plan file input (accepts pdf/docx/doc/image) + verify `enctype="multipart/form-data"`
- `app/templates/project_detail.html` — replace Thesis section markup with scrollable box + inline edit form + Extract/Re-extract upload modal
- `app/ai/parser.py` — add `extract_thesis_and_inspirations()` + helpers `_extract_pdf_text`, `_extract_docx_text`, `_extract_doc_text`, `_extract_image_text_via_vision`
- `app/ai/prompts.py` — add `BUSINESS_PLAN_EXTRACT_PROMPT`
- `app/ai/matching.py` — generalize `find_best_match()` with a `key=` callable so it works for both Projects and Ideas
- `app/crud.py` — add `save_thesis_extraction()`, `get_thesis_extraction()`, `apply_thesis_extraction()`
- `app/dependencies.py` — extend `_VIEWER_FORBIDDEN`
- `app/static/css/styles.css` — `.thesis-scrollable`, preview-page two-column layout, upload modal
- `app/version.py` — bump version string for Build 15
- `requirements.txt` — add `python-docx` (LibreOffice for .doc is a system-level optional dependency, not a pip install — documented in USER_GUIDE)
- `AI_TOOLS_REGISTRY.md` — add extract row; remove planned duplicate
- `VERSION.md`, `CHANGELOG.md`, `USER_GUIDE.md` — Build 15 entries (include note about optional `soffice` system dependency for .doc support)

#### Verification (`test_build15.py`)

1. **Permission:** viewer POST `/projects/{id}/thesis/extract-upload` → redirected (not allowed)
2. **Permission:** PM cannot trigger extract on a project they don't own (redirected)
3. **Detail-page buttons:** detail page shows "Extract from Business Plan" only when thesis is missing/short; "Re-extract" appears only once a business_plan file is attached
4. **PDF extraction happy path:** Upload a 1-page PDF → preview page renders with non-empty thesis textarea
5. **DOCX extraction happy path:** Upload a `.docx` containing a product description → preview page renders with non-empty thesis textarea
6. **Image extraction happy path:** Upload a PNG/JPG screenshot of a product brief → preview page renders with non-empty thesis textarea (covered if existing vision path works)
7. **Preview refresh does NOT re-trigger AI:** After step 4, count `ai_messages` rows where `message="thesis_extraction"` for the project; GET the preview URL a second and third time; count unchanged
8. **Confirm writes thesis:** POST confirm with edited thesis → project detail shows new thesis text + change log has `field_update` row for `project_thesis` AND an `event_note` row from `changed_by="ai"` + the AIMessage row has `confirmed_at` populated
9. **Inspirations: create new:** PDF mentions "magnetic sheath close" → preview shows it as an inspiration with `[Create new]` → confirm with `action=create` → new Idea row exists AND linked to project (visible in Inspired By section)
10. **Inspirations: link existing:** Pre-create idea "Magnetic Sheath Close" → upload similar PDF → preview shows fuzzy-match suggestion → confirm with `action=link` → no duplicate idea created, but linked
11. **Inspirations: skip:** uncheck → no idea created or linked
12. **Inline edit on detail:** PM edits thesis inline → form submits → updated text visible AND change log row written
13. **AI failure path:** simulate parser error (e.g. corrupted PDF) → AIMessage saved with `_error` → preview page renders with error banner + empty textarea + existing thesis preserved (no DB write to project_thesis)
14. **DOC graceful unsupported path:** if `soffice` is not on PATH in the test env, upload a `.doc` → AIMessage saved with `_error` mentioning DOCX/PDF → preview renders friendly message; project not corrupted (skip the test if `soffice` IS available — covered in step 5 functionality)
15. **AI Permission Guard:** unit-test that `is_forbidden_ai_question(viewer_user, "show me the business plan margin target")` returns True
16. **Regression:** `test_build8.py` 40/40, `test_build11.py` 20/20, `test_build12.py` 13/13, `test_build14.py` 18/18 all green

#### Out of Scope
- Versioning history of multiple business plans (each upload creates a new file row + new extraction; latest extraction id wins for the Re-extract redirect)
- AI bottom-chat triggering thesis extraction as a tool call (Build 20/21)
- AI editing inspirations after creation
- Auto-extract on any file upload to the generic Files section (only the Thesis-section button triggers extraction)
- Profit / pricing extraction (Build 16's Profit Model placeholder)
- Installing LibreOffice automatically (system dependency for `.doc` — documented; falls back to friendly error)

**Done when:** All 12 test cases pass, preview page renders correctly with both inspiration types (create + link), inline-edit on detail page works for PMs on their own projects, viewer cannot see Extract buttons, AI Permission Guard rejects business-plan questions for viewers, no regressions.

---

### Build 16 — Multi-SKU Variants + Packaging + Quotation + Profit Model placeholder ✓ SHIPPED v1.1.0-build16

#### Context
Real product development isn't one SKU; it's a family of SKUs (sizes, colors, materials). Today the project row has one `target_factory_cost` and one `target_msrp` — and that's the only place those numbers live. Build 16 adds Variants so each SKU can carry its own cost/MSRP/material/packaging, plus Packaging & Accessories (components shared across the project or scoped to one variant), plus a Quotation section (a friendlier view of files with `file_category="quotation"`), plus a Profit Model placeholder that documents the intended formula for v1.2.

Schema is already in place from Build 13 (`project_variants`, `project_variant_components`).

#### Feature Design Review (per FEATURE_DESIGN_PROCESS.md)

1. **Real workflow problem?** Yes — a single project row can't represent a family of SKUs with per-SKU costs.
2. **Repeated/edge?** Repeated — most projects ship 2+ variants.
3. **Structured data?** Yes — variants, components, both have well-defined fields.
4. **Could it live in notes?** Variants stored as free text would lose per-SKU cost tracking and the future Profit Model.
5. **Intake burden?** Low — variant CRUD is simple modal; packaging is a small form.
6. **AI reduce intake?** Out of scope for Build 16 (tools registered as planned for Build 20).
7. **Display/reminder?** Variant cards on project detail; primary star.
8. **Affects migration?** No — tables exist.
9. **Minimal schema change?** None.
10. **Minimal UI change?** Three new sections on project detail + one new placeholder section.
11. **Defer?** AI-driven variant create (Build 20). Profit Model real calculation (v1.2). Variant images/renderings (Build 18).

#### Permission Matrix

| Action | Admin | PM | Viewer |
|---|---|---|---|
| View variants (without costs) | ✓ | ✓ | ✓ |
| View variant costs (target_factory_cost, actual_factory_cost, target_msrp) | ✓ | ✓ | ✗ |
| Create variant | ✓ (any) | ✓ (own only) | ✗ |
| Edit variant | ✓ | ✓ (own only) | ✗ |
| Delete variant | ✓ | ✗ | ✗ |
| Set is_primary | ✓ | ✓ (own only) | ✗ |
| View packaging components | ✓ | ✓ | ✓ (without costs) |
| Create/edit packaging | ✓ | ✓ (own only) | ✗ |
| Delete packaging | ✓ | ✗ | ✗ |
| Upload quotation | ✓ | ✓ (own only) | ✗ |
| View quotation file list | ✓ | ✓ | ✓ (filename + factory, NOT cost lines in `source_note`) |
| Download quotation file | ✓ | ✓ | ✗ |

**Viewer block on quotation download:** existing files route already requires auth but does not restrict by file_category. Add a guard so any GET on a file whose category is `quotation` requires PM+ — viewer gets a friendly "Not available at your access level" redirect.

#### AI Permission Guard update

Add to `_VIEWER_FORBIDDEN`:
```python
"variant cost", "actual cost", "quotation", "packaging cost", "component cost",
```

#### CRUD (added to `app/crud.py`)

- `create_variant(db, project_id, data, set_primary=False)`
- `update_variant(db, variant_id, data)` — if data.is_primary=True, unset other variants' is_primary first (service-layer enforcement, no DB unique constraint)
- `delete_variant(db, variant_id) -> bool`
- `get_variants_for_project(db, project_id) -> list[ProjectVariant]` (ordered: primary first then by id)
- `set_primary_variant(db, project_id, variant_id) -> bool` — explicit endpoint
- `create_variant_component(db, project_id, data)` (data includes variant_id nullable)
- `update_variant_component(db, component_id, data)`
- `delete_variant_component(db, component_id) -> bool`
- `get_components_for_project(db, project_id) -> list` (project-wide + per-variant, ordered: project-wide first then by variant)
- `get_quotation_files_for_project(db, project_id) -> list[ProjectFile]`

All mutating helpers call `write_change()` with `change_type="event_note"` + descriptive summary.

#### Routes (added to `app/routes/projects.py`)

| Route | Purpose | Auth |
|---|---|---|
| `POST /projects/{id}/variants` | Create variant | `can_edit_project` |
| `POST /projects/{id}/variants/{vid}/edit` | Edit variant | `can_edit_project` |
| `POST /projects/{id}/variants/{vid}/delete` | Delete variant | admin only |
| `POST /projects/{id}/variants/{vid}/set-primary` | Set is_primary | `can_edit_project` |
| `POST /projects/{id}/components` | Create packaging/accessory component | `can_edit_project` |
| `POST /projects/{id}/components/{cid}/edit` | Edit component | `can_edit_project` |
| `POST /projects/{id}/components/{cid}/delete` | Delete component | admin only |

Quotation files already use the existing `POST /projects/{id}/files` route — just add "quotation" to the category dropdown in the upload form and create a new GET viewer guard.

#### UI

Section order on project detail after Build 16:
1. Product Thesis
2. (Journal — easter-egg, admin/PM only)
3. Inspired By
4. **Variants** (new)
5. **Packaging & Accessories** (new)
6. **Quotation Files** (new — filtered view of project_files)
7. **Profit Model** (placeholder)
8. Timeline
9. Files & Renderings
10. Change Log

#### Profit Model placeholder

New section showing:
- "Profit Model — coming in v1.2 (placeholder)"
- Pulls the primary variant; shows: SKU, target_factory_cost, target_msrp
- Shows the intended formula in a readable callout: `Margin = (MSRP − factory_cost − packaging_share) × volume − overhead`
- Lists the inputs that will eventually drive it (currently displayed as data, not computed)
- Link to `PROFIT_MODEL_INTENT.md` for the full design

New `PROFIT_MODEL_INTENT.md`:
- Inputs, formula draft, edge cases, when v1.2 is targeted
- Short and scannable (~200 lines max)

#### Files to Create
- `app/routes/variants.py` — new file containing variant + component + set-primary + quotation routes (keeps projects.py from sprawling)
- `app/templates/components/variants_section.html`
- `app/templates/components/packaging_section.html`
- `app/templates/components/quotation_section.html`
- `app/templates/components/profit_model_section.html`
- `PROFIT_MODEL_INTENT.md`
- `test_build16.py`

#### Files to Modify
- `app/crud.py` — 10 new helpers
- `app/dependencies.py` — extend `_VIEWER_FORBIDDEN`; add `can_view_costs(user)` helper
- `app/main.py` — mount variants_router
- `app/routes/projects.py` — pass new context (variants, components, quotation_files, primary_variant) to detail template
- `app/routes/files.py` — guard GET on quotation files for viewer
- `app/templates/project_detail.html` — include 4 new section partials in order
- `app/templates/project_detail.html` quotation/category dropdown in file upload form (add "quotation" option)
- `app/static/css/styles.css` — variant card layout, packaging table, primary-star indicator
- `app/version.py` — bump to 1.1.0-build16
- `AI_TOOLS_REGISTRY.md` — add planned tools for variants/components
- `VERSION.md`, `CHANGELOG.md`

#### Verification (`test_build16.py`)
1. PM creates variant on own project → variant appears
2. PM creates variant on another project → blocked
3. Setting one variant to primary unsets the others (service-layer enforcement)
4. Viewer cannot see cost columns on variant cards
5. Admin deletes variant; PM cannot delete
6. PM creates packaging component (project-wide) → appears
7. PM creates packaging component scoped to a variant → appears with variant tag
8. Viewer sees component names but not cost columns
9. Upload file with file_category=quotation → appears in Quotation section
10. Viewer GET on quotation file → redirected (not allowed to download)
11. Profit Model section renders showing primary variant
12. AI Permission Guard: viewer asking about "quotation" / "variant cost" → forbidden
13. Regression: prior test suites still pass

**Done when:** all 4 new sections render, permissions enforced, regression green, committed.

---

### v1.1.0 Builds 17–24

Each will be planned in its own plan-mode session when we start it. The blueprint above (in the v1.1.0 Roadmap) is intentionally loose — detailed schemas, route shapes, and edge cases decided per-build.

---

### Build 17 — Timeline 2.0 (Plan / Reality split + Finish Phase) ✓ SHIPPED v1.1.0-build17

Retrospective lives in [CHANGELOG.md](CHANGELOG.md). Roadmap scope: see the table row at line 1536.

---

### Build 18 — Rendering History + Prototype Photos ✓ SHIPPED v1.1.0-build18

Retrospective lives in [CHANGELOG.md](CHANGELOG.md). Roadmap scope: see the table row at line 1537.

---

### Build 19 — My Projects tab + Attention banner cleanup + Project state preservation ✓ SHIPPED v1.1.0-build19

#### Context
v1.1 has grown enough that PMs accumulate noise: the projects list shows everything (including projects they don't own), the attention banner double-flags Needs-Info (already shown on each card + as a filter tab), and the Projects nav link always dumps you back to the full list even when you were deep in one project. Build 19 is a small UX cleanup pass — three independent, low-risk pieces, all S.

#### Scope (three sub-items)

**1. New `/my-projects` route (admin + pm only, hidden from viewer).**
A focused row-per-project view of projects the current user is the PM of. Admin sees all projects (same view, no filtering, since admin "owns" the org). Viewer is redirected to `/projects`.

- New service fn `crud.get_projects_for_user(db, user)` — admin → all projects; pm → projects where `func.lower(project.product_manager) == user.username.lower()`; viewer → empty list.
- New route in `app/routes/projects.py` mirroring the admin-guard pattern from `app/routes/admin.py` but allowing `current_user.role in ('admin', 'pm')`. Returns `templates.TemplateResponse('my_projects.html', ...)`.
- New template `app/templates/my_projects.html` — wide row layout. Reuse the existing table-view markup from `projects_list.html:172-216` as the visual base; trim columns that don't fit a PM's daily workflow (keep: name, current stage, planned launch, delay badge, last updated; drop: brand, factory, cost if too wide).
- Navbar link in `app/templates/base.html` after line 34 (after AI Intake), guarded `{% if current_user and current_user.role in ('admin', 'pm') %}`. Icon: `bi-person-circle`.

**2. Remove Needs-Info from the attention banner.**
Surgical 3-line delete in `app/templates/projects_list.html:33-35`. The Needs-Info per-card badge (line ~156), the filter tab (line ~67-69), `card-needs-info` class wiring, table-view badge (line ~199), and the route `needs_attention` list logic all STAY. The banner becomes "delay-only."

**3. localStorage `pm_last_project_id` — last-project memory on the Projects nav.**
- On every `project_detail.html` load: inline `<script>` writes `localStorage.pm_last_project_id = {{ project.id }}`.
- Projects navbar link in `base.html` gets a click handler with a 250ms delay (so a real double-click can cancel it). Single-click → redirect to `/projects/{last_id}` if set, else `/projects`. Double-click → clear `pm_last_project_id` and go to `/projects`.
- No server-side persistence — pure client-side. Stale ID (deleted project) just 404s; user double-clicks the nav to clear.

#### AI tools registry
No new AI tools. `get_projects_for_user` is a service function only; not exposed via chat in v1.1.

#### Affected files
- New: `app/templates/my_projects.html`
- Modify: `app/routes/projects.py` (new `/my-projects` route), `app/crud.py` (new `get_projects_for_user`), `app/templates/base.html` (nav link + click handler), `app/templates/projects_list.html` (delete banner Needs-Info block), `app/templates/project_detail.html` (one-line localStorage write)
- Bump: `app/version.py`, `VERSION.md`, `CHANGELOG.md`, `USER_GUIDE.md`
- New: `test_build19.py`

#### Verification
- `python3 test_build19.py` cases: admin sees all projects in `/my-projects`; PM sees only own; viewer redirected from `/my-projects`; banner no longer contains `badge-needs-info` while the filter tab still does; project_detail page sets localStorage (assert via response HTML containing the inline write); navbar link in HTML for admin/PM but absent for viewer.
- Regression: `python3 test_build18.py` 17/17 + at least one earlier build (`test_build17.py` 17/17).

#### Out of scope (deferred)
- AI-assisted "show me my projects" via chat → Build 20 / 21.
- Server-side persistence of last-project (e.g. `users.last_project_id`) — pure localStorage is fine for v1.1.
- Renaming "Projects" nav to something else for PMs (would conflict with admin view).

---

### Build 20 — AI Tools Architecture + Permission Guard update ✓ SHIPPED v1.1.0-build20

#### Context
We've built 13 manual HTTP routes that mutate project data (Builds 14-18). Each represents something the AI should eventually be able to do via chat — but today the AI has no schema describing those tools, no dispatcher, no permission discipline applied at the tool boundary. Build 21 (Bottom Chat) needs that foundation. Build 20 builds it: define every tool's JSON schema in one place, wire ONE real handler (`create_journal_entry`) end-to-end to prove the pattern, and leave the other tools as schema + permission-checked stub. Also verifies the AI Permission Guard still covers every sensitive source we've added in v1.1.

#### Scope

**1. Create `app/ai/tools.py` with OpenAI function-calling schemas for all 16 tools.**
(Roadmap row 1539 said "14" originally — that was an approximation. Final count is 16; the row + AI_TOOLS_REGISTRY.md are updated to match.)

The tool list (matches `AI_TOOLS_REGISTRY.md`):

| # | Tool | Why it exists |
|---|------|---------------|
| 1 | `create_journal_entry(project_id, entry_text, entry_type)` | The one tool actually wired in v1.1 — AI can capture a journal entry from chat |
| 2 | `summarize_journal_entry(entry_id)` | AI summary on demand for journal entries |
| 3 | `extract_thesis_from_business_plan(project_id, file_id)` | Thesis extraction from uploaded plan |
| 4 | `create_variant(project_id, variant_name, sku, ...)` | Add a new SKU variant |
| 5 | `update_variant(variant_id, fields)` | Edit a variant's fields |
| 6 | `set_primary_variant(project_id, variant_id)` | Mark one variant as primary |
| 7 | `delete_variant(variant_id)` | Admin-only |
| 8 | `create_variant_component(project_id, variant_id, ...)` | Add packaging/accessory component |
| 9 | `update_variant_component(component_id, fields)` | Edit component |
| 10 | `delete_variant_component(component_id)` | Admin-only |
| 11 | `finish_phase(project_id, phase_id)` | Mark current phase done + advance next |
| 12 | `adjust_phase_plan(phase_id, planned_*_date, reason)` | Plan-date shift with mandatory reason |
| 13 | `update_file_comment(project_id, file_id, comment)` | Per-file annotation |
| 14 | `update_project_field(project_id, field_name, new_value)` | **NEW** — generic field edit, allowlist-gated |
| 15 | `link_idea_to_project(project_id, idea_id, note)` | **NEW** — wire a Good Idea to a project |
| 16 | `create_idea(name, description, idea_type, source)` | **NEW** — create a Good Idea entry |

Each entry is `{"type": "function", "function": {"name", "description", "parameters": {...JSON Schema...}}}` — the format OpenAI's `chat.completions.create(..., tools=[...])` expects.

Module structure (high-level):

```python
# app/ai/tools.py
TOOL_SCHEMAS = [...]  # 16 OpenAI tool objects

TOOL_PERMISSIONS = {
    "create_journal_entry": {"require_role": ("admin", "pm"), "needs_project": True, "needs_journal": True},
    "update_project_field": {"require_role": ("admin", "pm"), "needs_project": True, "field_allowlist": "UPDATE_PROJECT_FIELD_ALLOWED"},
    "delete_variant": {"require_role": ("admin",), ...},
    ...
}

# Deliberately conservative; EXCLUDES current_stage (derived per CLAUDE.md §5)
# and status (operationally consequential — dedicated change tool later).
UPDATE_PROJECT_FIELD_ALLOWED = {"name", "brand", "sku", "product_type", "project_owner",
                                "product_manager", "planned_launch_date", "project_thesis",
                                "notes"}

def dispatch(tool_name, args, db, user) -> dict:
    """
    Order of checks (security-first; never skipped, even for unwired tools):
      1. Tool exists in TOOL_SCHEMAS              → else {"ok": False, "error": "unknown_tool"}
      2. User passes role check per TOOL_PERMISSIONS → else {"ok": False, "error": "forbidden"}
      3. Field allowlist (for update_project_field) → else {"ok": False, "error": "field_not_allowlisted"}
      4. Handler exists in v1.1                    → else {"ok": False, "error": "not_wired_until_build_21"}
      5. Call handler                              → return its result
    """
    ...
```

**2. Wire `create_journal_entry` end-to-end.**
Reuses the existing `crud.create_journal_entry` service function (Build 14). Validates args → checks `can_edit_project` + `can_view_journal` → calls the service (which writes the change log) → returns `{"ok": True, "entry_id": ...}`.

**3. Verify the AI Permission Guard.**
`_VIEWER_FORBIDDEN` in `app/dependencies.py:92` is already comprehensive. Verification only — no additions for Build 18 (renderings/prototype photos aren't sensitive) or Build 19 (`/my-projects` is server-gated). Quick audit of `sanitize_project_for_user` to confirm variant costs / quotation file lists are never returned for viewers.

**4. Update `AI_TOOLS_REGISTRY.md`.**
- Move `update_project_field`, `link_idea_to_project`, `create_idea` from "Planned" to "Current Tools" with status `implemented (schema only; handler stub in app/ai/tools.py; full wiring in Build 21)`.
- Update existing "Current Tools" status strings from `route implemented (Build NN); bottom-chat tool wiring lands in Build 20/21` → `route + schema implemented (Build NN/20); handler wiring lands in Build 21`.
- The §Sensitive Field Allowlist already corrected pre-Build-20 (no `current_stage`, no `status`).
- Add a short "How the dispatcher works" subsection mirroring the 5-step order from `dispatch()`.

**5. Tests — `test_build20.py`.**

*Schema & dispatcher correctness:*
- `from app.ai.tools import TOOL_SCHEMAS, TOOL_PERMISSIONS, dispatch` imports cleanly.
- `len(TOOL_SCHEMAS) == 16` and every entry has shape `{"type": "function", "function": {"name", "description", "parameters"}}` with a matching key in `TOOL_PERMISSIONS`.

*The one real handler:*
- `dispatch("create_journal_entry", {"project_id": <pid>, "entry_text": "test entry", "entry_type": "general"}, db, admin_user)` returns `{"ok": True, "entry_id": <int>}`; a new row exists in `project_journal_entries`. (If `entry_type="general"` is not a valid enum value, swap to the correct one during implementation.)
- `dispatch("create_journal_entry", ..., viewer_user)` → `{"ok": False, "error": "forbidden"}`; NO row added.

*Permission-before-stub discipline:*
- `dispatch("delete_variant", {...}, pm_user)` → `{"ok": False, "error": "forbidden"}` (PM ≠ admin; permission check fires BEFORE the stub).
- `dispatch("delete_variant", {...}, admin_user)` → `{"ok": False, "error": "not_wired_until_build_21"}`.
- Neither is a 500.

*Field allowlist:*
- `dispatch("update_project_field", {"field_name": "factory", ...}, admin_user)` → `field_not_allowlisted`.
- `dispatch("update_project_field", {"field_name": "current_stage", ...}, admin_user)` → `field_not_allowlisted` (derived field).
- `dispatch("update_project_field", {"field_name": "status", ...}, admin_user)` → `field_not_allowlisted` (conservative-allowlist decision).
- `dispatch("update_project_field", {"field_name": "brand", ...}, admin_user)` → `not_wired_until_build_21` (handler stub, but field IS allowed).

*AI Permission Guard — one explicit case per v1.1 sensitive source:*
- viewer asking "summarize the business plan" → True
- viewer asking "what's in the journal entries" → True
- viewer asking "variant cost for the small SKU" → True
- viewer asking "packaging cost breakdown" → True
- viewer asking "quotation totals" → True
- pm asking "what factory does this use" → False (PM has factory access)
- admin asking "show the journal entries" → False

#### Affected files
- New: `app/ai/tools.py`, `test_build20.py`
- Modify: `AI_TOOLS_REGISTRY.md`, `app/dependencies.py` (verification only; likely no real changes), `app/version.py`, `VERSION.md`, `CHANGELOG.md`

#### Verification
- `python3 test_build20.py` — all assertions pass.
- Regression: `python3 test_build19.py` 15/15, `python3 test_build18.py` 17/17.
- `python -c "from app.ai.tools import TOOL_SCHEMAS; import json; print(json.dumps(TOOL_SCHEMAS[0], indent=2))"` prints a valid OpenAI function-call schema.
- Footer + Help modal show `v1.1.0-build20`.

#### Out of scope (deferred to Build 21)
- The actual Bottom Chat UI that *calls* these tools.
- Confirmation cards (mandatory for destructive tools like `delete_variant`, `update_project_field`).
- The 13 stub handlers becoming real (only `create_journal_entry` ships wired in v1.1).
- AI conversation history persistence (`ai_conversations` table exists from Build 13 — Build 21 uses it).

---

### Build 21 — Bottom AI Chat + Side Panel + Conversation History ✓ SHIPPED v1.1.0-build21

---

### Build 22 — AI-Assisted Create Project (consolidate intake into /projects/new) ✓ SHIPPED v1.1.0-build22

---

### Build 23 — Chinese i18n ✓ SHIPPED v1.1.0-build23

#### Context
The PM tracker is used by Chinese-speaking PMs. Today every label is English; switching the UI to Chinese requires translating ~150 user-facing strings (navbar / page titles / section headers / buttons / form labels / badges / alerts / empty-state copy) and adding a language switcher with persistence.

**Backend is ready** — Build 13 added `users.language` (String, default `"en"`, NOT NULL). No migration needed.

**Out of i18n scope (stays English):**
- AI prompts in `app/ai/prompts.py` (instructions to the model — English performs better; not user-visible).
- Deep docs: `USER_GUIDE.md`, `CHANGELOG.md`, `ARCHITECTURE.md`, `MASTERPLAN.md`, `CLAUDE.md`, `AGENTS.md`.
- Help modal body (~240 lines in `base.html`) — too much surface for v1.1, audience small; defer to v1.2 if needed.
- Admin-only pages (`/admin/database`, `/admin/users`) — internal tools.
- Changelog / version history strings.

This is "size: L" because of the breadth of template touches, not because of architectural complexity.

#### Scope

**1. New module `app/i18n.py`** —
```python
# Loads bundles at import time.
# Locale resolution order: user.language → "lang" cookie → "en" default.
TRANSLATIONS: dict[str, dict[str, str]]  # {"en": {...}, "zh": {...}}

def get_locale(request, current_user) -> str: ...

@jinja2.pass_context
def t(ctx, key: str, **kwargs) -> str:
    """Jinja2 global. Looks up key in current locale's bundle; falls back to
    English bundle; falls back to the literal key (so missing translations
    are visible in dev, not silent)."""
    locale = ctx.get("locale", "en")
    s = TRANSLATIONS.get(locale, {}).get(key)
    if s is None:
        s = TRANSLATIONS["en"].get(key, key)
    return s.format(**kwargs) if kwargs else s
```

Register `t` as a Jinja2 global in `app/main.py` (existing `_GLOBALS` injection pattern — add `t` to the dict).

**2. New bundles** —
- `app/i18n/en.json` — explicit English bundle (so `t('nav.projects')` works even when locale="en" instead of falling back to the raw key).
- `app/i18n/zh.json` — Chinese translations.

**Key convention:** dot-separated, scoped by area for scannability. ~150 keys total:
- `nav.*` (8): projects, calendar, ideas, my_projects, database, users, help, sign_out
- `title.*` (~12): all_projects, calendar, ideas, new_project, edit_project, my_projects, login, register, ai_intake, …
- `section.*` (~30): thesis, timeline, files, change_log, inspired_by, rendering_history, prototype_photos, variants, packaging, quotation, profit_model, journal, planned_launches, actually_launched, …
- `btn.*` (~25): save, cancel, create, edit, delete, archive, upload, extract_fields, analyze_file, confirm_create, …
- `form.*` (~40): project_name, brand, sku, product_manager, engineer, factory, target_factory_cost, target_msrp, planned_launch_date, project_thesis, phase_name, …
- `badge.*` / `status.*` (~15): required, critical, recommended, active, completed, paused, cancelled, archived, delayed, needs_info, on_track, not_started, in_progress, done, skipped
- `alert.*` (~12): needs_attention, days_late, critical_missing, no_projects, …
- `empty.*` (~8): no_files, no_journal, no_variants, no_quotation_files, no_linked_ideas, no_changes, no_phases, …

I'll seed all ~150 zh translations as a first pass. **Translations need user review** — I'm not a native Chinese speaker; I'll aim for natural product-management vocabulary but the user should sanity-check before shipping. The plan flags this as an explicit review step.

**Translation philosophy — product language, not mechanical translation.** Keep mixed-language terms when the Chinese version would be less clear or industry usage is English. Specifically: **Thesis, MSRP, SKU, AI, PM** stay as-is (don't try to translate to 论点 / 建议零售价 / 库存单位 / 人工智能 / 项目经理 — these are clunky or ambiguous in product-development context). Also keep brand names, factory names, product codes untranslated. The goal is to read naturally to a Chinese-speaking PM who already works in this domain.

**3. Locale resolution middleware** —
Small FastAPI middleware that resolves locale once per request and stashes on `request.state.locale`:
```python
@app.middleware("http")
async def i18n_middleware(request, call_next):
    request.state.locale = get_locale(request, current_user=None)  # cookie / default fallback
    response = await call_next(request)
    return response
```
For authenticated users, the locale is re-resolved inside each route's `get_current_user` step (or we layer a second helper that reads user.language first). Simplest: `get_locale(request, current_user)` is called by each TemplateResponse and the result is added to context as `locale`.

**Cleanest implementation chosen**: routes pass `"locale": get_locale(request, current_user)` to every TemplateResponse. Most routes already pass `"current_user": current_user` — same pattern. This is explicit + avoids middleware mutation of state that Jinja relies on.

**4. Language switcher partial** —
New `app/templates/components/lang_switcher.html`: a small `<form method="post" action="/lang/set">` with hidden `lang` field and `next` URL. Renders two buttons (EN / 中文) in the navbar; the current locale's button is disabled. Included from `base.html` inside the user-info span.

**5. New route `POST /lang/set`** in a new `app/routes/i18n.py`:
- Accepts `lang` (must be in `{"en", "zh"}`, default to "en" if invalid).
- Sets `lang` cookie (1-year max-age, samesite=lax).
- If `current_user` is authenticated, updates `user.language = lang` and commits.
- Redirects to `next` (or `/projects` if no next provided).

**6. Template sweep** — replace English literals with `{{ t('key') }}` calls across:
- `app/templates/base.html` (navbar)
- `app/templates/projects_list.html` (page title, filter tabs, attention banner labels, table headers, badges)
- `app/templates/project_detail.html` (every section header, action buttons, empty-state copy)
- `app/templates/project_form.html` (every form label, button)
- `app/templates/intake.html` / `app/templates/components/ai_intake_panel.html` (state-1 and state-2 labels)
- `app/templates/my_projects.html` (Build 19)
- `app/templates/components/*.html` (journal, quotation, media_history, bottom_chat — labels only, not AI prompts)
- `app/templates/calendar.html`, `app/templates/ideas.html` etc.
- `app/templates/auth_*.html` (login/register pages)

**NOT swept:** admin templates, `app/templates/intake.html` only if it's still rendered (we keep the file as legacy artifact), help modal content.

**Strategy to avoid breaking existing tests:** every test_buildNN.py that asserts a literal string is run AGAINST the English default (since default lang is "en" and tests don't set the cookie). So the sweep should only change template SOURCE — the rendered English output stays identical to current behavior. Verified by running the full regression suite after the sweep.

**7. Tests — `test_build23.py`:**

*Bundle integrity:*
- `from app.i18n import TRANSLATIONS, t, get_locale` imports cleanly.
- `len(TRANSLATIONS["zh"]) >= 100` (sanity that we shipped substantial coverage).
- Every key in `zh.json` exists in `en.json` (otherwise it's a typo we'd never catch).

*Default English renders existing English labels:*
- Anonymous GET `/auth/login` HTML contains the English label "Sign In" (or current equivalent) — proves the template sweep didn't break English rendering.
- Admin GET `/projects` (no cookie set) HTML contains "Projects" in the navbar.

*Switching to Chinese changes navbar labels:*
- POST `/lang/set` with `lang=zh` then GET `/projects` → navbar contains `项目` (Chinese for Projects). No restart required.

*Logged-in language switch updates `users.language`:*
- Admin POST `/lang/set` with `lang=zh` → DB row `users WHERE username='admin'` has `language='zh'`.
- Same for switching back to `en`.

*Cookie fallback works (logged-out user):*
- New `requests.Session()` (no login). Set cookie `lang=zh` manually. GET `/auth/login` → contains Chinese labels.
- Same session WITHOUT the cookie → English labels.

*Missing translation key does NOT crash:*
- `t(ctx, 'this.key.does.not.exist')` returns the literal string `'this.key.does.not.exist'` and does NOT raise.
- Render a template that calls `{{ t('this.key.does.not.exist') }}` → page returns 200 with the literal key visible (so devs see what's missing) — never 500.

*Locale resolution chain:*
- `get_locale(request, None)` with no cookie → `"en"`.
- `get_locale(request, None)` with cookie `lang=zh` → `"zh"`.
- `get_locale(request, user_with_zh_pref)` with no cookie → `"zh"` (user pref wins).
- `get_locale(request, user_with_en_pref)` with cookie `lang=zh` → `"en"` (user pref still wins; cookie is fallback for logged-out only).

*Regression — every prior build's English-asserting tests still pass:*
- The plan's verification step runs `test_build18.py`, `test_build19.py`, `test_build20.py`, `test_build21.py`, `test_build22.py`, `test_ai_e2e.py`. All must stay green. This proves the template sweep didn't change any rendered English text.

**8. Version + docs:**
- `app/version.py` → `1.1.0-build23`.
- `VERSION.md` "What's new in v1.1.0-build23" entry.
- `CHANGELOG.md` Build 23 entry (English).
- **`USER_GUIDE.md`** stays English; add a one-line note that Chinese UI is now available via the switcher.

#### Affected files
- New: `app/i18n.py`, `app/i18n/en.json`, `app/i18n/zh.json`, `app/routes/i18n.py`, `app/templates/components/lang_switcher.html`, `test_build23.py`
- Modify: `app/main.py` (register `t` global, mount i18n router), `app/templates/base.html` (include lang_switcher), `app/templates/projects_list.html`, `app/templates/project_detail.html`, `app/templates/project_form.html`, `app/templates/my_projects.html`, `app/templates/calendar.html`, `app/templates/ideas.html`, `app/templates/auth_login.html`, `app/templates/auth_register.html`, `app/templates/components/ai_intake_panel.html`, `app/templates/components/journal_section.html`, `app/templates/components/quotation_section.html`, `app/templates/components/media_history_section.html`, `app/templates/components/bottom_chat.html`, all relevant routes (add `"locale": get_locale(request, current_user)` to every TemplateResponse context — could be ~30 call-sites; consider a small helper)
- `app/version.py`, `VERSION.md`, `CHANGELOG.md`, `USER_GUIDE.md` (one-line note)

#### Verification
- `python3 test_build23.py` — all assertions pass.
- Regression: every existing `test_buildNN.py` (8, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22) still passes — confirms the template sweep didn't break any English-text assertions.
- Manual smoke: load `/projects` → click 中文 → navbar shows Chinese labels → click EN → switches back. Both directions persist across reloads.
- `test_ai_e2e.py` still 10P/7S/0F (no regression).
- Footer + Help modal show `v1.1.0-build23`.

#### Non-goals / safety rails (confirmed)
- **No `Accept-Language` browser header.** Locale resolution stays `user.language → lang cookie → "en"`. Manual switcher is enough.
- **No business logic, permission, AI behavior, or schema change.** Build 23 is UI i18n only. Permissions, routing, dispatcher, AI prompts, AI tool wiring all untouched.
- **`t(key)` is fail-safe.** Missing key returns the literal key string (visible to devs in dev) — never raises, never 500s a page. Same for missing locale (falls back to "en"; if "en" also missing, returns the key).
- **User reviews `zh.json` before merging.** I (Claude) write a first pass; user does a pass before this build is marked SHIPPED.

#### Out of scope (deferred)
- Translating the Help modal body, USER_GUIDE.md, AI prompts, admin pages, the changelog/version history strings.
- Right-to-left languages.
- Pluralization rules (Chinese doesn't need them; English uses N=1 vs N>1 in just a couple alert messages — handled inline if needed).
- Translation memory tooling, .po files, gettext infrastructure — overkill for ~150 keys.

---

### Build 24 — v1.1.0 release tests + USER_GUIDE update + bump ✓ SHIPPED v1.1.0

#### Feature Design Review
1. Real workflow problem: the v1.1.0 feature set needs one release-level source of truth so users and future agents can understand what shipped.
2. Repeated or edge-case: release docs and regression inventory are referenced repeatedly by deployers, testers, and future build handoffs.
3. Structured data: no new structured product data; this is version metadata, docs, and tests.
4. Could live in notes: no, release/version state must live in canonical repo files and runtime version constants.
5. Intake burden: no user-facing intake change.
6. AI reduce burden: no AI behavior change; better docs reduce future handoff ambiguity.
7. Display/reminder payoff: users get one concise guide for the whole v1.1 workspace and Chinese-speaking users get a short summary.
8. Migration impact: none.
9. Minimal schema change: no database schema change.
10. Minimal UI change: no UI change except the footer/help version string via `app/version.py`.
11. Deferred: native-speaker review of Chinese bundle wording and future full Profit Model implementation.

#### Scope
- `app/version.py` bumped from `1.1.0-build23` to final `1.1.0`.
- `VERSION.md` gets a consolidated v1.1.0 release summary.
- `CHANGELOG.md` gets a v1.1.0 mega entry above build-level entries.
- `USER_GUIDE.md` gets a short Chinese summary, English sections for all v1.1 features, and the intended Profit Model formula.
- `test_build24.py` verifies release docs, runtime version constants, regression-test inventory, and i18n bundle parity.

#### Verification
- `python3 test_build24.py` checks the release documentation and version state.
- Final regression includes Build 23 and the v1.1 regression set.
- No database schema change.

---

#### Context
Today the app has two ways to create a project: `/projects/new` (manual form) and `/ai/intake` (paste text / upload file → AI extracts fields → confirm). Conceptually they're the same task, and the navbar carries both as separate destinations. Build 22 consolidates them: `/projects/new` becomes a two-tab page (Manual Form / AI-Assisted), the AI Intake link is removed from the navbar, and the `/ai/intake` route stays as a 303 redirect to `/projects/new?tab=ai` so old bookmarks and test fixtures keep working.

This is "size: M" — UI relocation, not new logic. The AI parsing, extraction, idea classification, and confirmation flows are unchanged; only the page that hosts the input form moves.

#### Scope

**1. New tab structure on `/projects/new`.**
- Modify [app/templates/project_form.html](app/templates/project_form.html) (the existing Create-Project template). Wrap the current form body in a `tab-pane` for "Manual Form" and add a second `tab-pane` for "AI-Assisted" using the **same Bootstrap tab pattern already used by the Help modal** in [base.html](app/templates/base.html) lines 75-312.
- The `?tab=ai` query param picks the active tab on initial render. Default is Manual.
- Tab switching is client-side (Bootstrap data attributes); no extra route work.

**2. Move the AI Intake UI into the AI-Assisted tab.**
- Extract the relevant parts of [app/templates/intake.html](app/templates/intake.html) into a new partial [app/templates/components/ai_intake_panel.html](app/templates/components/ai_intake_panel.html). The partial supports the two states intake already has:
  - **State 1 (input):** textarea + file-upload zone, posting to `/ai/intake/extract` and `/ai/intake/extract-file` (unchanged endpoints).
  - **State 2 (review/confirm):** project review form posting to `/ai/intake/confirm`, OR idea review form posting to `/ai/intake/confirm-idea`. Unchanged.
- The "Manual Entry" cross-link inside intake.html (currently points to `/projects/new`) becomes a tab switch (`<a href="?tab=manual">` or a Bootstrap tab button trigger).
- Both confirm endpoints continue to RedirectResponse to `/projects/{id}` or `/ideas?highlight=...` on success.

**3. Server-side endpoints stay almost unchanged.**
- [app/routes/intake.py](app/routes/intake.py) endpoints `/ai/intake/extract`, `/ai/intake/extract-file`, `/ai/intake/confirm`, `/ai/intake/confirm-idea` keep their paths and behavior. The HTML they return is rebuilt to fit inside the tab (i.e., they render `ai_intake_panel.html` instead of the full `intake.html`).
- **The single GET `/ai/intake`** becomes a 303 redirect to `/projects/new?tab=ai`. This preserves old bookmarks and any test that POSTs to `/ai/intake/...` (those POSTs are unaffected).

**4. Navbar cleanup.**
- Remove the "AI Intake" link from [base.html](app/templates/base.html) lines 30-36.
- The Bottom AI Chat (Build 21) is the daily AI entry point now; AI-Assisted Create lives where you'd expect it: inside the Create Project flow.

**5. Routes/projects.py — GET /projects/new handles the new tab query param.**
- Read `tab = request.query_params.get("tab")` and pass to template context as `initial_tab` (default `"manual"`). The template uses it to set the `active` class on the right tab + `show active` on the right pane.

**6. Tests — `test_build22.py`.**
- GET `/projects/new` (no tab) renders both tab buttons + the manual pane as active.
- GET `/projects/new?tab=ai` renders the AI pane as active.
- GET `/ai/intake` (legacy) returns 303 redirect to `/projects/new?tab=ai`.
- POST `/ai/intake/extract` with a short text body returns the review HTML (smoke test — does NOT depend on full AI accuracy, just that the round-trip works).
- POST `/ai/intake/confirm` with a minimal valid field set creates a project (regression — confirm flow still works after UI move).
- Navbar smoke: GET `/projects` for admin/PM does NOT contain `href="/ai/intake"` in the navbar. Bottom chat bar (Build 21) is still present.
- Viewer cannot access `/projects/new` AI tab (existing role guard; just confirm it didn't regress).

#### Affected files
- New: [app/templates/components/ai_intake_panel.html](app/templates/components/ai_intake_panel.html), `test_build22.py`
- Modify: [app/templates/project_form.html](app/templates/project_form.html) (tab wrapper), [app/templates/intake.html](app/templates/intake.html) (shrink to redirect/legacy or remove), [app/routes/intake.py](app/routes/intake.py) (GET /ai/intake → 303 redirect; extract/confirm now render the partial), [app/routes/projects.py](app/routes/projects.py) (initial_tab in context), [app/templates/base.html](app/templates/base.html) (remove AI Intake nav link), `app/version.py`, `VERSION.md`, `CHANGELOG.md`, `USER_GUIDE.md`

#### Verification
- `python3 test_build22.py` — all assertions pass.
- Regression: `python3 test_build21.py` 20/20, `python3 test_build20.py` 23/23, `python3 test_build19.py` 15/15.
- Manual smoke: navbar no longer has AI Intake; `/ai/intake` redirects to `/projects/new?tab=ai`; both tabs render correctly; AI Extract round-trip still creates a project; idea-classification path still creates an idea.
- Footer + Help modal show `v1.1.0-build22`.

#### Out of scope
- Changes to the AI extraction logic itself (parser, prompts, dual-mode classification). Just relocating UI.
- Changes to the Bottom AI Chat (Build 21). Untouched.
- Renaming or restructuring `/ai/intake/...` POST endpoints.
- Mobile-specific tab styling — the existing Bootstrap tab pattern is fine.

---

#### Context
Build 20 shipped the tool schemas + dispatcher; nothing actually invokes them yet. Build 21 is where users meet the AI: a ChatGPT-style bottom chat bar visible on every authenticated page, a right-side panel that slides in when the user submits, and persistent conversation history backed by the `ai_conversations` table (created in Build 13). The only AI tool that actually mutates anything in v1.1 is `create_journal_entry` (per Build 20); the other 15 tools return `not_wired_until_build_21` and the chat surface renders that response as a friendly "I can't do that yet" card.

This is "size: L" but kept shippable in one session by deferring drag-drop file upload and streaming to follow-ups.

#### Scope

**1. Backend — new routes in `app/routes/ai_chat.py` (new file).**
- `POST /ai/chat` — Body: `{conversation_id?: int, message: str, mode: "ask"|"intake", project_id?: int}`. Server flow:
  1. `require_auth(current_user)`.
  2. Reject early with 400 if `is_forbidden_ai_question(user, message)` returns True (return JSON `{ok: false, error: "question_blocked_by_permission_guard"}`).
  3. Load or create `AIConversation` (new if `conversation_id` is null; tie to `user_id` + optional `project_id`).
  4. Append user message via `crud.save_ai_message(db, project_id=<conv.project_id>, role="user", message=<text>, metadata={"conversation_id": conv.id, "mode": mode})`.
  5. Build OpenAI messages list: system prompt (mode-specific) + recent N messages from conversation (newest first, capped at ~10 for token discipline) + the new user message.
  6. Call `openai.chat.completions.create(model="gpt-5.4", messages=..., tools=TOOL_SCHEMAS if mode=="intake" else None)`.
  7. If response contains `tool_calls`: for each, call `app.ai.tools.dispatch(name, args, db, user)` and capture results. Append assistant message + a follow-up assistant message describing each tool result. (Two-turn pattern — tool result fed back to AI in a final summarizing turn is a v1.2 enhancement; v1.1 just echoes the dispatcher response.)
  8. Append assistant message via `crud.save_ai_message(...)` with `metadata={"conversation_id": conv.id, "tool_calls": [...]}`.
  9. Return JSON `{ok: true, conversation_id: conv.id, messages: [latest user + assistant turn(s) with tool_call cards if any]}`.
- `GET /ai/conversations` — Returns list of user's active conversations `[{id, title, project_id, project_name?, updated_at}]` ordered by `updated_at desc`. Excludes archived.
- `GET /ai/chat/{conversation_id}` — Returns full message thread `{id, project_id, title, messages: [...]}`. 404 if conversation doesn't belong to current user.
- `POST /ai/conversations/{id}/archive` — Flips `status='archived'`. Idempotent.

**2. Service layer — new crud functions in `app/crud.py`.**
- `create_ai_conversation(db, user_id, project_id=None, title=None) -> AIConversation` — Auto-titles to "{project.name}" or "(global chat)" if no project, or "(new conversation)" if title-blank.
- `list_ai_conversations(db, user_id, include_archived=False) -> list[AIConversation]` — Ordered by `updated_at desc`.
- `get_ai_conversation(db, conversation_id, user_id) -> AIConversation | None` — Enforces ownership; returns None if not user's.
- `get_ai_messages_for_conversation(db, conversation_id, limit=None) -> list[AIMessage]` — Ordered by `created_at asc`.
- `archive_ai_conversation(db, conversation_id, user_id) -> bool` — Returns False if not user's.
- Modify `crud.save_ai_message` (already exists) — Already supports `metadata`; verify it bumps `conversation.updated_at` if `metadata["conversation_id"]` is set. If not, add a small `conversation.updated_at = datetime.utcnow()` write.

**3. AI prompts — extend `app/ai/prompts.py`.**
Two new system prompts:
- `CHAT_ASK_SYSTEM_PROMPT` — "You are an assistant for a PM tracker. Answer questions about the project/data. You CANNOT modify anything in this mode. If the user asks you to write/create/update something, tell them to switch to Intake mode."
- `CHAT_INTAKE_SYSTEM_PROMPT` — "You can help capture journal entries via the `create_journal_entry` tool. The other 15 tools are defined but not wired in this release; if you try to call them, you'll get back `not_wired_until_build_21` and you should tell the user the feature is coming. Always confirm important details with the user before calling a tool."

**4. Frontend — new partial `app/templates/components/bottom_chat.html`.**
- Renders fixed at viewport bottom. Wrapped in `{% if current_user %}` in `base.html` so anonymous pages don't show it.
- Two-row collapsed layout (~64px tall): mode toggle (Ask/Intake) + scope toggle (Project/Global, only when on a project detail page) + textarea + submit button.
- Textarea auto-grows up to ~6 lines (CSS + a small JS handler on `input`).
- Right-side panel (`<div id="aiSidePanel">`) starts off-screen (`transform: translateX(100%)`), slides in (`transform: translateX(0)`) when first message submitted.
- Panel header: conversation title (editable on click) + conversation history dropdown + archive button + close (collapses panel; chat bar stays).
- Panel body: scrollable message list. User bubbles (right-aligned, plain text). Assistant bubbles (left-aligned, rendered as markdown via the existing approach — or just plain text for v1.1). Tool-call cards render as a small bordered box showing `tool_name(args) → result.error_or_summary`.

**5. Frontend — wire it up in `app/templates/base.html` + `app/static/css/styles.css` + `app/static/js/main.js`.**
- `base.html`: include the partial inside `{% if current_user %}` block after the help modal (around line 320). Pass `project_id` from context if on a project detail page (use `request.url.path` parsing — or read from a template variable already in context like `current_project_id`; need to add it to project_detail.html's context).
- `styles.css`: append Build 21 CSS — `.bottom-chat-bar` (fixed bottom, full width, dark accent), `.ai-side-panel` (fixed right, 420px wide, slide-in transition), `.chat-message-user/.chat-message-assistant` (bubble styling), `.chat-tool-call-card`.
- `main.js`: append Build 21 IIFE — textarea auto-grow, submit handler (fetch POST `/ai/chat`, render messages, slide panel in), history dropdown handler, archive button handler, close button handler.

**6. Permission guard — verify no leak.**
The chat input is gated by `{% if current_user %}` in base.html. The `/ai/chat` route additionally:
- Checks `require_auth`.
- Checks `is_forbidden_ai_question` BEFORE calling OpenAI (so viewer-forbidden questions never reach the model).
- Calls `dispatch()` which already enforces role + project ownership per Build 20.

No new sources of sensitive data. The `_VIEWER_FORBIDDEN` list from `app/dependencies.py:92` already covers everything chat could ask about.

**7. Tests — `test_build21.py`.**

*Conversation CRUD:*
- Admin creates a conversation via POST `/ai/chat`, gets back `conversation_id`. Same `conversation_id` works on follow-up.
- Listing conversations excludes archived; archive endpoint flips status.

*Round-trip with the real tool:*
- Admin posts: "Please log a journal entry that says 'Build 21 round-trip test'" with `mode="intake"` and a valid `project_id`. AI calls `create_journal_entry`. Verify a new `project_journal_entries` row exists with that text.
- Viewer posts the same → response contains `forbidden` or guard rejection; no new journal row.

*Permission guard:*
- Viewer asks "what factory is this project using" → response is `question_blocked_by_permission_guard`; no OpenAI call (verify by absence of new ai_messages row beyond the user message that triggered the block — or just check the response error code).

*Mode discipline:*
- Same journal-write prompt with `mode="ask"` → AI does NOT call any tool (no journal row created); response is text only.

*Stubbed tools:*
- Admin asks chat to delete a variant → AI calls `delete_variant` → dispatcher returns `not_wired_until_build_21` → response renders the tool-call card with that error string. No deletion.

*UI smoke (HTTP only — no Playwright):*
- GET `/projects` for an authenticated user contains the `bottom-chat-bar` markup.
- GET `/auth/login` (anonymous) does NOT contain `bottom-chat-bar`.

#### Affected files
- New: `app/routes/ai_chat.py`, `app/templates/components/bottom_chat.html`, `test_build21.py`
- Modify: `app/crud.py` (5 new functions + `save_ai_message` updated_at bump), `app/ai/prompts.py` (2 new system prompts), `app/main.py` (register the new router), `app/templates/base.html` (include partial + side panel), `app/static/css/styles.css` (chat-bar + panel styles), `app/static/js/main.js` (chat IIFE), `app/routes/projects.py` (add `current_project_id` to context if not already present), `AI_TOOLS_REGISTRY.md` (mark `create_journal_entry` "Status" as fully wired via /ai/chat), `app/version.py`, `VERSION.md`, `CHANGELOG.md`, `USER_GUIDE.md`

#### Verification
- `python3 test_build21.py` — all assertions pass.
- Regression: `python3 test_build20.py` 23/23, `python3 test_build19.py` 15/15.
- Manual smoke: load `/projects` while logged in — bottom chat bar visible. Type "log an entry that says hello", submit in Intake mode → side panel slides in, AI calls tool, journal entry appears in the project's Journal section after refresh.
- Manual smoke: load `/auth/login` (logged out) — no chat bar present.
- Footer + Help modal show `v1.1.0-build21`.

#### Out of scope (deferred)
- **Drag-and-drop file/image upload into chat.** Mentioned in original roadmap row 1540 but defers to Build 22 (AI-Assisted Create Project), which is naturally where file intake belongs.
- **Streaming responses** (SSE/chunked). v1.1 returns the full response after `dispatch()` completes.
- **Two-turn tool follow-up** (feeding tool result back to the model for a natural-language wrap-up). v1.1 just echoes the dispatcher response as a tool-call card.
- **Confirmation cards for destructive tools.** None of the destructive tools are wired in v1.1, so this is unnecessary until Build 22+.
- **Per-conversation title editing.** Auto-titles only in v1.1.

---

## Requirements (Build 1)

```
fastapi
uvicorn[standard]
sqlalchemy
jinja2
python-multipart
python-dotenv
openai
python-dateutil
aiofiles
```

Add for Build 6: `pypdf python-docx openpyxl`

---

## Updated .gitignore Additions

```
uploads/
*.db
*.db-journal
```

---

## Verification (Build 1)

1. `python run.py` → `http://localhost:8000`
2. Create project with only `name` → succeeds, but "Needs Info" badge shows on card with count of missing critical fields
3. Create project with all critical fields filled → "Needs Info" badge absent
4. Project detail: Product Thesis section is the first section in main content, not buried
5. Card view and table view toggle both render correctly
6. Edit MSRP → save → updated value shown (change log row written even if log section not displayed yet)
7. Archive → disappears from Active filter, visible in Archived
8. `/admin/database` → field usage report loads, shows empty project_changes gracefully

---

## Critical Files

- `app/main.py`
- `app/database.py`
- `app/models.py`
- `app/crud.py` — contains: `get_project_health`, `calculate_delay`, `recalculate_stage_and_delay`, `write_change`, `create_project`, `update_project`, phase/file/change CRUD
- `app/routes/projects.py`
- `app/routes/admin.py`
- `app/templates/projects_list.html`
- `app/templates/project_detail.html`
- `app/templates/admin_db.html`
- `app/static/css/styles.css`
- `app/static/js/main.js`
- `ARCHITECTURE.md`
