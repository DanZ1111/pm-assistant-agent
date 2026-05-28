# PM Product Tracker — Changelog

## v1.1.0-build15 — Business Plan Upload + Thesis Extraction (Build 15)
_2026-05-27_

**Goal:** lower the burden of getting a Product Thesis onto a project. PMs upload a business plan once and AI proposes a thesis + any inspirations to capture as Ideas — preview, edit, then confirm before any DB write.

**One-time AI, then pure GET preview** — the AI extraction runs once on POST. The result is persisted as an `ai_messages` row (`message="thesis_extraction"`, payload in `metadata_json`). The preview page is a pure GET render — refreshing it does NOT re-trigger AI.

**File formats supported:** PDF, DOCX, DOC (via LibreOffice if installed; friendly error otherwise), and image (PNG/JPG/WEBP/GIF via vision). New dependency: `python-docx`.

**Two entry points:**
- Create Project form: optional Business Plan file input. On submit → project created → file saved as `file_category="business_plan"` → AI runs once → redirect to preview.
- Project Detail Thesis section: "Extract from Business Plan" button (or "Re-extract" if a plan is already attached) reveals an inline upload form that follows the same path.

**Preview screen** (`thesis_preview.html`): two-column. Proposed thesis textarea (editable) + detected inspirations checklist. Each inspiration is fuzzy-matched against existing open Ideas; matches above 65% surface a "Link existing IDEA-005 (87% match)" suggestion with radio toggle Link/Create new/Skip. Cancel returns to project; Confirm writes everything in one transaction.

**Confirm transaction:** `update_project(project_thesis=...)` writes automatic per-field change-log row; each inspiration with action=create/link creates/links an Idea; `write_change(event_note, changed_by="ai", source_type="ai_chat")` marks AI source; AIMessage row updated with `confirmed_at` + `confirmed_thesis` + `confirmed_inspirations` for full audit.

**Inline thesis edit on detail page:** click Edit on the Thesis section → textarea + Save without leaving the page. Distinct route from the full edit form so it only needs the thesis field.

**Detail page Thesis section:** now scrollable (max-height 220px) so long theses don't dominate the page. Extract/Re-extract button is admin/PM only.

**AI Permission Guard:** `_VIEWER_FORBIDDEN` extended with `business plan`, `thesis extraction`, `margin target`, `pricing strategy`.

**AI Tools Registry:** `extract_thesis_from_business_plan` added (HTTP route implemented; bottom-chat tool wiring lands in Build 20/21).

## v1.0.0 — Good Ideas + Project Linkage + AI Dual-Mode (Build 11)
_2026-05-24_

**Good Ideas board** (`/ideas`)
- New `ideas` table with: name, description, idea_type, source, source_detail, contributor, status
- Six type columns: material · structure · feature · aesthetic · manufacturing · other
- Seven sources: factory · tradeshow · internet · customer · team · competitor · other
- Serial number auto-derived: `IDEA-001`, `IDEA-002`, …
- Source filter on board
- Card visual style with source-tinted badges
- Permissions: all roles create; PM+admin edit; admin only deletes

**Project ↔ Idea linkage** (many-to-many via new `project_ideas` table)
- "Inspired By" section on project detail page
- Modal picker to link an existing idea, with optional usage note
- Unlink button per linked idea
- Idea status auto-flips: `open` → `in_use` on first link, back to `open` on last unlink

**AI Dual-Mode Intake**
- New `extract_intake()` in `app/ai/parser.py` classifies pasted text as project or idea
- Ambiguous input defaults to "idea" (low-friction capture)
- Confirmation page conditionally renders the project form OR the idea form
- User can toggle classification if AI got it wrong (link in banner)
- New route `POST /ai/intake/confirm-idea` creates an idea from confirmed extraction
- File-upload intake (PDF/image) still goes to the project path (unchanged)

## v0.9.0 — Calendar + Admin Nav Hardening (Build 10)
_2026-05-23_

- New `/calendar` route showing planned vs. actually-launched projects by month
- Year navigation; click a month in the left list to view its project roster on the right
- "Planned" = projects with `planned_launch_date` in the selected month
- "Actually launched" = projects whose Launch phase is marked done with `actual_end_date` in the selected month (no schema change — derived from existing phase data)
- Each project row shows SKU, name, brand, status, planned date, actual date, and variance ("5 days late" / "on time")
- Calendar visible to all authenticated users (admin/pm/viewer) — only non-sensitive fields shown
- Verified Database and Users nav links are admin-only (lock-in test added to test_build8.py)

## v0.8.0 — Multi-Role Auth + Railway Deploy (Build 8 + 9)
_2026-05-22_

**Auth & Permissions (Build 8):**
- New `users`, `invite_pins`, `user_sessions` tables
- Login / logout / register routes with HTTP-only session cookies
- Three roles: admin, pm, viewer
- Admin can generate role-prefixed invite PINs (`PM-XXXXXX` / `VW-XXXXXX`)
- Field-level permissions: factory + engineer hidden from viewers (sidebar + change log)
- AI Permission Guard: viewers cannot extract sensitive fields via AI, no role can extract system internals (.env, API keys, model name)
- `/admin/users` page for user management
- `create_admin.py` bootstrap script with hidden password prompt
- Help/Ask AI now requires auth

**Railway Deploy (Build 9):**
- `app/database.py` now reads `DATABASE_URL` env var (PostgreSQL on Railway, SQLite locally)
- Auto-normalizes legacy `postgres://` URLs to `postgresql://`
- `run.py` honors `$PORT` and disables reload when `RAILWAY_ENVIRONMENT` is set
- New `/healthz` endpoint for Railway healthchecks
- One-time admin bootstrap via `INITIAL_ADMIN_USERNAME` + `INITIAL_ADMIN_PASSWORD` env vars (idempotent, never overwrites existing admin)
- `railway.toml`, `runtime.txt`, `.env.example` added
- `psycopg2-binary` added to requirements.txt

## v0.6.0 — AI File/Image Intake (Build 6)
_2026-05-21_

- Added file upload option to AI Intake page (PDF + image)
- PDF extraction: text extracted via pypdf, fields parsed by GPT-5.4
- Image extraction: GPT-5.4 Vision analyzes image, generates ai_summary + extracts fields
- Uploaded file automatically attached to project on confirm
- `project_files.ai_summary` populated from AI vision analysis
- OR divider between text paste and file upload on intake form

## v0.5.0 — AI Text Intake (Build 5)
_2026-05-21_

- New AI Intake page at `/ai/intake`
- Paste messy notes → GPT-5.4 extracts structured project fields
- Health check preview: shows which critical fields are still missing before confirm
- Confirmation step required — AI never silently creates or overwrites
- Change log records `changed_by=ai` on AI-created projects
- `ai_messages` table stores full conversation history per project

## v0.4.0 — Change Log (Build 4)
_2026-05-21_

- Change log section (Section 4) on project detail page
- All field edits recorded with old → new values
- Phase updates, file uploads, and archive events recorded
- Change log header shows entry count
- `changed_by` column distinguishes user vs. AI edits

## v0.3.0 — File Uploads + Rendering Gallery (Build 3)
_2026-05-20_

- Drag-drop file upload zone on project detail page
- Image gallery with category filter tabs (All / Rendering / Reference / Quotation…)
- Full-resolution lightbox with left/right navigation and keyboard shortcuts
- Non-image files shown in document list with download link
- File category selector (rendering, reference, quotation, factory feedback, packaging, other)
- Delete file from gallery with confirmation

## v0.2.0 — Timeline + Delay (Build 2)
_2026-05-20_

- Project phases auto-created at project creation (single or double prototype template)
- Phase edit modal (8 fields: name, type, status, planned/actual dates, owner, notes)
- Add/delete phases from project detail
- Delay calculation: auto-detected from overdue phases, never stored as a status
- Red delay banner on project detail with days late + estimated launch date
- Delay badge on project cards
- "Phases Due This Week" in Needs Attention section

## v0.1.5 — Database Inspector (Build 1.5)
_2026-05-20_

- `/admin/database` read-only inspector page
- Table overview: row counts for all 5 tables
- Field usage report: % of projects with each field filled
- Project health summary: which active projects are missing critical fields
- Recent changes feed (last 50 entries)
- `ARCHITECTURE.md` added as living architecture document

## v0.1.0 — Project CRUD Skeleton (Build 1)
_2026-05-20_

- Clean project structure (FastAPI + SQLAlchemy + Jinja2 + Bootstrap 5)
- Create, view, edit, archive projects
- All 5 database tables: projects, project_phases, project_files, project_changes, ai_messages
- Project detail: Product Thesis as Section 1 (first-class, not buried)
- Projects list: card grid + table toggle view
- Filters: All / Active / Delayed / Needs Info / Completed / Archived
- Needs Info badge (count of missing critical fields)
- "Needs Attention" section at top of projects list
- `get_project_health()` service — calculated, never stored
- `CLAUDE.md` and `TESTING_RULES.md` governance files
