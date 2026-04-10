PREFERRED_RECORD_TYPES = {
    "note", "decision", "blocker", "next_action",
    "milestone", "origin", "insight", "question",
    "phase_change",
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_entity",
            "description": (
                "Create a new project or idea. "
                "Only set priority and target_date when the user explicitly states them — do not infer or invent them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "enum": ["project", "idea", "context"],
                        "description": "project = active initiative with phases; idea = vague concept not yet ready; context = business-level knowledge (brand, market assumptions, platform rules, pricing psychology, etc.) — no phases.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Short name for the entity.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "dormant", "done", "archived"],
                        "description": "Defaults to active.",
                    },
                    "product_phase": {
                        "type": "string",
                        "description": "Current product development phase. Only set if stated by the user.",
                    },
                    "marketing_phase": {
                        "type": "string",
                        "description": "Current marketing phase. Only set if stated by the user.",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "Only set when the user explicitly states it.",
                    },
                    "target_date": {
                        "type": "string",
                        "description": "ISO date string (YYYY-MM-DD). Only set when explicitly stated.",
                    },
                    "short_summary": {
                        "type": "string",
                        "description": "1-2 sentence summary of what this entity is.",
                    },
                    "initial_note": {
                        "type": "string",
                        "description": "Additional context to store as an initial note record.",
                    },
                },
                "required": ["entity_type", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_entity",
            "description": (
                "Update an existing entity's stable fields. "
                "When product_phase or marketing_phase is changed, the backend automatically creates a phase_change record — "
                "do NOT call add_record separately for phase changes. "
                "Only update priority/target_date when explicitly stated by the user. "
                "Update short_summary conservatively — only when new info genuinely changes the current state."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "integer",
                        "description": "ID of the entity to update.",
                    },
                    "title": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["active", "dormant", "done", "archived"],
                        "description": "Only update when user explicitly states the project status changed.",
                    },
                    "product_phase": {
                        "type": "string",
                        "description": "New product phase. Backend will write phase_change record automatically.",
                    },
                    "marketing_phase": {
                        "type": "string",
                        "description": "New marketing phase. Backend will write phase_change record automatically.",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "urgent"],
                        "description": "Only update when explicitly stated.",
                    },
                    "target_date": {
                        "type": "string",
                        "description": "ISO date. Only update when explicitly stated.",
                    },
                    "short_summary": {
                        "type": "string",
                        "description": "Updated summary. Preserve important ongoing context. Be conservative.",
                    },
                    "phase_change_rationale": {
                        "type": "string",
                        "description": "Why the phase changed. Stored in the auto-created phase_change record.",
                    },
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_record",
            "description": (
                "Add a record to an entity. Use for notes, decisions, blockers, milestones, insights, questions, next actions, origins. "
                "This is the primary tool for all rich information about an entity. "
                "Always include structured_data.track ('product', 'marketing', or null) to indicate which workstream the record belongs to. "
                "Do NOT use this for phase changes — those are handled automatically by update_entity."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "integer",
                        "description": "ID of the entity.",
                    },
                    "record_type": {
                        "type": "string",
                        "description": (
                            "Type of record. Preferred: note, decision, blocker, next_action, milestone, origin, insight, question. "
                            "Other types are accepted but will be flagged as a suggestion to formalize."
                        ),
                    },
                    "content": {
                        "type": "string",
                        "description": (
                            "Clear narrative of what happened, was decided, or was noted. "
                            "Preserve the original reasoning — do not over-polish."
                        ),
                    },
                    "structured_data": {
                        "type": "object",
                        "description": "Optional structured fields. Always include 'track' where relevant.",
                        "properties": {
                            "track": {
                                "type": "string",
                                "description": "Which workstream: 'product', 'marketing', or null for both/unspecified.",
                            },
                        },
                    },
                },
                "required": ["entity_id", "record_type", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_entity",
            "description": (
                "Get full details and records for a specific entity. "
                "Use before updating when you need current context, or when the user asks about a specific project. "
                "Also use to retrieve business context entities when they're relevant to the current question. "
                "Returns records in chronological order. Default limit is 20 most recent — pass a higher value only when full history is needed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "integer",
                        "description": "ID of the entity.",
                    },
                    "records_limit": {
                        "type": "integer",
                        "description": "Max number of records to return (default 20, most recent first then returned in chronological order). Omit for default.",
                    },
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_entities",
            "description": (
                "Find entities by keyword. Searches title, short_summary, and all record history. "
                "Returns up to 10 deduplicated results. "
                "Use to resolve references like 'the fish knife' or 'Damascus project', or to find anything related to a topic (e.g. 'Guangzhou', 'TikTok pricing')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search text matched against title, short_summary, and record content.",
                    },
                    "entity_type": {
                        "type": "string",
                        "enum": ["project", "idea", "context"],
                        "description": "Optional filter by type.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "dormant", "done", "archived"],
                        "description": "Optional filter by status.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_entities",
            "description": (
                "List entities with their current state. "
                "Use when the user asks for an overview, review, or status of projects/ideas. "
                "Also use proactively to discover what context entities already exist before creating a new one — avoid duplicates. "
                "Supports filtering by entity_type and status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_type": {
                        "type": "string",
                        "enum": ["project", "idea", "context"],
                        "description": "Filter by type — omit to return all types.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "dormant", "done", "archived"],
                        "description": "Filter by status — omit to return all statuses.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "promote_idea",
            "description": (
                "Promote an idea to a project in-place. Changes entity_type from 'idea' to 'project'. "
                "Only set the phase(s) that the user explicitly stated — do not invent or default the other track. "
                "Writes a milestone record automatically."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entity_id": {
                        "type": "integer",
                        "description": "ID of the idea to promote.",
                    },
                    "product_phase": {
                        "type": "string",
                        "description": "Initial product phase — only if the user stated it.",
                    },
                    "marketing_phase": {
                        "type": "string",
                        "description": "Initial marketing phase — only if the user stated it.",
                    },
                    "note": {
                        "type": "string",
                        "description": "Optional note about why or how this became a project.",
                    },
                },
                "required": ["entity_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "link_entities",
            "description": (
                "Create a directional link between two entities. "
                "Use 'inspired_by' when one entity meaningfully influenced the creation or direction of another. "
                "Use 'related_to' when two entities are connected but neither inspired the other — keep this conservative, not a vague catch-all. "
                "Links appear in get_entity results for both entities."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "from_entity_id": {
                        "type": "integer",
                        "description": "The entity that has the relationship (e.g. the one that was inspired).",
                    },
                    "to_entity_id": {
                        "type": "integer",
                        "description": "The entity being linked to (e.g. the source of inspiration).",
                    },
                    "link_type": {
                        "type": "string",
                        "enum": ["inspired_by", "related_to"],
                        "description": "Type of relationship.",
                    },
                    "note": {
                        "type": "string",
                        "description": "Optional short note explaining the connection.",
                    },
                },
                "required": ["from_entity_id", "to_entity_id", "link_type"],
            },
        },
    },
]
