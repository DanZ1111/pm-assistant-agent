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

| Tool | Params | Permission | Confirmation | Status |
|---|---|---|---|---|
| `create_journal_entry` (HTTP route) | project_id, entry_text, entry_type | auth + `can_view_journal` + `can_edit_project` | No (low-stakes capture) | **route implemented (Build 14)**; bottom-chat tool wiring lands in Build 20/21 |
| `summarize_journal_entry` (HTTP route) | entry_id (via URL) | auth + `can_view_journal` + `can_edit_project` | No (preserves existing on failure) | **route implemented (Build 14)**; bottom-chat tool wiring lands in Build 20/21 |
| `extract_thesis_from_business_plan` (HTTP route) | project_id, business_plan file (or file_id) | auth + `can_edit_project` | YES — preview/confirm screen before write | **route implemented (Build 15)**; one-time AI call persisted to `ai_messages` for refresh-safe preview; bottom-chat tool wiring lands in Build 20/21 |
| `create_variant` (HTTP route) | project_id, variant_name, sku, status, is_primary, costs, summaries, notes | auth + `can_edit_project` | No (additive) | **route implemented (Build 16)**; bottom-chat tool wiring lands in Build 20/21 |
| `update_variant` / `set_primary_variant` (HTTP routes) | project_id, variant_id, fields | auth + `can_edit_project` | No (small fields); is_primary auto-unsets siblings via service layer | **route implemented (Build 16)** |
| `delete_variant` (HTTP route) | project_id, variant_id | auth + admin only | YES — destructive, requires admin | **route implemented (Build 16)** |
| `create_variant_component` (HTTP route) | project_id, variant_id (nullable), component_type, name, costs | auth + `can_edit_project` | No (cost-tracking only) | **route implemented (Build 16)** |
| `update_variant_component` (HTTP route) | component_id, fields | auth + `can_edit_project` | No | **route implemented (Build 16)** |
| `delete_variant_component` (HTTP route) | component_id | auth + admin only | YES — destructive | **route implemented (Build 16)** |
| `finish_phase` (HTTP route) | project_id, phase_id | auth + `can_edit_project` | YES — irreversible state transition (one-click; user confirms in dialog) | **route implemented (Build 17)**; bottom-chat tool wiring lands in Build 20/21 |
| `adjust_phase_plan` (HTTP route — via phase_edit) | phase_id, planned_*_date, reason | auth + `can_edit_project` | YES — reason is mandatory; rejected if blank | **route implemented (Build 17)** |
| `update_file_comment` (HTTP route) | project_id, file_id, comment | auth + `can_edit_project` | No (low-stakes annotation; writes change_log) | **route implemented (Build 18)** — covers rendering & prototype-photo notes via the shared `project_files.source_note` field; bottom-chat tool wiring lands in Build 20/21 |

## Planned for v1.1.0 (priority order)

| Tool | Purpose | Permission | Confirmation | Target Build |
|---|---|---|---|---|
| `create_journal_entry(project_id, entry_text, entry_type)` | Create a Project Journal entry from chat | auth + `can_edit_project` (for that project_id) | No (creating new entry, not mutating) | 14 (Journal) / 20 (Tools arch) |
| `update_project_field(project_id, field_name, new_value)` | Propose a field change to an existing project | auth + `can_edit_project` + non-sensitive field allowlist | YES — show confirmation card with old → new | 20 |
| `link_idea_to_project(project_id, idea_id, note)` | Connect an existing idea to a project | auth + `can_edit_project` | YES | 20 |
| `create_idea(name, description, idea_type, source, ...)` | Create a Good Idea entry | auth (all roles) | No — idea creation is low-stakes | 20 |
| ~~`add_rendering_note(file_id, note)`~~ | Superseded by `update_file_comment` (Build 18) — see Current Tools | — | — | ✓ shipped Build 18 |
| ~~`add_prototype_photo_note(file_id, note)`~~ | Superseded by `update_file_comment` (Build 18) — see Current Tools | — | — | ✓ shipped Build 18 |
| `search_projects(query)` | Cross-project search for AI context | auth — filter by viewer permission | No (read-only) | 21 (Bottom chat) |
| `get_project_context(project_id)` | Build per-project AI context — role-filtered | auth — filter sensitive fields by role | No (read-only) | 21 |

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
