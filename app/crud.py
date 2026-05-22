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

def update_project(db: Session, project_id: int, data: dict, changed_by: str = "user") -> Project | None:
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
                source_type="manual_edit",
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
        result.append({
            "project": p,
            "health": health,
            "delay": delay,
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

def update_phase(db: Session, phase_id: int, data: dict, changed_by: str = "user") -> ProjectPhase | None:
    phase = db.query(ProjectPhase).filter(ProjectPhase.id == phase_id).first()
    if not phase:
        return None

    changes = []
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

    phase.updated_at = datetime.utcnow()

    if changes:
        summary_parts = [f"{f.replace('_', ' ')}: {o or '—'} → {n or '—'}" for f, o, n in changes]
        write_change(
            db, phase.project_id, "phase_update", changed_by=changed_by,
            field_name=phase.phase_name,
            summary=f"Phase '{phase.phase_name}' updated: {'; '.join(summary_parts)}",
            source_type="manual_edit",
        )

    db.commit()
    recalculate_stage_and_delay(db, phase.project_id)
    return phase

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
        db, project_id, "file_upload", changed_by="user",
        summary=f"File '{original_filename}' uploaded as {file_category}.",
        source_type="file_upload",
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
    msg = AIMessage(
        project_id=project_id,
        role=role,
        message=message,
        metadata_json=metadata,
    )
    db.add(msg)
    db.commit()
    return msg
