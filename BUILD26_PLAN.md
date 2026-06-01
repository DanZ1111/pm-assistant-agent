# Build 26 — AI Side Panel UX Polish + Idea Tools Wiring

> **Status:** Plan only. Awaiting Codex review before any code lands. See `## Codex Review` at the bottom.
> **Author:** Claude (plan written 2026-06-01)
> **Predecessor:** Build 25 (Beauty Department isolated deployment — shipped, code merged to `main` at `af96b46`)

---

## Context

The Build 21 AI side panel works functionally but the UX is rough enough that the user described it as "feels cheap, things keep covering each other." Six concrete problems, all in the same area:

1. When the side panel opens, the bottom intake bar stays visible underneath. There's no inline composer in the panel, so the only way to keep typing is into a textarea the panel is half-covering.
2. The `<select>` dropdowns for Intake/Ask mode and Project/Global scope look like raw Bootstrap form controls — out of character with the rest of the UI.
3. When the user is on a project detail page, the AI doesn't actually know that. The system prompt is static (`CHAT_INTAKE_SYSTEM_PROMPT`), so even though `conv.project_id` is stored, the model is never told "you are currently looking at project X."
4. The AI surfaces unexpected concepts like "Discovery" — really a `create_journal_entry.entry_type` enum value the model picks when the user mentions an inspiration, because it can't see a better tool.
5. The "Inspired by" workflow is two-step (create Idea → manually link it). User wants: speak naturally → AI creates the Idea and links it in one flow, asking follow-ups in chat for missing info (Codex/Claude-Code style, not modal-style).
6. `.navbar-main` (sticky, `z-index: 100`) sits over the top of `.ai-side-panel` (fixed `top: 0`, `z-index: 95`). The panel's Archive / Close / History controls live in its header — exactly the part that's covered.

The good news: `create_idea` and `link_idea_to_project` tool **schemas** already exist in [app/ai/tools.py](app/ai/tools.py); only the handlers are stubbed. `crud.link_idea_to_project()` is also already implemented and idempotent. So the backend work is wiring + prompt tuning, not new modeling.

Frame this as **Build 26 — AI Side Panel UX + Idea Wiring**, single build, no schema change.

---

## The six fixes, scoped concretely

### Fix 1 — Side panel is its own "app": move composer in, hide bottom bar when open

**Problem:** `body.side-panel-open` exists in JS only as a panel `.open` class. The bottom chat bar (`.bottom-chat-bar`, fixed, `z-index: 90`) has no rule that responds to it.

**Change:**
- [app/static/js/main.js](app/static/js/main.js#L212-L220): When `openPanel()` runs, also add `body.classList.add('side-panel-open')`. When `closePanel()` runs, remove it.
- [app/templates/components/bottom_chat.html](app/templates/components/bottom_chat.html#L33-L51): Add a composer inside the panel (textarea + send button + scope pill if `current_project_id`), at the bottom of `#aiSidePanel`. Same `id="chatInputTextarea"` / `id="chatSubmitBtn"` semantics — but a second copy with distinct IDs (e.g. `panelChatInput`, `panelChatSubmit`) so existing JS keeps working and the panel composer is independently bound.
- [app/static/css/styles.css](app/static/css/styles.css): Add `body.side-panel-open .bottom-chat-bar { display: none; }`. Also add `body.side-panel-open .main-content { padding-bottom: 0; }` so the reserved space collapses.
- The Close button on the panel header becomes the "minimize / hide" gesture — conversation stays in DB, bottom bar reappears, can be reopened from history dropdown. (This matches what already happens; we're just making the bar reappear correctly.)
- Conversation history dropdown in the panel header already exists — it's the discoverable way back into a previous chat.

**End state:** Two-mode feel. Side panel open = AI Assistant app, bottom bar gone, panel has its own input. Side panel closed = PM tracker, bottom bar back as the intake quick-entry.

### Fix 2 — Dropdowns: ditch the raw `<select>` for pill toggles

**Problem:** `.bottom-chat-toggles .form-select` uses dark grey raw selects (styles.css ~1853–1859). Cheap-looking next to the rest of the app.

**Change:**
- [app/templates/components/bottom_chat.html](app/templates/components/bottom_chat.html#L7-L22): Replace `<select id="chatModeSelect">` with a small segmented-control of two buttons: Intake (default) / Ask. Same for Project / Global scope.
- [app/static/js/main.js](app/static/js/main.js#L260-L270): Read selected button via a `data-active` attribute / class state, not `select.value`.
- [app/static/css/styles.css](app/static/css/styles.css): Add `.chat-segmented` — pill group with rounded corners, subtle border, active state with brand color background. Roughly matches the look of the existing `.btn-outline-secondary` family.
- Inside the panel, the scope (Project / Global) becomes a **context line** above the composer, e.g. `In project: {{ project.name }}` or `Global` — readable, not a dropdown — because the panel composer can read URL context same way the bottom bar does.

### Fix 3 — Tell the model what project the user is on

**Problem:** [app/routes/ai_chat.py:125](app/routes/ai_chat.py#L125) picks `CHAT_INTAKE_SYSTEM_PROMPT` verbatim. `conv.project_id` exists but is never injected.

**Change:**
- [app/routes/ai_chat.py](app/routes/ai_chat.py): Add a small `_build_system_prompt(base_prompt, db, conv, current_user)` helper. If `conv.project_id` is set, fetch the project and append a sentence like:
  > "Active project context: {project.name} (id={project.id}, status={project.status}, current_stage={project.current_stage}). Unless the user explicitly switches context, assume their messages refer to this project. When recording ideas, inspirations, or facts about this project, prefer the project-linked tools (`create_idea` + `link_idea_to_project`) over generic ones."
- Build that helper from existing data (no new queries beyond the project fetch).
- Pass the user's role/name too so the model knows when permission gates will reject a call before trying it.

### Fix 4 — Stop the AI from defaulting to `create_journal_entry(entry_type=discovery)`

**Root cause:** with no `create_idea` handler wired and no project context in the prompt, the model has only one structured-data tool — `create_journal_entry` — so it shoehorns inspirations in as journal entries with `entry_type=discovery`. The fix is structural: give it a better tool (Fix 5) and tell it when to use which (Fix 3 + prompt update).

**Change:**
- [app/ai/prompts.py](app/ai/prompts.py): Extend `CHAT_INTAKE_SYSTEM_PROMPT` with a short "When to use which tool" block:
  - User says they were *inspired by* / *saw* / *thinking of using* something → `create_idea` + `link_idea_to_project`
  - User reports a *decision*, *question*, *risk*, or general project update → `create_journal_entry`
  - User volunteers a *fact* about an existing project field (factory, MSRP, launch date, etc.) → defer to v1.2 (`update_project_field` stub still returns `not_wired_until_build_21`, so the model should tell the user the change is noted but not yet applied; OR ask the user to set it manually).
- Keep the existing "never invent project data; ask if project_id missing" guidance.

### Fix 5 — Wire `create_idea` and `link_idea_to_project` for real

**Currently** (app/ai/tools.py:265–298): both have schemas + permission rules but their dispatcher entries return `{"status": "not_wired_until_build_21"}`.

**Change:**
- Add real handlers in [app/ai/tools.py](app/ai/tools.py) (or wherever the dispatcher mapping lives):
  - `_handle_create_idea(db, current_user, args)`: validates `name` (required), defaults `idea_type="other"` and `source="other"` if absent (the model can fill them later via follow-up), inserts via `crud.create_idea(...)`. Wraps in `write_change()` per the CLAUDE.md non-negotiable for mutating service functions.
  - `_handle_link_idea_to_project(db, current_user, args, conv)`: reads `project_id` from args OR falls back to `conv.project_id` if the model omits it but conversation has a project context. Calls `crud.link_idea_to_project(db, project_id, idea_id, linked_by_user_id=current_user.id, note=args.get("note"))`. Already idempotent.
- Both write to the change log automatically through the crud helpers (verify and add if not).
- Update [AI_TOOLS_REGISTRY.md](AI_TOOLS_REGISTRY.md) — mark these two as "wired in Build 26" with examples.
- Add to [test_build26.py](test_build26.py) (new): end-to-end test that simulates "create an idea named X from a tradeshow and link it to project Y" → checks DB row, change log row, and the `inspired_by` rendering on the project detail page.

**Permission check (per CLAUDE.md §3 non-negotiables):**
- `create_idea` permission tuple narrowed from `("admin", "pm", "viewer")` → `("admin", "pm")` to match the rest of v1.1's viewer-is-read-only model. Update [app/ai/tools.py](app/ai/tools.py#L315-L333) and any corresponding entry in [AI_TOOLS_REGISTRY.md](AI_TOOLS_REGISTRY.md). Add an assertion in `test_build26.py` that a viewer-role caller gets refused.
- `link_idea_to_project` is allowed for `("admin", "pm")`. Good — no change.

**Missing-info follow-up behavior (confirmed):**
- `_handle_create_idea` accepts `name` as required, defaults `idea_type="other"` and `source="other"` if omitted, creates the idea immediately, and returns the new `idea_id` plus an `unresolved_fields` list (e.g. `["idea_type", "source"]`). The model then asks ONE short follow-up in the same chat turn — e.g. *"Got it, created IDEA-042. Quick — was this from a tradeshow, factory, or somewhere else?"* — so the user's next reply can refine the idea via a follow-up `update_idea` call.
- Decision: include a minimal `update_idea` handler in Build 26 scope. The schema can support only the editable fields (`idea_type`, `source`, `source_detail`, `contributor`, `notes`) — same allowlist as `/ideas/{id}/edit`. This keeps the conversational follow-up clean instead of breaking the flow with "go edit this in a different page."
- Update `CHAT_INTAKE_SYSTEM_PROMPT` to instruct the model: after `create_idea` with defaults, ask exactly one concise follow-up to resolve `idea_type` / `source`, no more.

### Fix 6 — Pull the side panel below the navbar

**Change in [app/static/css/styles.css](app/static/css/styles.css):**

```css
.ai-side-panel {
  position: fixed;
  top: 52px;             /* WAS: 0 — now sits below the sticky navbar */
  right: 0;
  width: 420px;
  height: calc(100vh - 52px);
  z-index: 95;           /* unchanged: navbar (100) still owns the top strip */
  transform: translateX(100%);
}
```

If the navbar wraps to a second row (post-Build-25 responsive fix), `top: 52px` is off by ~36px for narrow widths. Acceptable for v1 — the navbar wrap is only at very narrow widths where the panel is already constrained.

Optional polish: on narrow widths (`@media (max-width: 600px)`), make the panel full-width (`width: 100%`) so it doesn't look stranded on the right of a phone screen.

---

## Critical files

Read:
- [app/templates/components/bottom_chat.html](app/templates/components/bottom_chat.html) — both the bottom bar and the side panel live here
- [app/static/js/main.js:212-352](app/static/js/main.js#L212-L352) — open/close/archive/send logic
- [app/static/css/styles.css:1833-1995](app/static/css/styles.css#L1833-L1995) — `.bottom-chat-bar`, `.ai-side-panel`, `.has-bottom-chat`
- [app/routes/ai_chat.py:73-181](app/routes/ai_chat.py#L73-L181) — POST `/ai/chat` handler
- [app/ai/prompts.py:124-150](app/ai/prompts.py#L124-L150) — `CHAT_INTAKE_SYSTEM_PROMPT`
- [app/ai/tools.py:265-298](app/ai/tools.py#L265-L298) — `create_idea`, `link_idea_to_project` schemas + stubs
- [app/ai/tools.py:315-408](app/ai/tools.py#L315-L408) — permission rules + dispatcher
- [app/crud.py:965-993](app/crud.py#L965-L993) — `link_idea_to_project` helper (already exists)
- [app/models.py:181-227](app/models.py#L181-L227) — `Idea` + `ProjectIdea` schemas

Modify:
- `app/static/css/styles.css` (z-index, top offset, body.side-panel-open rules, segmented control, panel composer)
- `app/templates/components/bottom_chat.html` (segmented control, panel composer, context line)
- `app/static/js/main.js` (body class on open/close, segmented control state, panel-composer submit binding)
- `app/routes/ai_chat.py` (`_build_system_prompt` helper)
- `app/ai/prompts.py` (`CHAT_INTAKE_SYSTEM_PROMPT` extension)
- `app/ai/tools.py` (wire `create_idea` + `link_idea_to_project` + minimal `update_idea` handlers; narrow `create_idea` viewer permission)
- `AI_TOOLS_REGISTRY.md` (mark three tools wired in Build 26)
- `app/version.py` → `1.1.0-build26`
- `VERSION.md`, `CHANGELOG.md`, `MASTERPLAN.md` (Build 26 detail section)
- New: `test_build26.py`

No schema change → no migration → no `migrations/versions/` work.

---

## Verification

**Manual / browser:**
1. Log in as PM. Land on dashboard. Bottom chat bar visible at bottom. Click into a project. Bottom chat bar still visible.
2. Type "we're inspired by a Japanese tea ceramic mug I saw at last week's Canton tradeshow." Hit send.
3. Side panel slides in from the right. Bottom chat bar **disappears**. Panel header (title + Archive + Close + History) is fully visible — not covered by navbar.
4. The AI's response mentions the active project name and shows it called `create_idea` + `link_idea_to_project`. Refresh the project detail page → the new idea appears in the "Inspired By" section.
5. Close the panel. Bottom chat bar reappears. Reopen via the history dropdown → conversation state restored.
6. Drag window narrower. Segmented controls (Intake/Ask, Project/Global) wrap or stay legible, not the raw `<select>` look.
7. Try the same flow as a viewer → AI refuses (`create_idea` should be admin/pm only after the perm narrowing).

**Automated:**
- `python3 test_build26.py` — must pass all assertions (target: ≥ 15 incl. handler unit tests + endpoint smoke).
- Regression: `python3 test_build25.py` 15/15, `test_build24.py` 11/11, `test_build23.py` 24/24, `test_ai_e2e.py` 10P/7S/0F.

---

## Out of scope (defer to v1.2 unless user re-prioritises)

- True modal popups for missing idea info (Codex/Claude-Code style mode-based prompting is already what we do via the chat itself).
- Wiring `update_project_field` and the other 12 stubbed tools — separate, larger work.
- Native-speaker Chinese review of `app/i18n/zh.json` for new strings added in this build.
- Row-level multi-tenancy (Beauty deployment runbook in DEPLOYMENT.md still covers v1.1 needs).
- Removing the bottom chat bar entirely (replacing it with a single floating launcher) — the bar still has discovery value for new users.

---

## Codex Review

**Reviewed by:** _(awaiting Codex)_

**Date:**

**Verdict:** _(thumbs-up / amendments / blocking concerns)_

**Notes:**

_(Codex: write your review here. Either +1 the plan as-is, edit sections directly with rationale, or list specific blocking concerns below. Both agents can see this file. Once you're done, the user will tell Claude to proceed.)_
