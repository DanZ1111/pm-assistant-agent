"""Mini-journey — PM basic lifecycle (6 steps, deterministic, no AI).

PM creates a project (8 default phases auto-seeded from PHASE_TEMPLATES),
finishes Design, adjusts Engineering Review's due date with a reason,
opens a blocker on Mass Production, resolves it, then logs a journal
entry.

This is the FIRST journey scenario. Its job is to prove the multi-step
journey shape works end-to-end before QA-05+ layer in mocked AI and
disruptions.

Real integration insight caught during authoring: `crud.create_project`
auto-seeds 8 default phases from PHASE_TEMPLATES["single"] — a contract
scenario testing just "one project row exists after create" would miss
this; the journey shape forced us to predict and verify the full state
including the auto-seeded phases.

Each step is two functions: `do_*` performs the action (uses only
actions.* / fixtures.*), `check_*` pins the predicted state (uses only
assertions.*).
"""
from datetime import date

from scenario_contracts.lib import actions, assertions, fixtures
from scenario_contracts.lib.journey import Step

ID = "journey_basic_pm_lifecycle_001"
TITLE = "PM: create project → finish Design → delay Eng Review → block/unblock Mass Production → log journal"
TAGS = ["journey", "deterministic", "smoke"]
MATURITY = "candidate"
WHY_IT_MATTERS = (
    "First proof that multi-step journeys catch integration bugs no "
    "atomic contract scenario can. If create_project + finish_phase + "
    "update_phase + create_blocker + resolve_blocker + journal_entry "
    "don't compose, the PM lifecycle is broken and this journey will "
    "fail at the exact step that broke."
)

# Constants used across steps.
DEFAULT_PHASE_COUNT = 8         # PHASE_TEMPLATES['single']
DESIGN_PHASE_NAME = "Design"
ENG_REVIEW_PHASE_NAME = "Engineering Review"
MASS_PROD_PHASE_NAME = "Mass Production"
ENG_REVIEW_NEW_END = date(2026, 8, 15)
DELAY_REASON = "Coating supplier late by two weeks"
BLOCKER_TITLE = "Production line maintenance window collision"
JOURNAL_TEXT = "Discussed sample weight tradeoffs with factory; agreed to drop liner thickness 0.1mm."


def setup(db):
    pm = fixtures.create_user(db, username="alice", role="pm",
                              display_name="Alice")
    return {"pm": pm}


# ── Step 1: PM creates project (8 default phases auto-seeded) ──────────

def do_create_project(world, db, http):
    world["project"] = actions.create_project_for_pm(
        db, name="Marine Knife Lifecycle", pm_username="alice",
    )


def check_after_create(db, world):
    project_id = world["project"].id
    assertions.assert_row_count(
        db, "projects", expected=1,
        label="one project exists after creation",
    )
    assertions.assert_db_field(
        db, "projects", where={"id": project_id},
        field="product_manager", expected="alice",
        label="project owned by alice",
    )
    # The 'single' prototype template auto-seeds 8 phases.
    assertions.assert_row_count(
        db, "project_phases", expected=DEFAULT_PHASE_COUNT,
        where={"project_id": project_id},
        label="8 default phases auto-seeded from PHASE_TEMPLATES['single']",
    )
    # The first phase is Design.
    assertions.assert_db_field(
        db, "project_phases",
        where={"project_id": project_id, "phase_order": 1},
        field="phase_name", expected=DESIGN_PHASE_NAME,
        label="first phase is Design",
    )


# ── Step 2: Capture phase IDs into world (no mutation) ─────────────────

def do_capture_phase_ids(world, db, http):
    # Phase IDs are needed by later steps. Read them via a snapshot
    # action (no mutation; same discipline as snapshot_table_count).
    from sqlalchemy import text
    rows = db.execute(
        text("""
            SELECT id, phase_name, phase_order
            FROM project_phases
            WHERE project_id = :pid
            ORDER BY phase_order
        """),
        {"pid": world["project"].id},
    ).fetchall()
    world["phase_by_name"] = {r[1]: r[0] for r in rows}
    world["design_id"] = world["phase_by_name"][DESIGN_PHASE_NAME]
    world["eng_review_id"] = world["phase_by_name"][ENG_REVIEW_PHASE_NAME]
    world["mass_prod_id"] = world["phase_by_name"][MASS_PROD_PHASE_NAME]


def check_after_capture(db, world):
    # Confirm we found the IDs we'll need.
    assertions.assert_equal(
        world["design_id"] is not None, True,
        label="Design phase id captured",
    )
    assertions.assert_equal(
        world["eng_review_id"] is not None, True,
        label="Engineering Review phase id captured",
    )
    assertions.assert_equal(
        world["mass_prod_id"] is not None, True,
        label="Mass Production phase id captured",
    )


# ── Step 3: PM finishes Design — next phase auto-advances ──────────────

def do_finish_design(world, db, http):
    actions.finish_phase(db, phase_id=world["design_id"], user_id=world["pm"].id)


def check_after_finish_design(db, world):
    assertions.assert_phase_field(
        db, world["design_id"], field="status", expected="done",
        label="Design done after finish",
    )
    assertions.assert_phase_field(
        db, world["eng_review_id"], field="status", expected="in_progress",
        label="Engineering Review auto-advanced to in_progress",
    )
    assertions.assert_history_contains(
        db, world["project"].id, f"Phase '{DESIGN_PHASE_NAME}' marked done",
        label="change-log records the Design finish",
    )


# ── Step 4: PM adjusts Engineering Review's due date with a reason ─────

def do_delay_eng_review(world, db, http):
    actions.adjust_due_date(
        db, phase_id=world["eng_review_id"],
        new_end_date=ENG_REVIEW_NEW_END, reason=DELAY_REASON,
    )


def check_after_delay_eng_review(db, world):
    assertions.assert_phase_field(
        db, world["eng_review_id"], field="planned_end_date",
        expected=ENG_REVIEW_NEW_END.isoformat(),
        label="Engineering Review planned_end_date moved",
    )
    assertions.assert_phase_plan_change_recorded(
        db, world["eng_review_id"], reason_needle=DELAY_REASON,
        label="phase_plan_changes row recorded the supplier-late reason",
    )
    assertions.assert_history_contains(
        db, world["project"].id, DELAY_REASON,
        label="change-log surfaces the delay reason",
    )


# ── Step 5: PM opens a blocker on Mass Production ──────────────────────

def do_open_blocker(world, db, http):
    blocker = actions.create_blocker(
        db, project_id=world["project"].id, title=BLOCKER_TITLE,
        description="Production line is down for maintenance during planned start week.",
        severity="high", phase_id=world["mass_prod_id"], user_id=world["pm"].id,
    )
    world["blocker_id"] = blocker.id


def check_after_open_blocker(db, world):
    assertions.assert_active_blocker_count(
        db, world["project"].id, expected=1,
        label="one active blocker on the project",
    )
    assertions.assert_db_field(
        db, "project_blockers", where={"id": world["blocker_id"]},
        field="phase_id", expected=world["mass_prod_id"],
        label="blocker is attached to Mass Production phase",
    )
    assertions.assert_history_contains(
        db, world["project"].id, BLOCKER_TITLE,
        label="change-log records the blocker open",
    )


# ── Step 6: PM resolves the blocker; logs a journal entry ──────────────

def do_resolve_and_log(world, db, http):
    actions.resolve_blocker(
        db, blocker_id=world["blocker_id"], user_id=world["pm"].id,
    )
    actions.create_journal_entry(
        db, project_id=world["project"].id,
        entry_text=JOURNAL_TEXT, entry_type="design_decision",
        user_id=world["pm"].id,
    )


def check_after_resolve_and_log(db, world):
    assertions.assert_active_blocker_count(
        db, world["project"].id, expected=0,
        label="no active blockers after resolve",
    )
    assertions.assert_db_field(
        db, "project_blockers", where={"id": world["blocker_id"]},
        field="status", expected="resolved",
        label="blocker status is resolved",
    )
    assertions.assert_row_count(
        db, "project_journal_entries", expected=1,
        where={"project_id": world["project"].id},
        label="journal entry recorded",
    )


# ── Journey definition ─────────────────────────────────────────────────

STEPS = [
    Step("PM creates project (8 default phases auto-seeded)",
         do_create_project, check_after_create),
    Step("Capture phase IDs by name",
         do_capture_phase_ids, check_after_capture),
    Step("PM finishes Design — Engineering Review auto-advances",
         do_finish_design, check_after_finish_design),
    Step("PM adjusts Engineering Review due date with a reason",
         do_delay_eng_review, check_after_delay_eng_review),
    Step("PM opens a high-severity blocker on Mass Production",
         do_open_blocker, check_after_open_blocker),
    Step("PM resolves the blocker and logs a journal entry",
         do_resolve_and_log, check_after_resolve_and_log),
]
