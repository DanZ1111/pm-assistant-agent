import os
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models import Project, ProjectPhase, ProjectFile, ProjectChange, AIMessage

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "uploads")

# ---------------------------------------------------------------------------
# Field level definitions
# ---------------------------------------------------------------------------

CRITICAL_FIELDS = [
    "brand", "product_manager", "engineer", "factory",
    "target_factory_cost", "target_msrp", "planned_launch_date", "project_thesis",
]

RECOMMENDED_FIELDS = ["sku", "product_type"]

PHASE_TEMPLATES = {
    "single": [
        ("Design", "design", 1),
        ("Engineering Review", "engineering", 2),
        ("Prototype 1", "prototype", 3),
        ("Prototype Review", "review", 4),
        ("Pre-production Sample", "production", 5),
        ("Mass Production", "production", 6),
        ("Launch Prep", "launch", 7),
        ("Launch", "launch", 8),
    ],
    "double": [
        ("Design", "design", 1),
        ("Engineering Review", "engineering", 2),
        ("Prototype 1", "prototype", 3),
        ("Prototype 1 Review", "review", 4),
        ("Prototype 2", "prototype", 5),
        ("Prototype 2 Review", "review", 6),
        ("Pre-production Sample", "production", 7),
        ("Mass Production", "production", 8),
        ("Launch Prep", "launch", 9),
        ("Launch", "launch", 10),
    ],
}

# ---------------------------------------------------------------------------
# Change log
# ---------------------------------------------------------------------------

def write_change(
    db: Session,
    project_id: int,
    change_type: str,
    changed_by: str = "user",
    field_name: str = None,
    old_value: str = None,
    new_value: str = None,
    summary: str = None,
    reason: str = None,
    delay_impact_days: int = None,
    source_type: str = "manual_edit",
) -> ProjectChange:
    change = ProjectChange(
        project_id=project_id,
        changed_by=changed_by,
        change_type=change_type,
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        summary=summary,
        reason=reason,
        delay_impact_days=delay_impact_days,
        source_type=source_type,
    )
    db.add(change)
    return change

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def get_project_health(project: Project, phases: list, files: list) -> dict:
    critical_missing = []
    recommended_missing = []

    for field in ["brand", "product_manager", "engineer", "factory"]:
        if not getattr(project, field):
            critical_missing.append(field)

    if not project.target_factory_cost:
        critical_missing.append("target_factory_cost")
    if not project.target_msrp:
        critical_missing.append("target_msrp")
    if not project.planned_launch_date:
        critical_missing.append("planned_launch_date")
    if not project.project_thesis or len(project.project_thesis.strip()) < 80:
        critical_missing.append("project_thesis")
    if not phases:
        critical_missing.append("timeline_phases")

    # active_phase_planned_end_date is recommended (not critical) until Build 2
    # adds the phase-editing UI — flagging it as critical would mark every new
    # project as incomplete before timeline management exists.
    if phases:
        active_phase = next(
            (p for p in phases if p.status not in ("done", "skipped")), None
        )
        if active_phase and not active_phase.planned_end_date:
            recommended_missing.append("active_phase_planned_end_date")

    if not project.sku:
        recommended_missing.append("sku")
    if not project.product_type:
        recommended_missing.append("product_type")
    if not files:
        recommended_missing.append("at_least_one_file")
    if phases and any(not p.owner for p in phases):
        recommended_missing.append("phase_owners")

    return {
        "needs_info": len(critical_missing) > 0,
        "critical_missing": critical_missing,
        "recommended_missing": recommended_missing,
        "critical_count": len(critical_missing),
        "recommended_count": len(recommended_missing),
    }

# ---------------------------------------------------------------------------
# Delay calculation
# ---------------------------------------------------------------------------

def calculate_delay(project: Project, phases: list) -> dict | None:
    today = date.today()
    delayed = [
        p for p in phases
        if p.planned_end_date
        and p.planned_end_date < today
        and p.status not in ("done", "skipped")
    ]
    if not delayed:
        return None
    worst = max(delayed, key=lambda p: (today - p.planned_end_date).days)
    delay_days = (today - worst.planned_end_date).days
    estimated_launch = None
    if project.planned_launch_date:
        estimated_launch = project.planned_launch_date + timedelta(days=delay_days)
    return {
        "blocking_phase": worst.phase_name,
        "days_late": delay_days,
        "estimated_launch": estimated_launch,
    }

# ---------------------------------------------------------------------------
# current_stage derivation
# ---------------------------------------------------------------------------

def derive_current_stage(phases: list) -> str | None:
    for p in sorted(phases, key=lambda x: x.phase_order):
        if p.status not in ("done", "skipped"):
            return p.phase_name
    return phases[-1].phase_name if phases else None

def recalculate_stage_and_delay(db: Session, project_id: int) -> None:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return
    phases = db.query(ProjectPhase).filter(ProjectPhase.project_id == project_id).order_by(ProjectPhase.phase_order).all()
    project.current_stage = derive_current_stage(phases)
    delay = calculate_delay(project, phases)
    project.estimated_launch_date = delay["estimated_launch"] if delay else None
    project.updated_at = datetime.utcnow()
    db.commit()

# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

def get_project(db: Session, project_id: int) -> Project | None:
    return db.query(Project).filter(Project.id == project_id).first()

def get_projects(db: Session, status: str = None, brand: str = None, search: str = None) -> list[Project]:
    q = db.query(Project)
    if status and status != "all":
        q = q.filter(Project.status == status)
    if brand:
        q = q.filter(Project.brand == brand)
    if search:
        q = q.filter(Project.name.ilike(f"%{search}%"))
    return q.order_by(Project.updated_at.desc()).all()

def get_all_brands(db: Session) -> list[str]:
    rows = db.query(Project.brand).filter(Project.brand.isnot(None)).distinct().all()
    return sorted([r[0] for r in rows if r[0]])


def get_projects_for_user(db: Session, user) -> list[Project]:
    """Build 19 — projects the given user is the PM of.
    Admin sees all projects; PM sees only projects where product_manager matches their username
    (case-insensitive); viewer gets an empty list (the /my-projects route also redirects them away).
    """
    if user is None:
        return []
    if user.role == "admin":
        return get_projects(db)
    if user.role == "pm":
        uname = (user.username or "").strip().lower()
        if not uname:
            return []
        return (
            db.query(Project)
            .filter(func.lower(Project.product_manager) == uname)
            .order_by(Project.updated_at.desc())
            .all()
        )
    return []  # viewer

def create_project(db: Session, data: dict, prototype_rounds: str = "single") -> Project:
    project = Project(**{k: v for k, v in data.items() if v != "" and v is not None})
    db.add(project)
    db.flush()

    # Apply phase template
    template = PHASE_TEMPLATES.get(prototype_rounds, PHASE_TEMPLATES["single"])
    for phase_name, phase_type, order in template:
        phase = ProjectPhase(
            project_id=project.id,
            phase_name=phase_name,
            phase_type=phase_type,
            phase_order=order,
            status="not_started",
        )
        db.add(phase)

    db.flush()
    phases = db.query(ProjectPhase).filter(ProjectPhase.project_id == project.id).order_by(ProjectPhase.phase_order).all()
    project.current_stage = derive_current_stage(phases)

    write_change(
        db, project.id, "event_note", changed_by="user",
        summary=f"Project '{project.name}' created with {prototype_rounds}-prototype template ({len(template)} phases).",
        source_type="manual_edit",
    )

    db.commit()
    db.refresh(project)
    return project

def update_project(
    db: Session, project_id: int, data: dict,
    changed_by: str = "user", source_type: str = "manual_edit",
) -> Project | None:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None

    DISPLAY_NAMES = {
        "target_factory_cost": "Target Factory Cost",
        "target_msrp": "Target MSRP",
        "planned_launch_date": "Planned Launch Date",
        "project_thesis": "Product Thesis",
        "product_manager": "Product Manager",
    }

    for field, new_val in data.items():
        if new_val == "":
            new_val = None
        old_val = getattr(project, field, None)
        if str(old_val or "") != str(new_val or ""):
            display = DISPLAY_NAMES.get(field, field.replace("_", " ").title())
            write_change(
                db, project_id, "field_update", changed_by=changed_by,
                field_name=field,
                old_value=str(old_val) if old_val is not None else None,
                new_value=str(new_val) if new_val is not None else None,
                summary=f"{display} updated.",
                source_type=source_type,
            )
            setattr(project, field, new_val)

    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    return project

def archive_project(db: Session, project_id: int) -> Project | None:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None
    old_status = project.status
    project.status = "archived"
    project.archived_at = datetime.utcnow()
    project.updated_at = datetime.utcnow()
    write_change(
        db, project_id, "field_update", changed_by="user",
        field_name="status", old_value=old_status, new_value="archived",
        summary="Project archived.", source_type="manual_edit",
    )
    db.commit()
    db.refresh(project)
    return project

def delete_project(db: Session, project_id: int) -> bool:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return False
    db.delete(project)
    db.commit()
    return True

# ---------------------------------------------------------------------------
# Enriched project list (project + health + delay)
# ---------------------------------------------------------------------------

def get_projects_enriched(db: Session, status: str = None, brand: str = None, search: str = None) -> list[dict]:
    projects = get_projects(db, status=status, brand=brand, search=search)
    result = []
    for p in projects:
        phases = p.phases
        files = p.files
        health = get_project_health(p, phases, files)
        delay = calculate_delay(p, phases)
        latest_rendering = get_latest_rendering(db, p.id)
        result.append({
            "project": p,
            "health": health,
            "delay": delay,
            "latest_rendering": latest_rendering,
        })
    return result

# ---------------------------------------------------------------------------
# Phase CRUD
# ---------------------------------------------------------------------------

def get_phase(db: Session, phase_id: int) -> ProjectPhase | None:
    return db.query(ProjectPhase).filter(ProjectPhase.id == phase_id).first()

def add_phase(db: Session, project_id: int, data: dict) -> ProjectPhase:
    # Place new phase at the end
    max_order = db.query(func.max(ProjectPhase.phase_order)).filter(
        ProjectPhase.project_id == project_id
    ).scalar() or 0
    phase = ProjectPhase(
        project_id=project_id,
        phase_name=data["phase_name"],
        phase_type=data.get("phase_type") or None,
        phase_order=max_order + 1,
        status=data.get("status", "not_started"),
        planned_start_date=data.get("planned_start_date"),
        planned_end_date=data.get("planned_end_date"),
        owner=data.get("owner") or None,
        notes=data.get("notes") or None,
    )
    db.add(phase)
    db.flush()
    write_change(
        db, project_id, "phase_update", changed_by="user",
        summary=f"Phase '{phase.phase_name}' added.",
        source_type="manual_edit",
    )
    db.commit()
    recalculate_stage_and_delay(db, project_id)
    return phase

PLAN_DATE_FIELDS = ("planned_start_date", "planned_end_date")


def update_phase(
    db: Session, phase_id: int, data: dict,
    changed_by: str = "user", reason: str = "",
    changed_by_user_id: int | None = None,
    source_type: str = "manual_edit",
) -> ProjectPhase | None:
    """Build 17 — Timeline 2.0. Plan-date changes are tracked separately:
    every change to planned_start_date or planned_end_date writes a
    phase_plan_changes row recording the old/new date and the reason.
    Empty reason on a plan-date change is allowed (so existing flows don't
    break), but the UI requires it for new edits.
    """
    from app.models import PhasePlanChange  # local — avoid circular at module load

    phase = db.query(ProjectPhase).filter(ProjectPhase.id == phase_id).first()
    if not phase:
        return None

    changes = []
    plan_date_changes = []
    fields = [
        "phase_name", "phase_type", "status",
        "planned_start_date", "planned_end_date",
        "actual_start_date", "actual_end_date",
        "owner", "notes",
    ]
    for field in fields:
        if field not in data:
            continue
        new_val = data[field] if data[field] != "" else None
        old_val = getattr(phase, field)
        if str(old_val or "") != str(new_val or ""):
            changes.append((field, old_val, new_val))
            setattr(phase, field, new_val)
            if field in PLAN_DATE_FIELDS:
                plan_date_changes.append((field, old_val, new_val))

    phase.updated_at = datetime.utcnow()

    # Write a phase_plan_changes row for each plan-date shift
    for field, old_val, new_val in plan_date_changes:
        db.add(PhasePlanChange(
            phase_id=phase.id,
            field_changed=field,
            old_date=old_val if old_val else None,
            new_date=new_val if new_val else None,
            reason=(reason or "").strip() or "(no reason given)",
            changed_by_user_id=changed_by_user_id,
        ))

    if changes:
        summary_parts = [f"{f.replace('_', ' ')}: {o or '—'} → {n or '—'}" for f, o, n in changes]
        write_change(
            db, phase.project_id, "phase_update", changed_by=changed_by,
            field_name=phase.phase_name,
            summary=f"Phase '{phase.phase_name}' updated: {'; '.join(summary_parts)}"
                    + (f" (reason: {reason.strip()})" if reason and plan_date_changes else ""),
            source_type=source_type,
        )

    db.commit()
    recalculate_stage_and_delay(db, phase.project_id)
    return phase


def get_plan_changes_for_phase(db: Session, phase_id: int) -> list:
    """Newest first — used by the timeline history accordion."""
    from app.models import PhasePlanChange
    return (
        db.query(PhasePlanChange)
        .filter(PhasePlanChange.phase_id == phase_id)
        .order_by(PhasePlanChange.changed_at.desc())
        .all()
    )


def get_plan_changes_by_project(db: Session, project_id: int) -> dict:
    """Returns {phase_id: [PhasePlanChange, ...]} for the whole project.
    One query — used by the project detail page so the timeline section
    doesn't N+1 against phase_plan_changes."""
    from app.models import PhasePlanChange
    phase_ids = [p.id for p in db.query(ProjectPhase.id).filter(
        ProjectPhase.project_id == project_id).all()]
    if not phase_ids:
        return {}
    rows = (
        db.query(PhasePlanChange)
        .filter(PhasePlanChange.phase_id.in_(phase_ids))
        .order_by(PhasePlanChange.changed_at.desc())
        .all()
    )
    out = {pid: [] for pid in phase_ids}
    for r in rows:
        out[r.phase_id].append(r)
    return out


def finish_phase(
    db: Session, phase_id: int,
    changed_by: str = "user", changed_by_user_id: int | None = None,
    source_type: str = "manual_edit",
) -> dict | None:
    """Build 17 — one-click 'mark phase done and advance next phase'.
    - Current phase: status=done, actual_end_date=today.
      If actual_start_date is None, also set it (best guess = planned_start_date or today).
    - Next phase (next phase_order in same project that is not done/skipped):
      status=in_progress, actual_start_date=today (if not already set).
    Returns {'finished': phase, 'next': next_phase_or_None}, or None if phase
    not found.
    """
    phase = db.query(ProjectPhase).filter(ProjectPhase.id == phase_id).first()
    if not phase:
        return None
    today = date.today()

    # Finish the current phase
    if not phase.actual_start_date:
        phase.actual_start_date = phase.planned_start_date or today
    phase.actual_end_date = today
    phase.status = "done"
    phase.updated_at = datetime.utcnow()

    # Find the next phase to advance
    siblings = (
        db.query(ProjectPhase)
        .filter(
            ProjectPhase.project_id == phase.project_id,
            ProjectPhase.phase_order > phase.phase_order,
            ProjectPhase.status.notin_(("done", "skipped")),
        )
        .order_by(ProjectPhase.phase_order)
        .all()
    )
    next_phase = siblings[0] if siblings else None
    if next_phase:
        if not next_phase.actual_start_date:
            next_phase.actual_start_date = today
        next_phase.status = "in_progress"
        next_phase.updated_at = datetime.utcnow()

    summary = f"Phase '{phase.phase_name}' marked done."
    if next_phase:
        summary += f" '{next_phase.phase_name}' is now in progress."
    write_change(
        db, phase.project_id, "phase_update", changed_by=changed_by,
        field_name=phase.phase_name, summary=summary,
        source_type=source_type,
    )

    db.commit()
    recalculate_stage_and_delay(db, phase.project_id)
    return {"finished": phase, "next": next_phase}

def delete_phase(db: Session, phase_id: int) -> int | None:
    phase = db.query(ProjectPhase).filter(ProjectPhase.id == phase_id).first()
    if not phase:
        return None
    project_id = phase.project_id
    write_change(
        db, project_id, "phase_update", changed_by="user",
        summary=f"Phase '{phase.phase_name}' deleted.",
        source_type="manual_edit",
    )
    db.delete(phase)
    db.commit()
    recalculate_stage_and_delay(db, project_id)
    return project_id

# ---------------------------------------------------------------------------
# File CRUD
# ---------------------------------------------------------------------------

def upload_file(
    db: Session,
    project_id: int,
    filename: str,
    original_filename: str,
    file_path: str,
    file_type: str,
    file_category: str,
    file_size: int,
    source_note: str = None,
    ai_summary: str = None,
    changed_by: str = "user",
    source_type: str = "file_upload",
) -> ProjectFile:
    f = ProjectFile(
        project_id=project_id,
        filename=filename,
        original_filename=original_filename,
        file_path=file_path,
        file_type=file_type,
        file_category=file_category,
        file_size=file_size,
        source_note=source_note or None,
        ai_summary=ai_summary or None,
    )
    db.add(f)
    db.flush()
    write_change(
        db, project_id, "file_upload", changed_by=changed_by,
        summary=f"File '{original_filename}' uploaded as {file_category}.",
        source_type=source_type,
    )
    db.commit()
    db.refresh(f)
    return f

def delete_file(db: Session, file_id: int, project_id: int) -> bool:
    f = db.query(ProjectFile).filter(
        ProjectFile.id == file_id,
        ProjectFile.project_id == project_id,
    ).first()
    if not f:
        return False
    disk_path = os.path.join(UPLOAD_DIR, f.filename)
    write_change(
        db, project_id, "file_upload", changed_by="user",
        summary=f"File '{f.original_filename}' deleted.",
        source_type="manual_edit",
    )
    db.delete(f)
    db.commit()
    if os.path.exists(disk_path):
        os.remove(disk_path)
    return True

# ---------------------------------------------------------------------------
# Phases due this week (for Needs Attention section)
# ---------------------------------------------------------------------------

def get_phases_due_this_week(db: Session) -> list[dict]:
    today = date.today()
    week_end = today + timedelta(days=7)
    phases = (
        db.query(ProjectPhase)
        .filter(
            ProjectPhase.planned_end_date >= today,
            ProjectPhase.planned_end_date <= week_end,
            ProjectPhase.status.notin_(["done", "skipped"]),
        )
        .all()
    )
    result = []
    for p in phases:
        project = db.query(Project).filter(Project.id == p.project_id).first()
        if project and project.status == "active":
            result.append({"phase": p, "project": project})
    return result

# ---------------------------------------------------------------------------
# Admin / Database Inspector
# ---------------------------------------------------------------------------

def get_table_stats(db: Session) -> dict:
    stats = {}

    for model, name in [
        (Project, "projects"),
        (ProjectPhase, "project_phases"),
        (ProjectFile, "project_files"),
        (ProjectChange, "project_changes"),
        (AIMessage, "ai_messages"),
    ]:
        count = db.query(func.count(model.id)).scalar()
        stats[name] = {"count": count}

    return stats

def get_field_usage(db: Session) -> dict:
    """Returns field usage stats for the projects table."""
    total = db.query(func.count(Project.id)).scalar()
    if total == 0:
        return {}

    nullable_fields = [
        "sku", "brand", "product_type", "project_owner", "product_manager",
        "engineer", "factory", "target_factory_cost", "target_msrp",
        "planned_launch_date", "estimated_launch_date", "project_thesis",
    ]

    usage = {}
    for field in nullable_fields:
        col = getattr(Project, field)
        non_empty = db.query(func.count(Project.id)).filter(col.isnot(None)).scalar()
        # For thesis, also count short ones as empty
        if field == "project_thesis":
            non_empty = db.query(func.count(Project.id)).filter(
                Project.project_thesis.isnot(None),
                func.length(Project.project_thesis) >= 80,
            ).scalar()
        usage[field] = {
            "non_empty": non_empty,
            "empty": total - non_empty,
            "total": total,
            "pct": round(non_empty / total * 100, 1) if total else 0,
        }

    return usage

def get_missing_critical_summary(db: Session) -> dict:
    """Returns per-critical-field list of project names missing that field."""
    active_projects = db.query(Project).filter(Project.status == "active").all()
    summary = {}

    for field in CRITICAL_FIELDS:
        missing = []
        for p in active_projects:
            val = getattr(p, field)
            if field == "project_thesis":
                if not val or len(val.strip()) < 80:
                    missing.append(p.name)
            else:
                if not val:
                    missing.append(p.name)
        summary[field] = missing

    # phases check
    no_phases = []
    for p in active_projects:
        if not p.phases:
            no_phases.append(p.name)
    summary["timeline_phases"] = no_phases

    return summary


# ---------------------------------------------------------------------------
# AI Messages
# ---------------------------------------------------------------------------

def save_ai_message(
    db: Session,
    project_id: int | None,
    role: str,
    message: str,
    metadata: dict | None,
) -> AIMessage:
    conversation_id = None
    if metadata and isinstance(metadata, dict):
        conversation_id = metadata.get("conversation_id")
    msg = AIMessage(
        project_id=project_id,
        conversation_id=conversation_id,
        role=role,
        message=message,
        metadata_json=metadata,
    )
    db.add(msg)
    # Build 21 — bump the conversation's updated_at so the history dropdown
    # shows the most-recently-active threads first.
    if conversation_id:
        from app.models import AIConversation  # local — keeps top of file unchanged
        conv = db.query(AIConversation).filter(AIConversation.id == conversation_id).first()
        if conv:
            conv.updated_at = datetime.utcnow()
    db.commit()
    return msg


# ---------------------------------------------------------------------------
# Build 21 — AI Conversations
# ---------------------------------------------------------------------------

def create_ai_conversation(
    db: Session,
    user_id: int,
    project_id: int | None = None,
    title: str | None = None,
):
    """Auto-titles based on project context if no title supplied."""
    from app.models import AIConversation  # local import keeps top of file unchanged
    if not title:
        if project_id:
            proj = db.query(Project).filter(Project.id == project_id).first()
            title = proj.name if proj else "(new conversation)"
        else:
            title = "(global chat)"
    conv = AIConversation(
        user_id=user_id,
        project_id=project_id,
        title=title.strip()[:200],
        status="active",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def list_ai_conversations(db: Session, user_id: int, include_archived: bool = False):
    from app.models import AIConversation
    q = db.query(AIConversation).filter(AIConversation.user_id == user_id)
    if not include_archived:
        q = q.filter(AIConversation.status == "active")
    return q.order_by(AIConversation.updated_at.desc()).all()


def get_ai_conversation(db: Session, conversation_id: int, user_id: int):
    """Returns None if the conversation isn't owned by the user (ownership-enforced)."""
    from app.models import AIConversation
    return (
        db.query(AIConversation)
        .filter(AIConversation.id == conversation_id, AIConversation.user_id == user_id)
        .first()
    )


def get_ai_messages_for_conversation(
    db: Session,
    conversation_id: int,
    limit: int | None = None,
):
    q = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.asc())
    )
    if limit:
        # Take the LAST N messages (most recent), still chronological.
        all_msgs = q.all()
        return all_msgs[-limit:] if len(all_msgs) > limit else all_msgs
    return q.all()


def archive_ai_conversation(db: Session, conversation_id: int, user_id: int) -> bool:
    """Idempotent. Returns False if conversation doesn't exist or isn't user's."""
    conv = get_ai_conversation(db, conversation_id, user_id)
    if not conv:
        return False
    conv.status = "archived"
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Calendar — planned vs actual launches per month
# ---------------------------------------------------------------------------

def get_actual_launch_date(project: Project) -> date | None:
    """Derive the actual launch date from the project's 'Launch' phase.
    Returns the Launch phase's actual_end_date if it's marked done; falls
    back to the highest-order done phase's actual_end_date if the project
    is marked completed. Returns None otherwise.
    """
    if not project.phases:
        return None
    launch_done = [
        p for p in project.phases
        if (p.phase_name or "").strip().lower() == "launch"
        and p.status == "done"
        and p.actual_end_date
    ]
    if launch_done:
        return max(p.actual_end_date for p in launch_done)
    if project.status == "completed":
        ended = [p for p in project.phases if p.status == "done" and p.actual_end_date]
        if ended:
            return max(ended, key=lambda p: p.phase_order).actual_end_date
    return None


def get_calendar_data(db: Session, year: int) -> dict:
    """Returns {1..12: {'planned': [...], 'actual': [...]}} for the given year.
    Only non-archived projects are included. Each entry is a plain dict so the
    template doesn't accidentally access raw model attributes.
    """
    months = {m: {"planned": [], "actual": []} for m in range(1, 13)}
    projects = db.query(Project).filter(Project.status != "archived").all()

    for p in projects:
        actual = get_actual_launch_date(p)
        entry = {
            "id": p.id,
            "name": p.name,
            "sku": p.sku,
            "brand": p.brand,
            "status": p.status,
            "current_stage": p.current_stage,
            "planned_launch_date": p.planned_launch_date,
            "actual_launch_date": actual,
        }
        if p.planned_launch_date and p.planned_launch_date.year == year:
            months[p.planned_launch_date.month]["planned"].append(entry)
        if actual and actual.year == year:
            months[actual.month]["actual"].append(entry)

    # Sort each month's lists by date for consistent display
    for m in months.values():
        m["planned"].sort(key=lambda e: e["planned_launch_date"] or date.max)
        m["actual"].sort(key=lambda e: e["actual_launch_date"] or date.max)

    return months


def get_calendar_year_range(db: Session) -> tuple[int, int]:
    """Returns (min_year, max_year) across all planned + actual launch dates.
    Falls back to current year if no data."""
    today = date.today()
    years = {today.year}
    for p in db.query(Project).filter(Project.status != "archived").all():
        if p.planned_launch_date:
            years.add(p.planned_launch_date.year)
        actual = get_actual_launch_date(p)
        if actual:
            years.add(actual.year)
    return min(years), max(years)


# ---------------------------------------------------------------------------
# Ideas (Good Ideas board)
# ---------------------------------------------------------------------------

from app.models import Idea, ProjectIdea, User  # local import to keep top of file unchanged

IDEA_TYPES = ["material", "structure", "feature", "aesthetic", "manufacturing", "other"]
IDEA_SOURCES = ["factory", "tradeshow", "internet", "customer", "team", "competitor", "other"]


def create_idea(db: Session, data: dict, contributor_user_id: int | None = None) -> Idea:
    """Create a new idea. `data` keys: name, description, idea_type, source,
    source_detail, contributor, notes."""
    idea_type = data.get("idea_type") or "other"
    if idea_type not in IDEA_TYPES:
        idea_type = "other"
    source = data.get("source") or "other"
    if source not in IDEA_SOURCES:
        source = "other"

    idea = Idea(
        name=(data.get("name") or "").strip() or "(untitled)",
        description=(data.get("description") or "").strip() or None,
        idea_type=idea_type,
        source=source,
        source_detail=(data.get("source_detail") or "").strip() or None,
        contributor=(data.get("contributor") or "").strip() or None,
        contributor_user_id=contributor_user_id,
        status="open",
        notes=(data.get("notes") or "").strip() or None,
    )
    db.add(idea)
    db.commit()
    db.refresh(idea)
    return idea


def update_idea(
    db: Session,
    idea_id: int,
    data: dict,
    changed_by: str = "user",
    source_type: str = "manual_edit",
) -> Idea | None:
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        return None
    before = {
        field: getattr(idea, field)
        for field in (
            "name", "description", "source_detail", "contributor", "notes",
            "idea_type", "source", "status",
        )
    }
    for field in ("name", "description", "source_detail", "contributor", "notes"):
        if field in data:
            val = (data.get(field) or "").strip()
            setattr(idea, field, val or None)
    if "idea_type" in data:
        t = data["idea_type"]
        idea.idea_type = t if t in IDEA_TYPES else "other"
    if "source" in data:
        s = data["source"]
        idea.source = s if s in IDEA_SOURCES else "other"
    if "status" in data and data["status"] in ("open", "in_use", "archived"):
        idea.status = data["status"]
    idea.updated_at = datetime.utcnow()
    changed_fields = [
        field for field, old_value in before.items()
        if getattr(idea, field) != old_value
    ]
    if changed_fields:
        linked_project_ids = {
            link.project_id
            for link in db.query(ProjectIdea).filter(ProjectIdea.idea_id == idea_id).all()
        }
        for project_id in linked_project_ids:
            write_change(
                db,
                project_id=project_id,
                change_type="event_note",
                changed_by=changed_by,
                source_type=source_type,
                summary=f"Updated linked idea {idea.serial_number}: {', '.join(changed_fields)}",
            )
    db.commit()
    db.refresh(idea)
    return idea


def delete_idea(db: Session, idea_id: int) -> bool:
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        return False
    db.delete(idea)
    db.commit()
    return True


def get_idea(db: Session, idea_id: int) -> Idea | None:
    return db.query(Idea).filter(Idea.id == idea_id).first()


def get_ideas_grouped(db: Session, source_filter: str | None = None) -> dict:
    """Returns {idea_type: [Idea, ...]} for all non-archived ideas.
    Each list is sorted by created_at descending."""
    q = db.query(Idea).filter(Idea.status != "archived")
    if source_filter and source_filter in IDEA_SOURCES:
        q = q.filter(Idea.source == source_filter)
    ideas = q.order_by(Idea.created_at.desc()).all()
    grouped = {t: [] for t in IDEA_TYPES}
    for i in ideas:
        bucket = i.idea_type if i.idea_type in grouped else "other"
        grouped[bucket].append(i)
    return grouped


def get_all_open_ideas(db: Session) -> list[Idea]:
    """Used by the 'link existing idea' picker on project detail."""
    return (
        db.query(Idea)
        .filter(Idea.status != "archived")
        .order_by(Idea.created_at.desc())
        .all()
    )


def link_idea_to_project(
    db: Session,
    project_id: int,
    idea_id: int,
    linked_by_user_id: int | None = None,
    note: str | None = None,
    changed_by: str = "user",
    source_type: str = "manual_edit",
) -> ProjectIdea | None:
    """Idempotent: returns existing link if already linked, otherwise creates one."""
    existing = (
        db.query(ProjectIdea)
        .filter(ProjectIdea.project_id == project_id, ProjectIdea.idea_id == idea_id)
        .first()
    )
    if existing:
        return existing
    link = ProjectIdea(
        project_id=project_id,
        idea_id=idea_id,
        linked_by_user_id=linked_by_user_id,
        note=(note or "").strip() or None,
    )
    db.add(link)
    # Mark idea as in_use if it was open
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if idea and idea.status == "open":
        idea.status = "in_use"
    write_change(
        db,
        project_id=project_id,
        change_type="event_note",
        changed_by=changed_by,
        source_type=source_type,
        summary=f"Linked {idea.serial_number if idea else f'idea #{idea_id}'} to Inspired By",
    )
    db.commit()
    db.refresh(link)
    return link


def unlink_idea_from_project(
    db: Session,
    project_id: int,
    idea_id: int,
    changed_by: str = "user",
    source_type: str = "manual_edit",
) -> bool:
    link = (
        db.query(ProjectIdea)
        .filter(ProjectIdea.project_id == project_id, ProjectIdea.idea_id == idea_id)
        .first()
    )
    if not link:
        return False
    db.delete(link)
    # If no other projects link to this idea, set status back to open
    remaining = (
        db.query(ProjectIdea).filter(ProjectIdea.idea_id == idea_id).count()
    )
    if remaining == 1:  # this one being deleted
        idea = db.query(Idea).filter(Idea.id == idea_id).first()
        if idea and idea.status == "in_use":
            idea.status = "open"
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    write_change(
        db,
        project_id=project_id,
        change_type="event_note",
        changed_by=changed_by,
        source_type=source_type,
        summary=f"Unlinked {idea.serial_number if idea else f'idea #{idea_id}'} from Inspired By",
    )
    db.commit()
    return True


def create_and_link_idea(
    db: Session,
    project_id: int,
    data: dict,
    contributor_user_id: int | None = None,
    note: str | None = None,
    changed_by: str = "user",
    source_type: str = "manual_edit",
) -> tuple[Idea, ProjectIdea]:
    """Create an Idea and link it to a project through the normal services."""
    idea = create_idea(db, data, contributor_user_id=contributor_user_id)
    link = link_idea_to_project(
        db,
        project_id=project_id,
        idea_id=idea.id,
        linked_by_user_id=contributor_user_id,
        note=note,
        changed_by=changed_by,
        source_type=source_type,
    )
    return idea, link


def get_ideas_for_project(db: Session, project_id: int) -> list[dict]:
    """Returns linked ideas with metadata (link info + idea info)."""
    links = (
        db.query(ProjectIdea)
        .filter(ProjectIdea.project_id == project_id)
        .order_by(ProjectIdea.linked_at.desc())
        .all()
    )
    result = []
    for link in links:
        result.append({
            "idea": link.idea,
            "linked_at": link.linked_at,
            "linked_by_user": link.linked_by_user,
            "note": link.note,
        })
    return result


# ---------------------------------------------------------------------------
# v1.1 Build 14: Project Journal CRUD
# ---------------------------------------------------------------------------

from app.models import ProjectJournalEntry  # late import to avoid circular


def create_journal_entry(
    db: Session,
    project_id: int,
    entry_text: str,
    entry_type: str,
    author_user_id: int | None = None,
    changed_by: str = "user",
    source_type: str = "manual_edit",
) -> ProjectJournalEntry:
    """Create a journal entry. Raw entry_text is preserved forever — never
    overwritten silently. title and ai_summary are filled later via
    summarize_journal_entry()."""
    entry = ProjectJournalEntry(
        project_id=project_id,
        entry_text=entry_text.strip(),
        entry_type=(entry_type or "general").strip(),
        author_user_id=author_user_id,
        visibility="internal",
    )
    db.add(entry)
    snippet = entry.entry_text[:80]
    write_change(
        db, project_id, "event_note",
        changed_by=changed_by,
        summary=f"Journal entry added: '{snippet}…'" if len(entry.entry_text) > 80 else f"Journal entry added: '{snippet}'",
        source_type=source_type,
    )
    db.commit()
    db.refresh(entry)
    return entry


def update_journal_entry(
    db: Session,
    entry_id: int,
    entry_text: str,
    entry_type: str,
    edited_by_user_id: int | None = None,
) -> ProjectJournalEntry | None:
    """Edit raw text and/or type. Writes a project_changes audit row so the
    edit is visible in the project's change log even though per-edit text
    history isn't kept."""
    entry = db.query(ProjectJournalEntry).filter(ProjectJournalEntry.id == entry_id).first()
    if not entry:
        return None
    old_text = entry.entry_text or ""
    new_text = (entry_text or "").strip()
    if not new_text:
        return entry  # silently ignore empty save
    if new_text == old_text and entry_type == entry.entry_type:
        return entry  # no actual change

    entry.entry_text = new_text
    entry.entry_type = (entry_type or "general").strip()
    entry.updated_at = datetime.utcnow()
    # AI title/summary may be stale after edit — caller can re-Summarize.
    # Don't auto-invalidate; user might know they're fine.
    db.flush()

    # Audit row in project_changes
    snippet_old = (old_text[:60] + "…") if len(old_text) > 60 else old_text
    snippet_new = (new_text[:60] + "…") if len(new_text) > 60 else new_text
    write_change(
        db, entry.project_id, "event_note",
        changed_by="user",
        summary=f"Journal entry edited: '{snippet_old}' → '{snippet_new}'",
        source_type="manual_edit",
    )
    db.commit()
    db.refresh(entry)
    return entry


def delete_journal_entry(db: Session, entry_id: int) -> bool:
    entry = db.query(ProjectJournalEntry).filter(ProjectJournalEntry.id == entry_id).first()
    if not entry:
        return False
    project_id = entry.project_id
    snippet = (entry.entry_text or "")[:80]
    db.delete(entry)
    write_change(
        db, project_id, "event_note",
        changed_by="user",
        summary=f"Journal entry deleted: '{snippet}…'" if len(snippet) >= 80 else f"Journal entry deleted: '{snippet}'",
        source_type="manual_edit",
    )
    db.commit()
    return True


def get_journal_entries_for_project(
    db: Session, project_id: int
) -> list[ProjectJournalEntry]:
    """Returns entries newest-first. Always preserves raw entry_text."""
    return (
        db.query(ProjectJournalEntry)
        .filter(ProjectJournalEntry.project_id == project_id)
        .order_by(ProjectJournalEntry.created_at.desc())
        .all()
    )


def apply_ai_summary(
    db: Session, entry_id: int, title: str, summary: str
) -> ProjectJournalEntry | None:
    """Called only on AI summarize SUCCESS. On AI failure, the caller does
    not invoke this — existing title/ai_summary stay intact."""
    entry = db.query(ProjectJournalEntry).filter(ProjectJournalEntry.id == entry_id).first()
    if not entry:
        return None
    entry.title = title.strip() or None
    entry.ai_summary = summary.strip() or None
    entry.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# Build 15 — Business Plan Thesis Extraction (preview-confirm)
# ---------------------------------------------------------------------------

THESIS_EXTRACTION_SENTINEL = "thesis_extraction"


def save_thesis_extraction(
    db: Session,
    project_id: int,
    source_file: ProjectFile | None,
    payload: dict,
) -> AIMessage:
    """Persist a one-time AI extraction as an ai_messages row so the preview
    page can re-render without re-running AI. payload is the dict returned by
    parser.extract_thesis_and_inspirations (or {'_error': '...'} on failure —
    still saved so the failure is auditable)."""
    metadata = {
        "kind": THESIS_EXTRACTION_SENTINEL,
        "source_file_id": source_file.id if source_file else None,
        "source_filename": source_file.original_filename if source_file else None,
        "source_file_type": source_file.file_type if source_file else None,
        "confirmed_at": None,
        "confirmed_thesis": None,
        "confirmed_inspirations": None,
        **payload,
    }
    msg = AIMessage(
        project_id=project_id,
        role="assistant",
        message=THESIS_EXTRACTION_SENTINEL,
        metadata_json=metadata,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_thesis_extraction(db: Session, extraction_id: int, project_id: int) -> AIMessage | None:
    """Load a saved extraction by id, verifying it belongs to project_id AND
    is actually a thesis_extraction row. Returns None on any mismatch."""
    msg = db.query(AIMessage).filter(AIMessage.id == extraction_id).first()
    if not msg:
        return None
    if msg.project_id != project_id:
        return None
    if msg.message != THESIS_EXTRACTION_SENTINEL:
        return None
    return msg


def get_latest_business_plan_file(db: Session, project_id: int) -> ProjectFile | None:
    """Latest uploaded ProjectFile with file_category='business_plan' for the project."""
    return (
        db.query(ProjectFile)
        .filter(
            ProjectFile.project_id == project_id,
            ProjectFile.file_category == "business_plan",
        )
        .order_by(ProjectFile.uploaded_at.desc())
        .first()
    )


def apply_thesis_extraction(
    db: Session,
    project_id: int,
    extraction_id: int,
    new_thesis: str,
    inspirations: list[dict],
    user,
) -> dict:
    """Confirm path: write thesis + create/link selected ideas in one transaction.

    inspirations: list of {"action": "create"|"link"|"skip", "idea_id": int|None,
                           "name", "description", "idea_type", "source", "source_detail"}

    update_project() automatically writes a field_update change-log row for
    project_thesis. We also emit an event_note tagged changed_by='ai' so the
    AI source of the thesis is visible in the change log.
    """
    summary = {"thesis_updated": False, "ideas_created": 0, "ideas_linked": 0}

    # 1. Thesis write — only if non-empty (preserves existing on cancel-with-empty)
    new_thesis = (new_thesis or "").strip()
    if new_thesis:
        update_project(db, project_id, {"project_thesis": new_thesis}, changed_by="ai")
        summary["thesis_updated"] = True

    # 2. Ideas
    final_inspirations = []
    for insp in inspirations or []:
        action = (insp.get("action") or "skip").lower()
        if action == "create":
            new_idea = create_idea(
                db,
                {
                    "name": insp.get("name") or "(untitled)",
                    "description": insp.get("description"),
                    "idea_type": insp.get("idea_type"),
                    "source": insp.get("source"),
                    "source_detail": insp.get("source_detail"),
                },
                contributor_user_id=user.id if user else None,
            )
            link_idea_to_project(
                db, project_id, new_idea.id,
                linked_by_user_id=user.id if user else None,
                note="From business plan extraction",
                changed_by="ai",
                source_type="ai_chat",
            )
            summary["ideas_created"] += 1
            final_inspirations.append({**insp, "action": "create", "resulting_idea_id": new_idea.id})
        elif action == "link":
            idea_id = insp.get("idea_id")
            if idea_id:
                link_idea_to_project(
                    db, project_id, int(idea_id),
                    linked_by_user_id=user.id if user else None,
                    note="From business plan extraction",
                    changed_by="ai",
                    source_type="ai_chat",
                )
                summary["ideas_linked"] += 1
                final_inspirations.append({**insp, "action": "link", "resulting_idea_id": int(idea_id)})
        else:
            final_inspirations.append({**insp, "action": "skip"})

    # 3. Event-note row marking AI source
    write_change(
        db,
        project_id=project_id,
        change_type="event_note",
        changed_by="ai",
        source_type="ai_chat",
        summary=(
            f"Thesis extracted from business plan "
            f"(thesis_updated={summary['thesis_updated']}, "
            f"ideas_created={summary['ideas_created']}, "
            f"ideas_linked={summary['ideas_linked']})"
        ),
    )

    # 4. Mark the AIMessage with the user's final selections (audit)
    msg = db.query(AIMessage).filter(AIMessage.id == extraction_id).first()
    if msg and msg.metadata_json:
        meta = dict(msg.metadata_json)
        meta["confirmed_at"] = datetime.utcnow().isoformat()
        meta["confirmed_thesis"] = new_thesis
        meta["confirmed_inspirations"] = final_inspirations
        msg.metadata_json = meta
        db.commit()

    return summary


# ---------------------------------------------------------------------------
# Build 16 — Multi-SKU Variants + Packaging/Accessories + Quotation files
# ---------------------------------------------------------------------------

from app.models import ProjectVariant, ProjectVariantComponent  # late import

VARIANT_STATUSES = ("idea", "evaluating", "selected", "rejected", "launched")
COMPONENT_TYPES = ("packaging", "accessory")


def _parse_float_safe(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def get_variants_for_project(db: Session, project_id: int) -> list[ProjectVariant]:
    """Primary first, then by id ascending."""
    return (
        db.query(ProjectVariant)
        .filter(ProjectVariant.project_id == project_id)
        .order_by(ProjectVariant.is_primary.desc(), ProjectVariant.id.asc())
        .all()
    )


def get_variant(db: Session, variant_id: int) -> ProjectVariant | None:
    return db.query(ProjectVariant).filter(ProjectVariant.id == variant_id).first()


def get_primary_variant(db: Session, project_id: int) -> ProjectVariant | None:
    return (
        db.query(ProjectVariant)
        .filter(ProjectVariant.project_id == project_id, ProjectVariant.is_primary == True)
        .first()
    )


def _clear_primary_variants(db: Session, project_id: int) -> None:
    """Service-layer enforcement: only one variant per project may be primary.
    No DB unique constraint (too risky for migrations)."""
    db.query(ProjectVariant).filter(
        ProjectVariant.project_id == project_id,
        ProjectVariant.is_primary == True,
    ).update({"is_primary": False})


def create_variant(
    db: Session, project_id: int, data: dict,
    changed_by: str = "user", source_type: str = "manual_edit",
) -> ProjectVariant:
    status = data.get("status") or "evaluating"
    if status not in VARIANT_STATUSES:
        status = "evaluating"
    is_primary = bool(data.get("is_primary"))
    if is_primary:
        _clear_primary_variants(db, project_id)
    v = ProjectVariant(
        project_id=project_id,
        variant_name=(data.get("variant_name") or "").strip() or "(untitled)",
        sku=(data.get("sku") or "").strip() or None,
        status=status,
        is_primary=is_primary,
        target_factory_cost=_parse_float_safe(data.get("target_factory_cost")),
        actual_factory_cost=_parse_float_safe(data.get("actual_factory_cost")),
        target_msrp=_parse_float_safe(data.get("target_msrp")),
        material_summary=(data.get("material_summary") or "").strip() or None,
        size_color_summary=(data.get("size_color_summary") or "").strip() or None,
        packaging_summary=(data.get("packaging_summary") or "").strip() or None,
        notes=(data.get("notes") or "").strip() or None,
    )
    db.add(v)
    db.flush()
    write_change(
        db, project_id=project_id, change_type="event_note",
        summary=f"Variant created: {v.variant_name}" + (f" (SKU {v.sku})" if v.sku else ""),
        changed_by=changed_by, source_type=source_type,
    )
    db.commit()
    db.refresh(v)
    return v


def update_variant(
    db: Session, variant_id: int, data: dict,
    changed_by: str = "user", source_type: str = "manual_edit",
) -> ProjectVariant | None:
    v = get_variant(db, variant_id)
    if not v:
        return None
    if "is_primary" in data and bool(data["is_primary"]) and not v.is_primary:
        _clear_primary_variants(db, v.project_id)
        v.is_primary = True
    elif "is_primary" in data and not bool(data["is_primary"]):
        v.is_primary = False
    for field in ("variant_name", "sku", "material_summary", "size_color_summary",
                  "packaging_summary", "notes"):
        if field in data:
            val = (data.get(field) or "").strip()
            setattr(v, field, val or None)
    if "status" in data:
        s = data["status"]
        v.status = s if s in VARIANT_STATUSES else v.status
    for field in ("target_factory_cost", "actual_factory_cost", "target_msrp"):
        if field in data:
            setattr(v, field, _parse_float_safe(data.get(field)))
    v.updated_at = datetime.utcnow()
    write_change(
        db, project_id=v.project_id, change_type="event_note",
        summary=f"Variant updated: {v.variant_name}",
        changed_by=changed_by, source_type=source_type,
    )
    db.commit()
    db.refresh(v)
    return v


def delete_variant(db: Session, variant_id: int) -> bool:
    v = get_variant(db, variant_id)
    if not v:
        return False
    label = v.variant_name
    pid = v.project_id
    db.delete(v)
    write_change(
        db, project_id=pid, change_type="event_note",
        summary=f"Variant deleted: {label}",
    )
    db.commit()
    return True


def set_primary_variant(
    db: Session, project_id: int, variant_id: int,
    changed_by: str = "user", source_type: str = "manual_edit",
) -> bool:
    v = get_variant(db, variant_id)
    if not v or v.project_id != project_id:
        return False
    _clear_primary_variants(db, project_id)
    v.is_primary = True
    v.updated_at = datetime.utcnow()
    write_change(
        db, project_id=project_id, change_type="event_note",
        summary=f"Set primary variant: {v.variant_name}",
        changed_by=changed_by, source_type=source_type,
    )
    db.commit()
    return True


# --- Components (packaging / accessories) ---

def get_components_for_project(db: Session, project_id: int) -> list[ProjectVariantComponent]:
    """Project-wide first (variant_id NULL), then per-variant by variant_id."""
    rows = (
        db.query(ProjectVariantComponent)
        .filter(ProjectVariantComponent.project_id == project_id)
        .order_by(ProjectVariantComponent.id.asc())
        .all()
    )
    # Sort in Python — SQLite/PostgreSQL NULLs-first behavior differs
    rows.sort(key=lambda c: (c.variant_id is not None, c.variant_id or 0, c.id))
    return rows


def get_component(db: Session, component_id: int) -> ProjectVariantComponent | None:
    return db.query(ProjectVariantComponent).filter(
        ProjectVariantComponent.id == component_id).first()


def create_variant_component(
    db: Session, project_id: int, data: dict,
    changed_by: str = "user", source_type: str = "manual_edit",
) -> ProjectVariantComponent:
    ctype = data.get("component_type") or "accessory"
    if ctype not in COMPONENT_TYPES:
        ctype = "accessory"
    variant_id = data.get("variant_id")
    if variant_id in ("", "0", 0, None):
        variant_id = None
    else:
        try:
            variant_id = int(variant_id)
        except (ValueError, TypeError):
            variant_id = None
    c = ProjectVariantComponent(
        project_id=project_id,
        variant_id=variant_id,
        component_type=ctype,
        name=(data.get("name") or "").strip() or "(untitled)",
        target_cost=_parse_float_safe(data.get("target_cost")),
        actual_cost=_parse_float_safe(data.get("actual_cost")),
        notes=(data.get("notes") or "").strip() or None,
    )
    db.add(c)
    db.flush()
    write_change(
        db, project_id=project_id, change_type="event_note",
        summary=f"{ctype.title()} added: {c.name}",
        changed_by=changed_by, source_type=source_type,
    )
    db.commit()
    db.refresh(c)
    return c


def update_variant_component(
    db: Session, component_id: int, data: dict,
    changed_by: str = "user", source_type: str = "manual_edit",
) -> ProjectVariantComponent | None:
    c = get_component(db, component_id)
    if not c:
        return None
    if "component_type" in data and data["component_type"] in COMPONENT_TYPES:
        c.component_type = data["component_type"]
    if "name" in data:
        c.name = (data.get("name") or "").strip() or c.name
    if "notes" in data:
        c.notes = (data.get("notes") or "").strip() or None
    for field in ("target_cost", "actual_cost"):
        if field in data:
            setattr(c, field, _parse_float_safe(data.get(field)))
    if "variant_id" in data:
        vid = data.get("variant_id")
        if vid in ("", "0", 0, None):
            c.variant_id = None
        else:
            try:
                c.variant_id = int(vid)
            except (ValueError, TypeError):
                pass
    c.updated_at = datetime.utcnow()
    write_change(
        db, project_id=c.project_id, change_type="event_note",
        summary=f"Component updated: {c.name}",
        changed_by=changed_by, source_type=source_type,
    )
    db.commit()
    db.refresh(c)
    return c


def delete_variant_component(db: Session, component_id: int) -> bool:
    c = get_component(db, component_id)
    if not c:
        return False
    label = c.name
    pid = c.project_id
    db.delete(c)
    write_change(
        db, project_id=pid, change_type="event_note",
        summary=f"Component deleted: {label}",
    )
    db.commit()
    return True


# --- Quotation files (filtered view of project_files) ---

def get_quotation_files_for_project(db: Session, project_id: int) -> list[ProjectFile]:
    return (
        db.query(ProjectFile)
        .filter(
            ProjectFile.project_id == project_id,
            ProjectFile.file_category == "quotation",
        )
        .order_by(ProjectFile.uploaded_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Build 18 — Rendering History + Prototype Photos
# Per-upload comments are stored in the existing project_files.source_note
# field. PM+admin can update them inline via the new comment route.
# ---------------------------------------------------------------------------

def get_files_by_category(db: Session, project_id: int, category: str) -> list[ProjectFile]:
    """Newest first — used by Rendering History + Prototype Photos sections."""
    return (
        db.query(ProjectFile)
        .filter(
            ProjectFile.project_id == project_id,
            ProjectFile.file_category == category,
        )
        .order_by(ProjectFile.uploaded_at.desc())
        .all()
    )


def get_latest_rendering(db: Session, project_id: int) -> ProjectFile | None:
    """Used by the project card to show a tiny thumbnail."""
    return (
        db.query(ProjectFile)
        .filter(
            ProjectFile.project_id == project_id,
            ProjectFile.file_category == "rendering",
            ProjectFile.file_type == "image",
        )
        .order_by(ProjectFile.uploaded_at.desc())
        .first()
    )


def update_file_comment(
    db: Session, file_id: int, new_comment: str,
    changed_by: str = "user", source_type: str = "manual_edit",
) -> ProjectFile | None:
    """Inline-edit a per-file comment (uses project_files.source_note)."""
    pf = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not pf:
        return None
    old = (pf.source_note or "").strip()
    new = (new_comment or "").strip()
    if old == new:
        return pf
    pf.source_note = new or None
    write_change(
        db, project_id=pf.project_id, change_type="event_note",
        summary=f"Comment updated on {pf.file_category or 'file'}: "
                f"{pf.original_filename or pf.filename}",
        changed_by=changed_by, source_type=source_type,
    )
    db.commit()
    db.refresh(pf)
    return pf
