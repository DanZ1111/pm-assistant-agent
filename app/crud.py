import os
import uuid
import math
import re
import shutil
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, update, desc
from app.models import (
    Project, ProjectPhase, ProjectFile, ProjectChange, AIMessage,
    ProjectCreationToken, User,
    PlanningModule, PlanningTemplate, PlanningTemplateNode, PlanningTemplateEdge,
    PlanningSandbox, PlanningSandboxNode, PlanningSandboxEdge, PlanningApplyEvent,
    ProjectBlocker, DesignQuest, DesignQuestAssignment, DesignQuestReference,
    DesignQuestEvent, DesignSubmission, DesignSubmissionVersion,
    DesignRevisionRequest, DesignRevisionItem,
)

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


def parse_simple_usd_price(value) -> float | None:
    """Return a float only for one clean USD-ish amount.

    PM-facing fields preserve ranges/currencies in *_text columns; this legacy
    numeric value is only for old displays and future calculations.
    """
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = text.lower()
    if any(token in lowered for token in ("rmb", "cny", "人民币", "元", "¥")):
        return None
    if any(token in text for token in ("-", "–", "—", "~", "～", "至", "到", "－")) or " to " in lowered:
        return None
    cleaned = text.replace(",", "").replace("$", "")
    cleaned = cleaned.replace("USD", "").replace("usd", "").replace("US$", "").replace("美元", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def price_field_present(project: Project, field: str) -> bool:
    text_val = getattr(project, f"{field}_text", None)
    numeric_val = getattr(project, field, None)
    return bool(text_val) or numeric_val is not None

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

    if not price_field_present(project, "target_factory_cost"):
        critical_missing.append("target_factory_cost")
    if not price_field_present(project, "target_msrp"):
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

    Admin sees all projects; PM sees projects where product_manager matches
    their username OR their display_name (case-insensitive). Build 30A
    extended the match to display_name so legacy rows where the form was
    filled with a person's display name still surface for that PM. Viewer
    gets an empty list (the /my-projects route also redirects them away).
    """
    if user is None:
        return []
    if user.role == "admin":
        return get_projects(db)
    if user.role == "pm":
        uname = (user.username or "").strip().lower()
        if not uname:
            return []
        dname = (getattr(user, "display_name", "") or "").strip().lower()
        candidates = [uname]
        if dname and dname != uname:
            candidates.append(dname)
        return (
            db.query(Project)
            .filter(func.lower(Project.product_manager).in_(candidates))
            .order_by(Project.updated_at.desc())
            .all()
        )
    return []  # viewer


def normalize_pm_value(db: Session, raw: str) -> str | None:
    """Build 30A — resolve a free-text PM field to a canonical username.

    Matches against User.username and User.display_name (case-insensitive).
    Returns the canonical username only when exactly one user matches —
    that way ambiguous typed-in names (e.g. two users with display_name
    "John") fall through unchanged and the caller stores the raw text.
    """
    needle = (raw or "").strip().lower()
    if not needle:
        return None
    matches = db.query(User).filter(
        or_(
            func.lower(User.username) == needle,
            func.lower(User.display_name) == needle,
        )
    ).all()
    if len(matches) == 1:
        return matches[0].username
    return None


def _build_project_in_session(db: Session, data: dict, prototype_rounds: str) -> Project:
    """Build 30A — internal helper that inserts a Project + phases + change-log
    row inside the caller's transaction. Does NOT commit. The public
    create_project() commits; create_project_with_idempotency() commits once
    after also claiming the idempotency token in the same transaction.
    """
    project = Project(**{k: v for k, v in data.items() if v != "" and v is not None})
    db.add(project)
    db.flush()

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
    phases = (
        db.query(ProjectPhase)
        .filter(ProjectPhase.project_id == project.id)
        .order_by(ProjectPhase.phase_order)
        .all()
    )
    project.current_stage = derive_current_stage(phases)

    write_change(
        db, project.id, "event_note", changed_by="user",
        summary=f"Project '{project.name}' created with {prototype_rounds}-prototype template ({len(template)} phases).",
        source_type="manual_edit",
    )
    return project


def create_project(db: Session, data: dict, prototype_rounds: str = "single") -> Project:
    """Public create-project entry point. Commits in a single transaction.

    Callers that need idempotency (HTTP forms) should use
    create_project_with_idempotency() instead so the project insert and
    the token claim land atomically.
    """
    project = _build_project_in_session(db, data, prototype_rounds)
    db.commit()
    db.refresh(project)
    return project


# ---------------------------------------------------------------------------
# v1.5 Build 02 — Designer Portal design quest service layer
# ---------------------------------------------------------------------------

DESIGN_QUEST_ACTIVE_STATUSES = ("draft", "open", "reviewing", "revision_needed", "selected")
DESIGN_QUEST_DESIGNER_VISIBLE_STATUSES = ("open", "reviewing", "revision_needed", "selected")
DESIGN_QUEST_VISIBILITIES = ("all_active_designers", "assigned_designers_only")
DESIGNER_PORTAL_ROLES = ("designer", "designer_manager")
DESIGN_QUEST_SUBMISSION_OPEN_STATUSES = ("open", "reviewing", "revision_needed")
DESIGN_SUBMISSION_ACTIVE_STATUSES = ("submitted", "shortlisted", "revision_requested", "revised", "selected", "rejected")
DESIGN_SUBMISSION_ALLOWED_EXTENSIONS = ("jpg", "jpeg", "png", "webp", "pdf")
DESIGN_SUBMISSION_MAX_BYTES = 20 * 1024 * 1024
DESIGN_REVISION_OPEN_STATUSES = ("open", "partially_resolved")


def _can_edit_project_for_design_quest(user: User | None, project: Project | None) -> bool:
    if not user or not project:
        return False
    if user.role == "admin":
        return True
    if user.role == "pm":
        pm_field = (project.product_manager or "").lower().strip()
        return bool(pm_field) and (
            pm_field == (user.username or "").lower().strip()
            or pm_field == (user.display_name or "").lower().strip()
        )
    return False


def _require_design_quest_editor(db: Session, project: Project | None, user_id: int | None) -> User:
    user = db.query(User).filter(User.id == user_id).first() if user_id else None
    if not _can_edit_project_for_design_quest(user, project):
        raise PermissionError("user_cannot_edit_design_quest_project")
    return user


def _write_design_quest_event(
    db: Session,
    quest: DesignQuest,
    event_type: str,
    actor_user_id: int | None,
    summary: str,
    payload: dict | None = None,
) -> DesignQuestEvent:
    event = DesignQuestEvent(
        quest_id=quest.id,
        project_id=quest.project_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        summary=summary,
        payload_json=payload or {},
    )
    db.add(event)
    return event


def get_active_design_quest(db: Session, project_id: int) -> DesignQuest | None:
    return (
        db.query(DesignQuest)
        .filter(
            DesignQuest.project_id == project_id,
            DesignQuest.status.in_(DESIGN_QUEST_ACTIVE_STATUSES),
        )
        .order_by(DesignQuest.updated_at.desc())
        .first()
    )


def create_design_quest_draft(
    db: Session,
    project_id: int,
    user_id: int,
    title: str,
    brief: str,
    must_keep: str | None = None,
    must_avoid: str | None = None,
    soft_deadline: date | None = None,
    visibility: str = "all_active_designers",
    is_timeline_blocking: bool = False,
    linked_phase_id: int | None = None,
) -> DesignQuest:
    project = get_project(db, project_id)
    editor = _require_design_quest_editor(db, project, user_id)
    if not title or not title.strip():
        raise ValueError("title_required")
    if not brief or not brief.strip():
        raise ValueError("brief_required")
    if visibility not in DESIGN_QUEST_VISIBILITIES:
        raise ValueError("invalid_visibility")
    if get_active_design_quest(db, project_id):
        raise ValueError("active_design_quest_exists")
    if linked_phase_id is not None:
        phase = db.query(ProjectPhase).filter(
            ProjectPhase.id == linked_phase_id,
            ProjectPhase.project_id == project_id,
        ).first()
        if not phase:
            raise ValueError("linked_phase_not_in_project")

    now = datetime.utcnow()
    quest = DesignQuest(
        project_id=project_id,
        title=title.strip(),
        brief=brief.strip(),
        must_keep=(must_keep or "").strip() or None,
        must_avoid=(must_avoid or "").strip() or None,
        status="draft",
        visibility=visibility,
        soft_deadline=soft_deadline,
        is_timeline_blocking=bool(is_timeline_blocking),
        linked_phase_id=linked_phase_id,
        created_by_user_id=editor.id,
        created_at=now,
        updated_at=now,
    )
    db.add(quest)
    db.flush()
    _write_design_quest_event(
        db,
        quest,
        "quest_created",
        editor.id,
        f"Design quest '{quest.title}' created as draft.",
        {"status": quest.status, "visibility": quest.visibility},
    )
    db.commit()
    db.refresh(quest)
    return quest


def publish_design_quest(db: Session, quest_id: int, user_id: int) -> DesignQuest:
    quest = db.query(DesignQuest).filter(DesignQuest.id == quest_id).first()
    if not quest:
        raise ValueError("design_quest_not_found")
    editor = _require_design_quest_editor(db, quest.project, user_id)
    if quest.status != "draft":
        raise ValueError("only_draft_quest_can_publish")
    now = datetime.utcnow()
    quest.status = "open"
    quest.published_at = now
    quest.updated_at = now
    _write_design_quest_event(
        db,
        quest,
        "quest_published",
        editor.id,
        f"Design quest '{quest.title}' published.",
        {"status": quest.status},
    )
    db.commit()
    db.refresh(quest)
    return quest


def close_design_quest(db: Session, quest_id: int, user_id: int, reason: str | None = None) -> DesignQuest:
    quest = db.query(DesignQuest).filter(DesignQuest.id == quest_id).first()
    if not quest:
        raise ValueError("design_quest_not_found")
    editor = _require_design_quest_editor(db, quest.project, user_id)
    if quest.status in ("closed", "cancelled"):
        raise ValueError("design_quest_already_closed")
    now = datetime.utcnow()
    old_status = quest.status
    quest.status = "closed"
    quest.closed_at = now
    quest.updated_at = now
    _write_design_quest_event(
        db,
        quest,
        "quest_closed",
        editor.id,
        f"Design quest '{quest.title}' closed.",
        {"old_status": old_status, "reason": reason},
    )
    db.commit()
    db.refresh(quest)
    return quest


def assign_designers_to_quest(
    db: Session,
    quest_id: int,
    designer_user_ids: list[int],
    assigned_by_user_id: int,
) -> list[DesignQuestAssignment]:
    quest = db.query(DesignQuest).filter(DesignQuest.id == quest_id).first()
    if not quest:
        raise ValueError("design_quest_not_found")
    editor = _require_design_quest_editor(db, quest.project, assigned_by_user_id)

    now = datetime.utcnow()
    assignments: list[DesignQuestAssignment] = []
    for designer_user_id in designer_user_ids:
        designer = db.query(User).filter(User.id == designer_user_id).first()
        if not designer or designer.role not in DESIGNER_PORTAL_ROLES:
            raise ValueError("assigned_user_is_not_designer")
        assignment = (
            db.query(DesignQuestAssignment)
            .filter(
                DesignQuestAssignment.quest_id == quest_id,
                DesignQuestAssignment.designer_user_id == designer_user_id,
            )
            .first()
        )
        if assignment:
            assignment.status = "assigned"
            assignment.assigned_by_user_id = editor.id
            assignment.updated_at = now
        else:
            assignment = DesignQuestAssignment(
                quest_id=quest_id,
                designer_user_id=designer_user_id,
                assigned_by_user_id=editor.id,
                status="assigned",
                created_at=now,
                updated_at=now,
            )
            db.add(assignment)
        assignments.append(assignment)

    quest.updated_at = now
    _write_design_quest_event(
        db,
        quest,
        "designers_assigned",
        editor.id,
        f"{len(assignments)} designer(s) assigned to design quest '{quest.title}'.",
        {"designer_user_ids": designer_user_ids},
    )
    db.commit()
    for assignment in assignments:
        db.refresh(assignment)
    return assignments


def link_design_quest_reference(
    db: Session,
    quest_id: int,
    project_file_id: int,
    added_by_user_id: int,
    label: str | None = None,
    visibility: str = "designer_visible",
    sort_order: int | None = None,
) -> DesignQuestReference:
    quest = db.query(DesignQuest).filter(DesignQuest.id == quest_id).first()
    if not quest:
        raise ValueError("design_quest_not_found")
    editor = _require_design_quest_editor(db, quest.project, added_by_user_id)
    project_file = db.query(ProjectFile).filter(ProjectFile.id == project_file_id).first()
    if not project_file or project_file.project_id != quest.project_id:
        raise ValueError("reference_file_not_in_quest_project")
    if visibility not in ("designer_visible", "internal_only"):
        raise ValueError("invalid_reference_visibility")
    if sort_order is None:
        sort_order = (
            db.query(func.max(DesignQuestReference.sort_order))
            .filter(DesignQuestReference.quest_id == quest_id)
            .scalar()
            or 0
        ) + 10

    ref = DesignQuestReference(
        quest_id=quest_id,
        project_file_id=project_file_id,
        label=(label or "").strip() or project_file.original_filename,
        visibility=visibility,
        sort_order=sort_order,
        added_by_user_id=editor.id,
        created_at=datetime.utcnow(),
    )
    db.add(ref)
    quest.updated_at = datetime.utcnow()
    _write_design_quest_event(
        db,
        quest,
        "reference_linked",
        editor.id,
        f"Reference '{ref.label}' linked to design quest '{quest.title}'.",
        {"project_file_id": project_file_id, "visibility": visibility},
    )
    db.commit()
    db.refresh(ref)
    return ref


def can_designer_view_quest(user: User | None, quest: DesignQuest | None) -> bool:
    if not user or not quest:
        return False
    if user.role == "admin":
        return True
    if user.role not in DESIGNER_PORTAL_ROLES:
        return False
    if quest.status not in DESIGN_QUEST_DESIGNER_VISIBLE_STATUSES:
        return False
    if user.role == "designer_manager":
        return True
    if quest.visibility == "all_active_designers":
        return True
    if quest.visibility == "assigned_designers_only":
        return any(
            assignment.designer_user_id == user.id and assignment.status == "assigned"
            for assignment in quest.assignments
        )
    return False


def list_design_quests_for_designer(db: Session, designer_user_id: int) -> list[DesignQuest]:
    user = db.query(User).filter(User.id == designer_user_id).first()
    if not user or user.role not in DESIGNER_PORTAL_ROLES:
        return []
    quests = (
        db.query(DesignQuest)
        .filter(DesignQuest.status.in_(DESIGN_QUEST_DESIGNER_VISIBLE_STATUSES))
        .order_by(DesignQuest.updated_at.desc())
        .all()
    )
    return [quest for quest in quests if can_designer_view_quest(user, quest)]


def shape_design_quest_for_designer(quest: DesignQuest, user: User) -> dict:
    if not can_designer_view_quest(user, quest):
        raise PermissionError("designer_cannot_view_quest")
    return _shape_design_quest_safe_payload(quest)


def shape_design_quest_for_pm_preview(quest: DesignQuest) -> dict:
    """PM-side preview of the future designer-safe payload.

    No permission decision lives here; callers must already have project access.
    The important lock is output shape: never include Project internals or raw
    file paths that designers should not receive.
    """
    return _shape_design_quest_safe_payload(quest)


def _shape_design_quest_safe_payload(quest: DesignQuest) -> dict:
    references = []
    for ref in quest.references:
        if ref.visibility != "designer_visible":
            continue
        project_file = ref.project_file
        references.append({
            "id": ref.id,
            "label": ref.label or (project_file.original_filename if project_file else "Reference"),
            "file_id": ref.project_file_id,
            "original_filename": project_file.original_filename if project_file else None,
            "file_type": project_file.file_type if project_file else None,
            "file_size": project_file.file_size if project_file else None,
        })
    return {
        "id": quest.id,
        "title": quest.title,
        "brief": quest.brief,
        "must_keep": quest.must_keep,
        "must_avoid": quest.must_avoid,
        "status": quest.status,
        "visibility": quest.visibility,
        "soft_deadline": quest.soft_deadline.isoformat() if quest.soft_deadline else None,
        "references": references,
    }


def _design_submission_file_type(ext: str) -> str:
    if ext in ("jpg", "jpeg", "png", "webp"):
        return "image"
    if ext == "pdf":
        return "pdf"
    return "other"


def _validate_design_submission_file(original_filename: str, content: bytes) -> tuple[str, str]:
    if not original_filename or not original_filename.strip():
        raise ValueError("submission_filename_required")
    if "." not in original_filename:
        raise ValueError("submission_invalid_file_type")
    ext = original_filename.rsplit(".", 1)[-1].lower().strip()
    if ext not in DESIGN_SUBMISSION_ALLOWED_EXTENSIONS:
        raise ValueError("submission_invalid_file_type")
    if not content:
        raise ValueError("submission_file_empty")
    if len(content) > DESIGN_SUBMISSION_MAX_BYTES:
        raise ValueError("submission_file_too_large")
    return ext, _design_submission_file_type(ext)


def can_access_design_submission(user: User | None, submission: DesignSubmission | None) -> bool:
    if not user or not submission:
        return False
    if user.role == "admin":
        return True
    if user.role == "pm":
        return _can_edit_project_for_design_quest(user, submission.project)
    if user.role == "designer_manager":
        return can_designer_view_quest(user, submission.quest)
    if user.role == "designer":
        return submission.designer_user_id == user.id and can_designer_view_quest(user, submission.quest)
    return False


def _require_design_submission_reviewer(
    db: Session,
    submission_id: int,
    user_id: int,
) -> tuple[DesignSubmission, User]:
    submission = db.query(DesignSubmission).filter(DesignSubmission.id == submission_id).first()
    if not submission:
        raise ValueError("design_submission_not_found")
    reviewer = _require_design_quest_editor(db, submission.project, user_id)
    return submission, reviewer


def list_design_submissions_for_quest(db: Session, quest_id: int) -> list[DesignSubmission]:
    return (
        db.query(DesignSubmission)
        .filter(
            DesignSubmission.quest_id == quest_id,
            DesignSubmission.status != "archived",
        )
        .order_by(DesignSubmission.updated_at.desc())
        .all()
    )


def list_design_submissions_for_designer(
    db: Session,
    designer_user_id: int,
    quest_id: int | None = None,
) -> list[DesignSubmission]:
    user = db.query(User).filter(User.id == designer_user_id).first()
    if not user or user.role not in DESIGNER_PORTAL_ROLES:
        return []
    query = db.query(DesignSubmission).filter(DesignSubmission.status != "archived")
    if user.role == "designer":
        query = query.filter(DesignSubmission.designer_user_id == designer_user_id)
    if quest_id is not None:
        query = query.filter(DesignSubmission.quest_id == quest_id)
    submissions = query.order_by(DesignSubmission.updated_at.desc()).all()
    return [submission for submission in submissions if can_access_design_submission(user, submission)]


def list_open_revision_requests_for_submission(db: Session, submission_id: int) -> list[DesignRevisionRequest]:
    return (
        db.query(DesignRevisionRequest)
        .filter(
            DesignRevisionRequest.submission_id == submission_id,
            DesignRevisionRequest.status.in_(DESIGN_REVISION_OPEN_STATUSES),
        )
        .order_by(DesignRevisionRequest.created_at.desc())
        .all()
    )


def _shape_design_submission_version(version: DesignSubmissionVersion) -> dict:
    return {
        "id": version.id,
        "version_number": version.version_number,
        "original_filename": version.original_filename,
        "file_type": version.file_type,
        "file_size": version.file_size,
        "designer_note": version.designer_note,
        "revision_request_id": version.revision_request_id,
        "is_selected": bool(version.submission and version.submission.selected_version_id == version.id),
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }


def shape_design_submission_for_designer(submission: DesignSubmission, user: User) -> dict:
    if not can_access_design_submission(user, submission):
        raise PermissionError("designer_cannot_view_submission")
    versions = [_shape_design_submission_version(version) for version in submission.versions]
    latest_version = versions[-1] if versions else None
    open_revisions = [
        shape_design_revision_request_for_designer(revision_request, user)
        for revision_request in submission.revision_requests
        if revision_request.status in DESIGN_REVISION_OPEN_STATUSES
    ]
    return {
        "id": submission.id,
        "quest_id": submission.quest_id,
        "status": submission.status,
        "title": submission.title,
        "designer_note": submission.designer_note,
        "created_at": submission.created_at.isoformat() if submission.created_at else None,
        "updated_at": submission.updated_at.isoformat() if submission.updated_at else None,
        "versions": versions,
        "latest_version": latest_version,
        "open_revision_requests": open_revisions,
    }


def shape_design_submission_for_pm(submission: DesignSubmission) -> dict:
    versions = [_shape_design_submission_version(version) for version in submission.versions]
    latest_version = versions[-1] if versions else None
    designer = submission.designer
    open_revisions = [
        shape_design_revision_request_for_pm(revision_request)
        for revision_request in submission.revision_requests
        if revision_request.status in DESIGN_REVISION_OPEN_STATUSES
    ]
    return {
        "id": submission.id,
        "quest_id": submission.quest_id,
        "status": submission.status,
        "title": submission.title,
        "designer_note": submission.designer_note,
        "designer_display": (
            designer.display_name or designer.username
            if designer else "Designer"
        ),
        "created_at": submission.created_at.isoformat() if submission.created_at else None,
        "updated_at": submission.updated_at.isoformat() if submission.updated_at else None,
        "versions": versions,
        "latest_version": latest_version,
        "version_count": len(versions),
        "open_revision_requests": open_revisions,
        "selected_version_id": submission.selected_version_id,
        "selected_at": submission.selected_at.isoformat() if submission.selected_at else None,
    }


def _shape_design_revision_item(item: DesignRevisionItem) -> dict:
    return {
        "id": item.id,
        "text": item.text,
        "status": item.status,
        "sort_order": item.sort_order,
    }


def shape_design_revision_request_for_designer(revision_request: DesignRevisionRequest, user: User) -> dict:
    if not can_access_design_submission(user, revision_request.submission):
        raise PermissionError("designer_cannot_view_revision_request")
    return {
        "id": revision_request.id,
        "submission_id": revision_request.submission_id,
        "status": revision_request.status,
        "general_comment": revision_request.general_comment,
        "created_at": revision_request.created_at.isoformat() if revision_request.created_at else None,
        "items": [_shape_design_revision_item(item) for item in revision_request.items],
    }


def shape_design_revision_request_for_pm(revision_request: DesignRevisionRequest) -> dict:
    return {
        "id": revision_request.id,
        "submission_id": revision_request.submission_id,
        "status": revision_request.status,
        "general_comment": revision_request.general_comment,
        "created_at": revision_request.created_at.isoformat() if revision_request.created_at else None,
        "items": [_shape_design_revision_item(item) for item in revision_request.items],
    }


def shortlist_design_submission(db: Session, submission_id: int, user_id: int) -> DesignSubmission:
    submission, reviewer = _require_design_submission_reviewer(db, submission_id, user_id)
    if submission.status == "rejected":
        raise ValueError("cannot_shortlist_rejected_submission")
    submission.status = "shortlisted"
    submission.updated_at = datetime.utcnow()
    if submission.quest.status == "open":
        submission.quest.status = "reviewing"
    submission.quest.updated_at = submission.updated_at
    _write_design_quest_event(
        db,
        submission.quest,
        "submission_shortlisted",
        reviewer.id,
        f"Submission from {submission.designer.display_name or submission.designer.username} shortlisted.",
        {"submission_id": submission.id},
    )
    db.commit()
    db.refresh(submission)
    return submission


def reject_design_submission(
    db: Session,
    submission_id: int,
    user_id: int,
    reason: str | None = None,
) -> DesignSubmission:
    submission, reviewer = _require_design_submission_reviewer(db, submission_id, user_id)
    submission.status = "rejected"
    submission.updated_at = datetime.utcnow()
    if submission.quest.status == "open":
        submission.quest.status = "reviewing"
    submission.quest.updated_at = submission.updated_at
    _write_design_quest_event(
        db,
        submission.quest,
        "submission_rejected",
        reviewer.id,
        f"Submission from {submission.designer.display_name or submission.designer.username} rejected.",
        {"submission_id": submission.id, "reason": reason},
    )
    db.commit()
    db.refresh(submission)
    return submission


def request_design_revision(
    db: Session,
    submission_id: int,
    user_id: int,
    general_comment: str | None,
    checklist_text: str | None,
) -> DesignRevisionRequest:
    submission, reviewer = _require_design_submission_reviewer(db, submission_id, user_id)
    if submission.status in ("rejected", "selected", "archived"):
        raise ValueError("submission_not_revisionable")
    checklist_items = [
        line.strip("-• \t")
        for line in (checklist_text or "").splitlines()
        if line.strip("-• \t")
    ]
    if not (general_comment or "").strip() and not checklist_items:
        raise ValueError("revision_request_requires_content")
    now = datetime.utcnow()
    revision_request = DesignRevisionRequest(
        submission_id=submission.id,
        quest_id=submission.quest_id,
        project_id=submission.project_id,
        requested_by_user_id=reviewer.id,
        status="open",
        general_comment=(general_comment or "").strip() or None,
        created_at=now,
    )
    db.add(revision_request)
    db.flush()
    for index, item_text in enumerate(checklist_items, start=1):
        db.add(DesignRevisionItem(
            revision_request_id=revision_request.id,
            text=item_text,
            status="open",
            sort_order=index * 10,
            created_at=now,
        ))
    submission.status = "revision_requested"
    submission.updated_at = now
    submission.quest.status = "revision_needed"
    submission.quest.updated_at = now
    _write_design_quest_event(
        db,
        submission.quest,
        "revision_requested",
        reviewer.id,
        f"Revision requested for submission from {submission.designer.display_name or submission.designer.username}.",
        {
            "submission_id": submission.id,
            "revision_request_id": revision_request.id,
            "item_count": len(checklist_items),
        },
    )
    db.commit()
    db.refresh(revision_request)
    return revision_request


def select_final_design_submission_version(
    db: Session,
    submission_id: int,
    version_id: int,
    user_id: int,
) -> ProjectFile:
    submission, reviewer = _require_design_submission_reviewer(db, submission_id, user_id)
    if submission.status in ("rejected", "archived"):
        raise ValueError("submission_not_selectable")
    version = (
        db.query(DesignSubmissionVersion)
        .filter(
            DesignSubmissionVersion.id == version_id,
            DesignSubmissionVersion.submission_id == submission.id,
            DesignSubmissionVersion.quest_id == submission.quest_id,
            DesignSubmissionVersion.project_id == submission.project_id,
        )
        .first()
    )
    if not version:
        raise ValueError("design_submission_version_not_found")
    source_path = os.path.join(UPLOAD_DIR, version.filename)
    if not os.path.exists(source_path):
        raise ValueError("design_submission_file_missing")

    now = datetime.utcnow()
    ext = version.filename.rsplit(".", 1)[-1].lower() if "." in version.filename else ""
    promoted_filename = f"promoted-rendering-{uuid.uuid4().hex}.{ext}" if ext else f"promoted-rendering-{uuid.uuid4().hex}"
    promoted_path = os.path.join(UPLOAD_DIR, promoted_filename)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    shutil.copyfile(source_path, promoted_path)

    for sibling in list_design_submissions_for_quest(db, submission.quest_id):
        if sibling.id == submission.id:
            continue
        if sibling.status == "selected":
            sibling.status = "shortlisted"
        sibling.selected_version_id = None
        sibling.selected_by_user_id = None
        sibling.selected_at = None

    source_metadata = {
        "quest_id": submission.quest_id,
        "submission_id": submission.id,
        "version_id": version.id,
        "version_number": version.version_number,
        "designer_user_id": submission.designer_user_id,
        "designer_display": submission.designer.display_name or submission.designer.username,
        "selected_by_user_id": reviewer.id,
        "selected_by_display": reviewer.display_name or reviewer.username,
        "selected_at": now.isoformat(),
        "original_filename": version.original_filename,
    }
    rendering = ProjectFile(
        project_id=submission.project_id,
        filename=promoted_filename,
        original_filename=version.original_filename,
        file_path=f"uploads/{promoted_filename}",
        file_type=version.file_type,
        file_category="rendering",
        file_size=version.file_size,
        source_note=(
            f"Promoted from design submission v{version.version_number} "
            f"by {submission.designer.display_name or submission.designer.username}."
        ),
        source_type="design_submission_version",
        source_id=version.id,
        source_metadata=source_metadata,
        uploaded_at=now,
    )
    db.add(rendering)
    db.flush()

    submission.status = "selected"
    submission.selected_version_id = version.id
    submission.selected_by_user_id = reviewer.id
    submission.selected_at = now
    submission.updated_at = now

    submission.quest.status = "selected"
    submission.quest.selected_submission_id = submission.id
    submission.quest.selected_version_id = version.id
    submission.quest.selected_by_user_id = reviewer.id
    submission.quest.selected_at = now
    submission.quest.promoted_project_file_id = rendering.id
    submission.quest.updated_at = now

    _write_design_quest_event(
        db,
        submission.quest,
        "submission_selected",
        reviewer.id,
        f"Submission from {submission.designer.display_name or submission.designer.username} selected as final.",
        {
            "submission_id": submission.id,
            "version_id": version.id,
            "version_number": version.version_number,
        },
    )
    _write_design_quest_event(
        db,
        submission.quest,
        "submission_promoted_to_rendering",
        reviewer.id,
        f"Submission version {version.version_number} promoted to project rendering.",
        {
            "submission_id": submission.id,
            "version_id": version.id,
            "project_file_id": rendering.id,
        },
    )
    write_change(
        db,
        submission.project_id,
        "file_upload",
        changed_by="user",
        summary=f"Selected design promoted to renderings: {version.original_filename}.",
        source_type="design_submission_promotion",
    )
    db.commit()
    db.refresh(rendering)
    return rendering


def get_selected_design_rendering_source(db: Session, project_id: int) -> dict | None:
    rendering = (
        db.query(ProjectFile)
        .filter(
            ProjectFile.project_id == project_id,
            ProjectFile.file_category == "rendering",
            ProjectFile.source_type == "design_submission_version",
        )
        .order_by(ProjectFile.uploaded_at.desc())
        .first()
    )
    if not rendering:
        return None
    metadata = rendering.source_metadata or {}
    return {
        "project_file_id": rendering.id,
        "filename": rendering.filename,
        "original_filename": rendering.original_filename,
        "uploaded_at": rendering.uploaded_at.isoformat() if rendering.uploaded_at else None,
        "designer_display": metadata.get("designer_display"),
        "selected_by_display": metadata.get("selected_by_display"),
        "selected_at": metadata.get("selected_at"),
        "version_number": metadata.get("version_number"),
        "submission_id": metadata.get("submission_id"),
        "version_id": metadata.get("version_id"),
    }


def get_project_design_status(db: Session, project_id: int) -> dict:
    quest = (
        db.query(DesignQuest)
        .filter(DesignQuest.project_id == project_id)
        .order_by(DesignQuest.updated_at.desc(), DesignQuest.created_at.desc())
        .first()
    )
    if not quest:
        return {
            "key": "none",
            "quest_id": None,
            "title": None,
            "label_key": "design_quest.status_none",
            "is_timeline_blocking": False,
            "can_mark_complete": False,
        }

    submissions = [s for s in quest.submissions if s.status != "archived"]
    open_revision_count = sum(
        1
        for submission in submissions
        for revision_request in submission.revision_requests
        if revision_request.status in DESIGN_REVISION_OPEN_STATUSES
    )
    if quest.design_completed_at:
        key = "design_complete"
    elif quest.status in ("closed", "cancelled"):
        key = "closed"
    elif quest.status == "draft":
        key = "draft"
    elif quest.selected_version_id and quest.promoted_project_file_id:
        key = "final_selected"
    elif open_revision_count:
        key = "revision_requested"
    elif submissions:
        key = "pm_review_needed"
    else:
        key = "waiting_for_submissions"

    selected_by = quest.selected_by
    completed_by = quest.design_completed_by
    return {
        "key": key,
        "quest_id": quest.id,
        "title": quest.title,
        "label_key": f"design_quest.status_{key}",
        "is_timeline_blocking": bool(quest.is_timeline_blocking),
        "can_mark_complete": key == "final_selected",
        "selected_version_id": quest.selected_version_id,
        "selected_at": quest.selected_at.isoformat() if quest.selected_at else None,
        "selected_by_display": (
            selected_by.display_name or selected_by.username
            if selected_by else None
        ),
        "design_completed_at": quest.design_completed_at.isoformat() if quest.design_completed_at else None,
        "design_completed_by_display": (
            completed_by.display_name or completed_by.username
            if completed_by else None
        ),
        "submission_count": len(submissions),
        "open_revision_count": open_revision_count,
    }


def mark_design_quest_complete(db: Session, quest_id: int, user_id: int) -> DesignQuest:
    quest = db.query(DesignQuest).filter(DesignQuest.id == quest_id).first()
    if not quest:
        raise ValueError("design_quest_not_found")
    actor = _require_design_quest_editor(db, quest.project, user_id)
    if not quest.selected_version_id or not quest.promoted_project_file_id:
        raise ValueError("design_final_not_selected")
    if quest.design_completed_at:
        return quest
    now = datetime.utcnow()
    quest.design_completed_at = now
    quest.design_completed_by_user_id = actor.id
    quest.updated_at = now
    _write_design_quest_event(
        db,
        quest,
        "design_completed",
        actor.id,
        "Design marked complete.",
        {
            "selected_submission_id": quest.selected_submission_id,
            "selected_version_id": quest.selected_version_id,
            "promoted_project_file_id": quest.promoted_project_file_id,
        },
    )
    write_change(
        db,
        quest.project_id,
        "event_note",
        changed_by="user",
        summary="Design marked complete.",
        source_type="design_quest",
    )
    db.commit()
    db.refresh(quest)
    return quest


def _require_designer_manager(db: Session, user_id: int | None) -> User:
    user = db.query(User).filter(User.id == user_id).first() if user_id else None
    if not user or user.role != "designer_manager":
        raise PermissionError("designer_manager_required")
    return user


def list_designer_manager_operations(db: Session, manager_user_id: int) -> dict:
    _require_designer_manager(db, manager_user_id)
    designers = (
        db.query(User)
        .filter(User.role == "designer")
        .order_by(User.display_name.asc(), User.username.asc())
        .all()
    )
    quests = (
        db.query(DesignQuest)
        .filter(
            DesignQuest.visibility == "assigned_designers_only",
            DesignQuest.status.in_(("open", "reviewing", "revision_needed", "selected")),
        )
        .order_by(DesignQuest.updated_at.desc())
        .all()
    )
    rejected_submissions = (
        db.query(DesignSubmission)
        .filter(DesignSubmission.status == "rejected")
        .order_by(DesignSubmission.updated_at.desc())
        .all()
    )
    return {
        "designers": [
            {
                "id": designer.id,
                "username": designer.username,
                "display_name": designer.display_name or designer.username,
            }
            for designer in designers
        ],
        "quests": [
            {
                "id": quest.id,
                "title": quest.title,
                "status": quest.status,
                "soft_deadline": quest.soft_deadline,
                "assigned_designers": [
                    {
                        "id": assignment.designer.id,
                        "display_name": assignment.designer.display_name or assignment.designer.username,
                    }
                    for assignment in quest.assignments
                    if assignment.status == "assigned" and assignment.designer
                ],
            }
            for quest in quests
        ],
        "rejected_submissions": [
            {
                "id": submission.id,
                "quest_id": submission.quest_id,
                "quest_title": submission.quest.title if submission.quest else "Design quest",
                "designer_display": (
                    submission.designer.display_name or submission.designer.username
                    if submission.designer else "Designer"
                ),
                "title": submission.title,
                "updated_at": submission.updated_at,
            }
            for submission in rejected_submissions
        ],
    }


def manager_assign_designer_to_quest(
    db: Session,
    quest_id: int,
    designer_user_id: int,
    manager_user_id: int,
) -> DesignQuestAssignment:
    manager = _require_designer_manager(db, manager_user_id)
    quest = db.query(DesignQuest).filter(DesignQuest.id == quest_id).first()
    if not quest:
        raise ValueError("design_quest_not_found")
    if quest.visibility != "assigned_designers_only":
        raise ValueError("quest_not_assigned_only")
    if quest.status not in ("open", "reviewing", "revision_needed", "selected"):
        raise ValueError("quest_not_assignable")
    designer = db.query(User).filter(User.id == designer_user_id).first()
    if not designer or designer.role != "designer":
        raise ValueError("assigned_user_is_not_designer")
    now = datetime.utcnow()
    assignment = (
        db.query(DesignQuestAssignment)
        .filter(
            DesignQuestAssignment.quest_id == quest.id,
            DesignQuestAssignment.designer_user_id == designer.id,
        )
        .first()
    )
    if assignment:
        assignment.status = "assigned"
        assignment.assigned_by_user_id = manager.id
        assignment.updated_at = now
    else:
        assignment = DesignQuestAssignment(
            quest_id=quest.id,
            designer_user_id=designer.id,
            assigned_by_user_id=manager.id,
            status="assigned",
            created_at=now,
            updated_at=now,
        )
        db.add(assignment)
    quest.updated_at = now
    _write_design_quest_event(
        db,
        quest,
        "manager_designer_assigned",
        manager.id,
        f"Designer manager assigned {designer.display_name or designer.username} to design quest.",
        {"designer_user_id": designer.id},
    )
    db.commit()
    db.refresh(assignment)
    return assignment


def manager_reopen_design_submission(
    db: Session,
    submission_id: int,
    manager_user_id: int,
) -> DesignSubmission:
    manager = _require_designer_manager(db, manager_user_id)
    submission = db.query(DesignSubmission).filter(DesignSubmission.id == submission_id).first()
    if not submission:
        raise ValueError("design_submission_not_found")
    if submission.status != "rejected":
        raise ValueError("submission_not_reopenable")
    if submission.quest.status in ("closed", "cancelled"):
        raise ValueError("quest_not_accepting_reopen")
    now = datetime.utcnow()
    submission.status = "submitted"
    submission.updated_at = now
    if submission.quest.status == "open":
        submission.quest.status = "reviewing"
    submission.quest.updated_at = now
    _write_design_quest_event(
        db,
        submission.quest,
        "manager_submission_reopened",
        manager.id,
        f"Designer manager reopened rejected submission from {submission.designer.display_name or submission.designer.username}.",
        {"submission_id": submission.id},
    )
    db.commit()
    db.refresh(submission)
    return submission


def create_or_append_design_submission_version(
    db: Session,
    quest_id: int,
    designer_user_id: int,
    original_filename: str,
    content: bytes,
    designer_note: str | None = None,
    title: str | None = None,
    revision_request_id: int | None = None,
) -> DesignSubmission:
    designer = db.query(User).filter(User.id == designer_user_id).first()
    quest = db.query(DesignQuest).filter(DesignQuest.id == quest_id).first()
    if not designer or designer.role not in DESIGNER_PORTAL_ROLES:
        raise PermissionError("user_cannot_submit_design")
    if not quest or not can_designer_view_quest(designer, quest):
        raise PermissionError("designer_cannot_view_quest")
    if quest.status not in DESIGN_QUEST_SUBMISSION_OPEN_STATUSES:
        raise ValueError("quest_not_accepting_submissions")

    ext, file_type = _validate_design_submission_file(original_filename, content)
    now = datetime.utcnow()
    revision_request = None
    submission = (
        db.query(DesignSubmission)
        .filter(
            DesignSubmission.quest_id == quest_id,
            DesignSubmission.designer_user_id == designer.id,
            DesignSubmission.status != "archived",
        )
            .first()
    )
    if revision_request_id is not None:
        revision_request = db.query(DesignRevisionRequest).filter(
            DesignRevisionRequest.id == revision_request_id,
            DesignRevisionRequest.quest_id == quest_id,
            DesignRevisionRequest.status.in_(DESIGN_REVISION_OPEN_STATUSES),
        ).first()
        if not revision_request:
            raise ValueError("revision_request_not_found")
        if not submission or revision_request.submission_id != submission.id:
            raise PermissionError("revision_request_not_for_designer_submission")
    if submission is None:
        if revision_request_id is not None:
            raise ValueError("revision_request_requires_existing_submission")
        submission = DesignSubmission(
            quest_id=quest.id,
            project_id=quest.project_id,
            designer_user_id=designer.id,
            status="submitted",
            title=(title or "").strip() or None,
            designer_note=(designer_note or "").strip() or None,
            created_at=now,
            updated_at=now,
        )
        db.add(submission)
        db.flush()
    else:
        if title and title.strip():
            submission.title = title.strip()
        if designer_note and designer_note.strip():
            submission.designer_note = designer_note.strip()
        submission.updated_at = now

    version_number = (
        db.query(func.max(DesignSubmissionVersion.version_number))
        .filter(DesignSubmissionVersion.submission_id == submission.id)
        .scalar()
        or 0
    ) + 1
    unique_name = f"design-submission-{uuid.uuid4().hex}.{ext}"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    disk_path = os.path.join(UPLOAD_DIR, unique_name)
    with open(disk_path, "wb") as fh:
        fh.write(content)

    version = DesignSubmissionVersion(
        submission_id=submission.id,
        revision_request_id=revision_request.id if revision_request else None,
        quest_id=quest.id,
        project_id=quest.project_id,
        version_number=version_number,
        filename=unique_name,
        original_filename=original_filename,
        file_type=file_type,
        file_size=len(content),
        designer_note=(designer_note or "").strip() or None,
        uploaded_by_user_id=designer.id,
        created_at=now,
    )
    db.add(version)
    if revision_request is not None:
        revision_request.status = "resolved"
        revision_request.resolved_at = now
        for item in revision_request.items:
            item.status = "resolved"
        submission.status = "revised"
    elif submission.status == "revision_requested":
        submission.status = "revised"
    quest.updated_at = now
    _write_design_quest_event(
        db,
        quest,
        "revision_uploaded" if revision_request else "submission_uploaded",
        designer.id,
        f"{designer.display_name or designer.username} uploaded design submission v{version_number}.",
        {
            "submission_id": submission.id,
            "version_number": version_number,
            "original_filename": original_filename,
            "revision_request_id": revision_request.id if revision_request else None,
        },
    )
    db.commit()
    db.refresh(submission)
    return submission


def get_design_submission_version_for_download(
    db: Session,
    version_id: int,
    user: User | None,
) -> DesignSubmissionVersion:
    version = (
        db.query(DesignSubmissionVersion)
        .filter(DesignSubmissionVersion.id == version_id)
        .first()
    )
    if not version or not can_access_design_submission(user, version.submission):
        raise PermissionError("submission_version_not_found")
    return version


# ---------------------------------------------------------------------------
# Build 30A — idempotency tokens for the project-create POST handlers
# ---------------------------------------------------------------------------

TOKEN_TTL = timedelta(hours=24)


def mint_creation_token(db: Session, user_id: int) -> str:
    """Mint a fresh single-use idempotency token for a user, and opportunistically
    sweep tokens older than TOKEN_TTL that were never claimed.

    Returns the token string for the form to embed as a hidden input.
    """
    cutoff = datetime.utcnow() - TOKEN_TTL
    db.query(ProjectCreationToken).filter(
        ProjectCreationToken.created_at < cutoff,
        ProjectCreationToken.claimed_at.is_(None),
    ).delete(synchronize_session=False)

    token = uuid.uuid4().hex
    db.add(ProjectCreationToken(
        token=token,
        user_id=user_id,
        created_at=datetime.utcnow(),
    ))
    db.commit()
    return token


class IdempotencyResult:
    """Return shape for create_project_with_idempotency. Either:
    - status == "created" → project is the freshly-inserted Project.
    - status == "duplicate" → project_id is the originally-created project's id.
    - status == "invalid" → token missing / wrong user / never minted.
    """
    def __init__(self, status: str, project=None, project_id: int | None = None):
        self.status = status
        self.project = project
        self.project_id = project_id


class BatchIdempotencyResult:
    """Return shape for create_projects_batch_with_idempotency. Either:
    - status == "created" → projects is the list of newly-inserted Projects;
        skipped is a list of (row_index, reason) tuples for rows that failed
        validation (missing name, etc).
    - status == "duplicate" → project_ids is the list of originally-created
        project ids from the prior successful batch claim.
    - status == "invalid" → token missing / wrong user / never minted.
    """
    def __init__(
        self,
        status: str,
        projects: list | None = None,
        project_ids: list[int] | None = None,
        skipped: list[tuple[int, str]] | None = None,
    ):
        self.status = status
        self.projects = projects or []
        self.project_ids = project_ids or []
        self.skipped = skipped or []


def create_projects_batch_with_idempotency(
    db: Session,
    rows: list[dict],
    prototype_rounds: str,
    token: str,
    user_id: int,
) -> BatchIdempotencyResult:
    """Build 30B — atomic token claim + N project inserts in one transaction.

    Rows that fail validation (missing name) are skipped with a reason; the
    rest commit together. Reuses the Build 30A token table — one token covers
    the whole batch, so a double-click on "Save Batch" claims once and racing
    POSTs redirect to the prior batch's project IDs (recorded via comma-
    separated id list in the token's project_id-as-string convention is too
    hacky; instead we store the FIRST project id and on duplicate-claim we
    re-query all projects created with that token via the token timestamp +
    user. For now, the redirect target is simply /my-projects so the user
    sees their full set; the stored project_id is the first inserted row for
    audit pointing).
    """
    if not token:
        return BatchIdempotencyResult("invalid")

    claimed_at = datetime.utcnow()
    updated = db.execute(
        update(ProjectCreationToken)
        .where(ProjectCreationToken.token == token)
        .where(ProjectCreationToken.user_id == user_id)
        .where(ProjectCreationToken.claimed_at.is_(None))
        .values(claimed_at=claimed_at)
    ).rowcount

    if updated == 0:
        existing = db.query(ProjectCreationToken).filter(
            ProjectCreationToken.token == token,
            ProjectCreationToken.user_id == user_id,
        ).first()
        if existing and existing.project_id:
            return BatchIdempotencyResult("duplicate", project_ids=[existing.project_id])
        return BatchIdempotencyResult("invalid")

    created: list = []
    skipped: list[tuple[int, str]] = []
    for i, data in enumerate(rows):
        name = (data.get("name") or "").strip()
        if not name:
            skipped.append((i, "row missing project name — skipped"))
            continue
        try:
            project = _build_project_in_session(db, data, prototype_rounds)
            created.append(project)
        except Exception as exc:
            skipped.append((i, f"row {i + 1}: {exc}"))

    if created:
        # Stamp the first created project id on the token for audit; the
        # batch summary URL is /my-projects?imported=N regardless.
        db.query(ProjectCreationToken).filter(
            ProjectCreationToken.token == token
        ).update({"project_id": created[0].id}, synchronize_session=False)

    db.commit()
    for project in created:
        db.refresh(project)
    return BatchIdempotencyResult("created", projects=created, skipped=skipped)


def create_project_with_idempotency(
    db: Session,
    data: dict,
    prototype_rounds: str,
    token: str,
    user_id: int,
) -> IdempotencyResult:
    """Build 30A — atomic token-claim + project insert.

    Claim-by-UPDATE-rowcount: the first POST's UPDATE acquires the write
    lock and flips claimed_at; racing POSTs see rowcount=0 and we redirect
    to the originally-created project_id instead of inserting a duplicate.
    Works on both SQLite (which serializes writes) and PostgreSQL (which
    acquires a row lock on the matched row).
    """
    if not token:
        return IdempotencyResult("invalid")

    claimed_at = datetime.utcnow()
    updated = db.execute(
        update(ProjectCreationToken)
        .where(ProjectCreationToken.token == token)
        .where(ProjectCreationToken.user_id == user_id)
        .where(ProjectCreationToken.claimed_at.is_(None))
        .values(claimed_at=claimed_at)
    ).rowcount

    if updated == 0:
        # Either: token doesn't exist / wrong user / already-claimed.
        existing = db.query(ProjectCreationToken).filter(
            ProjectCreationToken.token == token,
            ProjectCreationToken.user_id == user_id,
        ).first()
        if existing and existing.project_id:
            return IdempotencyResult("duplicate", project_id=existing.project_id)
        return IdempotencyResult("invalid")

    # We hold the claim; build the project in the same transaction.
    project = _build_project_in_session(db, data, prototype_rounds)
    db.query(ProjectCreationToken).filter(
        ProjectCreationToken.token == token
    ).update({"project_id": project.id}, synchronize_session=False)
    db.commit()
    db.refresh(project)
    return IdempotencyResult("created", project=project)

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
        "target_factory_cost_text": "Target Factory Cost",
        "target_msrp_text": "Target MSRP",
        "planned_launch_date": "Planned Launch Date",
        "project_thesis": "Product Thesis",
        "product_manager": "Product Manager",
    }

    for field, new_val in data.items():
        if new_val == "":
            new_val = None
        if field in ("target_factory_cost", "target_msrp") and f"{field}_text" in data:
            setattr(project, field, new_val)
            continue
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
    """Delete a project + all related rows.

    Most child tables cascade via the SQLAlchemy `Project` relationships
    (phases, files, changes, ai_messages, idea_links, journal_entries,
    variants, variant_components, blockers — all cascade="all, delete-orphan").

    Two child tables have a `project_id` FK but NO corresponding `Project`
    relationship, so cascade does not fire. We delete them explicitly before
    the ORM delete to avoid a FOREIGN KEY constraint violation. This bug
    was silent on SQLite (dev) because the default `PRAGMA foreign_keys`
    is OFF, but always raised a 500 on PostgreSQL (Railway prod) where
    FK enforcement is always on.

      - `ai_conversations`: every AI-intake project gets one. The
        cascade also has to handle `ai_messages.conversation_id`, which
        is referenced via a separate FK chain through AIConversation.
      - `project_creation_tokens`: the Build 30A idempotency token row.
        Cleanup is opportunistic in normal operation but stragglers
        block project delete.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return False

    # Late imports to mirror the pattern used elsewhere in this file.
    from app.models import AIConversation, AIMessage, ProjectCreationToken

    # Sever ai_messages.conversation_id BEFORE the AIConversation rows go,
    # since the Project.ai_messages relationship already cascades via
    # project_id but those messages may also reference conversations being
    # deleted in the same transaction.
    db.query(AIMessage).filter(
        AIMessage.project_id == project_id
    ).update({"conversation_id": None}, synchronize_session=False)
    db.query(AIConversation).filter(
        AIConversation.project_id == project_id
    ).delete(synchronize_session=False)
    db.query(ProjectCreationToken).filter(
        ProjectCreationToken.project_id == project_id
    ).delete(synchronize_session=False)

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
        if field == "target_factory_cost":
            non_empty = db.query(func.count(Project.id)).filter(
                (Project.target_factory_cost.isnot(None)) | (Project.target_factory_cost_text.isnot(None))
            ).scalar()
        elif field == "target_msrp":
            non_empty = db.query(func.count(Project.id)).filter(
                (Project.target_msrp.isnot(None)) | (Project.target_msrp_text.isnot(None))
            ).scalar()
        # For thesis, also count short ones as empty
        elif field == "project_thesis":
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
            elif field in ("target_factory_cost", "target_msrp"):
                if not price_field_present(p, field):
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


def list_planning_modules(db: Session, active_only: bool = True) -> list[PlanningModule]:
    """v1.4 Build 01 — read-only module library for admin inspection."""
    q = db.query(PlanningModule)
    if active_only:
        q = q.filter(PlanningModule.is_active.is_(True))
    return q.order_by(PlanningModule.sort_order, PlanningModule.title).all()


def list_planning_templates(db: Session, active_only: bool = True) -> list[PlanningTemplate]:
    """v1.4 Build 01 — read-only system/user template inventory."""
    q = db.query(PlanningTemplate)
    if active_only:
        q = q.filter(PlanningTemplate.is_active.is_(True))
    return q.order_by(PlanningTemplate.sort_order, PlanningTemplate.name).all()


def list_planning_templates_for_user(
    db: Session,
    user: User | None,
    active_only: bool = True,
) -> list[PlanningTemplate]:
    """Return system templates plus user templates visible to the caller."""
    system_q = db.query(PlanningTemplate).filter(PlanningTemplate.is_system.is_(True))
    if active_only:
        system_q = system_q.filter(PlanningTemplate.is_active.is_(True))
    system_templates = system_q.order_by(PlanningTemplate.sort_order, PlanningTemplate.name).all()

    user_q = db.query(PlanningTemplate).filter(PlanningTemplate.is_system.is_(False))
    if active_only:
        user_q = user_q.filter(PlanningTemplate.is_active.is_(True))
    if not user:
        user_templates = []
    elif user.role == "admin":
        user_templates = user_q.order_by(desc(PlanningTemplate.created_at), PlanningTemplate.name).all()
    else:
        user_templates = (
            user_q
            .filter(PlanningTemplate.created_by_user_id == user.id)
            .order_by(desc(PlanningTemplate.created_at), PlanningTemplate.name)
            .all()
        )
    return system_templates + user_templates


def get_planning_template_counts(db: Session) -> dict[int, dict[str, int]]:
    """Return node/edge counts keyed by template id for the admin modules page."""
    node_rows = (
        db.query(PlanningTemplateNode.template_id, func.count(PlanningTemplateNode.id))
        .group_by(PlanningTemplateNode.template_id)
        .all()
    )
    edge_rows = (
        db.query(PlanningTemplateEdge.template_id, func.count(PlanningTemplateEdge.id))
        .group_by(PlanningTemplateEdge.template_id)
        .all()
    )
    counts: dict[int, dict[str, int]] = {}
    for template_id, count in node_rows:
        counts.setdefault(template_id, {"nodes": 0, "edges": 0})["nodes"] = count
    for template_id, count in edge_rows:
        counts.setdefault(template_id, {"nodes": 0, "edges": 0})["edges"] = count
    return counts


def get_active_planning_sandbox(db: Session, project_id: int) -> PlanningSandbox | None:
    """Return the one editable draft sandbox for a project, if present."""
    return (
        db.query(PlanningSandbox)
        .filter(PlanningSandbox.project_id == project_id, PlanningSandbox.status == "draft")
        .order_by(PlanningSandbox.updated_at.desc())
        .first()
    )


def _get_project_draft_sandbox(
    db: Session,
    project_id: int,
    sandbox_id: int,
) -> PlanningSandbox:
    sandbox = (
        db.query(PlanningSandbox)
        .filter(PlanningSandbox.id == sandbox_id, PlanningSandbox.project_id == project_id)
        .first()
    )
    if not sandbox:
        raise ValueError("sandbox_not_found")
    if sandbox.status != "draft":
        raise ValueError("sandbox_not_draft")
    return sandbox


def _get_project_sandbox_node(
    db: Session,
    project_id: int,
    sandbox_id: int,
    node_id: int,
) -> PlanningSandboxNode:
    _get_project_draft_sandbox(db, project_id, sandbox_id)
    node = (
        db.query(PlanningSandboxNode)
        .filter(
            PlanningSandboxNode.id == node_id,
            PlanningSandboxNode.sandbox_id == sandbox_id,
        )
        .first()
    )
    if not node:
        raise ValueError("node_not_found")
    return node


def _get_project_sandbox_edge(
    db: Session,
    project_id: int,
    sandbox_id: int,
    edge_id: int,
) -> PlanningSandboxEdge:
    _get_project_draft_sandbox(db, project_id, sandbox_id)
    edge = (
        db.query(PlanningSandboxEdge)
        .filter(
            PlanningSandboxEdge.id == edge_id,
            PlanningSandboxEdge.sandbox_id == sandbox_id,
        )
        .first()
    )
    if not edge:
        raise ValueError("edge_not_found")
    return edge


def _parse_node_id_list(node_ids) -> list[int]:
    if node_ids is None:
        return []
    if isinstance(node_ids, str):
        raw_values = [part for part in node_ids.replace(",", " ").split(" ") if part]
    else:
        raw_values = list(node_ids)
    parsed = []
    for raw in raw_values:
        try:
            node_id = int(raw)
        except (TypeError, ValueError):
            raise ValueError("node_not_found")
        if node_id not in parsed:
            parsed.append(node_id)
    return parsed


def _validate_sandbox_node_ids(
    db: Session,
    sandbox_id: int,
    node_ids: list[int],
) -> dict[int, PlanningSandboxNode]:
    if not node_ids:
        return {}
    nodes = (
        db.query(PlanningSandboxNode)
        .filter(PlanningSandboxNode.id.in_(node_ids))
        .all()
    )
    node_by_id = {node.id: node for node in nodes}
    if set(node_ids) - set(node_by_id):
        raise ValueError("node_not_found")
    if any(node.sandbox_id != sandbox_id for node in nodes):
        raise ValueError("cross_sandbox_edge")
    return node_by_id


def _raise_if_sandbox_has_hard_graph_error(db: Session, sandbox_id: int) -> None:
    schedule = compute_sandbox_schedule(db, sandbox_id, require_nodes=False)
    hard_errors = schedule.get("hard_errors") or []
    if not hard_errors:
        return
    first_code = hard_errors[0].get("code") or "sandbox_graph_error"
    raise ValueError(first_code)


def _sandbox_duration_bin(duration_days: int | None) -> tuple[str, int]:
    try:
        days = int(duration_days or 0)
    except (TypeError, ValueError):
        days = 0
    if days <= 7:
        return "S", 66
    if days <= 21:
        return "M", 82
    if days <= 45:
        return "L", 100
    return "XL", 122


def create_sandbox_blank(db: Session, project_id: int, user_id: int | None = None) -> PlanningSandbox:
    """v1.4 Build 03 — create the project's draft sandbox with no nodes.

    If a draft already exists, return it. This mirrors the one-draft lock and
    keeps double-clicks from creating duplicate drafts.
    """
    existing = get_active_planning_sandbox(db, project_id)
    if existing:
        return existing
    now = datetime.utcnow()
    sandbox = PlanningSandbox(
        project_id=project_id,
        name="Planning Sandbox",
        status="draft",
        created_by_user_id=user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(sandbox)
    db.commit()
    db.refresh(sandbox)
    return sandbox


def create_sandbox_from_template(
    db: Session,
    project_id: int,
    template_key: str,
    user_id: int | None = None,
    user_role: str | None = None,
) -> PlanningSandbox:
    """Clone a PlanningTemplate graph into the project's draft sandbox."""
    existing = get_active_planning_sandbox(db, project_id)
    if existing:
        return existing

    template_q = db.query(PlanningTemplate).filter(
        PlanningTemplate.template_key == template_key,
        PlanningTemplate.is_active.is_(True),
    )
    if user_role != "admin":
        template_q = template_q.filter(or_(
            PlanningTemplate.is_system.is_(True),
            PlanningTemplate.created_by_user_id == user_id,
        ))
    template = template_q.first()
    if not template:
        raise ValueError("template_not_found")

    now = datetime.utcnow()
    sandbox = PlanningSandbox(
        project_id=project_id,
        name=f"{template.name} Sandbox",
        status="draft",
        base_template_key=template.template_key,
        created_by_user_id=user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(sandbox)
    db.flush()

    node_map: dict[int, PlanningSandboxNode] = {}
    for template_node in sorted(template.nodes, key=lambda n: (n.sort_order, n.id)):
        module = template_node.module
        sandbox_node = PlanningSandboxNode(
            sandbox_id=sandbox.id,
            module_key=template_node.module_key,
            title=template_node.title,
            category=module.category if module else None,
            phase_type=module.phase_type if module else "design",
            duration_days=template_node.duration_days,
            owner_role=template_node.owner_role,
            deliverable=template_node.deliverable,
            exit_criteria=template_node.exit_criteria,
            x_position=template_node.x_position,
            y_position=template_node.y_position,
            sort_order=template_node.sort_order,
            created_at=now,
            updated_at=now,
        )
        db.add(sandbox_node)
        db.flush()
        node_map[template_node.id] = sandbox_node

    for template_edge in template.edges:
        from_node = node_map.get(template_edge.from_node_id)
        to_node = node_map.get(template_edge.to_node_id)
        if not from_node or not to_node:
            continue
        db.add(PlanningSandboxEdge(
            sandbox_id=sandbox.id,
            from_node_id=from_node.id,
            to_node_id=to_node.id,
            dependency_type=template_edge.dependency_type,
            created_at=now,
        ))

    db.commit()
    db.refresh(sandbox)
    return sandbox


def _template_key_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return slug[:42] or "template"


def _unique_template_key(db: Session, name: str) -> str:
    slug = _template_key_slug(name)
    for _ in range(12):
        candidate = f"{slug}-{uuid.uuid4().hex[:8]}"
        exists = (
            db.query(PlanningTemplate.id)
            .filter(PlanningTemplate.template_key == candidate)
            .first()
        )
        if not exists:
            return candidate
    return f"{slug}-{uuid.uuid4().hex}"


def save_sandbox_as_template(
    db: Session,
    project_id: int,
    sandbox_id: int,
    name: str,
    description: str | None = None,
    user_id: int | None = None,
) -> PlanningTemplate:
    """v1.4 Build 08 — save a draft/applied sandbox graph as a user template."""
    sandbox = (
        db.query(PlanningSandbox)
        .filter(PlanningSandbox.id == sandbox_id, PlanningSandbox.project_id == project_id)
        .first()
    )
    if not sandbox:
        raise ValueError("sandbox_not_found")
    if sandbox.status not in ("draft", "applied"):
        raise ValueError("sandbox_not_templateable")

    template_name = (name or "").strip()
    if not template_name:
        raise ValueError("template_name_required")
    template_name = template_name[:160]
    template_description = (description or "").strip()[:1000] or None
    now = datetime.utcnow()
    max_order = db.query(func.max(PlanningTemplate.sort_order)).scalar() or 0
    template = PlanningTemplate(
        template_key=_unique_template_key(db, template_name),
        name=template_name,
        description=template_description,
        is_system=False,
        created_by_user_id=user_id,
        is_active=True,
        created_at=now,
        updated_at=now,
        sort_order=max_order + 1,
    )
    db.add(template)
    db.flush()

    node_map: dict[int, PlanningTemplateNode] = {}
    for sandbox_node in sorted(sandbox.nodes, key=lambda n: (n.sort_order, n.id)):
        template_node = PlanningTemplateNode(
            template_id=template.id,
            module_key=sandbox_node.module_key,
            title=sandbox_node.title,
            duration_days=sandbox_node.duration_days,
            owner_role=sandbox_node.owner_role,
            deliverable=sandbox_node.deliverable,
            exit_criteria=sandbox_node.exit_criteria,
            x_position=sandbox_node.x_position,
            y_position=sandbox_node.y_position,
            sort_order=sandbox_node.sort_order,
            created_at=now,
            updated_at=now,
        )
        db.add(template_node)
        db.flush()
        node_map[sandbox_node.id] = template_node

    for sandbox_edge in sandbox.edges:
        from_node = node_map.get(sandbox_edge.from_node_id)
        to_node = node_map.get(sandbox_edge.to_node_id)
        if not from_node or not to_node:
            continue
        db.add(PlanningTemplateEdge(
            template_id=template.id,
            from_node_id=from_node.id,
            to_node_id=to_node.id,
            dependency_type=sandbox_edge.dependency_type,
            created_at=now,
        ))

    db.commit()
    db.refresh(template)
    return template


def get_sandbox_canvas_payload(db: Session, sandbox_id: int) -> dict:
    """Return Cytoscape-friendly read payload for the static canvas."""
    sandbox = db.query(PlanningSandbox).filter(PlanningSandbox.id == sandbox_id).first()
    if not sandbox:
        return {
            "sandbox": None,
            "elements": [],
            "modules": _planning_module_payload(db),
            "schedule": compute_sandbox_schedule(db, sandbox_id),
        }

    schedule = compute_sandbox_schedule(db, sandbox_id, require_nodes=False)
    scheduled_by_id = {node["id"]: node for node in schedule.get("nodes", [])}
    incoming_by_id: dict[int, list[int]] = {node.id: [] for node in sandbox.nodes}
    outgoing_by_id: dict[int, list[int]] = {node.id: [] for node in sandbox.nodes}
    for edge in sandbox.edges:
        incoming_by_id.setdefault(edge.to_node_id, []).append(edge.from_node_id)
        outgoing_by_id.setdefault(edge.from_node_id, []).append(edge.to_node_id)
    elements = []
    for node in sandbox.nodes:
        scheduled = scheduled_by_id.get(node.id, {})
        duration_bin, node_height = _sandbox_duration_bin(node.duration_days)
        elements.append({
            "data": {
                "id": f"node-{node.id}",
                "db_id": node.id,
                "label": node.title,
                "phase_type": node.phase_type,
                "duration_days": node.duration_days,
                "duration_bin": duration_bin,
                "node_height": node_height,
                "owner_role": node.owner_role or "",
                "deliverable": node.deliverable or "",
                "exit_criteria": node.exit_criteria or "",
                "depends_on_ids": sorted(incoming_by_id.get(node.id, [])),
                "dependent_ids": sorted(outgoing_by_id.get(node.id, [])),
                "start_day": scheduled.get("start_day"),
                "end_day": scheduled.get("end_day"),
                "warning_codes": scheduled.get("warning_codes", []),
            },
            "position": {"x": node.x_position, "y": node.y_position},
            "classes": f"phase-{node.phase_type}",
        })
    for edge in sandbox.edges:
        elements.append({
            "data": {
                "id": f"edge-{edge.id}",
                "db_id": edge.id,
                "source": f"node-{edge.from_node_id}",
                "target": f"node-{edge.to_node_id}",
                "dependency_type": edge.dependency_type,
            }
        })
    return {
        "sandbox": sandbox,
        "elements": elements,
        "modules": _planning_module_payload(db),
        "schedule": schedule,
    }


def _planning_module_payload(db: Session) -> list[dict]:
    """Return active module library rows for the sandbox palette."""
    modules = list_planning_modules(db, active_only=True)
    return [
        {
            "module_key": module.module_key,
            "title": module.title,
            "category": module.category,
            "phase_type": module.phase_type,
            "default_duration_days": module.default_duration_days,
            "default_owner_role": module.default_owner_role or "",
            "default_deliverable": module.default_deliverable or "",
            "default_exit_criteria": module.default_exit_criteria or "",
            "description": module.description or "",
            "sort_order": module.sort_order,
        }
        for module in modules
    ]


def create_sandbox_node_from_module(
    db: Session,
    project_id: int,
    sandbox_id: int,
    module_key: str,
    x_position: float | int | str | None = None,
    y_position: float | int | str | None = None,
) -> PlanningSandboxNode:
    """v1.4 Build 04 — copy one active module into a draft sandbox node."""
    sandbox = _get_project_draft_sandbox(db, project_id, sandbox_id)
    module = (
        db.query(PlanningModule)
        .filter(
            PlanningModule.module_key == (module_key or "").strip(),
            PlanningModule.is_active.is_(True),
        )
        .first()
    )
    if not module:
        raise ValueError("module_not_found")
    try:
        x = float(x_position) if x_position not in (None, "") else 80.0
        y = float(y_position) if y_position not in (None, "") else 80.0
    except (TypeError, ValueError):
        x, y = 80.0, 80.0
    if not math.isfinite(x):
        x = 80.0
    if not math.isfinite(y):
        y = 80.0

    max_order = (
        db.query(func.max(PlanningSandboxNode.sort_order))
        .filter(PlanningSandboxNode.sandbox_id == sandbox_id)
        .scalar()
    )
    now = datetime.utcnow()
    node = PlanningSandboxNode(
        sandbox_id=sandbox.id,
        module_key=module.module_key,
        title=module.title,
        category=module.category,
        phase_type=module.phase_type,
        duration_days=module.default_duration_days,
        owner_role=module.default_owner_role,
        deliverable=module.default_deliverable,
        exit_criteria=module.default_exit_criteria,
        x_position=x,
        y_position=y,
        sort_order=(max_order or 0) + 1,
        created_at=now,
        updated_at=now,
    )
    db.add(node)
    sandbox.updated_at = now
    db.commit()
    db.refresh(node)
    return node


def update_sandbox_node(
    db: Session,
    project_id: int,
    sandbox_id: int,
    node_id: int,
    data: dict,
) -> PlanningSandboxNode:
    """Update editable node fields in a draft sandbox."""
    node = _get_project_sandbox_node(db, project_id, sandbox_id, node_id)
    title = (data.get("title") or "").strip()
    if not title:
        raise ValueError("title_required")
    try:
        duration_days = int(data.get("duration_days"))
    except (TypeError, ValueError):
        raise ValueError("invalid_duration")
    if duration_days <= 0:
        raise ValueError("invalid_duration")

    node.title = title
    node.duration_days = duration_days
    node.owner_role = (data.get("owner_role") or "").strip() or None
    node.deliverable = (data.get("deliverable") or "").strip() or None
    node.exit_criteria = (data.get("exit_criteria") or "").strip() or None
    node.updated_at = datetime.utcnow()
    node.sandbox.updated_at = node.updated_at
    db.commit()
    db.refresh(node)
    return node


def update_sandbox_node_position(
    db: Session,
    project_id: int,
    sandbox_id: int,
    node_id: int,
    x_position: float | int | str,
    y_position: float | int | str,
) -> PlanningSandboxNode:
    """Persist a draft sandbox node's canvas position."""
    node = _get_project_sandbox_node(db, project_id, sandbox_id, node_id)
    try:
        x = float(x_position)
        y = float(y_position)
    except (TypeError, ValueError):
        raise ValueError("invalid_position")
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError("invalid_position")
    node.x_position = x
    node.y_position = y
    node.updated_at = datetime.utcnow()
    node.sandbox.updated_at = node.updated_at
    db.commit()
    db.refresh(node)
    return node


def delete_sandbox_node(
    db: Session,
    project_id: int,
    sandbox_id: int,
    node_id: int,
) -> bool:
    """Delete a draft sandbox node and any attached sandbox-only edges."""
    node = _get_project_sandbox_node(db, project_id, sandbox_id, node_id)
    now = datetime.utcnow()
    sandbox = node.sandbox
    db.query(PlanningSandboxEdge).filter(
        PlanningSandboxEdge.sandbox_id == sandbox_id,
        or_(
            PlanningSandboxEdge.from_node_id == node_id,
            PlanningSandboxEdge.to_node_id == node_id,
        ),
    ).delete(synchronize_session=False)
    db.delete(node)
    sandbox.updated_at = now
    db.commit()
    return True


def create_sandbox_edge(
    db: Session,
    project_id: int,
    sandbox_id: int,
    from_node_id: int,
    to_node_id: int,
) -> PlanningSandboxEdge:
    """Create one finish-to-start dependency edge inside a draft sandbox."""
    sandbox = _get_project_draft_sandbox(db, project_id, sandbox_id)
    try:
        from_id = int(from_node_id)
        to_id = int(to_node_id)
    except (TypeError, ValueError):
        raise ValueError("node_not_found")
    if from_id == to_id:
        raise ValueError("self_dependency")
    _validate_sandbox_node_ids(db, sandbox_id, [from_id, to_id])

    existing = (
        db.query(PlanningSandboxEdge)
        .filter(
            PlanningSandboxEdge.sandbox_id == sandbox_id,
            PlanningSandboxEdge.from_node_id == from_id,
            PlanningSandboxEdge.to_node_id == to_id,
        )
        .first()
    )
    if existing:
        return existing

    now = datetime.utcnow()
    edge = PlanningSandboxEdge(
        sandbox_id=sandbox_id,
        from_node_id=from_id,
        to_node_id=to_id,
        dependency_type="finish_to_start",
        created_at=now,
    )
    db.add(edge)
    sandbox.updated_at = now
    db.flush()
    try:
        _raise_if_sandbox_has_hard_graph_error(db, sandbox_id)
    except ValueError:
        db.rollback()
        raise
    db.commit()
    db.refresh(edge)
    return edge


def delete_sandbox_edge(
    db: Session,
    project_id: int,
    sandbox_id: int,
    edge_id: int,
) -> bool:
    """Delete one dependency edge inside a draft sandbox."""
    edge = _get_project_sandbox_edge(db, project_id, sandbox_id, edge_id)
    sandbox = edge.sandbox
    sandbox.updated_at = datetime.utcnow()
    db.delete(edge)
    db.commit()
    return True


def replace_sandbox_node_dependencies(
    db: Session,
    project_id: int,
    sandbox_id: int,
    node_id: int,
    depends_on_ids,
) -> list[PlanningSandboxEdge]:
    """Replace all incoming dependency edges for one sandbox node."""
    sandbox = _get_project_draft_sandbox(db, project_id, sandbox_id)
    target = _get_project_sandbox_node(db, project_id, sandbox_id, node_id)
    dependency_ids = _parse_node_id_list(depends_on_ids)
    if target.id in dependency_ids:
        raise ValueError("self_dependency")
    _validate_sandbox_node_ids(db, sandbox_id, dependency_ids)

    existing_edges = (
        db.query(PlanningSandboxEdge)
        .filter(
            PlanningSandboxEdge.sandbox_id == sandbox_id,
            PlanningSandboxEdge.to_node_id == target.id,
        )
        .all()
    )
    existing_from_ids = {edge.from_node_id for edge in existing_edges}
    desired_from_ids = set(dependency_ids)
    now = datetime.utcnow()

    for edge in existing_edges:
        if edge.from_node_id not in desired_from_ids:
            db.delete(edge)
    for from_id in sorted(desired_from_ids - existing_from_ids):
        db.add(PlanningSandboxEdge(
            sandbox_id=sandbox_id,
            from_node_id=from_id,
            to_node_id=target.id,
            dependency_type="finish_to_start",
            created_at=now,
        ))
    sandbox.updated_at = now
    db.flush()
    try:
        _raise_if_sandbox_has_hard_graph_error(db, sandbox_id)
    except ValueError:
        db.rollback()
        raise
    db.commit()
    return (
        db.query(PlanningSandboxEdge)
        .filter(
            PlanningSandboxEdge.sandbox_id == sandbox_id,
            PlanningSandboxEdge.to_node_id == target.id,
        )
        .order_by(PlanningSandboxEdge.id)
        .all()
    )


def update_sandbox_node_positions(
    db: Session,
    project_id: int,
    sandbox_id: int,
    positions: list[dict],
) -> int:
    """Persist bulk node positions for the Tidy canvas action."""
    sandbox = _get_project_draft_sandbox(db, project_id, sandbox_id)
    if not isinstance(positions, list):
        raise ValueError("invalid_position")
    node_ids = []
    parsed_positions = {}
    for item in positions:
        if not isinstance(item, dict):
            raise ValueError("invalid_position")
        try:
            node_id = int(item.get("node_id"))
            x = float(item.get("x_position"))
            y = float(item.get("y_position"))
        except (TypeError, ValueError):
            raise ValueError("invalid_position")
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("invalid_position")
        node_ids.append(node_id)
        parsed_positions[node_id] = (x, y)
    nodes = _validate_sandbox_node_ids(db, sandbox_id, node_ids)
    now = datetime.utcnow()
    for node_id, (x, y) in parsed_positions.items():
        node = nodes[node_id]
        node.x_position = x
        node.y_position = y
        node.updated_at = now
    sandbox.updated_at = now
    db.commit()
    return len(parsed_positions)


def _sandbox_apply_preconditions(db: Session, project_id: int) -> list[dict]:
    phases = (
        db.query(ProjectPhase)
        .filter(ProjectPhase.project_id == project_id)
        .order_by(ProjectPhase.phase_order, ProjectPhase.id)
        .all()
    )
    failures = []
    for phase in phases:
        base = {"phase_id": phase.id, "phase_name": phase.phase_name}
        if phase.actual_start_date:
            failures.append({**base, "code": "phase_has_actual_start"})
        if phase.actual_end_date:
            failures.append({**base, "code": "phase_has_actual_end"})
        if (phase.status or "not_started") not in ("not_started", "skipped"):
            failures.append({**base, "code": "phase_active_status", "status": phase.status})
    active_phase_blockers = (
        db.query(ProjectBlocker)
        .filter(
            ProjectBlocker.project_id == project_id,
            ProjectBlocker.status == "active",
            ProjectBlocker.phase_id.isnot(None),
        )
        .order_by(ProjectBlocker.created_at.desc())
        .all()
    )
    for blocker in active_phase_blockers:
        failures.append({
            "code": "active_blocker_attached",
            "blocker_id": blocker.id,
            "blocker_title": blocker.title,
            "phase_id": blocker.phase_id,
        })
    return failures


def validate_sandbox_for_apply(db: Session, project_id: int, sandbox_id: int) -> dict:
    sandbox = (
        db.query(PlanningSandbox)
        .filter(PlanningSandbox.id == sandbox_id, PlanningSandbox.project_id == project_id)
        .first()
    )
    if not sandbox:
        return {
            "ok": False,
            "error": "sandbox_not_found",
            "schedule": compute_sandbox_schedule(db, sandbox_id, require_nodes=True),
            "preconditions": [],
        }
    schedule = compute_sandbox_schedule(db, sandbox_id, require_nodes=True)
    hard_errors = schedule.get("hard_errors") or []
    preconditions = _sandbox_apply_preconditions(db, project_id)
    ok = sandbox.status == "draft" and not hard_errors and not preconditions
    error = None
    if sandbox.status != "draft":
        error = "sandbox_not_draft"
    elif hard_errors:
        error = hard_errors[0].get("code") or "invalid_graph"
    elif preconditions:
        error = "preconditions_failed"
    return {
        "ok": ok,
        "error": error,
        "sandbox": sandbox,
        "schedule": schedule,
        "preconditions": preconditions,
        "hard_errors": hard_errors,
        "soft_warnings": schedule.get("soft_warnings") or [],
    }


def get_sandbox_apply_preview(
    db: Session,
    project_id: int,
    sandbox_id: int,
    apply_start_date: date | None = None,
) -> dict:
    validation = validate_sandbox_for_apply(db, project_id, sandbox_id)
    schedule = validation.get("schedule") or {}
    start = apply_start_date or date.today()
    total_days = int(schedule.get("total_days") or 0)
    computed_end = start + timedelta(days=total_days)
    existing_phases = (
        db.query(ProjectPhase)
        .filter(ProjectPhase.project_id == project_id)
        .order_by(ProjectPhase.phase_order, ProjectPhase.id)
        .all()
    )
    return {
        **validation,
        "node_count": len(schedule.get("nodes") or []),
        "total_days": total_days,
        "apply_start_date": start,
        "computed_end_date": computed_end,
        "existing_phases": existing_phases,
        "replaceable_phase_count": len([
            phase for phase in existing_phases
            if not phase.actual_start_date
            and not phase.actual_end_date
            and (phase.status or "not_started") in ("not_started", "skipped")
        ]),
    }


def _sandbox_apply_snapshot(
    sandbox: PlanningSandbox,
    schedule: dict,
) -> dict:
    return {
        "sandbox": {
            "id": sandbox.id,
            "project_id": sandbox.project_id,
            "name": sandbox.name,
            "base_template_key": sandbox.base_template_key,
            "status": sandbox.status,
        },
        "schedule": schedule,
        "nodes": [
            {
                "id": node.id,
                "module_key": node.module_key,
                "title": node.title,
                "category": node.category,
                "phase_type": node.phase_type,
                "duration_days": node.duration_days,
                "owner_role": node.owner_role,
                "deliverable": node.deliverable,
                "exit_criteria": node.exit_criteria,
                "x_position": node.x_position,
                "y_position": node.y_position,
                "sort_order": node.sort_order,
            }
            for node in sandbox.nodes
        ],
        "edges": [
            {
                "id": edge.id,
                "from_node_id": edge.from_node_id,
                "to_node_id": edge.to_node_id,
                "dependency_type": edge.dependency_type,
            }
            for edge in sandbox.edges
        ],
    }


def _sandbox_phase_notes(node: PlanningSandboxNode) -> str | None:
    parts = [
        part.strip()
        for part in (node.deliverable, node.exit_criteria)
        if part and part.strip()
    ]
    return " / ".join(parts) if parts else None


def apply_sandbox_to_project(
    db: Session,
    project_id: int,
    sandbox_id: int,
    apply_start_date: date,
    update_launch_date: bool = False,
    user_id: int | None = None,
) -> PlanningApplyEvent:
    """v1.4 Build 07 — explicit audited Apply bridge into live phases."""
    if not apply_start_date:
        raise ValueError("invalid_start_date")
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ValueError("project_not_found")
    sandbox = _get_project_draft_sandbox(db, project_id, sandbox_id)
    validation = validate_sandbox_for_apply(db, project_id, sandbox_id)
    if not validation["ok"]:
        raise ValueError(validation.get("error") or "apply_blocked")

    schedule = validation["schedule"]
    scheduled_nodes = schedule.get("nodes") or []
    if not scheduled_nodes:
        raise ValueError("zero_nodes")
    scheduled_by_id = {node["id"]: node for node in scheduled_nodes}
    sandbox_nodes_by_id = {node.id: node for node in sandbox.nodes}
    now = datetime.utcnow()

    existing_phases = (
        db.query(ProjectPhase)
        .filter(ProjectPhase.project_id == project_id)
        .order_by(ProjectPhase.phase_order, ProjectPhase.id)
        .all()
    )
    phases_deleted = len(existing_phases)
    for phase in existing_phases:
        db.delete(phase)
    db.flush()

    created = []
    for order, scheduled in enumerate(scheduled_nodes, 1):
        node = sandbox_nodes_by_id[scheduled["id"]]
        phase = ProjectPhase(
            project_id=project_id,
            phase_name=node.title,
            phase_type=node.phase_type,
            phase_order=order,
            status="not_started",
            planned_start_date=apply_start_date + timedelta(days=int(scheduled.get("start_day") or 0)),
            planned_end_date=apply_start_date + timedelta(days=int(scheduled.get("end_day") or 0)),
            owner=node.owner_role or None,
            notes=_sandbox_phase_notes(node),
            created_at=now,
            updated_at=now,
        )
        db.add(phase)
        created.append(phase)

    total_days = int(schedule.get("total_days") or 0)
    computed_end = apply_start_date + timedelta(days=total_days)
    if update_launch_date:
        project.planned_launch_date = computed_end
    project.current_stage = derive_current_stage(created)
    delay = calculate_delay(project, created)
    project.estimated_launch_date = delay["estimated_launch"] if delay else None
    project.updated_at = now

    sandbox.status = "applied"
    sandbox.applied_at = now
    sandbox.applied_by_user_id = user_id
    sandbox.updated_at = now
    sandbox.last_computed_total_days = total_days

    event = PlanningApplyEvent(
        project_id=project_id,
        sandbox_id=sandbox_id,
        applied_at=now,
        applied_by_user_id=user_id,
        snapshot_json=_sandbox_apply_snapshot(sandbox, schedule),
        node_count=len(created),
        total_days=total_days,
        planned_start_date=apply_start_date,
        computed_end_date=computed_end,
        updated_project_planned_launch_date=bool(update_launch_date),
        phases_created=len(created),
        phases_updated=0,
        phases_deleted=phases_deleted,
    )
    db.add(event)
    write_change(
        db,
        project_id,
        "plan_applied",
        changed_by="user",
        summary=(
            f"Plan applied from sandbox: {len(created)} phases over "
            f"{total_days} days, launching {computed_end.isoformat()}."
        ),
        source_type="planning_sandbox",
    )
    db.commit()
    db.refresh(event)
    return event


def compute_sandbox_schedule(db: Session, sandbox_id: int, require_nodes: bool = False) -> dict:
    """v1.4 Build 02 — server-authoritative Planning Sandbox schedule engine.

    Calculates earliest start/end days for a sandbox DAG. The helper is read-
    only: it never mutates sandbox rows and never touches ProjectPhase.
    """
    sandbox = db.query(PlanningSandbox).filter(PlanningSandbox.id == sandbox_id).first()
    if not sandbox:
        return _sandbox_schedule_result(
            sandbox_id=sandbox_id,
            hard_errors=[{"code": "sandbox_not_found", "detail": "Sandbox not found"}],
        )

    nodes = (
        db.query(PlanningSandboxNode)
        .filter(PlanningSandboxNode.sandbox_id == sandbox_id)
        .order_by(PlanningSandboxNode.sort_order, PlanningSandboxNode.id)
        .all()
    )
    edges = (
        db.query(PlanningSandboxEdge)
        .filter(PlanningSandboxEdge.sandbox_id == sandbox_id)
        .order_by(PlanningSandboxEdge.id)
        .all()
    )

    hard_errors = []
    soft_warnings = []
    if require_nodes and not nodes:
        hard_errors.append({"code": "zero_nodes", "detail": "Sandbox is empty"})

    node_by_id = {node.id: node for node in nodes}
    for node in nodes:
        if not (node.title or "").strip():
            hard_errors.append({"code": "missing_title", "node_id": node.id})
        if node.duration_days is None or node.duration_days <= 0:
            hard_errors.append({"code": "invalid_duration", "node_id": node.id})

    outgoing = {node.id: set() for node in nodes}
    incoming = {node.id: set() for node in nodes}
    for edge in edges:
        from_node = node_by_id.get(edge.from_node_id)
        to_node = node_by_id.get(edge.to_node_id)
        if from_node is None or to_node is None:
            stored_from = from_node or db.query(PlanningSandboxNode).filter(PlanningSandboxNode.id == edge.from_node_id).first()
            stored_to = to_node or db.query(PlanningSandboxNode).filter(PlanningSandboxNode.id == edge.to_node_id).first()
            if stored_from is not None and stored_to is not None:
                hard_errors.append({"code": "cross_sandbox_edge", "edge_id": edge.id})
            else:
                hard_errors.append({"code": "dangling_edge", "edge_id": edge.id})
            continue
        if from_node.sandbox_id != sandbox_id or to_node.sandbox_id != sandbox_id:
            hard_errors.append({"code": "cross_sandbox_edge", "edge_id": edge.id})
            continue
        outgoing[edge.from_node_id].add(edge.to_node_id)
        incoming[edge.to_node_id].add(edge.from_node_id)

    topo_ids, cycle_ids = _topological_sort(node_by_id, outgoing, incoming)
    if cycle_ids:
        hard_errors.append({"code": "circular_dependency", "node_ids": cycle_ids})

    if hard_errors:
        return _sandbox_schedule_result(
            sandbox_id=sandbox_id,
            hard_errors=hard_errors,
            soft_warnings=soft_warnings,
            nodes=[_schedule_node_payload(node) for node in nodes],
        )

    start_days: dict[int, int] = {}
    end_days: dict[int, int] = {}
    for node_id in topo_ids:
        node = node_by_id[node_id]
        upstream_ends = [end_days[parent_id] for parent_id in incoming[node_id]]
        start = max(upstream_ends) if upstream_ends else 0
        end = start + int(node.duration_days)
        start_days[node_id] = start
        end_days[node_id] = end

    terminal_ids = [node_id for node_id in topo_ids if not outgoing[node_id]]
    total_days = max((end_days[node_id] for node_id in terminal_ids), default=0)

    component_count = _count_undirected_components(node_by_id, outgoing, incoming)
    if component_count > 1:
        soft_warnings.append({
            "code": "disconnected_branch",
            "component_count": component_count,
            "detail": f"This sandbox has {component_count} disconnected branches.",
        })

    ancestors_cache: dict[int, set[int]] = {}
    for node_id in topo_ids:
        node = node_by_id[node_id]
        node_warnings = []
        if node.duration_days > 60:
            node_warnings.append("very_long_duration")
            soft_warnings.append({"code": "very_long_duration", "node_id": node_id})
        if not node.owner_role:
            node_warnings.append("missing_owner")
            soft_warnings.append({"code": "missing_owner", "node_id": node_id})
        if not node.deliverable:
            node_warnings.append("missing_deliverable")
            soft_warnings.append({"code": "missing_deliverable", "node_id": node_id})
        if not node.exit_criteria:
            node_warnings.append("missing_exit_criteria")
            soft_warnings.append({"code": "missing_exit_criteria", "node_id": node_id})
        ancestors = _sandbox_ancestors(node_id, incoming, ancestors_cache)
        ancestor_types = {node_by_id[ancestor_id].phase_type for ancestor_id in ancestors}
        if node.phase_type == "packaging" and "design" not in ancestor_types:
            node_warnings.append("packaging_before_design")
            soft_warnings.append({"code": "packaging_before_design", "node_id": node_id})
        if node.phase_type == "production" and not ({"prototype", "review"} & ancestor_types):
            node_warnings.append("production_before_sample")
            soft_warnings.append({"code": "production_before_sample", "node_id": node_id})
        node._schedule_warning_codes = node_warnings

    for node_id in terminal_ids:
        node = node_by_id[node_id]
        if node.phase_type not in ("launch", "production", "review"):
            soft_warnings.append({"code": "terminal_not_launch_like", "node_id": node_id})
            current = getattr(node, "_schedule_warning_codes", [])
            node._schedule_warning_codes = [*current, "terminal_not_launch_like"]

    schedule_nodes = [
        _schedule_node_payload(
            node_by_id[node_id],
            start_day=start_days[node_id],
            end_day=end_days[node_id],
            upstream_ids=sorted(incoming[node_id]),
            downstream_ids=sorted(outgoing[node_id]),
            is_terminal=node_id in terminal_ids,
            warning_codes=getattr(node_by_id[node_id], "_schedule_warning_codes", []),
        )
        for node_id in topo_ids
    ]

    return _sandbox_schedule_result(
        sandbox_id=sandbox_id,
        hard_errors=[],
        soft_warnings=soft_warnings,
        nodes=schedule_nodes,
        topological_node_ids=topo_ids,
        terminal_node_ids=terminal_ids,
        total_days=total_days,
        connected_component_count=component_count,
    )


def _sandbox_schedule_result(
    sandbox_id: int,
    hard_errors: list | None = None,
    soft_warnings: list | None = None,
    nodes: list | None = None,
    topological_node_ids: list | None = None,
    terminal_node_ids: list | None = None,
    total_days: int = 0,
    connected_component_count: int = 0,
) -> dict:
    return {
        "sandbox_id": sandbox_id,
        "hard_errors": hard_errors or [],
        "soft_warnings": soft_warnings or [],
        "nodes": nodes or [],
        "topological_node_ids": topological_node_ids or [],
        "terminal_node_ids": terminal_node_ids or [],
        "total_days": total_days,
        "connected_component_count": connected_component_count,
    }


def _schedule_node_payload(
    node,
    start_day: int | None = None,
    end_day: int | None = None,
    upstream_ids: list | None = None,
    downstream_ids: list | None = None,
    is_terminal: bool = False,
    warning_codes: list | None = None,
) -> dict:
    return {
        "id": node.id,
        "title": node.title,
        "phase_type": node.phase_type,
        "duration_days": node.duration_days,
        "owner_role": node.owner_role,
        "start_day": start_day,
        "end_day": end_day,
        "upstream_ids": upstream_ids or [],
        "downstream_ids": downstream_ids or [],
        "is_terminal": is_terminal,
        "warning_codes": warning_codes or [],
    }


def _topological_sort(node_by_id: dict, outgoing: dict, incoming: dict) -> tuple[list[int], list[int]]:
    incoming_counts = {node_id: len(incoming[node_id]) for node_id in node_by_id}
    ready = sorted([node_id for node_id, count in incoming_counts.items() if count == 0])
    result = []
    while ready:
        node_id = ready.pop(0)
        result.append(node_id)
        for child_id in sorted(outgoing[node_id]):
            incoming_counts[child_id] -= 1
            if incoming_counts[child_id] == 0:
                ready.append(child_id)
                ready.sort()
    if len(result) == len(node_by_id):
        return result, []
    cycle_ids = sorted([node_id for node_id in node_by_id if node_id not in result])
    return result, cycle_ids


def _count_undirected_components(node_by_id: dict, outgoing: dict, incoming: dict) -> int:
    unseen = set(node_by_id)
    count = 0
    while unseen:
        count += 1
        stack = [unseen.pop()]
        while stack:
            node_id = stack.pop()
            neighbors = set(outgoing[node_id]) | set(incoming[node_id])
            for neighbor_id in list(neighbors & unseen):
                unseen.remove(neighbor_id)
                stack.append(neighbor_id)
    return count


def _sandbox_ancestors(node_id: int, incoming: dict, cache: dict[int, set[int]]) -> set[int]:
    if node_id in cache:
        return cache[node_id]
    ancestors = set()
    for parent_id in incoming[node_id]:
        ancestors.add(parent_id)
        ancestors.update(_sandbox_ancestors(parent_id, incoming, cache))
    cache[node_id] = ancestors
    return ancestors


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
        # v1.3 Build 05B — structured spec fields (all nullable)
        sales_format=(data.get("sales_format") or "").strip() or None,
        packaging_cost=_parse_float_safe(data.get("packaging_cost")),
        blade_summary=(data.get("blade_summary") or "").strip() or None,
        handle_summary=(data.get("handle_summary") or "").strip() or None,
        mechanism_summary=(data.get("mechanism_summary") or "").strip() or None,
        dimensions_summary=(data.get("dimensions_summary") or "").strip() or None,
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
                  "packaging_summary", "notes",
                  # v1.3 Build 05B
                  "sales_format", "blade_summary", "handle_summary",
                  "mechanism_summary", "dimensions_summary"):
        if field in data:
            val = (data.get(field) or "").strip()
            setattr(v, field, val or None)
    if "status" in data:
        s = data["status"]
        v.status = s if s in VARIANT_STATUSES else v.status
    for field in ("target_factory_cost", "actual_factory_cost", "target_msrp",
                  # v1.3 Build 05B
                  "packaging_cost"):
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


# ---------------------------------------------------------------------------
# v1.3 Build 07B — Project Blockers (first-class lifecycle model)
#
# All mutating functions write a project_changes audit row via write_change().
# Per V13_BUILD07B_EXECUTION_PLAN.md Lock 1/3/6: 2-state lifecycle, optional
# phase_id with same-project validation, resolve sets resolved_at/by + audit.
# ---------------------------------------------------------------------------

UPDATE_BLOCKER_ALLOWED = {"title", "description", "severity", "phase_id"}
_BLOCKER_SEVERITIES = {"low", "medium", "high"}


def _import_blocker():
    from app.models import ProjectBlocker  # late import to mirror journal pattern
    return ProjectBlocker


def create_blocker(
    db: Session,
    project_id: int,
    title: str,
    description: str | None = None,
    severity: str = "medium",
    phase_id: int | None = None,
    created_by_user_id: int | None = None,
    changed_by: str = "user",
    source_type: str = "manual_edit",
):
    """Lock 3: phase_id is optional; if provided it must belong to project_id.
    Returns the created ProjectBlocker, or None if phase_id mismatch / blank title.
    """
    ProjectBlocker = _import_blocker()
    clean_title = (title or "").strip()
    if not clean_title:
        return None
    sev = severity if severity in _BLOCKER_SEVERITIES else "medium"
    if phase_id is not None:
        phase = db.query(ProjectPhase).filter(ProjectPhase.id == phase_id).first()
        if not phase or phase.project_id != project_id:
            return None
    blocker = ProjectBlocker(
        project_id=project_id,
        phase_id=phase_id,
        title=clean_title,
        description=(description or "").strip() or None,
        severity=sev,
        status="active",
        created_by_user_id=created_by_user_id,
    )
    db.add(blocker)
    write_change(
        db, project_id, "blocker_opened", changed_by=changed_by,
        field_name=clean_title,
        summary=f"Blocker opened: '{clean_title}' (severity {sev})",
        source_type=source_type,
    )
    db.commit()
    db.refresh(blocker)
    return blocker


def update_blocker(
    db: Session,
    blocker_id: int,
    data: dict,
    changed_by: str = "user",
    changed_by_user_id: int | None = None,
    source_type: str = "manual_edit",
):
    """UPDATE_BLOCKER_ALLOWED whitelist enforced. Non-allowlisted keys are
    silently ignored (Lock 7 defense-in-depth)."""
    ProjectBlocker = _import_blocker()
    blocker = db.query(ProjectBlocker).filter(ProjectBlocker.id == blocker_id).first()
    if not blocker:
        return None
    changes = []
    for field in UPDATE_BLOCKER_ALLOWED:
        if field not in data:
            continue
        new_val = data[field]
        if field == "severity":
            if new_val not in _BLOCKER_SEVERITIES:
                continue
        if field == "phase_id":
            if new_val is not None:
                phase = db.query(ProjectPhase).filter(ProjectPhase.id == new_val).first()
                if not phase or phase.project_id != blocker.project_id:
                    continue
        if field == "title":
            new_val = (new_val or "").strip()
            if not new_val:
                continue
        if field == "description":
            new_val = ((new_val or "").strip() or None) if new_val is not None else None
        old_val = getattr(blocker, field)
        if str(old_val or "") != str(new_val or ""):
            changes.append((field, old_val, new_val))
            setattr(blocker, field, new_val)
    if changes:
        summary_parts = [f"{f}: {o or '—'} → {n or '—'}" for f, o, n in changes]
        write_change(
            db, blocker.project_id, "blocker_updated", changed_by=changed_by,
            field_name=blocker.title,
            summary=f"Blocker '{blocker.title}' updated: {'; '.join(summary_parts)}",
            source_type=source_type,
        )
    db.commit()
    db.refresh(blocker)
    return blocker


def resolve_blocker(
    db: Session,
    blocker_id: int,
    resolved_by_user_id: int | None = None,
    changed_by: str = "user",
    source_type: str = "manual_edit",
):
    """Lock 6: one-click resolve. Sets status, resolved_at, resolved_by_user_id
    AND writes blocker_resolved change-log row. The change-log row IS the
    auditable history record."""
    ProjectBlocker = _import_blocker()
    blocker = db.query(ProjectBlocker).filter(ProjectBlocker.id == blocker_id).first()
    if not blocker or blocker.status == "resolved":
        return None
    blocker.status = "resolved"
    blocker.resolved_at = datetime.utcnow()
    blocker.resolved_by_user_id = resolved_by_user_id
    write_change(
        db, blocker.project_id, "blocker_resolved", changed_by=changed_by,
        field_name=blocker.title,
        summary=f"Blocker resolved: '{blocker.title}'",
        source_type=source_type,
    )
    db.commit()
    db.refresh(blocker)
    return blocker


def get_active_blockers_for_project(db: Session, project_id: int) -> list:
    """Newest first. Used by Command Center tile + Pulse cascade."""
    ProjectBlocker = _import_blocker()
    return (
        db.query(ProjectBlocker)
        .filter(ProjectBlocker.project_id == project_id,
                ProjectBlocker.status == "active")
        .order_by(ProjectBlocker.created_at.desc())
        .all()
    )


def get_blockers_by_phase(db: Session, phase_id: int, only_active: bool = True) -> list:
    """Used by phase-strip dot derivation + Timeline History (Build 08)."""
    ProjectBlocker = _import_blocker()
    q = db.query(ProjectBlocker).filter(ProjectBlocker.phase_id == phase_id)
    if only_active:
        q = q.filter(ProjectBlocker.status == "active")
    return q.order_by(ProjectBlocker.created_at.desc()).all()


def get_active_phase_blocker_ids(db: Session, project_id: int) -> set:
    """Lock 3: returns the set of phase_ids that have ≥1 active blocker.
    Phase-strip red dot iterates this set. Project-level blockers (phase_id=NULL)
    are excluded so they never light up a phase block."""
    ProjectBlocker = _import_blocker()
    rows = (
        db.query(ProjectBlocker.phase_id)
        .filter(ProjectBlocker.project_id == project_id,
                ProjectBlocker.status == "active",
                ProjectBlocker.phase_id.isnot(None))
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


# ---------------------------------------------------------------------------
# v1.3 Build 08 — Timeline Updates / History (derived view)
#
# Pure derivation over project_changes + phase_plan_changes +
# project_journal_entries + planning_apply_events. Returns up to `limit` normalized
# TimelineEvent dicts, newest first. Deterministic tiebreaker on equal
# timestamps via (source_priority, source_id DESC).
# ---------------------------------------------------------------------------

COST_FIELDS = {
    "target_factory_cost", "actual_factory_cost",
    "target_msrp", "actual_msrp",
    "packaging_cost",
}
SENSITIVE_FILE_CATEGORIES = {"factory_feedback", "quotation"}
_SAMPLE_PHASE_TYPES = {"prototype", "review", "production"}

# Bucket constants — must match the 6 filter chips per Lock 2
BUCKET_DELAYS = "delays"
BUCKET_DECISIONS = "decisions"
BUCKET_BLOCKERS = "blockers"
BUCKET_PHASE_CHANGES = "phase_changes"
BUCKET_FILES = "files"  # files + renderings


def _is_ai_change(changed_by: str | None, source_type: str | None) -> bool:
    return (changed_by or "") == "ai" or (source_type or "") == "ai_chat"


def _classify_project_change(pc, phase_lookup: dict, file_lookup: dict) -> tuple[str, str | None, str | None] | None:
    """Return (bucket, subtype, link_anchor) for a project_changes row, or None
    if the row is unclassifiable (e.g., unknown change_type) — caller decides
    whether to drop or fall back."""
    ct = pc.change_type
    if ct == "phase_update":
        # Try to derive subtype from the affected phase's phase_type if we
        # can resolve it. field_name on phase_update events stores phase_name
        # — look up by name within this project's phases.
        subtype = None
        if pc.field_name:
            phase = phase_lookup.get(pc.field_name)
            if phase and (phase.phase_type or "") in _SAMPLE_PHASE_TYPES:
                subtype = "sample"
            link = f"#phase-row-{phase.id}" if phase else None
        else:
            link = None
        return (BUCKET_PHASE_CHANGES, subtype, link)
    if ct == "plan_applied":
        # Structured PlanningApplyEvent rows provide the user-facing card.
        # The project_changes row remains the general audit companion.
        return None
    if ct in ("blocker_opened", "blocker_updated", "blocker_resolved"):
        # subtype = the action verb (opened / updated / resolved) for badge
        verb = ct.split("_", 1)[1]
        return (BUCKET_BLOCKERS, verb, "#timeline-command-center")
    if ct == "file_upload":
        # field_name on file_upload events stores original_filename. Look up
        # the file by that filename within this project's files for category.
        pf = file_lookup.get(pc.field_name) if pc.field_name else None
        cat = (pf.file_category if pf else "") or ""
        if cat == "rendering":
            return (BUCKET_FILES, "rendering", "#files")
        if cat == "packaging":
            return (BUCKET_FILES, "packaging", "#files")
        return (BUCKET_FILES, None, "#files")
    if ct == "field_update":
        if (pc.field_name or "") in COST_FIELDS:
            return (BUCKET_DECISIONS, "cost", None)
        # Generic field updates fall through to Decisions (project-level
        # recorded changes) per Lock 2 — every event has a bucket.
        return (BUCKET_DECISIONS, None, None)
    if ct == "event_note":
        # event_note rows from create_journal_entry / create_variant / etc.
        # Fold into Decisions per Lock 2 (no orphan "All only" bucket).
        return (BUCKET_DECISIONS, None, None)
    return None


def _is_pc_sensitive(pc, file_lookup: dict) -> bool:
    """Lock 3: cost field_updates + sensitive-category file uploads + journal-
    mirror event_notes are hidden from viewers. Journal-mirror rows have
    summaries beginning with 'Journal entry added:' — they leak the journal
    body text via the audit log even though the source journal entry itself
    is can_view_journal-gated. Filter them out for parity with the journal-
    source row hiding."""
    if pc.change_type == "field_update" and (pc.field_name or "") in COST_FIELDS:
        return True
    if pc.change_type == "file_upload":
        pf = file_lookup.get(pc.field_name) if pc.field_name else None
        if pf and (pf.file_category or "") in SENSITIVE_FILE_CATEGORIES:
            return True
    if pc.change_type == "event_note":
        summary = pc.summary or ""
        if summary.startswith("Journal entry added:"):
            return True
    return False


def _journal_bucket_and_subtype(entry) -> tuple[str, str | None]:
    et = (entry.entry_type or "general").strip()
    if et == "decision":
        return (BUCKET_DECISIONS, None)
    if et == "packaging":
        return (BUCKET_DECISIONS, "packaging")
    # general / factory_discussion / cost_discovery / design_feedback /
    # question / risk / variant / other — all fold into Decisions with
    # the entry_type as a subtle subtype label for context.
    return (BUCKET_DECISIONS, et if et != "general" else None)


def get_timeline_events(
    db: Session,
    project_id: int,
    limit: int = 200,
    viewer: bool = False,
    user_lookup: dict | None = None,
) -> dict:
    """Return up to `limit` TimelineEvent dicts merged from 3 source tables.

    Output: {
        'events': [TimelineEvent...],     # already filtered for viewer
        'total_unfiltered_visible': int,  # before viewer hiding
        'viewer_hidden_count': int,       # rows hidden because viewer=True
        'total': int,                      # len(events) — what the UI shows
    }

    TimelineEvent shape (dict):
        occurred_at: datetime
        bucket: str           # one of the 6 filter chips
        subtype: str | None   # display badge (sample/rendering/packaging/cost/etc.)
        actor: str            # display_name OR username OR 'ai' OR 'system'
        title: str            # short summary headline
        body: str | None      # optional detail
        link_anchor: str | None  # #phase-row-N etc. (Lock 10 — may be None)
        is_ai: bool
        source_table: str     # 'project_changes' | 'phase_plan_changes' | 'project_journal_entries' | 'planning_apply_events'
        source_id: int        # row id in source_table (Lock 7 tiebreaker)
    """
    from app.models import (
        Project, ProjectPhase, ProjectFile, ProjectChange,
        ProjectJournalEntry, PhasePlanChange, PlanningApplyEvent, User,
    )

    # Resolve phase + file lookups once (cheap; typical project < 20 phases / 100 files)
    phases = db.query(ProjectPhase).filter(ProjectPhase.project_id == project_id).all()
    phase_by_name = {p.phase_name: p for p in phases}
    phase_ids = [p.id for p in phases]
    files = db.query(ProjectFile).filter(ProjectFile.project_id == project_id).all()
    file_by_name = {f.original_filename: f for f in files}

    if user_lookup is None:
        # Resolve referenced user ids in a single query at the end. For now
        # build an inline lookup for the actor strings.
        user_lookup = {}

    def _actor(changed_by: str | None, user_id: int | None = None) -> str:
        if user_id and user_id in user_lookup:
            return user_lookup[user_id]
        if user_id:
            u = db.query(User).filter(User.id == user_id).first()
            if u:
                name = u.display_name or u.username
                user_lookup[user_id] = name
                return name
        if (changed_by or "") == "ai":
            return "AI"
        return changed_by or "system"

    events: list[dict] = []
    viewer_hidden = 0

    # ── Source 1: project_changes ──
    pc_rows = (
        db.query(ProjectChange)
        .filter(ProjectChange.project_id == project_id)
        .order_by(ProjectChange.changed_at.desc())
        .limit(limit * 2)  # over-fetch; we may filter some
        .all()
    )
    for pc in pc_rows:
        classification = _classify_project_change(pc, phase_by_name, file_by_name)
        if classification is None:
            continue
        bucket, subtype, link = classification
        if viewer and _is_pc_sensitive(pc, file_by_name):
            viewer_hidden += 1
            continue
        is_ai = _is_ai_change(pc.changed_by, pc.source_type)
        events.append({
            "occurred_at": pc.changed_at,
            "bucket": bucket,
            "subtype": subtype,
            "actor": _actor(pc.changed_by),
            "title": pc.summary or pc.field_name or "(no summary)",
            "body": None,
            "link_anchor": link,
            "is_ai": is_ai,
            "source_table": "project_changes",
            "source_id": pc.id,
        })

    # ── Source 2: phase_plan_changes (delays + plan adjustments) ──
    if phase_ids:
        ppc_rows = (
            db.query(PhasePlanChange)
            .filter(PhasePlanChange.phase_id.in_(phase_ids))
            .order_by(PhasePlanChange.changed_at.desc())
            .limit(limit * 2)
            .all()
        )
        phase_by_id = {p.id: p for p in phases}
        for ppc in ppc_rows:
            phase = phase_by_id.get(ppc.phase_id)
            # A plan-date forward shift IS a delay; backward shifts (or new
            # date with no old) are plan adjustments.
            is_delay = bool(
                ppc.old_date and ppc.new_date and ppc.new_date > ppc.old_date
            )
            bucket = BUCKET_DELAYS if is_delay else BUCKET_PHASE_CHANGES
            subtype = None
            old_str = ppc.old_date.isoformat() if ppc.old_date else "—"
            new_str = ppc.new_date.isoformat() if ppc.new_date else "—"
            title = (
                f"{phase.phase_name if phase else 'Phase'} "
                f"{ppc.field_changed.replace('_', ' ')}: {old_str} → {new_str}"
            )
            body = ppc.reason if ppc.reason and ppc.reason != "(no reason given)" else None
            link = f"#phase-row-{ppc.phase_id}" if phase else None
            events.append({
                "occurred_at": ppc.changed_at,
                "bucket": bucket,
                "subtype": subtype,
                "actor": _actor(None, ppc.changed_by_user_id),
                "title": title,
                "body": body,
                "link_anchor": link,
                "is_ai": False,  # plan changes are always user-driven
                "source_table": "phase_plan_changes",
                "source_id": ppc.id,
            })

    # ── Source 3: project_journal_entries ──
    if not viewer:  # Lock 3: viewer cannot see journal entries at all
        je_rows = (
            db.query(ProjectJournalEntry)
            .filter(ProjectJournalEntry.project_id == project_id)
            .order_by(ProjectJournalEntry.created_at.desc())
            .limit(limit * 2)
            .all()
        )
        for je in je_rows:
            bucket, subtype = _journal_bucket_and_subtype(je)
            actor = _actor(None, je.author_user_id)
            snippet = (je.entry_text or "").strip()
            title = je.title or (snippet[:80] + "…" if len(snippet) > 80 else snippet)
            events.append({
                "occurred_at": je.created_at,
                "bucket": bucket,
                "subtype": subtype,
                "actor": actor,
                "title": title or "(empty entry)",
                "body": snippet if (snippet and snippet != title) else None,
                "link_anchor": "#journal",  # Lock 10: only renders for can_view_journal users (viewer already excluded above)
                "is_ai": False,
                "source_table": "project_journal_entries",
                "source_id": je.id,
            })
    else:
        # Count would-be-visible journal entries that we're hiding from viewer
        viewer_hidden += (
            db.query(ProjectJournalEntry)
            .filter(ProjectJournalEntry.project_id == project_id)
            .count()
        )

    # ── Source 4: planning_apply_events ──
    apply_rows = (
        db.query(PlanningApplyEvent)
        .filter(PlanningApplyEvent.project_id == project_id)
        .order_by(PlanningApplyEvent.applied_at.desc())
        .limit(limit * 2)
        .all()
    )
    for event in apply_rows:
        title = (
            f"Plan applied: {event.node_count} phases over "
            f"{event.total_days} days"
        )
        body = (
            f"Start {event.planned_start_date.isoformat()} · "
            f"Computed end {event.computed_end_date.isoformat()} · "
            f"Replaced {event.phases_deleted} phases"
        )
        if event.updated_project_planned_launch_date:
            body += " · Launch date updated"
        events.append({
            "occurred_at": event.applied_at,
            "bucket": BUCKET_PHASE_CHANGES,
            "subtype": "plan_applied",
            "actor": _actor(None, event.applied_by_user_id),
            "title": title,
            "body": body,
            "link_anchor": "#timeline-command-center",
            "is_ai": False,
            "source_table": "planning_apply_events",
            "source_id": event.id,
        })

    # ── Lock 7: merge + deterministic sort ──
    # Primary: occurred_at DESC.
    # Tiebreaker: source_priority ASC (project_changes=1, ppc=2, journal=3),
    # then source_id DESC.
    _priority = {
        "project_changes": 1,
        "phase_plan_changes": 2,
        "project_journal_entries": 3,
        "planning_apply_events": 4,
    }
    events.sort(
        key=lambda e: (
            -(e["occurred_at"].timestamp() if e["occurred_at"] else 0),
            _priority.get(e["source_table"], 99),
            -e["source_id"],
        )
    )

    truncated = events[:limit]
    return {
        "events": truncated,
        "total_unfiltered_visible": len(events),
        "viewer_hidden_count": viewer_hidden,
        "total": len(truncated),
    }
