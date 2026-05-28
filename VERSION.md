# PM Product Tracker — Version

**Current Version:** v1.1.0-build16
**Current Build:** Build 16 — Variants + Packaging + Quotation + Profit Model placeholder
**Status:** v1.1.0 in progress (build-by-build per roadmap)
**Last Updated:** 2026-05-27

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
