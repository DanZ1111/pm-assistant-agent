# PM Product Tracker — Version

**Current Version:** v1.1.0-build21
**Current Build:** Build 21 — Bottom AI Chat + Side Panel + Conversation History
**Status:** v1.1.0 in progress (build-by-build per roadmap)
**Last Updated:** 2026-05-29

## What's new in v1.1.0-build21

- **Bottom AI chat bar** on every authenticated page (hidden when logged out). ChatGPT-style: a single-line textarea that auto-grows up to 6 lines, an Intake/Ask mode toggle, and (on project detail pages) a Project/Global scope toggle. `Enter` submits; `Shift+Enter` newline.
- **Right-side panel** slides in when you submit. Shows the conversation thread with user bubbles (right-aligned blue) and assistant bubbles (left-aligned gray). Tool calls render as small colored cards (green when successful, yellow for "not wired yet," red for errors).
- **Conversation persistence** — every conversation is stored in `ai_conversations` (table existed since Build 13). The panel header has a history dropdown to switch between past conversations, plus an archive button.
- **One real tool wired**: `create_journal_entry`. Switch the chat to Intake mode on a project detail page and say "log a journal entry: tested the new gasket at 80°C, holds up well" — AI calls the tool and a new entry appears in the project's Journal section. The other 15 tools registered in Build 20 are still stubbed and surface as "not yet wired" cards.
- **Permission guard fires before any OpenAI call.** If a viewer asks about factory / costs / journal / business plan / variant cost / packaging cost / quotation, the request is short-circuited and no model call happens.
- **No new database schema.** Uses pre-existing `ai_conversations` + `ai_messages` from Build 13.

## What's new in v1.1.0-build20

- **New module `app/ai/tools.py`** — OpenAI function-calling schemas for all 16 AI-callable operations on the system (13 existing HTTP-route operations from Builds 14-18 plus 3 new: `update_project_field`, `link_idea_to_project`, `create_idea`).
- **Dispatcher with security-first checks** — `dispatch(tool_name, args, db, user)` runs role check, project ownership, journal access, and field allowlist BEFORE looking up the handler. This means unwired tools still report `forbidden` to unauthorized users; they only return `not_wired_until_build_21` once permission has passed. Build 21 inherits a tool surface that has never silently bypassed auth.
- **Only `create_journal_entry` is fully wired in v1.1** — the rest have schemas + permission rules + stub responses. Bottom-chat invocation lands in Build 21.
- **`update_project_field` allowlist is conservative**: excludes `current_stage` (derived from phases per CLAUDE.md §5), `status` (will get a dedicated change tool with confirmation if needed), and the existing sensitive set (factory, engineer, costs).
- **No user-facing UI changes** — this build is infrastructure for Build 21.

## What's new in v1.1.0-build19

- **My Projects** tab in the navbar (admin + PM only; hidden from viewer). Wide row-per-project layout. Admin sees all projects; PM sees only projects where they're listed as the PM (case-insensitive username match).
- **Attention banner is now delay-only.** "Needs-Info" no longer appears in the top-of-page banner — it still surfaces as the per-card badge and as a filter tab, so nothing is lost; the banner is just less noisy.
- **Last-opened project memory** on the Projects nav link. Single-click → returns you to the project detail page you last viewed (stored in `localStorage` as `pm_last_project_id`). Double-click → clears the memory and goes to the full `/projects` list. No server-side persistence; pure client-side.

## What's new in v1.1.0-build18

- **Rendering History** section on every project detail page — chronological (newest first) list of every file uploaded with category `Rendering`. Click a thumbnail to open full-size in a new tab.
- **Prototype Photos** section — same pattern, separate section, for files uploaded with the new `Prototype Photo` category.
- **Per-file comments** — every rendering / prototype-photo can carry an inline-editable comment ("what does this show? what pivot? who liked it?"). PM and admin can edit; viewers see read-only. The comment uses the existing `project_files.source_note` column (no schema change). Each edit writes a `change_log` row.
- **Latest rendering thumbnail on the project card** — when a project has at least one rendering uploaded, the most recent one shows as a small thumbnail in the top-right corner of the card on `/projects`.
- **Admin-only delete** stays consistent with the existing files-delete pattern.

## What's new in v1.1.0-build17

- **Plan / Reality split** on the timeline table — each phase row now shows Planned Start / Planned End side-by-side with Actual Start / Actual End. Plan and Reality have separate visual columns.
- **Plan-date changes require a reason** — any change to `planned_start_date` or `planned_end_date` writes a row to `phase_plan_changes` capturing the old date, new date, who changed it, and why. The reason field is in the phase edit modal.
- **`*` asterisk** appears next to any planned date that's been adjusted. Hovering shows the adjustment count.
- **Plan-change history accordion** — clicking the "N plan changes" link under a phase reveals the full edit trail (newest first) with old → new dates, who, when, and the reason.
- **Finish Phase button** (green checkmark) on every active phase — one click marks the phase done (sets `actual_end_date=today`, `status=done`) AND advances the next phase to in_progress (sets its `actual_start_date=today`).
- The current in-progress phase is outlined in blue on the timeline.
- `current_stage` and `calculate_delay` recalc automatically after Finish Phase + phase edits.

## What's new in v1.1.0-build16

- **Variants section** on every project detail page — track multiple SKUs (sizes, colors, materials, budget vs premium) with per-SKU target/actual cost and target MSRP.
- **One variant per project can be flagged as Primary** (★). Setting a new primary automatically unsets the previous one.
- **Packaging & Accessories section** — record packaging components and accessories that ship with the product. Each component can apply to all variants (project-wide) or only one specific variant.
- **Quotation Files section** — surfaces files uploaded with category `Quotation` separately from the general Files area. Viewers can see filenames but cannot download (server-side guard).
- **Profit Model placeholder** — shows the inputs a future Profit Model will use, the intended formula, and a naive per-unit margin preview if the data is present. Full model arrives in v1.2; see `PROFIT_MODEL_INTENT.md` for the design.
- **AI Permission Guard** extended — viewers cannot use AI bottom-chat (Build 21) to surface variant costs, packaging costs, or quotation content.
- **Permissions** — all roles can view variants/components (cost columns hidden from viewers); PM+ can create/edit on their own projects; admin only deletes variants and components.

## What's new in v1.1.0-build15

- **Upload a business plan to draft your Product Thesis.** Optional file input on Create Project; "Extract from Business Plan" button on the project detail page.
- **PDF, Word (DOCX), DOC, and image** are all supported. DOC requires LibreOffice on the server (otherwise a friendly error is shown).
- **AI proposes; you confirm.** Preview screen shows the proposed thesis (editable) + detected inspirations with create/link/skip toggles. Nothing is written to the DB until you click Confirm.
- **Refreshing the preview never re-runs AI** — the extraction is persisted on the upload POST and the preview is a pure GET render of the saved result.
- **Detected inspirations get fuzzy-matched against your Good Ideas board** — matches above 65% suggest linking instead of duplicating.
- **Inline thesis edit on the project detail page** for admin/PM — no need to open the full edit form for a quick tweak.
- **Thesis section is now scrollable** (max-height 220px) so long theses don't dominate the page.
- **AI Permission Guard updated** so viewer bottom-chat (Build 21) cannot surface business-plan / margin / pricing content.

## What's in v1.0.0

- Everything from v0.9.0 (see below)
- **Good Ideas board** at `/ideas` — collect raw inspirations (materials, structures, features, aesthetics, manufacturing) categorized into columns
- Anyone can submit ideas; PMs and admin can edit; admin can delete
- **Project ↔ Idea linkage** — projects can record which ideas they derive from (many-to-many)
- "Inspired By" section on project detail page with link/unlink modal
- **AI dual-mode intake** — AI now classifies pasted text/files as either a Project or an Idea and routes to the appropriate confirmation form
- AI defaults to "idea" on ambiguous input (low-friction capture)
- User can toggle classification if AI got it wrong

## What's in v0.9.0

- Everything from v0.8.0 (see below)
- **Calendar view** at `/calendar` — month-by-month roster of planned vs. actually-launched projects
- "Actual launch" derived from the Launch phase's `actual_end_date` (no schema change)
- Year navigation, click-to-select month
- Calendar nav link visible to all authenticated users (no sensitive fields shown)
- Verified: Database + Users nav links are admin-only (regression-locked in test_build8.py)

## What's in v0.8.0

- Full project lifecycle tracking (concept → mass production)
- Timeline with delay warnings
- File uploads + rendering gallery with lightbox
- Change log with AI attribution
- AI text intake (paste notes → extract → confirm → create)
- AI file intake (PDF + image → extract → confirm → create + attach)
- AI update existing project (fuzzy match → propose edits → confirm)
- Help/Ask AI modal (role-aware answers grounded in USER_GUIDE.md)
- Multi-role auth (admin / pm / viewer) with invite-PIN registration
- Field-level permissions (factory & engineer hidden from viewers)
- AI Permission Guard (AI cannot reveal sensitive fields or system internals)
- Railway-ready: env-driven DB config, PostgreSQL support, one-time admin bootstrap from env vars, `/healthz` endpoint

## Version Map

| Version | Build | Description |
|---|---|---|
| v0.1.0 | Build 1 | Project CRUD Skeleton |
| v0.1.5 | Build 1.5 | Database Inspector |
| v0.2.0 | Build 2 | Timeline + Delay |
| v0.3.0 | Build 3 | File Uploads + Gallery |
| v0.4.0 | Build 4 | Change Log |
| v0.5.0 | Build 5 | AI Text Intake |
| v0.6.0 | Build 6 | AI File/Image Intake |
| v0.7.0 | Build 7 | AI Update Existing Project + Help AI Assistant |
| v0.8.0 | Build 8 + 9 | Multi-Role Auth + Railway Deploy |
| v0.9.0 | Build 10 | Calendar + Admin Nav Hardening |
| v1.0.0 | Build 11 | Good Ideas + Project Linkage + AI Dual-Mode |
