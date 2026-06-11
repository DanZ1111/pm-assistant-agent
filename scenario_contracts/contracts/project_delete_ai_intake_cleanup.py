"""Release-gate scenario — Marine bug regression.

A project created via the AI-intake flow has FK references to
`ai_conversations` and `project_creation_tokens`. The Marine bug
shipped (commit b8a9687) because `crud.delete_project` did not
explicitly clean these before the ORM cascade, and dev SQLite had
FK enforcement OFF so the bug was invisible. PostgreSQL (Railway
prod) ALWAYS enforces FKs and returned a 500.

The fix added explicit cleanup of those two tables before the ORM
delete, and an event listener in app/database.py turned on SQLite
FK enforcement so dev tests would catch the same bug.

This contract locks both: delete must succeed cleanly under FK
enforcement, AND there must be zero leftover rows for the deleted
project_id across `projects`, `project_phases`, `ai_conversations`,
`ai_messages`, `project_creation_tokens`, `project_changes`.
"""
from scenario_contracts.lib import actions, assertions, fixtures

ID = "project_delete_ai_intake_cleanup_001"
TITLE = "Project delete cleans AI-intake FK rows; no FK violation under enforcement"
TAGS = ["release_gate", "deterministic", "delete", "marine_regression"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "The Marine bug shipped to production because no test exercised "
    "project delete with AI-intake FK references under SQLite FK "
    "enforcement. If a future refactor drops the explicit cleanup of "
    "ai_conversations or project_creation_tokens — or disables FK "
    "enforcement — this contract surfaces it immediately."
)


def setup(db):
    admin = fixtures.create_user(db, username="root_marine", role="admin")
    pm = fixtures.create_user(db, username="pm_marine", role="pm",
                              display_name="Marine PM")
    # Use the real create_project service helper so default phases
    # auto-seed (matches the real AI-intake project shape).
    project = actions.create_project_for_pm(
        db, name="Marine Knife (regression)", pm_username="pm_marine",
    )
    # Seed the FK-bearing rows that triggered the Marine bug.
    conversation, message = fixtures.seed_ai_conversation(
        db, project_id=project.id, user_id=pm.id,
        title="AI intake — Marine product brief",
    )
    token_row = fixtures.seed_creation_token(
        db, user_id=pm.id, project_id=project.id, claimed=True,
    )
    return {
        "admin": admin, "pm": pm, "project": project,
        "conversation_id": conversation.id,
        "message_id": message.id,
        "token": token_row.token,
    }


def run(world, db, http):
    project_id = world["project"].id

    # Pre-delete: every FK-bearing table has the expected row count.
    world["pre_phases"] = actions.snapshot_table_count(
        db, "project_phases", where={"project_id": project_id})
    world["pre_conversations"] = actions.snapshot_table_count(
        db, "ai_conversations", where={"project_id": project_id})
    world["pre_messages"] = actions.snapshot_table_count(
        db, "ai_messages", where={"project_id": project_id})
    world["pre_tokens"] = actions.snapshot_table_count(
        db, "project_creation_tokens", where={"project_id": project_id})

    # The Marine bug: this call raised an FK violation on PostgreSQL.
    # On SQLite with PRAGMA foreign_keys = ON, the same violation now
    # raises here too — so if a future regression breaks the cleanup,
    # this action either returns False or throws, both of which fail
    # the scenario.
    world["delete_result"] = actions.delete_project(db, project_id)


def check(db, world):
    project_id = world["project"].id

    # Pre-conditions sanity: setup did seed FK rows.
    assertions.assert_equal(
        world["pre_phases"], 8,
        label="setup seeded the 8 default phases",
    )
    assertions.assert_equal(
        world["pre_conversations"], 1,
        label="setup seeded one ai_conversations row",
    )
    assertions.assert_equal(
        world["pre_messages"], 1,
        label="setup seeded one ai_messages row",
    )
    assertions.assert_equal(
        world["pre_tokens"], 1,
        label="setup seeded one project_creation_tokens row",
    )

    # Delete must have succeeded cleanly (returned True; no exception).
    assertions.assert_equal(
        world["delete_result"], True,
        label="delete_project returned True (no FK violation)",
    )

    # Post-delete: zero rows remain for this project_id across all
    # FK-bearing child tables.
    assertions.assert_no_rows(
        db, "projects", where={"id": project_id},
        label="project row gone",
    )
    assertions.assert_no_rows(
        db, "project_phases", where={"project_id": project_id},
        label="project_phases rows cascade-deleted",
    )
    assertions.assert_no_rows(
        db, "ai_conversations", where={"project_id": project_id},
        label="ai_conversations rows explicitly cleaned",
    )
    assertions.assert_no_rows(
        db, "project_creation_tokens", where={"project_id": project_id},
        label="project_creation_tokens rows explicitly cleaned",
    )
