# PM Product Tracker — Version

**Current Version:** v1.3.0
**Current Build:** v1.3.0 — Project Detail Command Center (v1.3 Builds 01-09 + Planning Sandbox design lock)
**Status:** v1.1.0 released; v1.2.0 released; v1.2.1 released; v1.3.0 released
**Last Updated:** 2026-06-06

## What's new in v1.3.0

The v1.3.0 release turns Project Detail from a database-style record page into a daily PM command center. Ten plan-first builds shipped: 9 visible features + 1 design-lock for v1.4 Planning Sandbox + 1 cross-cutting fix for the Railway project-delete bug. The Project Detail page now splits cleanly into an **Overview** workspace (product concept, renderings, variants, files) and a **Timeline** workspace (Command Center, Detailed Table, History) — each tuned for the work PMs actually do daily.

- **Workspace Shell (Build 01)** — Project Detail now has explicit Overview / Timeline tabs under the project header. The old promoted Commercial Snapshot is gone; metadata (created / updated / price estimates) lives in a quieter Project Metadata section near the Change Log. `#timeline` URL anchor opens Timeline directly. No schema change.

- **Project Pulse v1 — rules-based (Build 02)** — Overview opens with a two-column Pulse summarizing current stage / status / PM / launch target / next suggested action. The next-action rules cascade is deterministic (delay → thesis missing → other missing critical field → no inspirations → no urgent). Build 07B inserts a higher-priority blocker branch on top. No AI for now.

- **Product Concept (Build 03)** — old "Product Thesis" section reframed as Product Concept with a primary `#product-concept` anchor and hidden `#thesis` compatibility anchor. Inspired By is no longer a peer section; linked Ideas now render as compact internal chips inside Product Concept.

- **Renderings Overview (Build 04)** — standalone Renderings section directly after Product Concept on Overview, showing the latest uploaded rendering/prototype visual with bounded preview, metadata, history links, document fallback, and a Designer Portal placeholder.

- **Variant Command Cards (Build 05 + 05B)** — variants render as expandable cards inside the existing `#variants` section. Collapsed summary shows variant name + Primary badge + SKU + status badge + (costs for can_view_costs) + component count in `"X shared + Y for this variant"` format. Expanded body uses a 2×2 CSS grid: Specs / Packaging / Pricing / Profit, with Notes & Actions spanning. Build 05B added 6 structured spec columns (`sales_format`, `packaging_cost`, `blade_summary`, `handle_summary`, `mechanism_summary`, `dimensions_summary`) via migration 005. Sales Format renders as a chip in the collapsed summary; expanded Specs cell shows 4 labeled sub-sections.

- **Timeline Command Center Shell (Build 06)** — display-only shell that opens the Timeline tab to the action surface, not the database table. Phase strip with Done / Current / Next / Later states (horizontal-scroll on mobile). 3-tile grid: Current Phase (name + health badge + started date), Next Action (current phase forward + owner), Deadline (due date + days-left/overdue badge + pressure dots). Existing Detailed Table wrapped in collapsed `<details>` summary; phase `<tr>` rows gain `id="phase-row-{phase.id}"` for anchor navigation. Health bands deterministic per Lock 3 (`on_track` / `at_risk` ≤3 days_late / `delayed` >3 / `not_scheduled`).

- **Timeline Command Actions Backend (Build 07A)** — three honest action wires from Command Center: Finish Current Phase (with stale-form race protection — server re-derives current_phase and rejects if the request's phase_id doesn't match), Adjust Due Date (server-side reason required, mirrors Detailed Table reason-required behavior), Add Update (gated on `can_view_journal` AND `can_edit_project`; viewer cannot POST even if they craft a request). All three redirect to `#timeline-command-center` with `?cc_action=...&cc_result=...` query params; the section renders a dismissible result banner. Buttons toggle inline forms inside a shared `<div id="cc-action-form">` mount; Cancel hides the mount. Add Update form gets `data-cc-disable-on-submit` JS for UX double-submit defense.

- **Project Blockers (Build 07B)** — first-class lifecycle model. New `project_blockers` table (migration 006, 11 columns): id, project_id, optional phase_id (with same-project validation; Lock 3 ensures phase-strip red dots fire ONLY for phase-linked blockers, never randomly), title, optional description, severity (low/medium/high default medium), status (active/resolved default active), created_at, optional created_by_user_id, optional resolved_at + resolved_by_user_id. Six new crud helpers, three new POST routes (`/command/add-blocker`, `/command/edit-blocker`, `/command/resolve-blocker`). Build 06 placeholder block replaced with honest tile showing newest active blocker + severity chip + opened-meta + Resolve + Edit buttons. When `count_active > 1`, tile shows `+N more active` text badge (Lock 4 — no expanded list; defer to Timeline History). Pulse cascade gains a new FIRST branch: when ≥1 active blocker exists, "Resolve blocker: '{title}'" beats delay/thesis/missing-field/inspiration. Phase strip blocks for phases with ≥1 active phase-linked blocker carry a red `bi-shield-exclamation` dot. Three new AI tools (`create_blocker` / `update_blocker` / `resolve_blocker`) in `CONFIRMATION_TOOLS` (Lock 9 — no exceptions); `delete_blocker` NOT exposed to AI (admin-only UI path, matches `delete_variant`).

- **Timeline Updates / History (Build 08)** — new `#timeline-history` section at the bottom of the Timeline workspace gives PMs a chronological "what happened and why" feed. Pure derivation over `project_changes` + `phase_plan_changes` + `project_journal_entries` — no new schema. Single helper `crud.get_timeline_events(db, project_id, limit=200, viewer=False)` merges the 3 sources and normalizes each row into a TimelineEvent dict with `source_table` + `source_id` (every event traces to exactly one source row). Six filter chips (All / Delays / Decisions / Blockers / Phase Changes / Files+Renderings) match the canonical doc exactly; client-side CSS toggle (no round-trip per click); applies to the full loaded 200-event array. Lock 2: every event has one primary bucket; subtypes (Sample / Rendering / Packaging / Cost) are display-only overlay badges. AI overlay badge (`bi-robot`) when source is AI. Deterministic tiebreaker on `occurred_at` ties via `(source_priority, source_id DESC)`. Viewer permission filtering removes restricted events entirely (cost field_updates, sensitive file_category uploads, journal entries, journal-mirror event_note rows whose summary begins with "Journal entry added:"). Three explicit empty states. Default 50 visible; "Show more (N)" reveals up to 200. Lock 10: anchor links omitted when target permission-hidden or DOM-missing — no broken anchors.

- **Planning Sandbox Design (Build 09 + Amendment 1 + Amendment 2)** — design-only build that ships the canonical engineering design for the v1.4 Planning Sandbox. Amendment 1 rewrote my original form-based-editor design as an engineering response to ChatGPT's PRD (visual workflow canvas + explicit draft/apply separation). Amendment 2 folded Codex's `V14_PLANNING_SANDBOX_IMPLEMENTATION_PLAN.md` additions: active-blocker precondition on Apply (Build 07B integration), 10-step Apply transaction sequence, 6-field Apply confirm modal spec, semantic soft warnings (packaging-before-design, production-before-sample, terminal-not-launch-like), "cross_sandbox_edge" as a new hard error, concrete route URL list, 14-helper service-layer enumeration, mobile guidance with 44×44 px touch targets, 9-build v1.4 sub-build sequence (was 8 — added "Canvas Interaction Hardening" + "Release Hardening" slices), `phase_type` propagated to sandbox_nodes, `updated_project_planned_launch_date` BOOLEAN on apply_events, explicit `draft/applied/archived` lifecycle with partial unique index, AI_TOOLS_REGISTRY.md requirement before v1.4 release. Build 09 ships zero code; v1.4 implements the design across 9 sub-builds with Cytoscape.js + cytoscape-dagre as the locked canvas-rendering library.

- **Project delete FK fix (cross-cutting between Builds 08 and 09)** — Marine projects on Railway returned 500 on delete because `ai_conversations.project_id → projects.id` and `project_creation_tokens.project_id → projects.id` were FKs without matching `Project` ORM cascade relationships. PostgreSQL always enforces FKs; local SQLite hid the bug because the default `PRAGMA foreign_keys` is OFF. Fix: `crud.delete_project` now explicitly deletes `ai_conversations` + `project_creation_tokens` rows and nulls `ai_messages.conversation_id` before the ORM delete cascades the rest. Plus `app/database.py` now turns on `PRAGMA foreign_keys = ON` for every SQLite connection via a connect-event listener so dev mirrors PostgreSQL FK enforcement going forward.

- **Build 10 — Legacy Change Log viewer leak fix (release hardening)** — Build 13's `#changes` (legacy Change Log section, distinct from Build 08's Timeline History) rendered `event_note` audit rows to viewers with summaries like `"Journal entry added: '{first 80 chars of journal text}'"` — leaking journal body content to viewers who cannot view the source journal entry (gated on `can_view_journal`). Build 08 fixed this in its own History feed but deferred the legacy section's fix per Lock 11 scope discipline. Build 10 closes the leak: 3-line patch in `project_detail.html` skips journal-mirror event_notes when `not can_view_journal`, mirroring Build 08's rule.

Migrations 005 (Build 05B — structured variant specs, 6 nullable columns on `project_variants`) and 006 (Build 07B — `project_blockers` table with 11 columns + 2 indexes) are the only schema changes in v1.3.0. Both additive + idempotent. Migration count locks at 6 for v1.3.0; v1.4 sandbox adds 4 more (007–010).

i18n bundle reaches 714/714 EN/zh parity at the v1.3.0 lock; up from 537/537 at v1.1.0 and 651/651 at v1.3 Build 06. Native-speaker Chinese review of strings added in v1.3 Builds 01-09 is deferred to v1.4 — the existing v1.2.1 Chinese summary block in this VERSION.md and USER_GUIDE.md is preserved.

## What's new in v1.2.1

The v1.2.1 release packages 7 unreleased patches that landed on the v1.2.0 line. Frame: a workflow-polish + onboarding-unlock release. PMs onboarding from existing Excel sheets, day-to-day PM ergonomics, and Chinese-keyboard typing all see meaningful improvements.

- **Excel batch intake (Build 30B)** — upload `.xlsx` / `.xlsm` / `.xls` / `.csv` portfolios; AI extracts a `projects` array preserving source sheet + row hint and pricing fidelity (`$32-38`, `under 120 RMB`); per-row review table with Create / Skip / Update Existing actions; one click commits everything atomically through a single Build 30A idempotency token. Unblocks new-department onboarding (Beauty etc.).
- **Project creation safety (Build 30A)** — server-side idempotency tokens prevent the "PM clicked Submit 6 times on a slow form, got 6 duplicate rows" failure mode. Blank `product_manager` defaults to the creator's username so PM-created projects land in their My Projects, not orphaned on admin. `get_projects_for_user` now matches by username OR display_name for legacy rows.
- **PM draft delete (Build 30C)** — PMs can now hard-delete their own projects when **no phase has started** (every phase still `status='not_started'` with no `actual_start_date`). Once any phase advances, the project leaves draft state and PM must use Archive instead. Admin retains unrestricted delete; viewer can delete nothing. Workflow-tied, not clock-tied.
- **Chinese IME chat fix (v2, mature composer controller)** — both assistant composers (bottom dock + side panel) now share a reusable controller with four-layer IME defense including a one-shot post-`compositionend` suppression window (`IME_CONFIRM_ENTER_SUPPRESS_MS = 80`). Chinese-keyboard typing of English fragments like `LC200N` no longer fires premature submits. Locked by 10 JSDOM behavioral cases.
- **PM-facing price strings** — `target_factory_cost_text` / `target_msrp_text` VARCHAR fields preserve real-world planning expressions like `"under 120 RMB"`, `"$70-100"`, `"约 120 RMB 出厂"`. Legacy float columns kept for back-compat and future profit math. AI extraction preserves the source expression verbatim.
- **Project detail layout refactor** — removed the low-value left sidebar; promoted PM / Engineer / Factory / Stage / Launch into a compact header facts grid under the project title; added a full-width Commercial Snapshot section near the top. Denser, cleaner, less wasted space.
- **Railway build fix (nixpacks)** — `nixpacks.toml` pins `providers = ["python"]` so Nixpacks ignores the new `package.json` (which exists only for local JSDOM tests) and stops trying to run `npm install` during deploy.

No database schema change in this release-hardening build itself. Build 30A's `project_creation_tokens` table (migration 004) shipped with that patch and is preserved.

## What's new in v1.2.0

The v1.2.0 release packages Builds 26-28 plus this release-hardening build (29). It turns the AI assistant from an experimental bottom chat into a professional, project-aware workspace where every write is reviewed before it lands.

- **Professional Assistant Workspace** (Build 26) — the assistant opens beside the tracker as a resizable split panel on desktop and a full-screen pane on mobile. Compact dock when collapsed; composer moves into the pane when expanded; Ask / Capture and This Project / Global are segmented controls, not raw dropdowns. Conversation scope is immutable after the first message.
- **Project-aware Idea Capture** (Build 26) — project-scoped chat receives a role-filtered project summary, linked Ideas, and recent permitted journal context. Speak naturally ("we were inspired by a Japanese ceramic mug at the Canton tradeshow") and the assistant proposes an Idea with duplicate detection and a one-step Create-and-Link confirmation.
- **Confirmation Cards for every assistant write** (Build 27) — journal capture, Idea actions, variants, packaging / accessory components, file comments, allowlisted project fields, reasoned phase-plan adjustments, and Finish Phase all wait for explicit Confirm / Cancel. Server-side revalidation on confirm re-checks auth, role, ownership, allowlists, and proposal state. Double-confirmed or cancelled proposals are rejected.
- **Global Search + Read-Only Context** (Build 27) — `search_projects` and `get_project_context` are immediate read-only tools so Global conversations can find and discuss work without auto-targeting writes. Role-filtered results keep viewer responses clear of factory, engineer, cost, and journal details.
- **Assistant Attachments** (Build 28) — PDF, DOCX, PNG, JPG/JPEG, WEBP, and GIF inputs can be attached from the dock or panel composer. Pending bytes live in ignored `app/pending_uploads/` (outside the public `/uploads` mount). PDF + DOCX text is extracted locally; pending images are passed to the assistant as image content. Saving to project files requires an explicit `save_pending_attachment` confirmation card; confirmed saves use the normal audited file service with `changed_by="ai"` and `source_type="ai_chat"`.
- **Sensitive fields gated** — factory, engineer, target cost, MSRP, launch date, and Thesis can be proposed only through the confirmed flow. Derived `current_stage` and operational `status` remain non-writable through chat (CLAUDE.md non-negotiables #4-#5).
- **Viewer read-only alignment** — viewers can browse Good Ideas and the assistant workspace, but cannot create, edit, link, or upload anything. Permission checks fire before the OpenAI call.
- **No schema migration in Build 29.** Pending proposals live in assistant-message metadata; confirmed writes use existing tables. Deployment isolation from Build 25 is unchanged.

## What's new in v1.2.0-build28

- **Assistant attachments.** PMs and admins can attach PDF, DOCX, PNG, JPG/JPEG, WEBP, and GIF inputs from the compact dock or expanded composer.
- **Discuss first, file second.** Pending bytes live outside public `/uploads`. Project-scoped conversations show an explicit editable **Save Pending Attachment** proposal; nothing enters project files until confirmation.
- **Natural document and image context.** PDF and DOCX text is extracted locally for discussion. Pending images are passed to the assistant as image content during the conversation.
- **Truthful Global behavior.** Global conversations can discuss pending inputs without guessing a target project. Saving requires a named project and the normal confirmation card.
- **Original bytes preserved.** Confirmed saves move the original input into project files through the normal service and record `changed_by="ai"` with `source_type="ai_chat"`.
- **Safe temporary lifecycle.** Unsupported files and inputs over 10 MB are rejected. Cancelled proposals remove pending bytes; stale pending inputs expire after 24 hours through request-time cleanup.
- **No schema migration.** Temporary metadata uses ignored JSON sidecars outside the database.

## What's new in v1.2.0-build27

- **Editable confirmation cards for all assistant writes.** Journal capture, Ideas, variants, packaging/accessory components, file comments, allowlisted project fields, phase-plan adjustments, and Finish Phase now wait for explicit review and confirmation.
- **Truthful Global scope.** `search_projects` and `get_project_context` are wired as immediate read-only tools. Results remain role-filtered, so viewers do not receive factory, engineer, cost, or journal details.
- **Server-side revalidation.** Confirmation re-checks authentication, role, project ownership, record relationships, allowlists, and reviewed values. Double-confirmed or cancelled proposals remain rejected.
- **Sensitive project-field proposals.** Factory, engineer, target cost, MSRP, launch date, and Thesis can be proposed only through the confirmed flow. Derived `current_stage` and operational `status` remain non-writable through chat.
- **Audited service reuse.** Confirmed AI writes use existing CRUD services and record `changed_by="ai"` with `source_type="ai_chat"`. Manual routes keep their existing defaults.
- **Schema alignment fixes.** Variant statuses and component cost fields now match the stored model values.
- **No schema migration.** Pending proposals continue to live in assistant-message metadata.

## What's new in v1.2.0-build26

- **Professional assistant workspace.** The AI assistant now opens beside the tracker as a resizable split workspace on desktop and a full-screen pane on mobile. Its header is no longer covered by the navbar.
- **Compact dock + panel composer.** The collapsed assistant is a compact bottom dock. When expanded, the dock disappears and the composer moves into the assistant pane.
- **Refined controls.** Ask / Capture and This Project / Global are segmented controls rather than raw dropdowns. Changing scope during an active conversation starts a new thread after confirmation.
- **Real project context.** Project-scoped chat receives a role-filtered project summary, linked Ideas, and permitted recent journal context. Viewers never receive PM-only fields.
- **Inspired By capture.** PMs and admins can create-and-link Ideas directly from the Inspired By section. Chat can propose create, link, and follow-up Idea updates using small confirmation cards.
- **No silent Idea writes.** Chat proposals require explicit confirmation. Confirmed project links write `ai_chat` change-log entries. Duplicate Idea names suggest linking the existing record or creating a new one.
- **Viewer read-only alignment.** Viewers can browse Good Ideas but cannot create, edit, link, or update Ideas.
- **No schema migration.** Build 26 reuses existing conversations, message metadata, Ideas, project links, and change logs.

## What's new in v1.1.0-build25

The tracker can now be deployed as **multiple independent instances**, one per department. PM dept and Beauty dept get full data isolation by running separate app + DB instances from the same git repo.

- **New `DEPLOYMENT.md`** at the project root — step-by-step Railway runbook for provisioning a new department instance (service creation, PostgreSQL plugin, env vars, custom domain, verification checklist, multi-instance operations).
- **Zero code change.** Isolation comes from the existing env-var-driven `DATABASE_URL` (`app/database.py`), `OPENAI_API_KEY`, and `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD` bootstrap (`app/main.py:_bootstrap_admin_from_env`). The app doesn't need to know about departments.
- **Per-instance independence.** Each instance has its own DB, its own user pool, its own OpenAI billing (or share a key — your call), its own bootstrap admin, its own SECRET_KEY.
- **Same code on every instance.** A single `git push` to `main` auto-deploys to all instances, so they always run identical features. Migrations are idempotent and per-instance.
- **Adding the 3rd/4th/Nth department** is the same runbook. If you hit ~4+ departments or need cross-department features (org-wide search, shared idea board), revisit the architecture — see `MASTERPLAN.md` Build 25 section + `~/.claude/plans/can-you-still-find-nested-cook.md`.

> **User action required:** the Railway provisioning steps in `DEPLOYMENT.md` must be performed manually in the Railway dashboard. The code side of Build 25 is complete; the infra side is on you.

## What's new in v1.1.0

v1.1.0 turns the tracker from a static project database into a product development workspace.

- **Project Journal** — PM/admin-only notes on project detail, with raw entries preserved and AI summarization available.
- **Business Plan Upload + Thesis Extraction** — upload PDF/DOCX/DOC/image plans, preview AI-proposed Product Thesis text and detected inspirations, then confirm before any write.
- **Variants, Packaging, Quotation, and Profit Model placeholder** — track SKU variants, package/accessory inputs, quotation files, and the intended future margin model.
- **Timeline 2.0** — planned dates and actual dates are split, plan changes require reasons, and Finish Phase advances the workflow.
- **Rendering History + Prototype Photos** — dedicated visual history sections with per-file comments and latest-rendering thumbnails on project cards.
- **My Projects** — focused PM/admin view, quieter attention banner, and browser-side last-project memory.
- **AI Tools + Bottom AI Chat** — security-first tool registry, permission guard updates, persistent chat conversations, and the first wired intake tool: `create_journal_entry`.
- **AI-Assisted Create Project** — manual and AI-assisted creation now live together at `/projects/new`; the old `/ai/intake` page redirects there.
- **Chinese UI** — EN / 中文 navbar switcher, persisted by `users.language` or cookie fallback, with broad first-pass coverage of primary user-facing screens.

No Build 24 schema migration. The final release build is documentation, version, and regression-test hardening only.

## What's new in v1.1.0-build23

- **中文 UI is now available.** A small EN / 中文 switcher sits in the navbar next to the Help button (visible to everyone, logged-in or not). Click to switch — the choice persists across visits.
- **Language preference is durable.** For logged-in users it's stored on `users.language` (the column shipped in Build 13); for logged-out visitors a `lang` cookie remembers the choice. Locale resolution order: user pref → cookie → English default.
- **First-pass translation coverage** (520 keys): navbar, auth screens, project list/table/card labels, My Projects, Create/Edit Project form, AI-assisted create panel, project-detail sidebar/Thesis/Inspired By/Timeline/Files/Change Log, Journal, Variants, Packaging, Quotation, Profit Model placeholder, Rendering History, Prototype Photos, Calendar, Good Ideas, status badges, alert banners, empty states, and bottom chat controls.
- **Translation philosophy:** product language, not mechanical translation. Industry-standard terms stay as-is — `Thesis`, `MSRP`, `SKU`, `AI`, `PM`, brand names, factory names, product codes.
- **Out of this first pass (deferred to a follow-up i18n update):** the Help modal body, AI prompts (they're instructions to the model — better in English), `/admin/*` pages, changelog/version-history strings, and the legacy `/ai/intake` artifact page.
- **Fail-safe:** a missing translation key surfaces the literal key string (so missing translations are visible in dev) — pages never 500 on i18n issues.

## What's new in v1.1.0-build22

- **Create Project now has two tabs**: **Manual Form** (the existing form) and **AI-Assisted** (paste notes or upload a file → AI extracts fields → review & confirm). Both live at `/projects/new`.
- **AI Intake link removed from the navbar.** Bottom AI Chat (Build 21) is the daily AI entry point now; AI-Assisted Create lives in the natural place for it — inside the Create Project flow. Old bookmarks still work: `/ai/intake` is now a 303 redirect to `/projects/new?tab=ai`.
- **No change to the AI extraction logic itself** (parser, prompts, dual-mode classification). UI relocation only — the `/ai/intake/extract`, `/ai/intake/extract-file`, `/ai/intake/confirm`, and `/ai/intake/confirm-idea` POST routes keep their paths and behavior. They now render inside the AI tab.
- **Edit Project (existing projects)** stays on the same single-form layout — tabs only appear on the create flow.

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
| v1.1.0 | Builds 12-24 | Product Development Workspace: Journal, Thesis extraction, variants/packaging/quotation, Timeline 2.0, media history, My Projects, bottom AI chat, AI-assisted create, Chinese i18n |
| v1.2.0 | Builds 26-29 | Assistant Workspace + Confirmation Cards + Attachments + release hardening |
| v1.2.1 | Builds 30A/30B/30C + 4 patches | Workflow polish + Excel batch intake + draft delete + IME / nixpacks / price-strings / layout patches |
| **v1.3.0** | **v1.3 Builds 01-10** | **Project Detail Command Center: workspace shell + Pulse + product concept + renderings + variant cards + Command Center shell + actions + blockers + history + Planning Sandbox design lock** |
