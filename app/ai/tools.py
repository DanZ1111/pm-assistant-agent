"""Build 20 — AI Tools Architecture.

This module defines OpenAI function-calling schemas for every AI-callable
operation on the system, plus a dispatcher that enforces permission discipline
even when handlers are not yet wired. Only `create_journal_entry` ships with a
real handler in v1.1; the rest return `{"ok": False, "error":
"not_wired_until_build_21"}` AFTER passing the permission check (so Build 21
inherits a tool surface where auth has never been silently bypassed).

The schemas mirror the manual HTTP routes shipped in Builds 14-18 plus three
new tools (`update_project_field`, `link_idea_to_project`, `create_idea`)
introduced here.

Source-of-truth discipline (per CLAUDE.md): the allowlist in
UPDATE_PROJECT_FIELD_ALLOWED deliberately excludes `current_stage` (derived
from phases) and `status` (operationally consequential — will get a dedicated
change tool with confirmation if needed in Build 21).
"""

from __future__ import annotations

from typing import Any

import app.crud as crud
from app.dependencies import can_edit_project, can_view_journal


# ---------------------------------------------------------------------------
# 1. Tool schemas (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "create_journal_entry",
            "description": "Create a Project Journal entry capturing a discovery, decision, open question, or note about a project. Raw text is preserved forever.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "ID of the project"},
                    "entry_text": {"type": "string", "description": "The raw text of the journal entry"},
                    "entry_type": {
                        "type": "string",
                        "enum": ["general", "decision", "question", "discovery", "risk"],
                        "description": "What kind of entry this is. Defaults to 'general'.",
                    },
                },
                "required": ["project_id", "entry_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summarize_journal_entry",
            "description": "Generate / refresh the short AI summary (title) for a specific journal entry.",
            "parameters": {
                "type": "object",
                "properties": {
                    "entry_id": {"type": "integer", "description": "ID of the journal entry"},
                },
                "required": ["entry_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_thesis_from_business_plan",
            "description": "Extract the Product Thesis (and any inspirations) from an uploaded business plan file attached to a project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "file_id": {"type": "integer", "description": "ID of the uploaded business plan in project_files"},
                },
                "required": ["project_id", "file_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_variant",
            "description": "Add a new SKU variant to a project (e.g. a different size, color, or trim).",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "variant_name": {"type": "string"},
                    "sku": {"type": "string"},
                    "status": {"type": "string", "enum": ["active", "draft", "discontinued"]},
                    "is_primary": {"type": "boolean", "description": "If true, this variant becomes the project's primary SKU."},
                    "target_factory_cost": {"type": "number"},
                    "target_msrp": {"type": "number"},
                    "material_summary": {"type": "string"},
                    "packaging_summary": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["project_id", "variant_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_variant",
            "description": "Edit fields on an existing variant.",
            "parameters": {
                "type": "object",
                "properties": {
                    "variant_id": {"type": "integer"},
                    "fields": {
                        "type": "object",
                        "description": "Map of field_name → new_value. Only changed fields need to be present.",
                    },
                },
                "required": ["variant_id", "fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_primary_variant",
            "description": "Mark one variant as the project's primary SKU (un-flags any sibling primary in the service layer).",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "variant_id": {"type": "integer"},
                },
                "required": ["project_id", "variant_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_variant",
            "description": "Delete a variant. Admin-only and destructive — require user confirmation in the chat surface.",
            "parameters": {
                "type": "object",
                "properties": {"variant_id": {"type": "integer"}},
                "required": ["variant_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_variant_component",
            "description": "Add a packaging or accessory component to a project (scope can be project-wide or per-variant).",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "variant_id": {"type": ["integer", "null"], "description": "If null, component applies to the whole project."},
                    "component_type": {"type": "string", "enum": ["packaging", "accessory", "insert", "other"]},
                    "name": {"type": "string"},
                    "target_unit_cost": {"type": "number"},
                    "actual_unit_cost": {"type": "number"},
                    "supplier": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["project_id", "component_type", "name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_variant_component",
            "description": "Edit fields on an existing variant component.",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_id": {"type": "integer"},
                    "fields": {"type": "object"},
                },
                "required": ["component_id", "fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_variant_component",
            "description": "Delete a variant component. Admin-only and destructive.",
            "parameters": {
                "type": "object",
                "properties": {"component_id": {"type": "integer"}},
                "required": ["component_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_phase",
            "description": "Mark the current in-progress phase as done and advance the next phase to in-progress. Both actual_* dates are set to today server-side.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "phase_id": {"type": "integer"},
                },
                "required": ["project_id", "phase_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "adjust_phase_plan",
            "description": "Change the planned start or end date of a phase. A reason is mandatory and writes a phase_plan_changes audit row.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phase_id": {"type": "integer"},
                    "planned_start_date": {"type": ["string", "null"], "format": "date"},
                    "planned_end_date": {"type": ["string", "null"], "format": "date"},
                    "reason": {"type": "string", "description": "Required — why the plan is changing"},
                },
                "required": ["phase_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_file_comment",
            "description": "Set or edit the per-file comment (renderings, prototype photos, etc.). Writes a change_log row.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "file_id": {"type": "integer"},
                    "comment": {"type": "string"},
                },
                "required": ["project_id", "file_id", "comment"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_project_field",
            "description": "Propose a change to a non-sensitive project field. The chat surface must show a confirmation card before applying. Sensitive fields (factory, engineer, costs), derived fields (current_stage), and operationally consequential fields (status) are rejected by the allowlist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "field_name": {"type": "string", "description": "One of: name, brand, sku, product_type, project_owner, product_manager, planned_launch_date, project_thesis, notes"},
                    "new_value": {"description": "New value for the field. Type depends on the field (string, ISO date, etc.)"},
                },
                "required": ["project_id", "field_name", "new_value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "link_idea_to_project",
            "description": "Connect an existing Good Idea to a project. Idempotent: re-linking the same idea returns the existing link.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "idea_id": {"type": "integer"},
                    "note": {"type": "string", "description": "Optional note about why this idea inspires the project"},
                },
                "required": ["project_id", "idea_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_idea",
            "description": "Create a new entry on the Good Ideas board.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "idea_type": {"type": "string", "enum": ["material", "structure", "feature", "aesthetic", "manufacturing", "other"]},
                    "source": {"type": "string", "enum": ["factory", "tradeshow", "internet", "customer", "team", "competitor", "other"]},
                    "source_detail": {"type": "string"},
                    "contributor": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# 2. Permission rules per tool — consulted by the dispatcher
# ---------------------------------------------------------------------------

# Conservative allowlist for update_project_field. See module docstring.
UPDATE_PROJECT_FIELD_ALLOWED: set[str] = {
    "name", "brand", "sku", "product_type",
    "project_owner", "product_manager",
    "planned_launch_date", "project_thesis", "notes",
}

# Roles allowed to call each tool. "needs_project" means the dispatcher must
# also verify can_edit_project() against the project_id in args.
# "needs_journal" means can_view_journal() must also pass.
TOOL_PERMISSIONS: dict[str, dict[str, Any]] = {
    "create_journal_entry":            {"require_role": ("admin", "pm"), "needs_project": True, "needs_journal": True},
    "summarize_journal_entry":         {"require_role": ("admin", "pm"), "needs_journal": True},
    "extract_thesis_from_business_plan": {"require_role": ("admin", "pm"), "needs_project": True},
    "create_variant":                  {"require_role": ("admin", "pm"), "needs_project": True},
    "update_variant":                  {"require_role": ("admin", "pm")},
    "set_primary_variant":             {"require_role": ("admin", "pm"), "needs_project": True},
    "delete_variant":                  {"require_role": ("admin",)},
    "create_variant_component":        {"require_role": ("admin", "pm"), "needs_project": True},
    "update_variant_component":        {"require_role": ("admin", "pm")},
    "delete_variant_component":        {"require_role": ("admin",)},
    "finish_phase":                    {"require_role": ("admin", "pm"), "needs_project": True},
    "adjust_phase_plan":               {"require_role": ("admin", "pm")},
    "update_file_comment":             {"require_role": ("admin", "pm"), "needs_project": True},
    "update_project_field":            {"require_role": ("admin", "pm"), "needs_project": True,
                                        "field_allowlist": UPDATE_PROJECT_FIELD_ALLOWED},
    "link_idea_to_project":            {"require_role": ("admin", "pm"), "needs_project": True},
    "create_idea":                     {"require_role": ("admin", "pm", "viewer")},
}


# ---------------------------------------------------------------------------
# 3. Dispatcher
# ---------------------------------------------------------------------------

def _err(error: str, **extra) -> dict:
    out = {"ok": False, "error": error}
    out.update(extra)
    return out


def dispatch(tool_name: str, args: dict, db, user) -> dict:
    """Look up the tool, enforce permissions, then call the handler.

    Order of checks (security-first; never skipped, even for unwired tools):
      1. Tool exists in TOOL_SCHEMAS              → else unknown_tool
      2. User passes role check per TOOL_PERMISSIONS → else forbidden
      3. needs_project / needs_journal sub-checks → else forbidden
      4. Field allowlist (for update_project_field) → else field_not_allowlisted
      5. Handler exists in v1.1                    → else not_wired_until_build_21
      6. Call handler                              → return its result

    Permission discipline must apply even when the handler is a stub —
    otherwise Build 21 inherits a tool surface where unwired tools silently
    bypassed auth.
    """
    # 1. Tool exists
    schema_names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    if tool_name not in schema_names:
        return _err("unknown_tool", tool=tool_name)
    perms = TOOL_PERMISSIONS.get(tool_name)
    if perms is None:
        return _err("permission_rule_missing", tool=tool_name)

    args = args or {}

    # 2. Role check (always — anonymous or wrong role fails here)
    if user is None:
        return _err("forbidden", reason="not_authenticated")
    if user.role not in perms["require_role"]:
        return _err("forbidden", reason="role_not_allowed", required=list(perms["require_role"]))

    # 3a. needs_project — must be ownership-eligible
    if perms.get("needs_project"):
        project_id = args.get("project_id")
        if project_id is None:
            return _err("missing_argument", argument="project_id")
        project = crud.get_project(db, int(project_id))
        if project is None:
            return _err("project_not_found", project_id=project_id)
        if not can_edit_project(user, project):
            return _err("forbidden", reason="cannot_edit_project")

    # 3b. needs_journal
    if perms.get("needs_journal") and not can_view_journal(user):
        return _err("forbidden", reason="cannot_view_journal")

    # 4. Field allowlist (only update_project_field today)
    if "field_allowlist" in perms:
        field_name = args.get("field_name")
        if field_name not in perms["field_allowlist"]:
            return _err(
                "field_not_allowlisted",
                field=field_name,
                allowed=sorted(perms["field_allowlist"]),
            )

    # 5. Handler exists?
    handler = _HANDLERS.get(tool_name)
    if handler is None:
        return _err("not_wired_until_build_21", tool=tool_name)

    # 6. Call handler
    return handler(args, db, user)


# ---------------------------------------------------------------------------
# 4. Real handlers (v1.1: just create_journal_entry)
# ---------------------------------------------------------------------------

def _handle_create_journal_entry(args: dict, db, user) -> dict:
    project_id = int(args["project_id"])
    entry_text = str(args.get("entry_text") or "").strip()
    if not entry_text:
        return _err("missing_argument", argument="entry_text")
    entry_type = str(args.get("entry_type") or "general").strip()
    entry = crud.create_journal_entry(
        db,
        project_id=project_id,
        entry_text=entry_text,
        entry_type=entry_type,
        author_user_id=user.id,
    )
    return {
        "ok": True,
        "entry_id": entry.id,
        "entry_type": entry.entry_type,
    }


_HANDLERS: dict[str, Any] = {
    "create_journal_entry": _handle_create_journal_entry,
    # All other tools intentionally absent → dispatcher returns
    # "not_wired_until_build_21" AFTER permission checks pass.
}
