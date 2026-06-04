"""AI tool schemas, permission checks, proposal guards, and handlers.

Build 27 keeps read-only tools immediate and routes every chat-driven mutation
through a proposal card. Confirmation re-runs this dispatcher, so record
relationships, ownership, and allowlists are enforced against reviewed values.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import app.crud as crud
from app.ai.attachments import (
    AttachmentError, get_pending_attachment, persist_pending_attachment,
)
from app.dependencies import (
    can_edit_project, can_view_journal, sanitize_project_for_user,
)
from app.models import ProjectFile


# ---------------------------------------------------------------------------
# 1. Tool schemas (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_projects",
            "description": "Search projects accessible to the current user by name, brand, SKU, or product type. Read-only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search text. Leave blank to list recent accessible projects."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_context",
            "description": "Get a role-filtered summary for one project. Read-only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                },
                "required": ["project_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_pending_attachment",
            "description": "Propose saving a pending assistant-discussion attachment into a project's normal Files section. Always requires user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "attachment_id": {"type": "string"},
                    "file_category": {
                        "type": "string",
                        "enum": ["rendering", "reference", "quotation", "thesis", "factory_feedback", "packaging", "other"],
                    },
                    "source_note": {"type": "string"},
                },
                "required": ["project_id", "attachment_id"],
            },
        },
    },
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
                        "enum": ["general", "factory_discussion", "cost_discovery", "design_feedback", "decision", "question", "risk", "packaging", "variant", "other"],
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
                    "status": {"type": "string", "enum": ["idea", "evaluating", "selected", "rejected", "launched"]},
                    "is_primary": {"type": "boolean", "description": "If true, this variant becomes the project's primary SKU."},
                    "target_factory_cost": {"type": "number"},
                    "target_msrp": {"type": "number"},
                    "material_summary": {"type": "string", "description": "Legacy free-text material summary; prefer the new blade_summary/handle_summary fields."},
                    "packaging_summary": {"type": "string", "description": "Legacy free-text packaging summary; prefer packaging_cost + dimensions_summary for new variants."},
                    "notes": {"type": "string"},
                    # v1.3 Build 05B — structured spec fields
                    "sales_format": {
                        "type": "string",
                        "enum": ["single", "combo", "colorway", "packaging_variant", "retail", "amazon", "other"],
                        "description": "Sales-format identifier: single product, combo pack, colorway variant, packaging variant, retail edition, Amazon edition, or other.",
                    },
                    "packaging_cost": {"type": "number", "description": "Per-unit packaging cost in USD (separate from factory cost)."},
                    "blade_summary": {"type": "string", "description": "Blade specs narrative, e.g. 'Steel: VG-10; Length: 3.5\"; Finish: stonewash; Edge: drop point'."},
                    "handle_summary": {"type": "string", "description": "Handle specs narrative, e.g. 'Material: G-10; Color: black; Texture: football leather'."},
                    "mechanism_summary": {"type": "string", "description": "Mechanism specs narrative, e.g. 'Lock: liner; Opening: flipper; Clip: deep-carry'."},
                    "dimensions_summary": {"type": "string", "description": "Dimensions narrative, e.g. 'Overall: 7.5\"; Closed: 4.1\"; Weight: 95g'."},
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
                    "component_type": {"type": "string", "enum": ["packaging", "accessory"]},
                    "name": {"type": "string"},
                    "target_cost": {"type": "number"},
                    "actual_cost": {"type": "number"},
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
                    "project_id": {"type": "integer"},
                    "phase_id": {"type": "integer"},
                    "planned_start_date": {"type": ["string", "null"], "format": "date"},
                    "planned_end_date": {"type": ["string", "null"], "format": "date"},
                    "reason": {"type": "string", "description": "Required — why the plan is changing"},
                },
                "required": ["project_id", "phase_id", "reason"],
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
            "description": "Propose a confirmed change to an allowlisted project field. Derived fields and status are rejected.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer"},
                    "field_name": {"type": "string", "description": "One of: name, brand, sku, product_type, project_owner, product_manager, engineer, factory, target_factory_cost, target_msrp, planned_launch_date, project_thesis"},
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
            "description": "Propose a new Good Idea. When project_id is supplied, confirmation creates the idea and links it to that project's Inspired By section.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "integer", "description": "Active project to link this idea to, when applicable"},
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
    {
        "type": "function",
        "function": {
            "name": "update_idea",
            "description": "Propose a small edit to an existing Good Idea after the user provides follow-up detail.",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_id": {"type": "integer"},
                    "fields": {
                        "type": "object",
                        "description": "Editable fields only: idea_type, source, source_detail, contributor, notes, description.",
                    },
                },
                "required": ["idea_id", "fields"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# 2. Permission rules per tool — consulted by the dispatcher
# ---------------------------------------------------------------------------

# Confirmed project-field updates. Derived and operational status fields stay
# excluded; sensitive values are allowed only because this path always reviews.
UPDATE_PROJECT_FIELD_ALLOWED: set[str] = {
    "name", "brand", "sku", "product_type",
    "project_owner", "product_manager", "engineer", "factory",
    "target_factory_cost", "target_msrp",
    "planned_launch_date", "project_thesis",
}
UPDATE_VARIANT_ALLOWED = {
    "variant_name", "sku", "status", "is_primary", "target_factory_cost",
    "actual_factory_cost", "target_msrp", "material_summary",
    "size_color_summary", "packaging_summary", "notes",
    # v1.3 Build 05B — structured spec fields
    "sales_format", "packaging_cost", "blade_summary", "handle_summary",
    "mechanism_summary", "dimensions_summary",
}
UPDATE_COMPONENT_ALLOWED = {
    "variant_id", "component_type", "name", "target_cost", "actual_cost", "notes",
}

# Roles allowed to call each tool. "needs_project" means the dispatcher must
# also verify can_edit_project() against the project_id in args.
# "needs_journal" means can_view_journal() must also pass.
TOOL_PERMISSIONS: dict[str, dict[str, Any]] = {
    "search_projects":                 {"require_role": ("admin", "pm", "viewer")},
    "get_project_context":             {"require_role": ("admin", "pm", "viewer")},
    "save_pending_attachment":         {"require_role": ("admin", "pm"), "needs_project": True},
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
    "adjust_phase_plan":               {"require_role": ("admin", "pm"), "needs_project": True},
    "update_file_comment":             {"require_role": ("admin", "pm"), "needs_project": True},
    "update_project_field":            {"require_role": ("admin", "pm"), "needs_project": True,
                                        "field_allowlist": UPDATE_PROJECT_FIELD_ALLOWED},
    "link_idea_to_project":            {"require_role": ("admin", "pm"), "needs_project": True},
    "create_idea":                     {"require_role": ("admin", "pm"), "optional_project": True},
    "update_idea":                     {"require_role": ("admin", "pm")},
}

CONFIRMATION_TOOLS = {
    "create_journal_entry",
    "create_variant", "update_variant", "set_primary_variant",
    "create_variant_component", "update_variant_component",
    "finish_phase", "adjust_phase_plan", "update_file_comment",
    "update_project_field",
    "save_pending_attachment",
    "create_idea", "link_idea_to_project", "update_idea",
}
UPDATE_IDEA_ALLOWED = {
    "idea_type", "source", "source_detail", "contributor", "notes", "description",
}


# ---------------------------------------------------------------------------
# 3. Dispatcher
# ---------------------------------------------------------------------------

def _err(error: str, **extra) -> dict:
    out = {"ok": False, "error": error}
    out.update(extra)
    return out


def _int_arg(args: dict, name: str) -> int | None:
    try:
        return int(args.get(name))
    except (TypeError, ValueError):
        return None


def _relationship_error(tool_name: str, args: dict, db, user) -> dict | None:
    """Validate object-ID tools against their owning project before proposal
    display and again on confirmation."""
    project_id = _int_arg(args, "project_id")
    if tool_name == "update_variant":
        variant = crud.get_variant(db, _int_arg(args, "variant_id") or 0)
        if not variant:
            return _err("variant_not_found")
        if not can_edit_project(user, variant.project):
            return _err("forbidden", reason="cannot_edit_project")
    elif tool_name == "set_primary_variant":
        variant = crud.get_variant(db, _int_arg(args, "variant_id") or 0)
        if not variant or variant.project_id != project_id:
            return _err("variant_not_found")
    elif tool_name == "create_variant_component" and args.get("variant_id") not in (None, "", 0, "0"):
        variant = crud.get_variant(db, _int_arg(args, "variant_id") or 0)
        if not variant or variant.project_id != project_id:
            return _err("variant_not_found")
    elif tool_name == "update_variant_component":
        component = crud.get_component(db, _int_arg(args, "component_id") or 0)
        if not component:
            return _err("component_not_found")
        if not can_edit_project(user, component.project):
            return _err("forbidden", reason="cannot_edit_project")
        fields = args.get("fields") or {}
        if isinstance(fields, dict) and fields.get("variant_id") not in (None, "", 0, "0"):
            variant = crud.get_variant(db, _int_arg(fields, "variant_id") or 0)
            if not variant or variant.project_id != component.project_id:
                return _err("variant_not_found")
    elif tool_name in ("finish_phase", "adjust_phase_plan"):
        phase = crud.get_phase(db, _int_arg(args, "phase_id") or 0)
        if not phase or phase.project_id != project_id:
            return _err("phase_not_found")
    elif tool_name == "update_file_comment":
        pf = db.query(ProjectFile).filter(ProjectFile.id == (_int_arg(args, "file_id") or 0)).first()
        if not pf or pf.project_id != project_id:
            return _err("file_not_found")
    elif tool_name == "save_pending_attachment":
        attachment_id = str(args.get("attachment_id") or "")
        try:
            get_pending_attachment(attachment_id, user.id)
        except AttachmentError as exc:
            return _err(exc.code, message=exc.message)
    return None


def dispatch(tool_name: str, args: dict, db, user, confirmed: bool = False) -> dict:
    """Look up the tool, enforce permissions, then call the handler.

    Order of checks (security-first; never skipped, even for unwired tools):
      1. Tool exists in TOOL_SCHEMAS              → else unknown_tool
      2. User passes role check per TOOL_PERMISSIONS → else forbidden
      3. needs_project / needs_journal sub-checks → else forbidden
      4. Field allowlist (for update_project_field) → else field_not_allowlisted
      5. Relationship checks for object-ID tools   → else record-specific error
      6. Confirmation guard for every AI write     → else confirmation_required
      7. Handler exists                            → else not_wired_until_build_21
      8. Call handler                              → return its result

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
        project_id = _int_arg(args, "project_id")
        if project_id is None:
            return _err("missing_argument", argument="project_id")
        project = crud.get_project(db, project_id)
        if project is None:
            return _err("project_not_found", project_id=project_id)
        if not can_edit_project(user, project):
            return _err("forbidden", reason="cannot_edit_project")

    # 3c. Some tools can operate globally but must enforce project ownership
    # whenever the model proposes a project-linked form of the action.
    if perms.get("optional_project") and args.get("project_id") is not None:
        project_id = _int_arg(args, "project_id")
        if project_id is None:
            return _err("invalid_argument", argument="project_id")
        project = crud.get_project(db, project_id)
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

    # 5. Relationship checks apply before a card is shown and again when the
    # reviewed proposal is confirmed.
    relationship_error = _relationship_error(tool_name, args, db, user)
    if relationship_error:
        return relationship_error

    # 6. Build 27 proposal guard for every chat-driven write.
    if tool_name in CONFIRMATION_TOOLS and not confirmed:
        return _err("confirmation_required", tool=tool_name)

    # 7. Handler exists?
    handler = _HANDLERS.get(tool_name)
    if handler is None:
        return _err("not_wired_until_build_21", tool=tool_name)

    # 8. Call handler
    return handler(args, db, user)


# ---------------------------------------------------------------------------
# 4. Real handlers
# ---------------------------------------------------------------------------

def _handle_search_projects(args: dict, db, user) -> dict:
    query = str(args.get("query") or "").strip().lower()
    projects = crud.get_projects(db)
    if query:
        projects = [
            p for p in projects
            if query in " ".join(
                str(value or "").lower()
                for value in (p.name, p.brand, p.sku, p.product_type)
            )
        ]
    results = []
    for project in projects[:10]:
        item = sanitize_project_for_user(project, user)
        item["id"] = project.id
        results.append(item)
    return {
        "ok": True, "read_only": True, "projects": results, "count": len(results),
        "message": f"Found {len(results)} matching project{'s' if len(results) != 1 else ''}.",
    }


def _handle_get_project_context(args: dict, db, user) -> dict:
    project_id = _int_arg(args, "project_id")
    project = crud.get_project(db, project_id or 0)
    if not project:
        return _err("project_not_found", project_id=project_id)
    context = sanitize_project_for_user(project, user)
    context["id"] = project.id
    context["linked_ideas"] = [
        {
            "id": item["idea"].id,
            "serial_number": item["idea"].serial_number,
            "name": item["idea"].name,
            "idea_type": item["idea"].idea_type,
            "source": item["idea"].source,
        }
        for item in crud.get_ideas_for_project(db, project.id)
    ]
    if can_view_journal(user):
        context["recent_journal"] = [
            {"entry_type": entry.entry_type, "entry_text": entry.entry_text}
            for entry in crud.get_journal_entries_for_project(db, project.id)[:5]
        ]
    return {
        "ok": True, "read_only": True, "project": context,
        "message": f"Loaded role-filtered context for {project.name}.",
    }


def _handle_save_pending_attachment(args: dict, db, user) -> dict:
    try:
        project_file = persist_pending_attachment(
            db,
            attachment_id=str(args.get("attachment_id") or ""),
            user_id=user.id,
            project_id=int(args["project_id"]),
            file_category=str(args.get("file_category") or "reference"),
            source_note=args.get("source_note"),
        )
    except AttachmentError as exc:
        return _err(exc.code, message=exc.message)
    return {
        "ok": True,
        "attachment_id": str(args.get("attachment_id") or ""),
        "file_id": project_file.id,
        "message": f"Saved {project_file.original_filename} to project files.",
    }

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
        changed_by="ai",
        source_type="ai_chat",
    )
    return {
        "ok": True,
        "entry_id": entry.id,
        "entry_type": entry.entry_type,
    }


def _handle_create_variant(args: dict, db, user) -> dict:
    project_id = int(args["project_id"])
    name = str(args.get("variant_name") or "").strip()
    if not name:
        return _err("missing_argument", argument="variant_name")
    variant = crud.create_variant(
        db, project_id, args, changed_by="ai", source_type="ai_chat",
    )
    return {
        "ok": True, "variant_id": variant.id,
        "message": f"Created variant: {variant.variant_name}.",
    }


def _handle_update_variant(args: dict, db, user) -> dict:
    fields = args.get("fields") or {}
    if not isinstance(fields, dict) or not fields:
        return _err("missing_argument", argument="fields")
    unexpected = sorted(set(fields) - UPDATE_VARIANT_ALLOWED)
    if unexpected:
        return _err("field_not_allowlisted", fields=unexpected)
    variant = crud.update_variant(
        db, int(args["variant_id"]), fields,
        changed_by="ai", source_type="ai_chat",
    )
    if not variant:
        return _err("variant_not_found")
    return {
        "ok": True, "variant_id": variant.id,
        "message": f"Updated variant: {variant.variant_name}.",
    }


def _handle_set_primary_variant(args: dict, db, user) -> dict:
    project_id = int(args["project_id"])
    variant_id = int(args["variant_id"])
    if not crud.set_primary_variant(
        db, project_id, variant_id, changed_by="ai", source_type="ai_chat",
    ):
        return _err("variant_not_found")
    return {"ok": True, "variant_id": variant_id, "message": "Primary variant updated."}


def _handle_create_variant_component(args: dict, db, user) -> dict:
    project_id = int(args["project_id"])
    name = str(args.get("name") or "").strip()
    if not name:
        return _err("missing_argument", argument="name")
    component = crud.create_variant_component(
        db, project_id, args, changed_by="ai", source_type="ai_chat",
    )
    return {
        "ok": True, "component_id": component.id,
        "message": f"Created {component.component_type}: {component.name}.",
    }


def _handle_update_variant_component(args: dict, db, user) -> dict:
    fields = args.get("fields") or {}
    if not isinstance(fields, dict) or not fields:
        return _err("missing_argument", argument="fields")
    unexpected = sorted(set(fields) - UPDATE_COMPONENT_ALLOWED)
    if unexpected:
        return _err("field_not_allowlisted", fields=unexpected)
    component = crud.update_variant_component(
        db, int(args["component_id"]), fields,
        changed_by="ai", source_type="ai_chat",
    )
    if not component:
        return _err("component_not_found")
    return {
        "ok": True, "component_id": component.id,
        "message": f"Updated component: {component.name}.",
    }


def _date_value(args: dict, name: str) -> tuple[date | None, dict | None]:
    value = args.get(name)
    if value in (None, ""):
        return None, None
    try:
        return date.fromisoformat(str(value)), None
    except ValueError:
        return None, _err("invalid_date", field=name)


def _handle_adjust_phase_plan(args: dict, db, user) -> dict:
    reason = str(args.get("reason") or "").strip()
    if not reason:
        return _err("missing_argument", argument="reason")
    data = {}
    for field in ("planned_start_date", "planned_end_date"):
        if field in args:
            value, error = _date_value(args, field)
            if error:
                return error
            data[field] = value
    if not data:
        return _err("missing_argument", argument="planned_start_date_or_planned_end_date")
    phase = crud.update_phase(
        db, int(args["phase_id"]), data,
        changed_by="ai", reason=reason, changed_by_user_id=user.id,
        source_type="ai_chat",
    )
    if not phase:
        return _err("phase_not_found")
    return {"ok": True, "phase_id": phase.id, "message": f"Updated phase plan: {phase.phase_name}."}


def _handle_finish_phase(args: dict, db, user) -> dict:
    result = crud.finish_phase(
        db, int(args["phase_id"]), changed_by="ai",
        changed_by_user_id=user.id, source_type="ai_chat",
    )
    if not result:
        return _err("phase_not_found")
    return {
        "ok": True, "phase_id": result["finished"].id,
        "message": f"Finished phase: {result['finished'].phase_name}.",
    }


def _handle_update_file_comment(args: dict, db, user) -> dict:
    pf = crud.update_file_comment(
        db, int(args["file_id"]), str(args.get("comment") or ""),
        changed_by="ai", source_type="ai_chat",
    )
    if not pf:
        return _err("file_not_found")
    return {"ok": True, "file_id": pf.id, "message": "File comment updated."}


def _handle_update_project_field(args: dict, db, user) -> dict:
    field_name = str(args.get("field_name") or "")
    value = args.get("new_value")
    if field_name in ("target_factory_cost", "target_msrp"):
        if value in ("", None):
            value_text = None
            value_number = None
        else:
            value_text = str(value).strip()
            value_number = crud.parse_simple_usd_price(value_text)
        data = {
            f"{field_name}_text": value_text,
            field_name: value_number,
        }
    elif field_name == "planned_launch_date":
        if value in ("", None):
            value = None
        else:
            try:
                value = date.fromisoformat(str(value))
            except ValueError:
                return _err("invalid_date", field=field_name)
        data = {field_name: value}
    else:
        data = {field_name: value}
    project = crud.update_project(
        db, int(args["project_id"]), data,
        changed_by="ai", source_type="ai_chat",
    )
    if not project:
        return _err("project_not_found")
    return {"ok": True, "project_id": project.id, "message": f"Updated {field_name.replace('_', ' ')}."}


def _handle_create_idea(args: dict, db, user) -> dict:
    name = str(args.get("name") or "").strip()
    if not name:
        return _err("missing_argument", argument="name")
    data = {
        field: args.get(field)
        for field in (
            "name", "description", "idea_type", "source", "source_detail",
            "contributor", "notes",
        )
    }
    data["name"] = name
    data["contributor"] = (
        data.get("contributor") or user.display_name or user.username
    )
    project_id = args.get("project_id")
    if project_id is not None:
        idea, _link = crud.create_and_link_idea(
            db,
            project_id=int(project_id),
            data=data,
            contributor_user_id=user.id,
            note=args.get("note"),
            changed_by="ai",
            source_type="ai_chat",
        )
    else:
        idea = crud.create_idea(db, data, contributor_user_id=user.id)
    unresolved = [
        field for field in ("idea_type", "source")
        if not args.get(field)
    ]
    return {
        "ok": True,
        "idea_id": idea.id,
        "serial_number": idea.serial_number,
        "linked_project_id": int(project_id) if project_id is not None else None,
        "unresolved_fields": unresolved,
        "message": f"Saved {idea.serial_number}: {idea.name}.",
    }


def _handle_link_idea_to_project(args: dict, db, user) -> dict:
    project_id = int(args["project_id"])
    idea_id = int(args["idea_id"])
    idea = crud.get_idea(db, idea_id)
    if idea is None:
        return _err("idea_not_found", idea_id=idea_id)
    link = crud.link_idea_to_project(
        db,
        project_id=project_id,
        idea_id=idea_id,
        linked_by_user_id=user.id,
        note=args.get("note"),
        changed_by="ai",
        source_type="ai_chat",
    )
    return {
        "ok": True,
        "idea_id": idea.id,
        "serial_number": idea.serial_number,
        "project_id": project_id,
        "message": f"Linked {idea.serial_number}: {idea.name}.",
        "already_linked": link is not None,
    }


def _handle_update_idea(args: dict, db, user) -> dict:
    idea_id = int(args.get("idea_id") or 0)
    fields = args.get("fields") or {}
    if not idea_id:
        return _err("missing_argument", argument="idea_id")
    if not isinstance(fields, dict) or not fields:
        return _err("missing_argument", argument="fields")
    unexpected = sorted(set(fields) - UPDATE_IDEA_ALLOWED)
    if unexpected:
        return _err("field_not_allowlisted", fields=unexpected)
    idea = crud.update_idea(
        db,
        idea_id=idea_id,
        data=fields,
        changed_by="ai",
        source_type="ai_chat",
    )
    if idea is None:
        return _err("idea_not_found", idea_id=idea_id)
    return {
        "ok": True,
        "idea_id": idea.id,
        "serial_number": idea.serial_number,
        "message": f"Updated {idea.serial_number}: {idea.name}.",
    }


_HANDLERS: dict[str, Any] = {
    "search_projects": _handle_search_projects,
    "get_project_context": _handle_get_project_context,
    "save_pending_attachment": _handle_save_pending_attachment,
    "create_journal_entry": _handle_create_journal_entry,
    "create_variant": _handle_create_variant,
    "update_variant": _handle_update_variant,
    "set_primary_variant": _handle_set_primary_variant,
    "create_variant_component": _handle_create_variant_component,
    "update_variant_component": _handle_update_variant_component,
    "finish_phase": _handle_finish_phase,
    "adjust_phase_plan": _handle_adjust_phase_plan,
    "update_file_comment": _handle_update_file_comment,
    "update_project_field": _handle_update_project_field,
    "create_idea": _handle_create_idea,
    "link_idea_to_project": _handle_link_idea_to_project,
    "update_idea": _handle_update_idea,
    # Delete, thesis-extraction, and journal-summary tools intentionally remain
    # absent until their dedicated follow-up slices.
}
