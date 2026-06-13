from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, JSON, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    sku = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    status = Column(String, default="active")  # active / completed / archived / cancelled / paused
    current_stage = Column(String, nullable=True)  # cached from phases
    product_type = Column(String, nullable=True)
    project_owner = Column(String, nullable=True)
    product_manager = Column(String, nullable=True)
    engineer = Column(String, nullable=True)
    factory = Column(String, nullable=True)
    target_factory_cost = Column(Float, nullable=True)
    target_msrp = Column(Float, nullable=True)
    # PM-facing price fields preserve real-world ranges/currency phrases such
    # as "$70-100" or "under 120 RMB". Legacy numeric fields remain as optional
    # derived/simple-USD values for old rows and future profit math.
    target_factory_cost_text = Column(String, nullable=True)
    target_msrp_text = Column(String, nullable=True)
    planned_launch_date = Column(Date, nullable=True)
    estimated_launch_date = Column(Date, nullable=True)
    project_thesis = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    archived_at = Column(DateTime, nullable=True)

    phases = relationship("ProjectPhase", back_populates="project", cascade="all, delete-orphan", order_by="ProjectPhase.phase_order")
    files = relationship("ProjectFile", back_populates="project", cascade="all, delete-orphan")
    changes = relationship("ProjectChange", back_populates="project", cascade="all, delete-orphan")
    ai_messages = relationship("AIMessage", back_populates="project", cascade="all, delete-orphan")
    idea_links = relationship("ProjectIdea", back_populates="project", cascade="all, delete-orphan")
    # v1.1 (Build 13)
    journal_entries = relationship("ProjectJournalEntry", back_populates="project",
                                   cascade="all, delete-orphan",
                                   order_by="ProjectJournalEntry.created_at.desc()")
    variants = relationship("ProjectVariant", back_populates="project",
                            cascade="all, delete-orphan",
                            order_by="ProjectVariant.created_at")
    variant_components = relationship("ProjectVariantComponent", back_populates="project",
                                      cascade="all, delete-orphan")
    # v1.3 Build 07B — first-class blockers with active/resolved lifecycle
    blockers = relationship("ProjectBlocker", back_populates="project",
                            cascade="all, delete-orphan",
                            order_by="ProjectBlocker.created_at.desc()")
    # v1.4 Build 01 — Planning Sandbox draft/applied graph storage.
    planning_sandboxes = relationship("PlanningSandbox", back_populates="project",
                                      cascade="all, delete-orphan",
                                      order_by="PlanningSandbox.updated_at.desc()")
    apply_events = relationship("PlanningApplyEvent", back_populates="project",
                                cascade="all, delete-orphan",
                                order_by="PlanningApplyEvent.applied_at.desc()")
    # v1.5 Build 02 — Designer Portal design quest source of truth.
    design_quests = relationship("DesignQuest", back_populates="project",
                                 cascade="all, delete-orphan",
                                 order_by="DesignQuest.updated_at.desc()")
    design_submissions = relationship("DesignSubmission", back_populates="project",
                                      cascade="all, delete-orphan",
                                      order_by="DesignSubmission.updated_at.desc()")

    @property
    def target_factory_cost_display(self) -> str | None:
        if self.target_factory_cost_text:
            return self.target_factory_cost_text
        if self.target_factory_cost is not None:
            return f"${self.target_factory_cost:.2f}"
        return None

    @property
    def target_msrp_display(self) -> str | None:
        if self.target_msrp_text:
            return self.target_msrp_text
        if self.target_msrp is not None:
            return f"${self.target_msrp:.2f}"
        return None


class ProjectPhase(Base):
    __tablename__ = "project_phases"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    phase_name = Column(String, nullable=False)
    phase_type = Column(String, nullable=True)  # design / engineering / prototype / review / production / launch
    phase_order = Column(Integer, nullable=False, default=0)
    planned_start_date = Column(Date, nullable=True)
    planned_end_date = Column(Date, nullable=True)
    actual_start_date = Column(Date, nullable=True)
    actual_end_date = Column(Date, nullable=True)
    owner = Column(String, nullable=True)
    status = Column(String, default="not_started")  # not_started / in_progress / done / delayed / skipped
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="phases")
    # v1.1 (Build 13): Timeline 2.0 — record reasons when planned dates shift
    plan_changes = relationship("PhasePlanChange", back_populates="phase",
                                cascade="all, delete-orphan",
                                order_by="PhasePlanChange.changed_at")
    # v1.3 Build 07B — optional phase-level blocker association
    blockers = relationship("ProjectBlocker", back_populates="phase",
                            order_by="ProjectBlocker.created_at.desc()")


class ProjectFile(Base):
    __tablename__ = "project_files"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_type = Column(String, nullable=True)   # image / pdf / word / excel / other
    file_category = Column(String, default="other")  # rendering / reference / quotation / thesis / factory_feedback / packaging / other
    file_size = Column(Integer, nullable=True)
    ai_summary = Column(Text, nullable=True)
    source_note = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="files")


class ProjectChange(Base):
    __tablename__ = "project_changes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    changed_at = Column(DateTime, default=datetime.utcnow)
    changed_by = Column(String, default="user")   # user / ai
    change_type = Column(String, nullable=False)  # field_update / event_note / phase_update / file_upload / ai_update
    field_name = Column(String, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    delay_impact_days = Column(Integer, nullable=True)
    source_type = Column(String, default="manual_edit")  # manual_edit / ai_chat / file_upload / timeline_update

    project = relationship("Project", back_populates="changes")


class AIMessage(Base):
    __tablename__ = "ai_messages"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    # v1.1 (Build 13): groups messages into conversations. Nullable for
    # backward compat with v1.0 messages that pre-date this column.
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id"), nullable=True)
    role = Column(String, nullable=False)   # user / assistant / system
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata_json = Column(JSON, nullable=True)

    project = relationship("Project", back_populates="ai_messages")
    conversation = relationship("AIConversation", back_populates="messages")


# ---------------------------------------------------------------------------
# Auth models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="viewer")  # admin / pm / viewer
    # v1.1 (Build 13): UI language. ALL READS must fallback to "en":
    #   lang = user.language or "en"
    # DEFAULT may not backfill existing rows uniformly across SQLite/Postgres.
    language = Column(String, default="en")
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    created_pins = relationship("InvitePin", foreign_keys="InvitePin.created_by_user_id", back_populates="created_by")
    used_pins = relationship("InvitePin", foreign_keys="InvitePin.used_by_user_id", back_populates="used_by")
    ai_conversations = relationship("AIConversation", back_populates="user", cascade="all, delete-orphan")
    design_quest_assignments = relationship("DesignQuestAssignment",
                                            foreign_keys="DesignQuestAssignment.designer_user_id",
                                            back_populates="designer")
    created_design_quests = relationship("DesignQuest",
                                         foreign_keys="DesignQuest.created_by_user_id",
                                         back_populates="created_by")
    design_submissions = relationship("DesignSubmission",
                                      foreign_keys="DesignSubmission.designer_user_id",
                                      back_populates="designer")


class InvitePin(Base):
    __tablename__ = "invite_pins"

    id = Column(Integer, primary_key=True, index=True)
    pin = Column(String, unique=True, nullable=False, index=True)
    role = Column(String, nullable=False)  # pm / viewer
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    used_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    created_by = relationship("User", foreign_keys=[created_by_user_id], back_populates="created_pins")
    used_by = relationship("User", foreign_keys=[used_by_user_id], back_populates="used_pins")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="sessions")


class ProjectCreationToken(Base):
    """Build 30A — one-shot idempotency token for project create POSTs.

    Minted on GET of the New Project form (manual and AI-assisted). Claimed
    atomically on POST via an UPDATE-rowcount check. If a racing POST
    (e.g. user double-clicked Submit during a slow request) sees the token
    already claimed, the route redirects to the originally-created project
    instead of inserting a duplicate.

    24h TTL; opportunistic cleanup on every mint.
    """
    __tablename__ = "project_creation_tokens"

    token = Column(String, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    claimed_at = Column(DateTime, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)


# ---------------------------------------------------------------------------
# Ideas (Good Ideas board) + Project ↔ Idea many-to-many linkage
# ---------------------------------------------------------------------------

class Idea(Base):
    __tablename__ = "ideas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    idea_type = Column(String, nullable=False)
    # material / structure / feature / aesthetic / manufacturing / other
    source = Column(String, nullable=False)
    # factory / tradeshow / internet / customer / team / competitor / other
    source_detail = Column(String, nullable=True)
    contributor = Column(String, nullable=True)
    contributor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="open")   # open / in_use / archived
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    contributor_user = relationship("User", foreign_keys=[contributor_user_id])
    project_links = relationship(
        "ProjectIdea",
        back_populates="idea",
        cascade="all, delete-orphan",
    )

    @property
    def serial_number(self) -> str:
        return f"IDEA-{self.id:03d}"


class ProjectIdea(Base):
    """Association table linking projects to ideas (many-to-many).
    Records who linked the idea, when, and an optional note about how the
    idea was used in the project.
    """
    __tablename__ = "project_ideas"

    project_id = Column(Integer, ForeignKey("projects.id"), primary_key=True)
    idea_id = Column(Integer, ForeignKey("ideas.id"), primary_key=True)
    linked_at = Column(DateTime, default=datetime.utcnow)
    linked_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    note = Column(String, nullable=True)

    project = relationship("Project", back_populates="idea_links")
    idea = relationship("Idea", back_populates="project_links")
    linked_by_user = relationship("User", foreign_keys=[linked_by_user_id])


# ---------------------------------------------------------------------------
# v1.1 — Build 13: schema additions
#
# All 5 tables below are purely additive. Existing v1.0 tables are untouched.
# Two existing tables get nullable columns (users.language, ai_messages.conversation_id).
# Migration helper in app/migrations.py adds those columns idempotently.
# ---------------------------------------------------------------------------


class ProjectJournalEntry(Base):
    """Product reasoning evolution — raw text, AI summary, proposed updates.
    Distinct from ProjectChange (which audits field-level edits): journal
    records WHY product thinking changed (factory discussions, cost discoveries,
    abandoned directions, open questions).

    Raw `entry_text` is the source of truth. AI summary and extracted_updates
    are derived and re-parseable from raw text in future builds.
    """
    __tablename__ = "project_journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    entry_text = Column(Text, nullable=False)
    entry_type = Column(String, default="general")
    # general / factory_discussion / cost_discovery / design_feedback /
    # decision / risk / packaging / variant / other
    title = Column(String, nullable=True)            # short AI-generated summary
    visibility = Column(String, default="internal")  # internal / public
    author_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ai_summary = Column(Text, nullable=True)
    extracted_updates_json = Column(JSON, nullable=True)
    open_questions_json = Column(JSON, nullable=True)
    decisions_json = Column(JSON, nullable=True)
    options_json = Column(JSON, nullable=True)
    linked_file_id = Column(Integer, ForeignKey("project_files.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="journal_entries")
    author = relationship("User", foreign_keys=[author_user_id])
    linked_file = relationship("ProjectFile", foreign_keys=[linked_file_id])


class ProjectBlocker(Base):
    """v1.3 Build 07B — first-class project blockers.

    Lifecycle: active → resolved (Lock 1, 2 states only). No 'archived' state;
    admin-only hard delete is the escape hatch.

    phase_id is OPTIONAL (Lock 3): blockers can be project-level (phase_id=NULL)
    or phase-level. Phase-strip red dot fires only for phase-level blockers.

    Severity is a String enum (low / medium / high) — same shape as
    ProjectPhase.status to avoid SQL ENUM type migration risk.

    Audit trail: every create / update / resolve writes a project_changes row
    via write_change(). No separate audit table.
    """
    __tablename__ = "project_blockers"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    phase_id = Column(Integer, ForeignKey("project_phases.id"), nullable=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String, nullable=False, default="medium")  # low / medium / high
    status = Column(String, nullable=False, default="active")    # active / resolved
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    project = relationship("Project", back_populates="blockers")
    phase = relationship("ProjectPhase", back_populates="blockers", foreign_keys=[phase_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id])


# ---------------------------------------------------------------------------
# v1.4 — Planning Sandbox graph model
# ---------------------------------------------------------------------------

class PlanningModule(Base):
    """Reusable planning block for the future visual Planning Sandbox.

    Build 01 seeds this library only. Later builds clone modules into sandbox
    nodes, then Apply copies sandbox nodes into ProjectPhase rows.
    """
    __tablename__ = "planning_module_library"

    module_key = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)
    phase_type = Column(String, nullable=False)
    default_duration_days = Column(Integer, nullable=False)
    default_owner_role = Column(String, nullable=True)
    default_deliverable = Column(Text, nullable=True)
    default_exit_criteria = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sandbox_nodes = relationship("PlanningSandboxNode", back_populates="module")
    template_nodes = relationship("PlanningTemplateNode", back_populates="module")


class PlanningSandbox(Base):
    __tablename__ = "planning_sandboxes"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="draft")
    base_template_key = Column(String, nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    applied_at = Column(DateTime, nullable=True)
    applied_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    last_computed_total_days = Column(Integer, nullable=True)

    project = relationship("Project", back_populates="planning_sandboxes")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    applied_by = relationship("User", foreign_keys=[applied_by_user_id])
    nodes = relationship("PlanningSandboxNode", back_populates="sandbox",
                         cascade="all, delete-orphan",
                         order_by="PlanningSandboxNode.sort_order")
    edges = relationship("PlanningSandboxEdge", back_populates="sandbox",
                         cascade="all, delete-orphan")
    apply_events = relationship("PlanningApplyEvent", back_populates="sandbox",
                                cascade="all, delete-orphan",
                                order_by="PlanningApplyEvent.applied_at.desc()")


class PlanningSandboxNode(Base):
    __tablename__ = "planning_sandbox_nodes"

    id = Column(Integer, primary_key=True, index=True)
    sandbox_id = Column(Integer, ForeignKey("planning_sandboxes.id"), nullable=False)
    module_key = Column(String, ForeignKey("planning_module_library.module_key"), nullable=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=True)
    phase_type = Column(String, nullable=False)
    duration_days = Column(Integer, nullable=False)
    owner_role = Column(String, nullable=True)
    deliverable = Column(Text, nullable=True)
    exit_criteria = Column(Text, nullable=True)
    x_position = Column(Float, nullable=False, default=0)
    y_position = Column(Float, nullable=False, default=0)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sandbox = relationship("PlanningSandbox", back_populates="nodes")
    module = relationship("PlanningModule", back_populates="sandbox_nodes")
    outgoing_edges = relationship("PlanningSandboxEdge",
                                  foreign_keys="PlanningSandboxEdge.from_node_id",
                                  back_populates="from_node",
                                  cascade="all, delete-orphan")
    incoming_edges = relationship("PlanningSandboxEdge",
                                  foreign_keys="PlanningSandboxEdge.to_node_id",
                                  back_populates="to_node",
                                  cascade="all, delete-orphan")


class PlanningSandboxEdge(Base):
    __tablename__ = "planning_sandbox_edges"
    __table_args__ = (
        UniqueConstraint("from_node_id", "to_node_id", name="uq_planning_sandbox_edge_pair"),
    )

    id = Column(Integer, primary_key=True, index=True)
    sandbox_id = Column(Integer, ForeignKey("planning_sandboxes.id"), nullable=False)
    from_node_id = Column(Integer, ForeignKey("planning_sandbox_nodes.id"), nullable=False)
    to_node_id = Column(Integer, ForeignKey("planning_sandbox_nodes.id"), nullable=False)
    dependency_type = Column(String, nullable=False, default="finish_to_start")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    sandbox = relationship("PlanningSandbox", back_populates="edges")
    from_node = relationship("PlanningSandboxNode",
                             foreign_keys=[from_node_id],
                             back_populates="outgoing_edges")
    to_node = relationship("PlanningSandboxNode",
                           foreign_keys=[to_node_id],
                           back_populates="incoming_edges")


class PlanningApplyEvent(Base):
    """v1.4 Build 07 — audited bridge from sandbox draft to live phases."""
    __tablename__ = "planning_apply_events"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    sandbox_id = Column(Integer, ForeignKey("planning_sandboxes.id"), nullable=False)
    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    applied_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    snapshot_json = Column(JSON, nullable=False)
    node_count = Column(Integer, nullable=False, default=0)
    total_days = Column(Integer, nullable=False, default=0)
    planned_start_date = Column(Date, nullable=False)
    computed_end_date = Column(Date, nullable=False)
    updated_project_planned_launch_date = Column(Boolean, nullable=False, default=False)
    phases_created = Column(Integer, nullable=False, default=0)
    phases_updated = Column(Integer, nullable=False, default=0)
    phases_deleted = Column(Integer, nullable=False, default=0)

    project = relationship("Project", back_populates="apply_events")
    sandbox = relationship("PlanningSandbox", back_populates="apply_events")
    applied_by = relationship("User", foreign_keys=[applied_by_user_id])


class PlanningTemplate(Base):
    __tablename__ = "planning_templates"

    id = Column(Integer, primary_key=True, index=True)
    template_key = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, nullable=False, default=False)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)

    created_by = relationship("User", foreign_keys=[created_by_user_id])
    nodes = relationship("PlanningTemplateNode", back_populates="template",
                         cascade="all, delete-orphan",
                         order_by="PlanningTemplateNode.sort_order")
    edges = relationship("PlanningTemplateEdge", back_populates="template",
                         cascade="all, delete-orphan")


class PlanningTemplateNode(Base):
    __tablename__ = "planning_template_nodes"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("planning_templates.id"), nullable=False)
    module_key = Column(String, ForeignKey("planning_module_library.module_key"), nullable=True)
    title = Column(String, nullable=False)
    duration_days = Column(Integer, nullable=False)
    owner_role = Column(String, nullable=True)
    deliverable = Column(Text, nullable=True)
    exit_criteria = Column(Text, nullable=True)
    x_position = Column(Float, nullable=False, default=0)
    y_position = Column(Float, nullable=False, default=0)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    template = relationship("PlanningTemplate", back_populates="nodes")
    module = relationship("PlanningModule", back_populates="template_nodes")
    outgoing_edges = relationship("PlanningTemplateEdge",
                                  foreign_keys="PlanningTemplateEdge.from_node_id",
                                  back_populates="from_node",
                                  cascade="all, delete-orphan")
    incoming_edges = relationship("PlanningTemplateEdge",
                                  foreign_keys="PlanningTemplateEdge.to_node_id",
                                  back_populates="to_node",
                                  cascade="all, delete-orphan")


class PlanningTemplateEdge(Base):
    __tablename__ = "planning_template_edges"
    __table_args__ = (
        UniqueConstraint("from_node_id", "to_node_id", name="uq_planning_template_edge_pair"),
    )

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("planning_templates.id"), nullable=False)
    from_node_id = Column(Integer, ForeignKey("planning_template_nodes.id"), nullable=False)
    to_node_id = Column(Integer, ForeignKey("planning_template_nodes.id"), nullable=False)
    dependency_type = Column(String, nullable=False, default="finish_to_start")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    template = relationship("PlanningTemplate", back_populates="edges")
    from_node = relationship("PlanningTemplateNode",
                             foreign_keys=[from_node_id],
                             back_populates="outgoing_edges")
    to_node = relationship("PlanningTemplateNode",
                           foreign_keys=[to_node_id],
                           back_populates="incoming_edges")


# ---------------------------------------------------------------------------
# v1.5 — Designer Portal design quest model
# ---------------------------------------------------------------------------

class DesignQuest(Base):
    """PM-created brief for restricted designer work.

    Build 02 stores the source of truth only. PM/designer UI, guarded file
    serving, submissions, revisions, and final rendering promotion arrive in
    later v1.5 builds.
    """
    __tablename__ = "design_quests"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    title = Column(String, nullable=False)
    brief = Column(Text, nullable=False)
    must_keep = Column(Text, nullable=True)
    must_avoid = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="draft")
    visibility = Column(String, nullable=False, default="all_active_designers")
    soft_deadline = Column(Date, nullable=True)
    is_timeline_blocking = Column(Boolean, nullable=False, default=False)
    linked_phase_id = Column(Integer, ForeignKey("project_phases.id"), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    published_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="design_quests")
    linked_phase = relationship("ProjectPhase", foreign_keys=[linked_phase_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id],
                              back_populates="created_design_quests")
    assignments = relationship("DesignQuestAssignment", back_populates="quest",
                               cascade="all, delete-orphan")
    references = relationship("DesignQuestReference", back_populates="quest",
                              cascade="all, delete-orphan",
                              order_by="DesignQuestReference.sort_order")
    events = relationship("DesignQuestEvent", back_populates="quest",
                          cascade="all, delete-orphan",
                          order_by="DesignQuestEvent.created_at.desc()")
    submissions = relationship("DesignSubmission", back_populates="quest",
                               cascade="all, delete-orphan",
                               order_by="DesignSubmission.updated_at.desc()")


class DesignQuestAssignment(Base):
    __tablename__ = "design_quest_assignments"
    __table_args__ = (
        UniqueConstraint("quest_id", "designer_user_id", name="uq_design_quest_assignment_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    quest_id = Column(Integer, ForeignKey("design_quests.id"), nullable=False)
    designer_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, nullable=False, default="assigned")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    quest = relationship("DesignQuest", back_populates="assignments")
    designer = relationship("User", foreign_keys=[designer_user_id],
                            back_populates="design_quest_assignments")
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id])


class DesignQuestReference(Base):
    __tablename__ = "design_quest_references"

    id = Column(Integer, primary_key=True, index=True)
    quest_id = Column(Integer, ForeignKey("design_quests.id"), nullable=False)
    project_file_id = Column(Integer, ForeignKey("project_files.id"), nullable=False)
    label = Column(String, nullable=True)
    visibility = Column(String, nullable=False, default="designer_visible")
    sort_order = Column(Integer, nullable=False, default=0)
    added_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    quest = relationship("DesignQuest", back_populates="references")
    project_file = relationship("ProjectFile", foreign_keys=[project_file_id])
    added_by = relationship("User", foreign_keys=[added_by_user_id])


class DesignQuestEvent(Base):
    __tablename__ = "design_quest_events"

    id = Column(Integer, primary_key=True, index=True)
    quest_id = Column(Integer, ForeignKey("design_quests.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    event_type = Column(String, nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    summary = Column(Text, nullable=True)
    payload_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    quest = relationship("DesignQuest", back_populates="events")
    project = relationship("Project")
    actor = relationship("User", foreign_keys=[actor_user_id])


class DesignSubmission(Base):
    """Designer-owned submission record for one quest.

    Build 05 keeps each designer to one active submission per quest and stores
    every upload as an immutable DesignSubmissionVersion row.
    """
    __tablename__ = "design_submissions"

    id = Column(Integer, primary_key=True, index=True)
    quest_id = Column(Integer, ForeignKey("design_quests.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    designer_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False, default="submitted")
    title = Column(String, nullable=True)
    designer_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    quest = relationship("DesignQuest", back_populates="submissions")
    project = relationship("Project", back_populates="design_submissions")
    designer = relationship("User", foreign_keys=[designer_user_id],
                            back_populates="design_submissions")
    versions = relationship("DesignSubmissionVersion", back_populates="submission",
                            cascade="all, delete-orphan",
                            order_by="DesignSubmissionVersion.version_number")


class DesignSubmissionVersion(Base):
    """Immutable uploaded file version for a design submission."""
    __tablename__ = "design_submission_versions"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("design_submissions.id"), nullable=False)
    quest_id = Column(Integer, ForeignKey("design_quests.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    designer_note = Column(Text, nullable=True)
    uploaded_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    submission = relationship("DesignSubmission", back_populates="versions")
    quest = relationship("DesignQuest")
    project = relationship("Project")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_user_id])


class ProjectVariant(Base):
    """Multi-SKU support. A project can have multiple variants (colors,
    materials, sizes, budget/premium splits).

    is_primary is enforced at the SERVICE LAYER (Build 16): only one variant
    per project should be primary at a time. NOT a DB unique constraint —
    too risky for migrations.
    """
    __tablename__ = "project_variants"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    variant_name = Column(String, nullable=False)
    sku = Column(String, nullable=True)
    status = Column(String, default="evaluating")
    # idea / evaluating / selected / rejected / launched
    is_primary = Column(Boolean, default=False)
    target_factory_cost = Column(Float, nullable=True)
    actual_factory_cost = Column(Float, nullable=True)
    target_msrp = Column(Float, nullable=True)
    material_summary = Column(Text, nullable=True)
    size_color_summary = Column(Text, nullable=True)
    packaging_summary = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    # v1.3 Build 05B — structured spec grouping matching the Overview
    # redesign wireframe §5.4-5.7. All nullable; per-section narrative
    # text preserves units / mixed languages / qualifiers.
    sales_format = Column(String, nullable=True)
    # canonical values: single / combo / colorway / packaging_variant /
    # retail / amazon / other. Stored as String for forward flexibility;
    # custom values allowed.
    packaging_cost = Column(Float, nullable=True)
    blade_summary = Column(Text, nullable=True)
    handle_summary = Column(Text, nullable=True)
    mechanism_summary = Column(Text, nullable=True)
    dimensions_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="variants")
    components = relationship("ProjectVariantComponent", back_populates="variant",
                              cascade="all, delete-orphan")


class ProjectVariantComponent(Base):
    """Packaging + accessories. May belong to a specific variant
    (variant_id set) OR apply to all variants of the project (variant_id NULL).
    """
    __tablename__ = "project_variant_components"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    variant_id = Column(Integer, ForeignKey("project_variants.id"), nullable=True)
    component_type = Column(String, default="accessory")  # packaging / accessory
    name = Column(String, nullable=False)
    target_cost = Column(Float, nullable=True)
    actual_cost = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="variant_components")
    variant = relationship("ProjectVariant", back_populates="components")


class PhasePlanChange(Base):
    """Records when a phase's planned date is shifted and WHY.
    Required for Timeline 2.0 (Build 17). Plan dates aren't freely mutable —
    every change must capture a reason.
    """
    __tablename__ = "phase_plan_changes"

    id = Column(Integer, primary_key=True, index=True)
    phase_id = Column(Integer, ForeignKey("project_phases.id"), nullable=False)
    field_changed = Column(String, nullable=False)  # e.g. 'planned_end_date'
    old_date = Column(Date, nullable=True)
    new_date = Column(Date, nullable=True)
    reason = Column(Text, nullable=False)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    changed_at = Column(DateTime, default=datetime.utcnow)

    phase = relationship("ProjectPhase", back_populates="plan_changes")
    changed_by = relationship("User", foreign_keys=[changed_by_user_id])


class AIConversation(Base):
    """Groups AI chat messages into conversations.
    project_id NULL = global chat. status='archived' removes from active
    runtime context but keeps the conversation searchable.
    """
    __tablename__ = "ai_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    title = Column(String, nullable=True)
    status = Column(String, default="active")  # active / archived
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="ai_conversations")
    project = relationship("Project", foreign_keys=[project_id])
    messages = relationship("AIMessage", back_populates="conversation",
                            order_by="AIMessage.created_at")
