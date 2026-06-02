# v1.2.0 Codex Roadmap - Professional AI Assistant Workspace

> **Status:** Build 26 authorized and implemented locally; Builds 27-29 remain planning only.
> **Author:** Codex
> **Written:** 2026-06-01
> **Review target:** Claude should compare this staged roadmap with `BUILD26_PLAN.md` before either agent edits application code.

---

## Summary

The assistant redesign is too large for one build. Ship it as the `v1.2.0` feature series, using the same small-build discipline that worked for `v1.1.0`.

The series keeps the existing database schema. It reuses conversations, message metadata, project records, Ideas, variants, components, files, phases, journal entries, and the change log. Each build must be usable on its own and preserve Build 25 department-isolation behavior.

| Build | Version | Theme | Size |
| --- | --- | --- | --- |
| **26** | `v1.2.0-build26` | Professional assistant workspace + project-aware Idea capture | L |
| **27** | `v1.2.0-build27` | Confirmation cards + daily PM assistant actions + Global read-only search | L |
| **28** | `v1.2.0-build28` | Assistant PDF, DOCX, and image intake | M |
| **29** | `v1.2.0` | Release hardening, documentation, and full regression | S |

Do not pull unrelated future `v1.2` ideas such as the full Profit Model into this series. They remain separate roadmap candidates.

---

## Feature Design Review

1. **What real workflow problem are we solving?** PMs need to discuss active work with an assistant without losing screen space, repeating project context, or manually translating inspiration and project updates into several forms.
2. **Is it repeated or edge-case?** This is a repeated daily workflow across project review, sourcing, option comparison, and follow-up.
3. **Does it need structured data?** No new tables are needed; existing records and message metadata cover the required state.
4. **Could it live first in Journal / notes / metadata?** Pending assistant proposals should live in message metadata until confirmed, while confirmed records continue through existing services.
5. **Does it increase intake burden?** No; it reduces burden by accepting natural language and files while retaining manual forms.
6. **Can AI reduce intake burden?** Yes; AI can classify intent, resolve project context, identify duplicates, propose records, and ask concise questions.
7. **What display/reminder does it enable?** PMs see the tracker and assistant together, review proposed actions, and see confirmed updates immediately in the correct project section.
8. **Does it affect migration?** No database migration is required for Builds 26-29.
9. **What is the minimal schema change?** None.
10. **What is the minimal UI change?** Replace the current assistant overlay and raw dropdowns with a split workspace, compact dock, panel composer, segmented controls, and staged proposal cards.
11. **What should be deferred?** Deletes, admin redesign, Help redesign, auth redesign, unrelated Profit Model work, row-level multi-tenancy, and autonomous writes.

---

## Locked Product Decisions

- Use a quiet, professional visual tone.
- Redesign the shell, assistant, and project-detail workflow only.
- Collapsed state: show a compact assistant composer dock.
- Expanded desktop state: show a resizable tracker-plus-assistant split workspace.
- Expanded mobile state: show the assistant as a full-screen pane with a clear return control.
- Move the composer into the assistant pane while expanded; never leave the dock underneath it.
- Default project-detail conversations to the current project.
- Ask before switching the scope of an active conversation.
- Use segmented controls for **Ask / Capture** and **This Project / Global**.
- Require only an Idea name; collect optional detail naturally.
- Detect likely duplicate Ideas and offer link-existing or create-new choices.
- Add a manual **Create & Link Idea** fallback in Inspired By.
- Allow sensitive project-field proposals only with explicit confirmation.
- Analyze PDF, DOCX, and image attachments, but ask before saving them into project files.
- Keep deletes manual and keep derived values such as `current_stage`, `delayed`, and `needs_info` non-writable.

---

## Build 26 - Professional Workspace + Project-Aware Idea Capture

### Goal

Fix the broken assistant experience visible in the screenshot and make project-scoped inspiration capture genuinely useful. This build deliberately stops before the generalized confirmation-card framework.

### Implementation Refinement Log

#### 2026-06-01 - Idea-specific confirmation cards moved into Build 26

During implementation, `CLAUDE.md` and `ARCHITECTURE.md` exposed a hard constraint: AI writes must not apply silently. The earlier staged draft placed generalized confirmation cards in Build 27 while also asking Build 26 chat to create and link Ideas immediately. Those two statements conflicted.

Build 26 now includes a deliberately narrow confirmation path for Idea actions only:

- `create_idea`, `link_idea_to_project`, and allowlisted `update_idea` return `confirmation_required` before mutation.
- The chat route stores each pending Idea proposal in assistant-message `metadata_json`.
- The panel renders a small review card with **Confirm** / **Cancel**.
- Duplicate Idea matches render **Link existing** / **Create new anyway**.
- The confirmation endpoint re-checks conversation ownership, role, project access, and dispatcher rules before applying the mutation.
- Build 27 still owns the generalized proposal framework for variants, components, project fields, phase changes, Finish Phase, file comments, and Global project lookup.

This keeps Build 26 independently useful without creating a disposable or unsafe write path.

#### 2026-06-01 - Viewer Idea permissions aligned across surfaces

The existing Good Ideas board allowed authenticated viewers to open the standalone New Idea flow, while the Build 26 plan explicitly chose read-only viewer behavior. Build 26 aligns the board, standalone Idea routes, legacy AI-assisted Idea confirmation, manual Create & Link route, and assistant dispatcher so viewer Idea mutations are consistently unavailable.

#### 2026-06-01 - Verification state

- `python3 test_build26.py` passes `19/19`.
- Regressions pass: `test_build20.py` `23/23`, `test_build21.py` `20/20`, `test_build22.py` `15/15`, `test_build23.py` `24/24`, `test_build24.py` `11/11`, `test_build25.py` `15/15`.
- `python3 test_ai_e2e.py` passes `10`, skips `7` configured external-AI checks, and fails `0`.
- Static checks pass: `python3 -m compileall -q app`, JSON parse + EN/ZH parity, `node --check app/static/js/main.js`, and `git diff --check`.
- Headless Playwright geometry smoke passes at `1600x1000` and `390x844`: navbar and tracker stop at the panel boundary, the dock hides while expanded, and the panel composer remains reachable.

#### 2026-06-01 - Expanded tracker header compacting

Visual screenshot inspection showed that the tracker navbar no longer overlapped the assistant, but Sign Out wrapped onto a second row when the desktop split reduced the tracker to `1160px`. Build 26 now tightens nav padding and font sizes only while `assistant-open` is active. This preserves the normal full-width navbar while keeping the side-by-side workspace compact.

#### 2026-06-01 - Resume finalization

After the network interruption, Codex resumed from `CURRENT_TASK.md`, reran static checks and `test_build26.py`, and visually re-inspected the refined desktop and mobile screenshots. The tree is commit-ready. No Build 27 or Build 28 work has started.

### Implementation Changes

#### App Shell And Assistant Workspace

- Introduce a shell-level `assistant-open` state that changes desktop layout from a full-width tracker to a two-column tracker-plus-assistant workspace.
- Use a CSS custom property for assistant width. Default to `440px`, constrain it to `360px` minimum and `min(680px, 50vw)` maximum, and persist the chosen width in `localStorage`.
- Add a drag handle on the assistant edge. On mobile, use a full-screen pane rather than a narrow split.
- Keep navigation outside the assistant pane so it cannot cover Archive, Close, History, messages, or the composer.
- Move the composer into the assistant footer while expanded. Restore a compact dock when the pane closes.
- Replace raw `<select>` controls with compact segmented controls.
- Preserve conversation history, archive, close, and reopen behavior. Closing the pane must not archive the conversation.
- Add EN and Chinese labels in lockstep.

#### Project Context

- On project-detail pages, default new conversations to that project.
- Inject role-filtered active-project context into the system prompt, including project name, ID, status, derived stage, thesis, linked Ideas, and recent journal context.
- Treat unqualified messages in project scope as referring to the active project.
- Keep scope immutable after the first message. If the user requests a scope switch, ask before starting a new conversation.
- Replace unexplained internal enum language such as `discovery` with human labels such as **Inspiration**, **Decision**, **Question**, and **Risk**.

#### Idea And Inspired By Workflow

- Wire `create_idea`, `link_idea_to_project`, and minimal allowlisted `update_idea` handlers through existing `crud.py` services and `write_change()`.
- Restrict Idea mutations to admin and PM roles; viewers remain read-only.
- Interpret phrases such as "inspired by", "saw at a tradeshow", and "thinking of using" as Idea candidates rather than generic journal entries.
- Require only the Idea name. Ask one concise follow-up for optional type, source, contributor, or notes.
- Search existing Ideas before creation. If a likely duplicate exists, ask whether to link the existing Idea or create a new one.
- Add a manual **Create & Link Idea** action beside Inspired By for precise fallback entry.
- Keep the Good Ideas board and existing manual linking routes intact.

### Acceptance

- The assistant opens beside the tracker without covering the navbar or leaving the dock underneath it.
- Pane width is resizable and restored after reload.
- Project-mode chat knows the active project without asking the PM to repeat it.
- A PM can describe an inspiration and create-or-link it into Inspired By in one conversational flow.
- A viewer cannot create, update, or link Ideas.
- `test_build26.py` covers workspace state, i18n parity, project context, duplicate handling, create-and-link idempotency, permissions, and change-log writes.

---

## Build 27 - Confirmed Daily PM Actions + Global Read-Only Search

### Goal

Generalize the assistant from Idea capture into a trustworthy PM copilot. AI proposes; the user confirms.

### Feature Design Review (2026-06-01)

1. **Real workflow problem:** PMs need to turn normal project conversations into structured tracker updates without leaving the assistant workspace.
2. **Repeated or edge-case:** Journal capture, product-option edits, file notes, phase-plan changes, and project-field corrections are repeated daily PM work.
3. **Structured data:** These actions update existing structured records; no new table or column is needed.
4. **Could live in notes:** General observations can live in the journal, but variants, components, files, project fields, and phases must update their existing records.
5. **Intake burden:** The PM writes naturally, reviews one compact editable proposal, then confirms or cancels.
6. **AI reduce burden:** The assistant selects the existing service action and pre-fills fields while the PM retains final control.
7. **Display/reminder payoff:** Confirmed updates appear in the normal tracker sections and project change history.
8. **Migration impact:** None; pending proposals remain in assistant-message `metadata_json`.
9. **Minimal schema change:** No schema change.
10. **Minimal UI change:** Extend the Build 26 proposal card and composer workspace; do not redesign unrelated tracker surfaces.
11. **Deferred:** Deletes, chat-driven thesis extraction, journal summarization, file/image attachment intake, and autonomous writes remain outside Build 27.

### Implementation Detail (2026-06-01)

- Expand the existing Build 26 proposal lifecycle routes rather than adding parallel endpoints. Pending proposals stay inside assistant-message `metadata_json`; no migration is needed.
- Guard every chat-driven mutation behind confirmation, including journal capture. `CLAUDE.md` wins over the older registry text that treated journal capture and file comments as low-stakes direct writes.
- Keep `search_projects` and `get_project_context` immediate and read-only. Search only projects accessible to the current user; context remains role-filtered through the existing sanitizer.
- Preserve established tool names from `app/ai/tools.py`: use `update_project_field` and `adjust_phase_plan` rather than introducing plural or renamed aliases.
- Wire the daily PM handlers through existing `crud.py` services: journal entries, Ideas, variants, components, file comments, project fields, phase-plan adjustments, and Finish Phase.
- Add target-record authorization checks for object-ID tools (`update_variant`, `update_variant_component`, `adjust_phase_plan`) and validate that file and phase records belong to the supplied target project.
- Make proposal values editable in the conversation card. Confirmation may submit reviewed args, but the server must re-run role checks, project access checks, record relationship checks, allowlists, and handler validation against the reviewed values.
- Keep delete tools permission-checked but unwired. Leave chat-driven `summarize_journal_entry` and `extract_thesis_from_business_plan` deferred because their dedicated manual workflows already exist and they are not part of this daily-action slice.
- Normalize reused CRUD services so confirmed AI writes pass `changed_by="ai"` and `source_type="ai_chat"` into `write_change()` before commit. Manual callers keep their current defaults.
- Expand project-field proposals to include sensitive PM fields such as factory, engineer, target costs, MSRP, launch date, and thesis only because the common confirmation gate now applies. Keep derived `current_stage`, computed health fields, and operational `status` non-writable through chat.

### Implementation Changes

#### Proposal Framework

- Store pending structured proposals in assistant-message `metadata_json`, following the existing extraction-preview precedent. Do not add a pending-actions table.
- Render editable proposal cards in the conversation with target project, editable fields, validation feedback, and explicit **Confirm** / **Cancel** controls.
- Add:

```text
POST /ai/chat/{conversation_id}/proposals/{proposal_id}/confirm
POST /ai/chat/{conversation_id}/proposals/{proposal_id}/cancel
```

- Re-check authentication, role, project access, allowlists, and proposal state on confirmation.
- Reject stale and double-confirmed proposals.
- Route every confirmed mutation through `crud.py`; every mutating service must call `write_change()`.

#### Daily PM Tool Set

Wire and document these tools in `AI_TOOLS_REGISTRY.md`:

| Capability | Behavior |
| --- | --- |
| `search_projects` | Read-only search across projects accessible to the current user. |
| `get_project_context` | Read-only role-filtered project summary. |
| `create_journal_entry` | Propose a journal item with a human-facing type. |
| `create_idea` / `link_idea_to_project` / `update_idea` | Move Build 26 Idea mutations behind the common proposal-card flow. |
| `create_variant` / `update_variant` / `set_primary_variant` | Propose product-option changes. |
| `create_variant_component` / `update_variant_component` | Propose BOM and packaging changes. |
| `update_file_comment` | Propose a project-file comment update. |
| `update_project_fields` | Propose safe allowlisted project fields; sensitive fields remain confirm-only. |
| `update_phase` | Propose phase-plan adjustments without writing derived stage. |
| `finish_phase` | Propose Finish Phase through the existing service. |

- Make Global scope truthful by enabling read-only `search_projects` and `get_project_context`.
- Keep Global mutations project-targeted: the proposal card must name the target project before confirmation.
- Leave delete tools manual.

### Acceptance

- Every consequential assistant write waits for explicit user confirmation.
- Sensitive project fields and Finish Phase never apply silently.
- Global search returns only projects accessible to the current user.
- Derived fields remain non-writable.
- `test_build27.py` covers proposal lifecycle, validation, stale/double-confirm rejection, role enforcement, Global access filtering, every wired handler, and change-log writes.

### Refinement Log

- **2026-06-01:** Reused the Build 26 proposal endpoints instead of adding new routes.
- **2026-06-01:** Tightened the confirmation policy to cover every AI mutation, including journal entries and file comments, to match repository non-negotiables.
- **2026-06-01:** Kept established schema names `update_project_field` and `adjust_phase_plan`; roadmap aliases are documentation-only wording.
- **2026-06-01:** Deferred delete tools, chat-driven journal summarization, and thesis extraction so Build 27 remains an independently testable daily-workflow slice.
- **2026-06-01:** Corrected pre-existing schema/service drift while wiring handlers: variant statuses now use `idea | evaluating | selected | rejected | launched`, and components use the stored `target_cost` / `actual_cost` fields with `packaging | accessory` types.
- **2026-06-01:** Normalized reused CRUD audit sequencing so change rows are added before commit and AI callers can pass `changed_by="ai"` plus `source_type="ai_chat"` without changing manual-route defaults.
- **2026-06-01:** Refined proposal cards after desktop/mobile visual smoke: humanize tool labels, widen cards slightly, and use compact textareas for longer reviewed values so journal text and notes remain readable.
- **2026-06-01:** Marked Global lookup results explicitly read-only in handler payloads and UI cards; append a deterministic role-filtered summary so search remains truthful even before a future multi-turn tool-result-to-model enhancement.
- **2026-06-01:** Verification complete: `test_build27.py` passes 29/29; Build 20-26 regressions pass; `test_ai_e2e.py` passes 10 with 7 expected external-AI skips and 0 failures; static checks and EN/Chinese parity pass at 534/534.
- **2026-06-01:** Desktop `1600x1000` and mobile `390x844` Playwright geometry smoke passed after the proposal-card refinement. Refined screenshots: `/tmp/pm-tracker-build27-desktop-refined.png` and `/tmp/pm-tracker-build27-mobile-refined.png`.
- **2026-06-01:** Regression maintenance: widened `test_build25.py`'s staged-v1.2 version assertion after it rejected the valid `1.2.0-build27` bump; rerun passed 15/15.

---

## Build 28 - Assistant File And Image Intake

### Goal

Let PMs discuss reference files and images naturally while preserving original inputs and preventing silent project-file changes.

### Implementation Changes

- Add PDF, DOCX, and image attachments to the compact dock and expanded assistant composer.
- Reuse existing extraction helpers for analysis and discussion.
- Keep uploaded bytes in a temporary pending area until the user confirms **Save to project files**.
- In project scope, propose saving through the normal project-file service and preserve original bytes.
- In Global scope, allow discussion first; require a selected target project and confirmation before saving.
- Add safe cleanup for cancelled and stale pending uploads.
- Record confirmed file persistence through the normal change-log path.

### Acceptance

- A PM can upload and discuss PDF, DOCX, and image inputs without silently changing a project.
- Confirmed saves appear in project files with original bytes preserved.
- Cancelled and stale uploads are cleaned safely.
- Viewer restrictions remain intact.
- `test_build28.py` covers accepted types, rejected types, extraction, pending state, project-target confirmation, persistence, cleanup, permissions, and change-log writes.

---

## Build 29 - v1.2.0 Release Hardening

### Goal

Close the assistant-workspace release with consolidated documentation and broad regression proof.

### Implementation Changes

- Bump runtime and release docs to `v1.2.0`.
- Update `CHANGELOG.md`, `VERSION.md`, `MASTERPLAN.md`, `USER_GUIDE.md`, and `AI_TOOLS_REGISTRY.md` to describe the shipped series.
- Add a concise Chinese summary for new user-facing workflows and verify EN / Chinese key parity.
- Keep Build 25 deployment isolation unchanged.

### Acceptance

- Run `python3 test_build29.py` for release-level checks.
- Run `python3 test_build20.py`, `python3 test_build21.py`, `python3 test_build22.py`, `python3 test_build23.py`, `python3 test_build24.py`, `python3 test_build25.py`, `python3 test_build26.py`, `python3 test_build27.py`, `python3 test_build28.py`, and `python3 test_ai_e2e.py`.
- Manually verify desktop and mobile layouts in English and Chinese.
- Capture browser screenshots showing that the navbar, tracker, dock, resize handle, assistant header, proposal cards, message list, and composer do not overlap.

---

## Explicitly Deferred

- Autonomous AI writes without confirmation.
- Delete tools.
- Admin-only screens, Help modal body, auth screens, and unrelated page redesigns.
- Row-level multi-tenancy; department separation remains deployment-level as documented for Build 25.
- New database tables or migrations.
- Translation of AI prompts and user-authored project data.
- Full Profit Model implementation and other unrelated `v1.2` roadmap candidates.

---

## Claude Review Request

Please compare this roadmap with `BUILD26_PLAN.md` and record:

1. Whether Build 26 is a safe replacement for the narrower overlay patch while remaining independently shippable.
2. Whether Build 26 Idea handlers can ship conversationally first and move behind generalized confirmation cards in Build 27 without rework.
3. Whether assistant-message `metadata_json` is sufficient for Build 27 proposal cards and confirmed execution.
4. Which Build 27 handlers can reuse existing `crud.py` services without violating confirmation and change-log rules.
5. Whether Build 28 temporary-file cleanup needs an explicit lifecycle job or can use request-time cleanup.
6. Any scope movement you recommend between Builds 26-29, with the user-visible tradeoff stated explicitly.

Build 26 was explicitly started by the user. Do not implement Build 27 or later until the user explicitly starts that build.
