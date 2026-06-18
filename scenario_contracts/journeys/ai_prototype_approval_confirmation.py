"""Journey — AI proposal guard for prototype approval.

A PM receives pseudo-business information:

    "The factory returned the prototype and the engineer says it is good enough."

AI should be able to propose recording that update and moving the phase forward,
but it must not write anything until the PM confirms. This journey tests the
service-layer AI dispatcher contract directly, then checks the resulting DB and
history state after confirmation.
"""
from scenario_contracts.lib import actions, assertions, fixtures
from scenario_contracts.lib.journey import Step

ID = "journey_ai_prototype_approval_confirmation_001"
TITLE = "AI prototype approval proposal requires confirmation before journal and phase mutation"
TAGS = ["journey", "deterministic", "ai_mocked", "confirmation", "timeline"]
MATURITY = "candidate"
WHY_IT_MATTERS = (
    "The PM assistant is only trustworthy if AI can suggest updates without "
    "silently changing project state. This journey catches silent mutation of "
    "journal entries or phase status before confirmation, plus missing history "
    "after the PM approves the proposed action."
)

PROJECT_NAME = "QA Prototype Approval Folder"
APPROVAL_NOTE = (
    "Factory returned Prototype 1. Engineer reviewed fit, lockup, and action; "
    "approved to move into pre-production sample."
)
CURRENT_PHASE_NAME = "Prototype Review"
NEXT_PHASE_NAME = "Pre-production Sample"


def setup(db):
    pm = fixtures.create_user(
        db,
        username="qa_ai_proto_pm",
        role="pm",
        display_name="QA AI Prototype PM",
    )
    return {"pm": pm}


def _phase_rows(db, project_id):
    from sqlalchemy import text

    return db.execute(
        text("""
            SELECT id, phase_name, status
            FROM project_phases
            WHERE project_id = :project_id
            ORDER BY phase_order
        """),
        {"project_id": project_id},
    ).fetchall()


def _phase_id(db, project_id, phase_name):
    for row in _phase_rows(db, project_id):
        if row[1] == phase_name:
            return row[0]
    raise RuntimeError(f"phase not found: {phase_name}")


def do_create_project_at_prototype_review(world, db, http):
    project = actions.create_project_for_pm(
        db,
        name=PROJECT_NAME,
        pm_username=world["pm"].username,
        brand="QA",
        project_thesis=(
            "A synthetic QA project for verifying AI proposal confirmation "
            "around prototype approval."
        ),
    )
    world["project_id"] = project.id
    rows = _phase_rows(db, project.id)
    # Finish Design, Engineering Review, and Prototype 1 so Prototype Review
    # becomes the current in-progress phase.
    for phase_id, phase_name, _status in rows[:3]:
        actions.finish_phase(
            db,
            phase_id=phase_id,
            user_id=world["pm"].id,
            changed_by="user",
        )
        world[f"finished_{phase_name}"] = phase_id
    world["prototype_review_phase_id"] = _phase_id(
        db, project.id, CURRENT_PHASE_NAME
    )
    world["preproduction_phase_id"] = _phase_id(
        db, project.id, NEXT_PHASE_NAME
    )


def check_project_at_prototype_review(db, world):
    assertions.assert_phase_field(
        db,
        world["prototype_review_phase_id"],
        "status",
        "in_progress",
        label="Prototype Review is current before AI proposal",
    )
    assertions.assert_phase_field(
        db,
        world["preproduction_phase_id"],
        "status",
        "not_started",
        label="Pre-production Sample has not started yet",
    )


def do_ai_proposes_journal(world, db, http):
    world["journal_count_before"] = actions.snapshot_table_count(
        db,
        "project_journal_entries",
        where={"project_id": world["project_id"]},
    )
    world["history_count_before_journal"] = actions.snapshot_table_count(
        db,
        "project_changes",
        where={"project_id": world["project_id"]},
    )
    world["unconfirmed_journal"] = actions.ai_dispatch(
        db,
        "create_journal_entry",
        {
            "project_id": world["project_id"],
            "entry_text": APPROVAL_NOTE,
            "entry_type": "decision",
        },
        world["pm"],
        confirmed=False,
    )


def check_unconfirmed_journal_did_not_mutate(db, world):
    assertions.assert_dispatch_required_confirmation(
        world["unconfirmed_journal"],
        "create_journal_entry",
        label="AI journal proposal requires confirmation",
    )
    assertions.assert_row_count(
        db,
        "project_journal_entries",
        world["journal_count_before"],
        where={"project_id": world["project_id"]},
        label="unconfirmed AI journal did not create a journal row",
    )
    assertions.assert_row_count(
        db,
        "project_changes",
        world["history_count_before_journal"],
        where={"project_id": world["project_id"]},
        label="unconfirmed AI journal did not create history",
    )


def do_confirm_journal(world, db, http):
    world["confirmed_journal"] = actions.ai_dispatch(
        db,
        "create_journal_entry",
        {
            "project_id": world["project_id"],
            "entry_text": APPROVAL_NOTE,
            "entry_type": "decision",
        },
        world["pm"],
        confirmed=True,
    )


def check_confirmed_journal_wrote_history(db, world):
    assertions.assert_dispatch_succeeded(
        world["confirmed_journal"],
        label="confirmed AI journal succeeds",
    )
    assertions.assert_row_count(
        db,
        "project_journal_entries",
        world["journal_count_before"] + 1,
        where={"project_id": world["project_id"]},
        label="confirmed AI journal creates exactly one journal row",
    )
    assertions.assert_history_contains(
        db,
        world["project_id"],
        "Factory returned Prototype 1",
        label="confirmed AI journal appears in project history",
    )


def do_ai_proposes_finish_phase(world, db, http):
    world["history_count_before_finish"] = actions.snapshot_table_count(
        db,
        "project_changes",
        where={"project_id": world["project_id"]},
    )
    world["unconfirmed_finish"] = actions.ai_dispatch(
        db,
        "finish_phase",
        {
            "project_id": world["project_id"],
            "phase_id": world["prototype_review_phase_id"],
        },
        world["pm"],
        confirmed=False,
    )


def check_unconfirmed_finish_did_not_mutate(db, world):
    assertions.assert_dispatch_required_confirmation(
        world["unconfirmed_finish"],
        "finish_phase",
        label="AI finish-phase proposal requires confirmation",
    )
    assertions.assert_phase_field(
        db,
        world["prototype_review_phase_id"],
        "status",
        "in_progress",
        label="unconfirmed AI finish leaves Prototype Review in progress",
    )
    assertions.assert_phase_field(
        db,
        world["preproduction_phase_id"],
        "status",
        "not_started",
        label="unconfirmed AI finish does not advance next phase",
    )
    assertions.assert_row_count(
        db,
        "project_changes",
        world["history_count_before_finish"],
        where={"project_id": world["project_id"]},
        label="unconfirmed AI finish does not create phase history",
    )


def do_confirm_finish_phase(world, db, http):
    world["confirmed_finish"] = actions.ai_dispatch(
        db,
        "finish_phase",
        {
            "project_id": world["project_id"],
            "phase_id": world["prototype_review_phase_id"],
        },
        world["pm"],
        confirmed=True,
    )


def check_confirmed_finish_advances_project(db, world):
    assertions.assert_dispatch_succeeded(
        world["confirmed_finish"],
        label="confirmed AI finish-phase succeeds",
    )
    assertions.assert_phase_field(
        db,
        world["prototype_review_phase_id"],
        "status",
        "done",
        label="confirmed AI finish marks Prototype Review done",
    )
    assertions.assert_phase_field(
        db,
        world["preproduction_phase_id"],
        "status",
        "in_progress",
        label="confirmed AI finish advances Pre-production Sample",
    )
    assertions.assert_history_contains(
        db,
        world["project_id"],
        "Prototype Review",
        label="confirmed AI finish writes phase history",
    )


STEPS = [
    Step(
        "PM project is already at Prototype Review",
        do_create_project_at_prototype_review,
        check_project_at_prototype_review,
    ),
    Step(
        "AI proposes prototype approval journal without confirmation",
        do_ai_proposes_journal,
        check_unconfirmed_journal_did_not_mutate,
    ),
    Step(
        "PM confirms AI journal proposal",
        do_confirm_journal,
        check_confirmed_journal_wrote_history,
    ),
    Step(
        "AI proposes finishing Prototype Review without confirmation",
        do_ai_proposes_finish_phase,
        check_unconfirmed_finish_did_not_mutate,
    ),
    Step(
        "PM confirms AI phase advancement",
        do_confirm_finish_phase,
        check_confirmed_finish_advances_project,
    ),
]
