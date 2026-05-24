# PM Product Tracker — Version

**Current Version:** v1.0.0
**Current Build:** Build 11 — Good Ideas + AI Dual-Mode Intake
**Status:** Feature-complete
**Last Updated:** 2026-05-24

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
