# PM Product Tracker — Changelog

## Unreleased
_2026-06-02_

- **Chinese IME chat fix (v2, mature composer controller).** The initial isComposing / keyCode 229 guards did not catch the Chrome + Sogou Pinyin and Edge + Microsoft Pinyin case, where `compositionend` fires BEFORE the Enter keydown that triggered it — all three guards were already cleared by the time the Enter handler ran, so the IME-confirmation Enter sent the message prematurely.
  - Both composers (bottom dock + assistant side panel) now share a new `createComposerController` helper in `app/static/js/composer_controller.js` (ES module).
  - Four defense layers: local `isComposing` flag, `e.isComposing`, `e.keyCode === 229`, AND a one-shot `suppressNextEnterUntil` window (`IME_CONFIRM_ENTER_SUPPRESS_MS = 80`) seeded on every `compositionend`. The window self-clears after blocking exactly one Enter so a deliberate rapid follow-up Enter still sends.
  - Single shared `maybeSubmitComposer()` entry point — keyboard Enter and send-button clicks both route through it for consistent trim / disabled / final-submit logic. The send button click is intentionally NOT IME-gated (explicit user intent); send buttons keep `type="submit"` for accessibility but the click handler intercepts via `preventDefault`.
  - Plain Enter still sends. Shift+Enter still inserts a newline.
  - Locked by JSDOM behavioral tests (`npm run test:composer`, 10 cases), folded into `test_build29.py` as a subprocess assertion that skips cleanly on environments without Node/jsdom.
  - main.js is now loaded as `type="module"` (still IIFE-wrapped; no global behavior change).
- **PM-facing price strings.** Project Target Factory Cost and Target MSRP now preserve real-world planning expressions such as `under 120 RMB` and `$70-100` instead of forcing USD-only floats. Simple USD values still mirror into the legacy numeric columns for old displays and future profit math.

## v1.2.0 — Assistant Workspace Release
_2026-06-02_

The v1.2.0 release packages Builds 26-28 plus this release-hardening build (29). It turns the AI assistant from an experimental bottom chat into a professional, project-aware workspace where every write is reviewed before it lands.

- **Professional assistant workspace** (Build 26): resizable desktop split panel, mobile full-screen pane, compact collapsed dock, panel composer, Ask / Capture and This Project / Global segmented controls, immutable conversation scope, role-filtered project context injection, project-aware Idea capture with duplicate detection and one-step Create-and-Link.
- **Confirmed daily PM actions** (Build 27): editable proposal cards in chat for journal entries, Idea actions, variants, packaging / accessory components, file comments, allowlisted project fields, reasoned phase-plan adjustments, and Finish Phase. Confirmation revalidates auth, role, ownership, allowlists, and proposal state; double-confirmed and cancelled proposals are rejected. Sensitive fields (factory, engineer, costs, MSRP, launch date, Thesis) are proposal-only. Derived `current_stage` and operational `status` remain non-writable.
- **Global read-only search** (Build 27): `search_projects` and `get_project_context` wired as immediate read-only tools. Results are role-filtered so viewers never see PM-only fields.
- **Assistant attachments** (Build 28): PDF, DOCX, PNG, JPG/JPEG, WEBP, and GIF discussion with bytes held in pending storage outside `/uploads` until the user confirms `save_pending_attachment`. PDF + DOCX text extracted locally; pending images passed to the assistant as image content. Confirmed saves move bytes through the normal audited file service with `changed_by="ai"` and `source_type="ai_chat"`. 10 MB cap and 24-hour request-time cleanup.
- **Audit + safety**: every confirmed mutation reuses existing CRUD helpers and writes change-log rows. Viewers remain read-only across the new surfaces.
- **No schema migration in Build 29**. Pending proposals live in assistant-message metadata; confirmed writes use existing tables. Deployment isolation from Build 25 is unchanged.

**Test:** `test_build29.py` is the release-proof regression. Full Build 20-28 suite + `test_ai_e2e.py` (10 passed, 7 external-AI skips, 0 failed) must stay green.

## v1.2.0-build28 — Assistant PDF, DOCX, and image intake (Build 28)
_2026-06-01_

**Goal:** let PMs discuss file-backed product evidence naturally without silently adding project files.

**Pending attachment lifecycle:**
- Adds PDF, DOCX, PNG, JPG/JPEG, WEBP, and GIF attachment controls to the compact dock and expanded assistant composer.
- Stores pending original bytes and JSON sidecars in ignored, non-public `app/pending_uploads/`.
- Extracts PDF and DOCX text locally; passes pending image bytes into the current assistant turn for visual discussion.
- Rejects unsupported extensions and inputs over 10 MB before writing; request-time cleanup removes pending inputs after 24 hours.

**Confirmed persistence:**
- Adds `save_pending_attachment(project_id, attachment_id, file_category, source_note)`.
- Project scope offers a save proposal automatically after attachment discussion, even when the external model call is unavailable.
- Global scope allows discussion without auto-targeting a project.
- Confirm and cancel reuse the Build 27 proposal lifecycle. Confirm moves original bytes through `crud.upload_file()` with `changed_by="ai"` and `source_type="ai_chat"`; cancel removes pending bytes.

**Test:** `test_build28.py` covers accepted and rejected inputs, DOCX extraction, non-public storage, cleanup, permissions, auto-proposal behavior, cancel cleanup, byte-preserving confirmed persistence, audit attribution, Global behavior, and workspace markup.

## v1.2.0-build27 — Confirmed daily PM actions + Global read-only search (Build 27)
_2026-06-01_

**Goal:** turn the assistant workspace into a trustworthy daily PM copilot while preserving explicit human control over writes.

**Proposal framework:**
- Generalized Build 26 Idea review cards into editable proposal cards for every chat-driven mutation.
- Confirmation merges only reviewed fields from the original stored proposal, then re-checks auth, project access, record relationships, allowlists, and handler validation.
- Keeps pending state in assistant-message metadata; no migration or pending-actions table.

**Daily PM actions + Global lookup:**
- Wires confirmed journal capture, Idea actions, variants, package/accessory components, file comments, allowlisted project fields, reasoned phase-plan adjustments, and Finish Phase.
- Adds immediate read-only `search_projects` and `get_project_context` tools for truthful Global conversations.
- Role-filtered lookup keeps viewer responses clear of factory, engineer, cost, and journal details.

**Audit + safety:**
- Reused CRUD helpers now accept AI attribution and write change-log rows before commit.
- Sensitive fields remain proposal-only; derived `current_stage` and operational `status` remain blocked.
- Corrected older AI-schema drift for variant statuses and component cost fields.

**Test:** `test_build27.py` covers schema parity, Global role filtering, every wired daily handler, audit attribution, relationship and ownership checks, editable HTTP confirmation, and double-confirm rejection.

## v1.2.0-build26 — Professional assistant workspace + project-aware Idea capture (Build 26)
_2026-06-01_

**Goal:** make bottom chat feel like a professional second workspace while fixing the awkward inspiration workflow.

**Assistant workspace:**
- Replaced the overlay-style expanded state with a resizable desktop split workspace and a mobile full-screen assistant pane.
- Moved the active composer into the pane and reduced the collapsed state to a compact dock.
- Replaced raw mode/scope dropdowns with Ask / Capture and This Project / Global segmented controls.
- Added immutable conversation scope: switching project/global context starts a fresh conversation after confirmation.
- Kept assistant header controls above tracker navigation so Archive, History, and Close stay reachable.

**Project-aware capture:**
- Injects role-filtered project context into project-scoped chat. Viewers do not receive factory, engineer, or cost fields.
- Adds `create_idea`, `link_idea_to_project`, and allowlisted `update_idea` handlers.
- Adds small Idea-specific review cards with Confirm / Cancel and duplicate-aware Link Existing / Create New actions.
- Adds manual **Create & Link Idea** in the project-detail Inspired By section.
- Aligns viewers with read-only Good Ideas behavior.

**Audit + safety:**
- No schema migration.
- Idea linkage and linked-Idea edits use service-layer writes and project change-log entries.
- Chat writes remain preview-confirm; Build 27 will generalize proposal cards to the broader daily PM tool set.

**Test:** `test_build26.py` covers schema parity, i18n parity, role-filtered prompt context, guarded Idea tools, audit writes, duplicate matching, HTTP proposal lifecycle, immutable scope, manual Create & Link, workspace markup, and viewer restrictions.

## v1.1.0-build25 — Beauty Department isolated deployment (Build 25)
_2026-05-30_

**Goal:** unblock the Beauty department's adoption of the tracker without disrupting the existing PM department's data. Architectural review (recorded in `~/.claude/plans/can-you-still-find-nested-cook.md`) chose **separate-deployment-per-department** (multi-tenancy Option 4) over row-level multi-tenancy: hard isolation, zero code-change risk, ships in hours of devops work. The trade-off (no cross-department views) is acceptable since none are planned.

**Code changes: none.** Per-instance isolation comes for free from existing patterns:
- `app/database.py` reads `DATABASE_URL` from env (Railway PostgreSQL plugin auto-provides it).
- `app/main.py:_bootstrap_admin_from_env()` (shipped in Build 9) lets each instance bootstrap its own first admin from env vars.
- `OPENAI_API_KEY` is read from env, so each instance can have its own.

**New file: `DEPLOYMENT.md`** at the project root — canonical runbook covering Railway service creation, PostgreSQL plugin attachment, per-instance env vars (`INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_PASSWORD`, `OPENAI_API_KEY`, `SECRET_KEY`, `DISABLE_RELOAD`), custom domain CNAME setup (subdomain convention: `pm.tracker.example.com`, `beauty.tracker.example.com`), 5-step post-deploy verification checklist (health check, version string, first admin login, cross-instance isolation check, bootstrap-cleanup), and multi-instance operating guidance (migrations, backups, code changes, user accounts, OpenAI spend, file uploads).

**Bumps:**
- `app/version.py` → `1.1.0-build25`
- `VERSION.md` → "What's new" block at top.
- `MASTERPLAN.md` → Build 25 detail section (FDR + scope + verification).

**Test — `test_build25.py`** verifies what Claude can verify remotely:
- `DEPLOYMENT.md` exists at project root with the required runbook sections.
- `app/version.py` is bumped to `1.1.0-build25` with the right build name.
- `VERSION.md` has a `v1.1.0-build25` "What's new" block.
- `CHANGELOG.md` has a Build 25 entry.
- The existing v1.1.0 PM instance still passes its health check and serves the bumped version string.

The actual Railway provisioning is on the user (Claude can't reach into your Railway account); the runbook is the deliverable.

**Out of scope (deferred to v1.2 if needed):** cross-department views, shared Good Ideas board, org-wide AI search, SSO across departments, per-department branding, auto-provisioning script. All of these would require row-level multi-tenancy (Option 1) — a v1.2-scoped conversation.

**Files created:** `DEPLOYMENT.md`, `test_build25.py`

**Files modified:** `app/version.py`, `VERSION.md`, `MASTERPLAN.md`, `CHANGELOG.md`, `CURRENT_TASK.md`

## v1.1.0 — Product Development Workspace Release (Build 24)
_2026-05-30_

**Goal:** close the v1.1.0 roadmap with a final release bump, consolidated user documentation, and a release-level regression test.

**Release theme:** the app is now a product development workspace rather than only a static project database. v1.1.0 adds daily PM workflows around project memory, thesis extraction, SKU/packaging detail, timeline reality, visual iteration, and AI-assisted capture.

**Major features included across v1.1.0:**
- **Governance + migration foundation** — canonical runtime version source, product/AI working rules, idempotent migration infrastructure, and additive schema for v1.1 data.
- **Project Journal** — internal PM/admin project notes with AI summary support; viewers cannot access journal content.
- **Business Plan Upload + Thesis Extraction** — AI proposes Product Thesis text and inspiration links from uploaded plans; users preview, edit, and confirm before data is written.
- **Variants, Packaging, Quotation, and Profit Model placeholder** — multi-SKU tracking, package/accessory components, quotation file surfacing, and the intended profit formula documented for the future full model.
- **Timeline 2.0** — Plan / Reality columns, required reason capture for planned-date changes, plan-change history, and Finish Phase workflow.
- **Rendering History + Prototype Photos** — dedicated visual iteration sections, per-file comments, latest rendering thumbnails on project cards.
- **My Projects + project memory** — focused PM/admin project list, delay-only attention banner, and browser-side last-opened project memory.
- **AI tools architecture + Bottom AI Chat** — OpenAI tool schemas, security-first dispatcher, viewer permission guard checks before model calls, persistent chat threads, and wired `create_journal_entry`.
- **AI-Assisted Create Project** — manual and AI-assisted create flows consolidated into `/projects/new`, with `/ai/intake` preserved as a redirect.
- **Chinese i18n** — EN / 中文 switcher with durable preference, cookie fallback for logged-out visitors, broad first-pass translation coverage of primary user-facing screens, and exact English/Chinese bundle parity.

**Build 24 changes:**
- `app/version.py` bumped to final `1.1.0`.
- `VERSION.md` now carries a consolidated "What's new in v1.1.0" release summary.
- `USER_GUIDE.md` now has a short Chinese summary plus English sections for all v1.1 features and the intended Profit Model formula.
- `MASTERPLAN.md` marks Build 24 shipped.
- `test_build24.py` added release-doc/version checks and regression inventory checks.

**No schema migration in Build 24.** This build changes only docs, version metadata, and tests.

## v1.1.0-build23 — Chinese i18n (Build 23)
_2026-05-30_

**Goal:** ship a Chinese UI option for the PM tracker. The architecture has been ready since Build 13 (which added `users.language` with default `"en"`); Build 23 is the actual translation layer + switcher.

**New module `app/i18n`** (Python package):
- `app/i18n/__init__.py` — `TRANSLATIONS` dict loaded from JSON bundles; `t(key, **kwargs)` Jinja2 `pass_context` global; `get_locale(request, current_user)` helper.
- `app/i18n/en.json` and `app/i18n/zh.json` — 520 keys each, dot-namespaced by area (`nav.*`, `title.*`, `section.*`, `btn.*`, `form.*`, `badge.*`, `status.*`, `filter.*`, `alert.*`, `empty.*`, `chat.*`, `idea_*`, `timeline.*`, `files.*`, `journal.*`, `variant.*`, `component.*`, `profit.*`, `common.*`).
- Locale resolution: authenticated `users.language` → `lang` cookie → `"en"`. No `Accept-Language` header (per agreed plan).
- Fail-safe: missing key returns literal key string, missing locale falls back to en, format errors return the raw template. **Pages never 500 on i18n issues.**

**New route `POST /lang/set`** (`app/routes/i18n.py`):
- Accepts a `lang` form value; silently falls back to `"en"` if not in `SUPPORTED_LOCALES`.
- Sets `lang` cookie (1-year, samesite=lax).
- For authenticated users, also persists to `users.language` (durable across browser/cookie clears).
- 303 redirect back to the `next` form value (sanitized to local paths only).

**Switcher UI** — new partial `app/templates/components/lang_switcher.html`. Two small `EN | 中文` buttons in the navbar (visible to everyone). Active locale is styled distinctly. POSTs to `/lang/set` with `next=<current path>` so users stay on the same page after switching.

**Template sweep — primary surfaces translated:**
- `base.html` — navbar links, Help button, Sign Out button.
- Auth pages — login/register labels, buttons, helper copy, and emergency reset labels.
- `projects_list.html` / `my_projects.html` — page titles, counts, filters, table headers, badges, empty states, and primary actions.
- `project_form.html` — page title, both tab labels (Manual / AI), section headers, form labels, required/critical/recommended badges, prototype controls, Thesis help, Cancel / Save / Create buttons.
- `project_detail.html` — sidebar labels, Product Thesis controls, Inspired By, Timeline table/modals, Files & Renderings, Change Log, and file upload labels.
- Detail sub-components — Project Journal, Variants, Packaging & Accessories, Quotation Files, Profit Model placeholder, Rendering History, Prototype Photos.
- Calendar and Good Ideas board/form pages.
- AI-assisted create panel — paste/upload states, review/confirm forms, classification banner, status copy, and actions.
- `components/bottom_chat.html` — mode toggle (Intake/Ask), scope toggle (Project/Global), placeholder text, panel title, history/archive/close titles.
- `components/lang_switcher.html` — uses i18n keys for its labels too.

**Translation philosophy** (per agreed clarification): product language, not mechanical translation. Industry-standard terms stay as-is — `Thesis`, `MSRP`, `SKU`, `AI`, `PM`, brand names, factory names, product codes are not translated. Goal is to read naturally to a Chinese-speaking PM who already works in this domain.

**Out of scope for this first pass** (deferred to a v1.2 i18n update):
- Help modal body (~240 lines of deep doc).
- AI prompts in `app/ai/prompts.py` (English performs better; not user-visible).
- `/admin/*` pages (internal tools).
- Legacy `app/templates/intake.html` (kept as historical artifact; no longer rendered).

**Safety rails (confirmed):**
- No business logic, permission, AI behavior, or schema change. UI i18n only.
- No `Accept-Language` browser detection. Manual switcher only.
- User reviews `zh.json` wording before final v1.1.0 release.

**No schema migration.** `users.language` already exists (Build 13).

**Files created:** `app/i18n/__init__.py`, `app/i18n/en.json`, `app/i18n/zh.json`, `app/routes/i18n.py`, `app/templates/components/lang_switcher.html`, `test_build23.py`

**Files modified:** `app/main.py` (mount i18n router; register `t` and locale helper as Jinja2 globals), `app/routes/auth.py`, `app/routes/projects.py`, `app/routes/intake.py`, `app/routes/calendar.py`, `app/routes/ideas.py` (locale contexts), user-facing templates across projects/auth/calendar/ideas/detail components, `app/version.py`, `VERSION.md`, `USER_GUIDE.md` (one-line note), `CURRENT_TASK.md` (handoff status).

## v1.1.0-build22 — AI-Assisted Create Project (Build 22)
_2026-05-30_

**Goal:** consolidate the two ways to create a project (manual form + AI intake) into a single page with two tabs. Removes the standalone AI Intake nav link now that Bottom AI Chat (Build 21) is the daily AI entry point.

**`/projects/new` is now a two-tab page:**
- **Manual Form tab** — the existing project_form.html content, unchanged.
- **AI-Assisted tab** — new partial `app/templates/components/ai_intake_panel.html` containing both intake states (input + review/confirm).
- Tabs use the same Bootstrap pattern as the Help modal in base.html.
- `?tab=ai` query param picks the AI tab on initial render; default is Manual.

**Server-side endpoints unchanged in behavior:**
- `/ai/intake/extract`, `/ai/intake/extract-file`, `/ai/intake/confirm`, `/ai/intake/confirm-idea` — all 4 POST routes keep their paths and create/update logic. They now render `project_form.html` with `initial_tab="ai"` so the AI panel shows after extraction.
- `GET /ai/intake` becomes a 303 redirect to `/projects/new?tab=ai`. Old bookmarks and any test that GETs `/ai/intake` continue to work.

**Code cleanup:** introduced `_ai_panel_response(request, current_user, **overrides)` helper in `app/routes/intake.py` so every intake response gets the project_form.html scaffolding (project=None, is_edit=False, initial_tab="ai", current_user) plus safe defaults for all intake context keys. Eliminated 8+ near-duplicate context dicts.

**Navbar:** the "AI Intake" link is removed from `base.html`. A short Jinja comment is left in its place pointing to the new home.

**Edit Project (existing projects)** is untouched — tabs only render when `is_edit=False`. The edit flow stays a single form (no AI-Assisted edit in v1.1).

**No schema change. No AI logic change.** UI relocation + helper refactor.

**Files modified:** `app/routes/intake.py` (helper + 8 TemplateResponse call-sites refactored, GET /ai/intake → redirect), `app/routes/projects.py` (GET /projects/new accepts tab=, passes initial_tab + intake defaults), `app/templates/project_form.html` (Bootstrap tab wrapper on create flow), `app/templates/base.html` (AI Intake nav link removed), `app/version.py`, `VERSION.md`, `USER_GUIDE.md`

**Files created:** `app/templates/components/ai_intake_panel.html`, `test_build22.py`

**Files removed:** none (intake.html is no longer rendered but the file stays in the repo as a historical artifact for now; can be deleted in a follow-up if desired).

## v1.1.0-build21 — Bottom AI Chat + Side Panel + Conversation History (Build 21)
_2026-05-29_

**Goal:** Build 20 shipped the AI tool schemas + dispatcher; nothing called them. Build 21 puts a ChatGPT-style chat bar on every authenticated page so users can actually invoke the one wired tool (`create_journal_entry`) — and lays the UI groundwork for the other 15 tools to come online in follow-ups without UI rework.

**Bottom chat bar** (`app/templates/components/bottom_chat.html` included from `base.html` inside `{% if current_user %}` so anonymous pages don't render it):
- Fixed-position bar at the viewport bottom, dark accent.
- Mode toggle: `Intake` (AI can call tools) / `Ask` (read-only Q&A; no tools passed to the model).
- Scope toggle (only on project detail pages): `Project` (passes `project_id` so AI has project context) / `Global`.
- Textarea auto-grows from 38px up to 200px on `input`; `Enter` submits, `Shift+Enter` inserts a newline.
- Body gets `.has-bottom-chat` class so `.main-content` adds `padding-bottom: 80px` (no footer overlap).

**Right-side panel** slides in from the right when the user submits:
- Header: conversation title + history dropdown + archive button + close button.
- Message thread: user bubbles right-aligned (primary blue), assistant bubbles left-aligned (gray).
- Tool-call cards rendered inline beneath the assistant message:
  - `ok` (green): "✓ create_journal_entry — Success (id 47)"
  - `not_wired_until_build_21` (yellow): "⚠ delete_variant — not_wired_until_build_21"
  - other errors (red): "⚠ tool_name — error_string"
- Close button collapses the panel but leaves the bar in place.

**Backend — new file `app/routes/ai_chat.py`:**
- `POST /ai/chat` — accepts `{message, mode, conversation_id?, project_id?}`. Flow:
  1. `require_auth`.
  2. Reject early with `question_blocked_by_permission_guard` if `is_forbidden_ai_question(user, message)` returns True (NO OpenAI call).
  3. Load or create `AIConversation` (idempotent if `conversation_id` is supplied and owned; else create new).
  4. Persist the user message via `crud.save_ai_message(...)` with `metadata={"conversation_id": ..., "mode": ...}`.
  5. Build OpenAI `messages` list: mode-specific system prompt + last 10 history messages.
  6. Call `gpt-5.4`. In `intake` mode, pass `tools=TOOL_SCHEMAS, tool_choice="auto"`.
  7. If `tool_calls` present, run each through `app.ai.tools.dispatch(...)` and capture results.
  8. Persist the assistant message with `metadata={"tool_calls": [...]}`.
  9. Return `{ok, conversation_id, assistant_message, tool_calls}`.
- `GET /ai/conversations` — returns user's active (non-archived) conversations, newest-first.
- `GET /ai/chat/{conversation_id}` — returns full thread; 404 if not user's.
- `POST /ai/conversations/{id}/archive` — flips status; idempotent.

**Backend — new crud functions in `app/crud.py`:**
- `create_ai_conversation(db, user_id, project_id=None, title=None)` — auto-titles `"{project.name}"` or `"(global chat)"`.
- `list_ai_conversations(db, user_id, include_archived=False)` — ordered by `updated_at desc`.
- `get_ai_conversation(db, conversation_id, user_id)` — enforces ownership (returns None if not user's).
- `get_ai_messages_for_conversation(db, conversation_id, limit=None)` — chronological order; `limit=N` returns the last N still chronologically.
- `archive_ai_conversation(db, conversation_id, user_id) -> bool` — idempotent.
- **`save_ai_message` was modified** to also set `conversation_id` from metadata AND bump `AIConversation.updated_at` (so the history dropdown shows most-recently-active threads at top).

**Backend — 2 new system prompts in `app/ai/prompts.py`:** `CHAT_ASK_SYSTEM_PROMPT` (read-only Q&A; no tools), `CHAT_INTAKE_SYSTEM_PROMPT` (knows it has 16 tools but only `create_journal_entry` is wired; politely defers when other tools fail).

**Permission discipline:**
- Chat bar gated by `{% if current_user %}` in `base.html` — never renders for anonymous users.
- `POST /ai/chat` re-checks `require_auth`, then `is_forbidden_ai_question` BEFORE any OpenAI call.
- Tool calls run through `app.ai.tools.dispatch(...)` which already enforces role + project ownership per Build 20.

**No schema migration.** `ai_conversations` + `ai_messages` (with `conversation_id` column) have existed since Build 13.

**Out of scope (deferred):**
- Drag-and-drop file/image upload into chat → defers to Build 22 (AI-Assisted Create Project).
- Streaming responses (SSE/chunked) — v1.1 returns the full response.
- Two-turn tool follow-up (feeding result back to model for a natural-language wrap-up).
- Confirmation cards for destructive tools (none of those are wired in v1.1 anyway).
- Per-conversation title editing — titles are auto-generated only.

**Files modified:** `app/crud.py`, `app/ai/prompts.py`, `app/main.py`, `app/routes/projects.py` (added `current_project_id` to context), `app/templates/base.html`, `app/static/css/styles.css`, `app/static/js/main.js`, `app/version.py`, `VERSION.md`, `USER_GUIDE.md`

**Files created:** `app/routes/ai_chat.py`, `app/templates/components/bottom_chat.html`, `test_build21.py`

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
