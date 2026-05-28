# PM Product Tracker — Changelog

## v1.1.0-build20 — AI Tools Architecture + Permission Guard (Build 20)
_2026-05-28_

**Goal:** Build 21's Bottom Chat will need to invoke our v1.1 features via OpenAI function-calling. Today the AI has no schema describing those operations, no dispatcher, no permission discipline applied at the tool boundary. Build 20 builds that foundation: schemas for everything, ONE real handler to prove the pattern, and a security-first dispatcher.

**New module `app/ai/tools.py`** —
- `TOOL_SCHEMAS` — 16 OpenAI function-calling schemas (`{"type": "function", "function": {"name", "description", "parameters"}}`) covering every AI-callable operation: 13 mapped to existing HTTP routes from Builds 14-18, plus 3 new (`update_project_field`, `link_idea_to_project`, `create_idea`).
- `TOOL_PERMISSIONS` — per-tool role/project/journal/allowlist rules consulted by the dispatcher.
- `UPDATE_PROJECT_FIELD_ALLOWED` — conservative set: `name, brand, sku, product_type, project_owner, product_manager, planned_launch_date, project_thesis, notes`. **Deliberately excludes `current_stage`** (derived per CLAUDE.md §5) and **`status`** (operationally consequential — will get a dedicated `change_project_status` tool with mandatory confirmation in Build 21+ if needed).
- `dispatch(tool_name, args, db, user)` — 6-step pipeline: tool exists → role check → project ownership → journal access → field allowlist → handler (or `not_wired_until_build_21` stub). **Permission discipline applies even when the handler is a stub.**

**Only `create_journal_entry` is fully wired in v1.1.** Reuses `crud.create_journal_entry` (Build 14) end-to-end; on success returns `{"ok": True, "entry_id": <int>}`. The other 15 schemas have stubs that return `{"ok": False, "error": "not_wired_until_build_21"}` after permission has passed. This means Build 21 only needs to add handlers — the schema layer, permission layer, and dispatcher contract are all done.

**AI Permission Guard verified.** `_VIEWER_FORBIDDEN` in `app/dependencies.py:92` already covered every v1.1 sensitive source. Build 20 adds explicit per-source test coverage (business plan, journal entries, variant cost, packaging cost, quotation) so the guard can't silently rot.

**AI_TOOLS_REGISTRY.md updated** — "Current Tools" now lists all 16 with `route + schema implemented (Build NN/20); handler wiring lands in Build 21` status strings. New "How the dispatcher works" subsection documents the 6-step pipeline. The "Planned" table now only has post-v1.1 entries (`search_projects`, `get_project_context`, `change_project_status`).

**No schema change. No user-facing UI changes.** Infrastructure for Build 21.

**Files modified:** `AI_TOOLS_REGISTRY.md`, `app/version.py`, `VERSION.md`

**Files created:** `app/ai/tools.py`, `test_build20.py`

## v1.1.0-build19 — My Projects + Attention banner cleanup + last-project memory (Build 19)
_2026-05-28_

**Goal:** small UX polish pass — give PMs a focused view, cut noise from the attention banner, and stop sending them back to the full list every time they click the Projects nav.

**My Projects** — new `/my-projects` route (admin + PM only; viewer is 303-redirected to `/projects`). Wide table layout: name, current stage, planned launch (with inline delay badge), status, last updated. Admin sees all projects; PM sees only projects where `product_manager` matches their username (case-insensitive). Empty-state copy differs by role.

**Attention banner is now delay-only.** `needs_attention = [e for e in active_enriched if e["delay"]]` in `app/routes/projects.py` (was `e["delay"] or e["health"]["needs_info"]`). The Needs-Info per-card badge, the Needs-Info filter tab, the `card-needs-info` row class, the table-view badge, and the route filter logic all remain — only the banner block changed.

**Last-opened project memory** — `app/templates/project_detail.html` writes `localStorage.pm_last_project_id` on every page load. The Projects navbar link gets a 250ms click handler in `app/templates/base.html`: single-click → `/projects/{last_id}` if set, else `/projects`; double-click → clear and go to `/projects`. The click handler uses a setTimeout that's cancelled by `dblclick` so the two events don't compound.

**Navbar** — new "My Projects" link with `bi-person-circle` icon, gated `{% if current_user.role in ('admin', 'pm') %}`. Sits between Good Ideas and AI Intake.

**Permissions** —
- Viewer: `/my-projects` redirects to `/projects`; navbar link hidden.
- PM: sees own projects only.
- Admin: sees all projects in the same view.

**No schema migration.** Pure UI + a new service function (`crud.get_projects_for_user`).

**Files modified:**
- `app/crud.py` — new `get_projects_for_user(db, user)`
- `app/routes/projects.py` — new `/my-projects` route; `needs_attention` tightened to delay-only
- `app/templates/base.html` — My Projects nav link + Projects-nav click/dblclick handler
- `app/templates/projects_list.html` — Needs-Info badge removed from attention banner block
- `app/templates/project_detail.html` — `localStorage.pm_last_project_id` writer in extra_js
- `app/version.py`, `VERSION.md`, `USER_GUIDE.md`

**Files created:**
- `app/templates/my_projects.html`
- `test_build19.py`

## v1.1.0-build18 — Rendering History + Prototype Photos (Build 18)
_2026-05-28_

**Goal:** product development is visual — renderings get iterated, prototypes get photographed, and PMs need a chronological record of "what did this thing look like in week 3?" with a quick note about why each version mattered. Build 18 surfaces this history without forcing a new schema.

**Two new sections** on every project detail page (inserted after the existing Files & Renderings section, before the Change Log):
- **Rendering History** — every file uploaded with `file_category="rendering"`, newest first. Image previews render inline (96×96 thumb, clickable to full-size). Non-image files (PDF mocks etc.) render as a generic doc icon.
- **Prototype Photos** — same pattern, dedicated section for `file_category="prototype_photo"` (new category added to the upload dropdown).

**Per-file comments** — each entry shows the current `source_note` plus an inline-edit link (PM + admin only). The comment uses the existing `project_files.source_note` column — no new schema. Saving writes a `change_log` row (`change_type=event_note`).

**New POST route:** `/projects/{project_id}/files/{file_id}/comment` — guarded by `can_edit_project`, redirects back to the originating anchor.

**Latest rendering thumbnail on the project card** — `/projects` card view shows the most recent rendering (image only) as a 56×56 thumbnail in the top-right corner. `get_projects_enriched` attaches `latest_rendering` per project; card hides cleanly when no rendering exists.

**Reusable partial** — `app/templates/components/media_history_section.html` is parameterized by `media_kind` / `media_title` / `media_icon` / `media_files` / `media_anchor` so both new sections share one template.

**Permissions** —
- Viewer: see filenames, thumbnails, comments. Cannot edit comments or delete (existing rule).
- PM: edit comments on own projects; can delete files PM uploaded? — delete stays admin-only per existing pattern.
- Admin: full control.

**No schema migration.** All data lives in pre-existing columns of `project_files`.

**Files modified:**
- `app/crud.py` — new `get_files_by_category`, `get_latest_rendering`, `update_file_comment`; `get_projects_enriched` now attaches `latest_rendering` per project
- `app/routes/files.py` — new POST `/projects/{pid}/files/{fid}/comment` route
- `app/routes/projects.py` — `project_detail()` passes `renderings` + `prototype_photos` to template
- `app/templates/project_detail.html` — two new `{% include %}` blocks + `toggleMediaCommentEdit()` JS + `prototype_photo` added to upload category select
- `app/templates/projects_list.html` — `card-rendering-thumb` block
- `app/static/css/styles.css` — Build 18 media-history + card-thumb styles
- `app/version.py`, `VERSION.md`, `USER_GUIDE.md`, `AI_TOOLS_REGISTRY.md`

**Files created:**
- `app/templates/components/media_history_section.html`
- `test_build18.py`
- `AGENTS.md`, `HANDOFF.md` (Claude/Codex handoff protocol — applies project-wide, not specific to this build)

## v1.1.0-build17 — Timeline 2.0 (Plan / Reality split + Finish Phase) (Build 17)
_2026-05-27_

**Goal:** projects evolve — original plans slip, and we need to capture WHY without losing the original commitment. Build 17 separates Plan from Reality on the timeline, makes plan-date shifts auditable with a required reason, and adds a one-click Finish Phase that correctly advances the next phase.

**Plan / Reality column split** — each phase row now has two visually distinct column groups: Plan (Planned Start, Planned End) and Reality (Actual Start, Actual End). Plan group is blue-tinted; Reality is neutral.

**Plan-date changes are tracked** — any change to `planned_start_date` or `planned_end_date` via the phase edit modal writes a `phase_plan_changes` row (table existed since Build 13) capturing `old_date`, `new_date`, `changed_by_user_id`, `changed_at`, and `reason`. Reason is required by the route — saving plan-date changes without one redirects with `?timeline_error=reason_required` and a friendly banner.

**Visual indicators** —
- `*` appears next to any planned date that's been adjusted (one star per field with history, with adjustment count in tooltip).
- The current in-progress phase row is outlined in blue.
- A "N plan changes" link under each phase reveals an inline history accordion showing every old → new date shift, who changed it, when, and the reason.

**Finish Phase button** (green checkmark on every active phase row) — one click does the right thing:
- Marks the current phase done: sets `actual_end_date=today`, `status=done`, and `actual_start_date` if it was still empty (best guess: planned_start or today).
- Advances the next phase (next `phase_order` that's not done/skipped): sets `actual_start_date=today` (if not already set), `status=in_progress`.
- Writes one combined change-log event_note recording both transitions.
- Triggers `recalculate_stage_and_delay` so `current_stage` + `estimated_launch_date` stay correct.

**Permissions** — Finish Phase requires `can_edit_project` (admin + PM on own project). Phase delete now also gated to admin only (consistent with variants/components from Build 16). The reason field appears in the modal only for users who can edit.

**Modal updates** — phase edit modal explicitly splits Plan (with the reason field next to the planned dates) from Reality (with a tip to use the Finish Phase button instead). Reason field is cleared every time the modal opens to avoid stale text.

**No schema migration** — `phase_plan_changes` was created in Build 13.

**Files modified:**
- `app/crud.py` — `update_phase` extended (reason + changed_by_user_id params, writes `PhasePlanChange` rows on plan-date changes); new `finish_phase`, `get_plan_changes_for_phase`, `get_plan_changes_by_project`
- `app/routes/projects.py` — phase_edit accepts `plan_change_reason` Form param + redirects with `timeline_error=reason_required` if a plan date changed without one; new `phase_finish` route
- `app/templates/project_detail.html` — full timeline section rebuild + reason field in modal + plan-history accordion JS
- `app/static/css/styles.css` — Plan/Reality column tinting, asterisk marker, history accordion, Finish Phase button
- `app/version.py`, `VERSION.md`, `AI_TOOLS_REGISTRY.md`

**Files created:** `test_build17.py`

## v1.1.0-build16 — Variants + Packaging + Quotation + Profit Model placeholder (Build 16)
_2026-05-27_

**Goal:** real product development isn't one SKU. Build 16 adds the data scaffolding for multi-SKU projects: variants with per-SKU cost/MSRP, packaging/accessory components scoped per-variant or project-wide, a dedicated Quotation Files surface, and a Profit Model placeholder that documents the future v1.2 formula.

**Variants** — new section on project detail (after Inspired By, before Timeline). Card grid with CRUD via inline form + per-card edit form. Fields: variant_name, sku, status (idea/evaluating/selected/rejected/launched), is_primary (★), target_factory_cost, actual_factory_cost, target_msrp, material/size/color/packaging summaries, notes. `is_primary` is enforced at the service layer — setting one to primary unsets the others (no DB unique constraint, safer for migrations).

**Packaging & Accessories** — table-style section below Variants. Each component has type (packaging/accessory), name, scope (project-wide or per-variant), target_cost, actual_cost, notes. Per-variant components only apply to their variant; project-wide components apply to all.

**Quotation Files** — filtered view of `project_files` where `file_category="quotation"`. Listed with friendly UI separately from the general Files area. Server-side guard on download: `GET /projects/{id}/files/{fid}/download` redirects viewers away from quotation files (other categories pass through to the existing static `/uploads/` path).

**Profit Model placeholder** — surfaces the intended v1.2 formula in a callout, shows the primary variant's costs as a preview, and computes a naive per-unit margin if MSRP + factory_cost are both set. Costs hidden from viewers. Full model design in `PROFIT_MODEL_INTENT.md`.

**Permissions** —
- View variants/components (no costs): all roles
- View cost columns: admin + PM only (new `can_view_costs()` helper)
- Create/edit variant or component: admin + PM on own project
- Delete variant or component: admin only
- Download quotation file: admin + PM only (server-side route guard)

**AI Permission Guard** — `_VIEWER_FORBIDDEN` extended with `variant cost`, `actual cost`, `quotation`, `packaging cost`, `component cost`.

**Files created:** `app/routes/variants.py`, `app/templates/components/variants_section.html`, `app/templates/components/packaging_section.html`, `app/templates/components/quotation_section.html`, `app/templates/components/profit_model_section.html`, `PROFIT_MODEL_INTENT.md`, `test_build16.py`
**Files modified:** `app/crud.py` (10 new helpers), `app/dependencies.py` (`can_view_costs`, `_VIEWER_FORBIDDEN`), `app/main.py` (mount router), `app/routes/projects.py` (detail context), `app/routes/files.py` (quotation download guard), `app/templates/project_detail.html` (4 new section includes), `app/static/css/styles.css`, `app/version.py`, `VERSION.md`, `AI_TOOLS_REGISTRY.md`

**No schema migration** — tables (`project_variants`, `project_variant_components`) already created in Build 13.

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
