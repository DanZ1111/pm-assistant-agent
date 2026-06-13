# AI Tools Registry

Every feature that creates structured data MUST have a corresponding AI tool here.
AI must eventually be able to use every major feature — not just chat about them.

> **This registry defines tool schemas and implementation status. It does not override `CLAUDE.md` or `ARCHITECTURE.md`.** Tool allowlists must respect source-of-truth rules such as derived fields not being manually updated (e.g. `current_stage` is derived from phases per CLAUDE.md non-negotiable rule §5 and must NOT appear in any AI write allowlist).

Status legend:
- `implemented` — registered in `app/ai/tools.py`, wired into the chat flow, has tests
- `planned`     — schema defined here; handler is a stub or not wired yet
- `deferred`    — intentionally not for this release

## Rules for every tool

1. **Auth required.** Every tool checks `get_current_user` and rejects on missing/expired session.
2. **Role + ownership enforced.** Same checks the manual UI uses (e.g. `can_edit_project`).
3. **Sensitive field filter.** Tools must use `sanitize_project_for_user` / `is_forbidden_ai_question` so AI cannot bypass viewer restrictions on factory / engineer / cost / journal entries / business plans / quotations.
4. **AI proposes; user confirms.** Every chat-driven write surfaces an editable confirmation card. No silent mutations.
5. **Change log recording.** Every confirmed write calls `write_change()` with `changed_by="ai"` and `source_type="ai_chat"`.
6. **Pending attachment isolation.** Discussion inputs stay outside public `/uploads`; only confirmed `save_pending_attachment` moves original bytes into project files.

## How to add a new tool (3-step checklist)

1. Add the tool definition (name, JSON schema for params, permission rule, confirmation rule) to `app/ai/tools.py`.
2. Add a row to this registry. Set `status: planned` if not wired yet.
3. When wiring: register in the tool dispatcher, add a test in the corresponding build's test file.

---

## Current Tools

The original 16 schemas landed in Build 20. Build 26 added `update_idea`; Build 27 added two read-only lookup tools; Build 28 adds confirmed pending-attachment persistence, bringing the registered total to 20. Deferred stubs still pass through dispatcher permission checks before returning an unavailable response.

| Tool | Params | Permission | Confirmation | Status |
|---|---|---|---|---|
| `search_projects` | query | auth; role-filter results | No — read-only | **implemented (Build 27)** |
| `get_project_context` | project_id | auth; role-filter fields | No — read-only | **implemented (Build 27)** |
| `save_pending_attachment` | project_id, attachment_id, file_category, source_note | auth + `can_edit_project` + pending ownership | YES | **implemented (Build 28)** |
| `create_journal_entry` | project_id, entry_text, entry_type | auth + `can_view_journal` + `can_edit_project` | YES | **implemented (Build 27)** |
| `summarize_journal_entry` | entry_id | auth + `can_view_journal` + `can_edit_project` | No | **dedicated UI implemented; chat handler deferred** |
| `extract_thesis_from_business_plan` | project_id, file_id | auth + `can_edit_project` | YES — preview/confirm before write | **dedicated UI implemented; chat handler deferred** |
| `create_variant` | project_id, variant_name, sku, status, is_primary, costs, summaries, notes | auth + `can_edit_project` | YES | **implemented (Build 27)** |
| `update_variant` | variant_id, fields | auth + owning-project edit access | YES | **implemented (Build 27)** |
| `set_primary_variant` | project_id, variant_id | auth + `can_edit_project` + relationship check | YES | **implemented (Build 27)** |
| `delete_variant` | variant_id | auth + admin only | YES — destructive, requires admin | **manual UI only; chat handler deferred** |
| `create_variant_component` | project_id, variant_id (nullable), component_type, name, costs | auth + `can_edit_project` + relationship check | YES | **implemented (Build 27)** |
| `update_variant_component` | component_id, fields | auth + owning-project edit access | YES | **implemented (Build 27)** |
| `delete_variant_component` | component_id | auth + admin only | YES — destructive | **manual UI only; chat handler deferred** |
| `finish_phase` | project_id, phase_id | auth + `can_edit_project` + relationship check | YES — irreversible state transition | **implemented (Build 27)** |
| `adjust_phase_plan` | project_id, phase_id, planned_*_date, reason | auth + `can_edit_project` + relationship check | YES — reason mandatory | **implemented (Build 27)** |
| `update_file_comment` | project_id, file_id, comment | auth + `can_edit_project` + relationship check | YES | **implemented (Build 27)** |
| `update_project_field` | project_id, field_name, new_value | auth + `can_edit_project` + field allowlist | YES | **implemented (Build 27)** |
| `link_idea_to_project` | project_id, idea_id, note | admin/PM + `can_edit_project` | YES — Idea-specific review card | **implemented (Build 26)** |
| `create_idea` | project_id (optional), name, description, idea_type, source, source_detail, contributor, notes | admin/PM; `can_edit_project` when linking | YES — Idea-specific review card | **implemented (Build 26)** |
| `update_idea` | idea_id, editable fields | admin/PM | YES — Idea-specific review card | **implemented (Build 26)** |
| `create_blocker` | project_id, title, description (optional), severity, phase_id (optional) | admin/PM + `can_edit_project` + phase same-project check | YES | **implemented (v1.3 Build 07B)** |
| `update_blocker` | blocker_id, fields (UPDATE_BLOCKER_ALLOWED whitelist) | admin/PM + owning-project edit access | YES | **implemented (v1.3 Build 07B)** |
| `resolve_blocker` | blocker_id | admin/PM + owning-project edit access | YES | **implemented (v1.3 Build 07B)** |
| `delete_blocker` | — | not exposed to AI (admin-only UI path; matches `delete_variant`) | n/a | **not registered — by design** |

## How the dispatcher works

`app/ai/tools.dispatch(tool_name, args, db, user)` runs in this order — **permission discipline applies even when the handler is a stub**, so Build 21 inherits a tool surface where unwired tools have never silently bypassed auth:

1. **Tool exists** in `TOOL_SCHEMAS` → else `{"ok": False, "error": "unknown_tool"}`.
2. **User role check** per `TOOL_PERMISSIONS[tool_name]["require_role"]` → else `forbidden / role_not_allowed`.
3. **Project ownership** if `needs_project: True` — checks `can_edit_project(user, project)` → else `forbidden / cannot_edit_project`.
4. **Journal access** if `needs_journal: True` — checks `can_view_journal(user)` → else `forbidden / cannot_view_journal`.
5. **Field allowlist** for tools that carry a `field_allowlist` → else `field_not_allowlisted`.
6. **Target-record relationship validation** for object-ID tools.
7. **Confirmation guard** for every AI write → return `confirmation_required` until the user confirms the editable review card.
8. **Handler lookup** in `_HANDLERS` — if absent, return `not_wired_until_build_21` (the legacy stub response).
9. **Call handler** → return its `{"ok": True, ...}` or `{"ok": False, ...}`.

## Planned (post v1.1.0)

| Tool | Purpose | Permission | Confirmation | Target Build |
|---|---|---|---|---|
| `change_project_status(project_id, new_status, reason)` | Dedicated tool for the operationally consequential status flip | auth + `can_edit_project` | YES — mandatory reason + confirm | 21+ (replaces using `update_project_field` for `status`) |
| `list_timeline_templates` | List visible system/user Planning Sandbox templates | auth; template visibility filtered by system/creator/admin | No — read-only | planned after v1.4 manual UI |
| `apply_timeline_template` | Create a draft sandbox from a visible template | auth + `can_edit_project` + template visibility | YES | planned after v1.4 manual UI |
| `apply_sandbox_to_project` | Apply a valid Planning Sandbox to live project phases | auth + `can_edit_project` + active-execution preconditions | YES — explicit Apply confirmation required | planned after v1.4 manual UI |
| `save_sandbox_as_template` | Save the current planning sandbox graph as a reusable workflow template | auth + `can_edit_project` + visible sandbox relationship | YES — user confirmation required | deferred after v1.4 manual UI |
| `explain_sandbox_estimate` | Explain schedule duration, warnings, and critical path from sandbox graph | auth + project visibility | No — read-only | deferred |
| `propose_sandbox_edits` | Suggest node/dependency edits for a Planning Sandbox | auth + `can_edit_project` | YES before any write | deferred |
| `draft_design_quest` | Draft a PM-reviewed designer-facing brief from project context | auth + `can_edit_project` | YES — PM confirms before any quest write | deferred after v1.5 manual UI |
| `publish_design_quest` | Publish an existing draft design quest to designer visibility | auth + `can_edit_project` + owning quest/project check | YES — explicit publish confirmation | deferred after v1.5 manual UI |
| `close_design_quest` | Close an active design quest with optional reason | auth + `can_edit_project` + owning quest/project check | YES — explicit close confirmation | deferred after v1.5 manual UI |
| `request_design_revision` | Request structured revision on a designer submission | auth + `can_edit_project` + owning submission/project check | YES — PM confirms revision text/checklist | deferred after v1.5 manual UI |
| `select_final_design_submission` | Select a submission version and promote it to project renderings | auth + `can_edit_project` + owning version/project check | YES — explicit final selection confirmation | deferred after v1.5 manual UI |
| `mark_design_complete` | Mark selected design work complete without phase mutation | auth + `can_edit_project` + selected rendering required | YES — explicit completion confirmation | deferred after v1.5 manual UI |
| `designer_manager_assign` | Assign a designer to an assigned-only design quest | designer_manager only; portal-safe quest scope | YES — explicit manager confirmation | deferred after v1.5 manual UI |
| `designer_manager_reopen_submission` | Reopen a mistakenly rejected designer submission | designer_manager only; rejected submission only | YES — explicit manager confirmation | deferred after v1.5 manual UI |
| ~~`add_rendering_note(file_id, note)`~~ | Superseded by `update_file_comment` (Build 18) | — | — | ✓ shipped Build 18 |
| ~~`add_prototype_photo_note(file_id, note)`~~ | Superseded by `update_file_comment` (Build 18) | — | — | ✓ shipped Build 18 |

## Deferred (post v1.1.0)

| Tool | Reason for deferring |
|---|---|
| `propose_split_into_variants` | Requires the AI confirmation flow to be mature first |
| `compare_quotations` | Quotation matrix parsing is out of scope for v1.1 |
| `recommend_msrp(profit_target)` | Profit Model is a placeholder in v1.1 |

---

## Sensitive Field Allowlist for `update_project_field`

AI can propose confirmed updates to: `name`, `brand`, `sku`, `product_type`, `project_owner`, `product_manager`, `engineer`, `factory`, `target_factory_cost`, `target_msrp`, `planned_launch_date`, `project_thesis`.

AI MUST NOT directly write:
- `current_stage` — derived from phases per CLAUDE.md non-negotiable rule §5; never settable directly.
- `status` — operationally consequential (wrong archive via AI typo is a real failure mode); will get a dedicated `change_project_status` tool with mandatory confirmation if needed in Build 21+.

(This list is enforced in the tool handler in `app/ai/tools.py`, not just in this doc.)
