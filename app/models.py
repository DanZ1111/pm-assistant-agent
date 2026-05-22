from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, JSON, ForeignKey, Boolean
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
    role = Column(String, nullable=False)   # user / assistant / system
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata_json = Column(JSON, nullable=True)

    project = relationship("Project", back_populates="ai_messages")


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
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    created_pins = relationship("InvitePin", foreign_keys="InvitePin.created_by_user_id", back_populates="created_by")
    used_pins = relationship("InvitePin", foreign_keys="InvitePin.used_by_user_id", back_populates="used_by")


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
