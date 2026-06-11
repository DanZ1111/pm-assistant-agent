"""Shared fixture helpers extracted from test_v14_build09.py:34-95.

Each call to build_db() returns a fresh in-memory SQLite + sessionmaker with
all migrations applied. Scenarios use these helpers in setup() only.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def build_db():
    """Build a fresh sqlite DB with all migrations applied.

    Returns (tempdir, engine, Session). Caller is responsible for keeping
    tempdir alive for the lifetime of the engine.
    """
    tmp = tempfile.TemporaryDirectory()
    db_path = Path(tmp.name) / "scenario.db"
    engine = create_engine(f"sqlite:///{db_path}")

    import app.models  # noqa: F401  — register models on Base
    from app.database import Base
    from app import migrations

    Base.metadata.create_all(bind=engine)
    migrations.run_pending(engine)
    Session = sessionmaker(bind=engine)
    return tmp, engine, Session


def create_user(db, username="scenario_pm", role="pm", display_name=None):
    from app.models import User

    user = User(
        username=username,
        display_name=display_name or username,
        hashed_password="scenario",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_project(db, name="Scenario Project", pm_name="scenario_pm",
                   status="active", **fields):
    from app.models import Project

    project = Project(name=name, status=status, product_manager=pm_name, **fields)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def create_project_with_costs(db, name, pm_name, target_factory_cost=None,
                              target_msrp=None, status="active"):
    """Create a project with optional initial cost fields seeded."""
    fields = {}
    if target_factory_cost is not None:
        fields["target_factory_cost"] = target_factory_cost
    if target_msrp is not None:
        fields["target_msrp"] = target_msrp
    return create_project(db, name=name, pm_name=pm_name, status=status, **fields)


def seed_ai_conversation(db, project_id, user_id,
                         title="AI intake conversation"):
    """Seed one AIConversation row + one AIMessage row for the project.

    Mirrors what the AI intake flow produces. Used by
    project_delete_ai_intake_cleanup to reconstruct the Marine-bug
    surface: project + AI rows under SQLite FK enforcement.

    `user_id` is required because AIConversation.user_id is non-nullable
    (every conversation has an owning user).
    """
    from app.models import AIConversation, AIMessage

    conversation = AIConversation(
        project_id=project_id, title=title, user_id=user_id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    message = AIMessage(
        project_id=project_id, conversation_id=conversation.id,
        role="assistant",
        message="(seeded for QA scenario)",
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return conversation, message


def seed_creation_token(db, user_id, project_id=None, claimed=False):
    """Seed one project_creation_tokens row to simulate an unclaimed
    or claimed token."""
    import uuid
    from datetime import datetime
    from app.models import ProjectCreationToken

    token_row = ProjectCreationToken(
        token=uuid.uuid4().hex,
        user_id=user_id,
        created_at=datetime.utcnow(),
        claimed_at=datetime.utcnow() if claimed else None,
        project_id=project_id if claimed else None,
    )
    db.add(token_row)
    db.commit()
    db.refresh(token_row)
    return token_row


def seed_phases(db, project_id, names, start_date=None, duration_days=10):
    """Create a sequential set of not-started phases for a project."""
    from app.models import ProjectPhase

    start = start_date or date.today()
    phases = []
    for i, name in enumerate(names):
        phase_start = start + timedelta(days=i * duration_days)
        phase_end = phase_start + timedelta(days=duration_days - 1)
        phase = ProjectPhase(
            project_id=project_id,
            phase_name=name,
            phase_order=i + 1,
            status="not_started",
            planned_start_date=phase_start,
            planned_end_date=phase_end,
        )
        db.add(phase)
        phases.append(phase)
    db.commit()
    for phase in phases:
        db.refresh(phase)
    return phases
