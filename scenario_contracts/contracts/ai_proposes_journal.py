"""Release-gate scenario — AI must propose, not directly write, a journal entry.

CLAUDE.md non-negotiable:
  "AI never writes directly to the database without user confirmation."

The contract for `create_journal_entry`:
  - PM/admin dispatch unconfirmed → result is `confirmation_required`;
    `project_journal_entries` table unchanged.
  - PM/admin dispatch confirmed → exactly one new entry; one
    `project_changes` "event_note" row with a snippet of the text.
  - Viewer dispatch → `forbidden`; no DB write.
"""
from scenario_contracts.lib import actions, assertions, fixtures

ID = "ai_proposes_journal_001"
TITLE = "AI proposing a journal entry must require confirmation; viewer denied"
TAGS = ["release_gate", "deterministic", "ai_confirmation"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "The CLAUDE.md non-negotiable says AI never writes without "
    "confirmation. If a future refactor drops create_journal_entry from "
    "CONFIRMATION_TOOLS, AI could silently log private journal entries "
    "on behalf of PMs. This contract locks the guard."
)

ENTRY_TEXT = "AI-proposed note: factory confirmed Pantone match on grip."
ENTRY_SNIPPET = "AI-proposed note: factory confirmed"


def setup(db):
    admin = fixtures.create_user(db, username="root_ai", role="admin")
    pm = fixtures.create_user(db, username="pm_ai", role="pm",
                              display_name="PM-AI")
    viewer = fixtures.create_user(db, username="guest_ai", role="viewer")
    project = fixtures.create_project(db, name="AI Journal Project",
                                      pm_name="pm_ai")
    return {"admin": admin, "pm": pm, "viewer": viewer, "project": project}


def run(world, db, http):
    project_id = world["project"].id
    args = {"project_id": project_id, "entry_text": ENTRY_TEXT,
            "entry_type": "general"}

    world["pre_journal_count"] = actions.snapshot_table_count(
        db, "project_journal_entries", where={"project_id": project_id})
    world["pre_change_count"] = actions.snapshot_table_count(
        db, "project_changes", where={"project_id": project_id})

    # 1. PM unconfirmed — must return confirmation_required, no write.
    world["unconfirmed_result"] = actions.ai_dispatch(
        db, "create_journal_entry", args, world["pm"], confirmed=False,
    )
    world["after_unconfirmed_journal_count"] = actions.snapshot_table_count(
        db, "project_journal_entries", where={"project_id": project_id})

    # 2. Viewer attempt — must be forbidden, no write.
    world["viewer_result"] = actions.ai_dispatch(
        db, "create_journal_entry", args, world["viewer"], confirmed=False,
    )
    world["after_viewer_journal_count"] = actions.snapshot_table_count(
        db, "project_journal_entries", where={"project_id": project_id})

    # 3. PM confirmed — must succeed; entry + project_changes audit row.
    world["confirmed_result"] = actions.ai_dispatch(
        db, "create_journal_entry", args, world["pm"], confirmed=True,
    )


def check(db, world):
    project_id = world["project"].id

    # Unconfirmed path
    assertions.assert_dispatch_required_confirmation(
        world["unconfirmed_result"], "create_journal_entry",
        label="PM unconfirmed dispatch returns confirmation_required",
    )
    assertions.assert_equal(
        world["after_unconfirmed_journal_count"], world["pre_journal_count"],
        label="unconfirmed dispatch did NOT write a journal row",
    )

    # Viewer path
    assertions.assert_dispatch_blocked(
        world["viewer_result"], "forbidden",
        label="viewer dispatch is forbidden",
    )
    assertions.assert_equal(
        world["after_viewer_journal_count"], world["pre_journal_count"],
        label="viewer dispatch did NOT write a journal row",
    )

    # Confirmed path
    assertions.assert_dispatch_succeeded(
        world["confirmed_result"],
        label="PM confirmed dispatch succeeded",
    )
    assertions.assert_row_count(
        db, "project_journal_entries", expected=1,
        where={"project_id": project_id},
        label="exactly one journal entry was written",
    )
    assertions.assert_history_contains(
        db, project_id, ENTRY_SNIPPET,
        label="project_changes records the journal entry snippet",
    )
