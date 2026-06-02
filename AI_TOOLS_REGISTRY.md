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
4. **AI proposes; user confirms.** Any tool that writes important data must surface a confirmation card. No silent mutations. (Confirmation UI ships in a later build — until then, AI is read-only for those tools.)
5. **Change log recording.** Every confirmed write calls `write_change()` with `changed_by="ai"` and `source_type="ai_chat"`.

## How to add a new tool (3-step checklist)

1. Add the tool definition (name, JSON schema for params, permission rule, confirmation rule) to `app/ai/tools.py`.
2. Add a row to this registry. Set `status: planned` if not wired yet.
3. When wiring: register in the tool dispatcher, add a test in the corresponding build's test file.

---

## Current Tools

The original 16 schemas landed in Build 20. Build 26 wires the Idea workflow and adds `update_idea`, bringing the registered total to 17. Remaining stubs still pass through dispatcher permission checks before returning an unavailable response.

| Tool | Params | Permission | Confirmation | Status |
|---|---|---|---|---|
| `create_journal_entry` | project_id, entry_text, entry_type | auth + `can_view_journal` + `can_edit_project` | No (low-stakes capture) | **route + schema + handler implemented (Build 14/20)** — fully wired |
| `summarize_journal_entry` | entry_id | auth + `can_view_journal` + `can_edit_project` | No | **route + schema implemented (Build 14/20)**; handler wiring lands in Build 21 |
| `extract_thesis_from_business_plan` | project_id, file_id | auth + `can_edit_project` | YES — preview/confirm before write | **route + schema implemented (Build 15/20)**; handler wiring lands in Build 21 |
| `create_variant` | project_id, variant_name, sku, status, is_primary, costs, summaries, notes | auth + `can_edit_project` | No (additive) | **route + schema implemented (Build 16/20)**; handler wiring lands in Build 21 |
| `update_variant` | variant_id, fields | auth + `can_edit_project` | No (small fields) | **route + schema implemented (Build 16/20)**; handler wiring lands in Build 21 |
| `set_primary_variant` | project_id, variant_id | auth + `can_edit_project` | No (auto-unsets siblings via service layer) | **route + schema implemented (Build 16/20)**; handler wiring lands in Build 21 |
| `delete_variant` | variant_id | auth + admin only | YES — destructive, requires admin | **route + schema implemented (Build 16/20)**; handler wiring lands in Build 21 |
| `create_variant_component` | project_id, variant_id (nullable), component_type, name, costs | auth + `can_edit_project` | No (cost-tracking) | **route + schema implemented (Build 16/20)**; handler wiring lands in Build 21 |
| `update_variant_component` | component_id, fields | auth + `can_edit_project` | No | **route + schema implemented (Build 16/20)**; handler wiring lands in Build 21 |
| `delete_variant_component` | component_id | auth + admin only | YES — destructive | **route + schema implemented (Build 16/20)**; handler wiring lands in Build 21 |
| `finish_phase` | project_id, phase_id | auth + `can_edit_project` | YES — irreversible state transition | **route + schema implemented (Build 17/20)**; handler wiring lands in Build 21 |
| `adjust_phase_plan` | phase_id, planned_*_date, reason | auth + `can_edit_project` | YES — reason mandatory | **route + schema implemented (Build 17/20)**; handler wiring lands in Build 21 |
| `update_file_comment` | project_id, file_id, comment | auth + `can_edit_project` | No (low-stakes annotation) | **route + schema implemented (Build 18/20)**; handler wiring lands in Build 21 |
| `update_project_field` | project_id, field_name, new_value | auth + `can_edit_project` + field allowlist | YES — show confirmation card with old → new | **schema implemented (Build 20)** — handler stub; full wiring in Build 21 |
| `link_idea_to_project` | project_id, idea_id, note | admin/PM + `can_edit_project` | YES — Idea-specific review card | **implemented (Build 26)** |
| `create_idea` | project_id (optional), name, description, idea_type, source, source_detail, contributor, notes | admin/PM; `can_edit_project` when linking | YES — Idea-specific review card | **implemented (Build 26)** |
| `update_idea` | idea_id, editable fields | admin/PM | YES — Idea-specific review card | **implemented (Build 26)** |

## How the dispatcher works

`app/ai/tools.dispatch(tool_name, args, db, user)` runs in this order — **permission discipline applies even when the handler is a stub**, so Build 21 inherits a tool surface where unwired tools have never silently bypassed auth:

1. **Tool exists** in `TOOL_SCHEMAS` → else `{"ok": False, "error": "unknown_tool"}`.
2. **User role check** per `TOOL_PERMISSIONS[tool_name]["require_role"]` → else `forbidden / role_not_allowed`.
3. **Project ownership** if `needs_project: True` — checks `can_edit_project(user, project)` → else `forbidden / cannot_edit_project`.
4. **Journal access** if `needs_journal: True` — checks `can_view_journal(user)` → else `forbidden / cannot_view_journal`.
5. **Field allowlist** for tools that carry a `field_allowlist` → else `field_not_allowlisted`.
6. **Confirmation guard** for Idea writes → return `confirmation_required` until the user confirms the review card.
7. **Handler lookup** in `_HANDLERS` — if absent, return `not_wired_until_build_21` (the legacy stub response).
8. **Call handler** → return its `{"ok": True, ...}` or `{"ok": False, ...}`.

## Planned (post v1.1.0)

| Tool | Purpose | Permission | Confirmation | Target Build |
|---|---|---|---|---|
| `search_projects(query)` | Cross-project search for AI context | auth — filter by viewer permission | No (read-only) | 21 (Bottom chat) |
| `get_project_context(project_id)` | Build per-project AI context — role-filtered | auth — filter sensitive fields by role | No (read-only) | 21 |
| `change_project_status(project_id, new_status, reason)` | Dedicated tool for the operationally consequential status flip | auth + `can_edit_project` | YES — mandatory reason + confirm | 21+ (replaces using `update_project_field` for `status`) |
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

AI can propose updates to: `name`, `brand`, `sku`, `product_type`, `project_owner`, `product_manager`, `planned_launch_date`, `project_thesis`, `notes`.

AI MUST NOT directly write:
- `factory`, `engineer`, `target_factory_cost`, `target_msrp` — operationally consequential; require explicit user confirmation even from admin.
- `current_stage` — derived from phases per CLAUDE.md non-negotiable rule §5; never settable directly.
- `status` — operationally consequential (wrong archive via AI typo is a real failure mode); will get a dedicated `change_project_status` tool with mandatory confirmation if needed in Build 21+.

(This list is enforced in the tool handler in `app/ai/tools.py`, not just in this doc.)
