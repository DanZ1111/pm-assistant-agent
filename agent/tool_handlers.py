import json
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_
from models import Entity, EntityRecord, EntityLink, User
from agent.tools import PREFERRED_RECORD_TYPES
from permissions import apply_entity_visibility_filter


def check_write_permission(user: User) -> dict | None:
    """Returns an error dict if the user cannot write. Tool handlers return dicts, not HTTP exceptions."""
    if user.role == "viewer":
        return {"error": "Permission denied: viewers cannot modify entities"}
    return None


def handle_create_entity(args: dict, db: Session, user: User) -> dict:
    err = check_write_permission(user)
    if err:
        return err

    entity_type = args["entity_type"]

    # Only owners can create context entities
    if entity_type == "context" and user.role != "owner":
        return {"error": "Permission denied: only owners can create context entities"}

    # context entities default to restricted; projects/ideas default to workspace
    default_visibility = "restricted" if entity_type == "context" else "workspace"
    visibility = args.get("visibility", default_visibility)
    # Non-owners cannot force restricted visibility on non-context entities either
    if visibility == "restricted" and user.role != "owner":
        visibility = "workspace"

    entity = Entity(
        entity_type=entity_type,
        visibility=visibility,
        title=args["title"],
        status=args.get("status", "active"),
        product_phase=args.get("product_phase"),
        marketing_phase=args.get("marketing_phase"),
        priority=args.get("priority"),
        target_date=args.get("target_date"),
        short_summary=args.get("short_summary"),
    )
    db.add(entity)
    db.flush()  # get the id before adding records

    # If a project is created with an initial phase, record where it started
    if entity.entity_type == "project":
        for track, phase_val in [("product", entity.product_phase), ("marketing", entity.marketing_phase)]:
            if phase_val:
                record = EntityRecord(
                    entity_id=entity.id,
                    record_type="phase_change",
                    content=f"Project started at '{phase_val}' on the {track} track.",
                    structured_data={"track": track, "old_phase": None, "new_phase": phase_val},
                    source="system",
                )
                db.add(record)

    if args.get("initial_note"):
        record = EntityRecord(
            entity_id=entity.id,
            record_type="note",
            content=args["initial_note"],
            source="chat",
        )
        db.add(record)

    db.commit()
    db.refresh(entity)
    return {
        "id": entity.id,
        "title": entity.title,
        "entity_type": entity.entity_type,
        "status": entity.status,
        "visibility": entity.visibility,
    }


def handle_update_entity(args: dict, db: Session, user: User) -> dict:
    err = check_write_permission(user)
    if err:
        return err

    q = db.query(Entity).filter(Entity.id == args["entity_id"])
    q = apply_entity_visibility_filter(q, user)
    entity = q.first()
    if not entity:
        return {"error": f"Entity {args['entity_id']} not found or access denied"}

    phase_changes = []

    new_product_phase = args.get("product_phase")
    if new_product_phase is not None and new_product_phase != entity.product_phase:
        phase_changes.append({
            "track": "product",
            "old_phase": entity.product_phase,
            "new_phase": new_product_phase,
            "rationale": args.get("phase_change_rationale"),
        })
        entity.product_phase = new_product_phase

    new_marketing_phase = args.get("marketing_phase")
    if new_marketing_phase is not None and new_marketing_phase != entity.marketing_phase:
        phase_changes.append({
            "track": "marketing",
            "old_phase": entity.marketing_phase,
            "new_phase": new_marketing_phase,
            "rationale": args.get("phase_change_rationale"),
        })
        entity.marketing_phase = new_marketing_phase

    for field in ["title", "status", "priority", "target_date", "short_summary"]:
        if field in args and args[field] is not None:
            setattr(entity, field, args[field])

    entity.updated_at = datetime.utcnow()

    # Auto-create phase_change records in the backend — LLM does not do this manually
    for change in phase_changes:
        old = change["old_phase"] or "not started"
        new = change["new_phase"]
        track = change["track"]
        content = f"Phase updated from '{old}' to '{new}' on the {track} track."
        if change.get("rationale"):
            content += f" {change['rationale']}"

        record = EntityRecord(
            entity_id=entity.id,
            record_type="phase_change",
            content=content,
            structured_data=change,
            source="system",
        )
        db.add(record)

    db.commit()
    db.refresh(entity)
    return {
        "id": entity.id,
        "updated": True,
        "phase_changes_recorded": len(phase_changes),
    }


def handle_add_record(args: dict, db: Session, user: User) -> dict:
    err = check_write_permission(user)
    if err:
        return err

    q = db.query(Entity).filter(Entity.id == args["entity_id"])
    q = apply_entity_visibility_filter(q, user)
    entity = q.first()
    if not entity:
        return {"error": f"Entity {args['entity_id']} not found or access denied"}

    record_type = args["record_type"]
    is_new_type = record_type not in PREFERRED_RECORD_TYPES

    record = EntityRecord(
        entity_id=args["entity_id"],
        record_type=record_type,
        content=args["content"],
        structured_data=args.get("structured_data"),
        source="chat",
    )
    db.add(record)

    entity.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(record)

    return {
        "id": record.id,
        "record_type": record_type,
        "new_type_flag": is_new_type,
    }


def handle_get_entity(args: dict, db: Session, user: User) -> dict:
    q = db.query(Entity).filter(Entity.id == args["entity_id"])
    q = apply_entity_visibility_filter(q, user)
    entity = q.first()
    if not entity:
        return {"error": f"Entity {args['entity_id']} not found or access denied"}

    records_limit = args.get("records_limit", 20)

    # Fetch most recent N records, then return in chronological order
    recent_records = (
        db.query(EntityRecord)
        .filter(EntityRecord.entity_id == entity.id)
        .order_by(EntityRecord.created_at.desc())
        .limit(records_limit)
        .all()
    )
    records = sorted(recent_records, key=lambda r: r.created_at or datetime.min)

    # Outgoing links (from this entity)
    outgoing = db.query(EntityLink).filter(EntityLink.from_entity_id == entity.id).all()
    # Incoming links (to this entity)
    incoming = db.query(EntityLink).filter(EntityLink.to_entity_id == entity.id).all()

    def visible_entity_title(eid):
        q = db.query(Entity).filter(Entity.id == eid)
        q = apply_entity_visibility_filter(q, user)
        e = q.first()
        return e.title if e else "[restricted]"

    links = []
    for lnk in outgoing:
        links.append({
            "direction": "outgoing",
            "link_type": lnk.link_type,
            "other_entity_id": lnk.to_entity_id,
            "other_entity_title": visible_entity_title(lnk.to_entity_id),
            "note": lnk.note,
        })
    for lnk in incoming:
        links.append({
            "direction": "incoming",
            "link_type": lnk.link_type,
            "other_entity_id": lnk.from_entity_id,
            "other_entity_title": visible_entity_title(lnk.from_entity_id),
            "note": lnk.note,
        })

    return {
        "id": entity.id,
        "entity_type": entity.entity_type,
        "title": entity.title,
        "status": entity.status,
        "product_phase": entity.product_phase,
        "marketing_phase": entity.marketing_phase,
        "priority": entity.priority,
        "target_date": entity.target_date,
        "short_summary": entity.short_summary,
        "created_at": entity.created_at.isoformat() if entity.created_at else None,
        "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        "records": [
            {
                "id": r.id,
                "record_type": r.record_type,
                "content": r.content,
                "structured_data": r.structured_data,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
        "links": links,
    }


def handle_search_entities(args: dict, db: Session, user: User) -> dict:
    query = args["query"]

    # Entity-level matches: title + short_summary
    entity_q = db.query(Entity).filter(
        or_(
            Entity.title.ilike(f"%{query}%"),
            Entity.short_summary.ilike(f"%{query}%"),
        )
    )
    entity_q = apply_entity_visibility_filter(entity_q, user)
    if args.get("entity_type"):
        entity_q = entity_q.filter(Entity.entity_type == args["entity_type"])
    if args.get("status"):
        entity_q = entity_q.filter(Entity.status == args["status"])

    entity_matches = entity_q.all()

    # Record-level matches: entity_records.content
    record_q = (
        db.query(EntityRecord.entity_id)
        .filter(EntityRecord.content.ilike(f"%{query}%"))
        .distinct()
    )
    record_entity_ids = {row[0] for row in record_q.all()}

    if record_entity_ids:
        record_entities_q = db.query(Entity).filter(Entity.id.in_(record_entity_ids))
        record_entities_q = apply_entity_visibility_filter(record_entities_q, user)
        if args.get("entity_type"):
            record_entities_q = record_entities_q.filter(Entity.entity_type == args["entity_type"])
        if args.get("status"):
            record_entities_q = record_entities_q.filter(Entity.status == args["status"])
        record_entities = record_entities_q.all()
    else:
        record_entities = []

    # Deduplicate by entity id, entity-level matches first
    seen = set()
    combined = []
    for e in entity_matches + record_entities:
        if e.id not in seen:
            seen.add(e.id)
            combined.append(e)

    # Sort by updated_at desc, cap at 10
    combined.sort(key=lambda e: e.updated_at or datetime.min, reverse=True)
    entities = combined[:10]

    return {
        "results": [
            {
                "id": e.id,
                "entity_type": e.entity_type,
                "title": e.title,
                "status": e.status,
                "product_phase": e.product_phase,
                "marketing_phase": e.marketing_phase,
                "short_summary": e.short_summary,
            }
            for e in entities
        ],
        "count": len(entities),
    }


def handle_list_entities(args: dict, db: Session, user: User) -> dict:
    q = db.query(Entity)
    q = apply_entity_visibility_filter(q, user)

    if args.get("entity_type"):
        q = q.filter(Entity.entity_type == args["entity_type"])
    if args.get("status"):
        q = q.filter(Entity.status == args["status"])

    entities = q.order_by(Entity.updated_at.desc()).all()

    return {
        "entities": [
            {
                "id": e.id,
                "entity_type": e.entity_type,
                "title": e.title,
                "status": e.status,
                "product_phase": e.product_phase,
                "marketing_phase": e.marketing_phase,
                "priority": e.priority,
                "short_summary": e.short_summary,
                "updated_at": e.updated_at.isoformat() if e.updated_at else None,
            }
            for e in entities
        ],
        "count": len(entities),
    }


def handle_promote_idea(args: dict, db: Session, user: User) -> dict:
    err = check_write_permission(user)
    if err:
        return err

    q = db.query(Entity).filter(Entity.id == args["entity_id"])
    q = apply_entity_visibility_filter(q, user)
    entity = q.first()
    if not entity:
        return {"error": f"Entity {args['entity_id']} not found or access denied"}
    if entity.entity_type != "idea":
        return {"error": f"Entity {args['entity_id']} is already a project"}

    entity.entity_type = "project"
    entity.updated_at = datetime.utcnow()

    # Only set phases that were explicitly passed — never invent the other track
    phases_set = []
    if args.get("product_phase"):
        entity.product_phase = args["product_phase"]
        phases_set.append(("product", args["product_phase"]))
    if args.get("marketing_phase"):
        entity.marketing_phase = args["marketing_phase"]
        phases_set.append(("marketing", args["marketing_phase"]))

    note_text = args.get("note", "")
    content = "Promoted from idea to project."
    if note_text:
        content += f" {note_text}"

    record = EntityRecord(
        entity_id=entity.id,
        record_type="milestone",
        content=content,
        structured_data={"track": None, "event": "idea_promoted"},
        source="system",
    )
    db.add(record)

    # Write phase_change records for any phases set at promotion time
    for track, phase_val in phases_set:
        record = EntityRecord(
            entity_id=entity.id,
            record_type="phase_change",
            content=f"Phase set to '{phase_val}' on the {track} track at promotion.",
            structured_data={"track": track, "old_phase": None, "new_phase": phase_val},
            source="system",
        )
        db.add(record)

    db.commit()
    db.refresh(entity)
    return {"id": entity.id, "promoted": True, "title": entity.title}


def handle_link_entities(args: dict, db: Session, user: User) -> dict:
    err = check_write_permission(user)
    if err:
        return err

    from_id = args["from_entity_id"]
    to_id = args["to_entity_id"]
    link_type = args["link_type"]

    from_q = db.query(Entity).filter(Entity.id == from_id)
    from_q = apply_entity_visibility_filter(from_q, user)
    from_entity = from_q.first()
    if not from_entity:
        return {"error": f"Entity {from_id} not found or access denied"}

    to_q = db.query(Entity).filter(Entity.id == to_id)
    to_q = apply_entity_visibility_filter(to_q, user)
    to_entity = to_q.first()
    if not to_entity:
        return {"error": f"Entity {to_id} not found or access denied"}

    # Check for duplicate link
    existing = (
        db.query(EntityLink)
        .filter(
            EntityLink.from_entity_id == from_id,
            EntityLink.to_entity_id == to_id,
            EntityLink.link_type == link_type,
        )
        .first()
    )
    if existing:
        return {"id": existing.id, "created": False, "note": "Link already exists"}

    link = EntityLink(
        from_entity_id=from_id,
        to_entity_id=to_id,
        link_type=link_type,
        note=args.get("note"),
    )
    db.add(link)
    db.commit()
    db.refresh(link)

    return {
        "id": link.id,
        "created": True,
        "from": from_entity.title,
        "to": to_entity.title,
        "link_type": link_type,
    }


TOOL_HANDLERS = {
    "create_entity": handle_create_entity,
    "update_entity": handle_update_entity,
    "add_record": handle_add_record,
    "get_entity": handle_get_entity,
    "search_entities": handle_search_entities,
    "list_entities": handle_list_entities,
    "promote_idea": handle_promote_idea,
    "link_entities": handle_link_entities,
}


def dispatch_tool(tool_name: str, arguments_json: str, db: Session, user: User) -> dict:
    try:
        args = json.loads(arguments_json)
    except json.JSONDecodeError:
        return {"error": "Invalid tool arguments JSON"}

    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Unknown tool: {tool_name}"}

    return handler(args, db, user)
