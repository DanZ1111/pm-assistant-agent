"""Release-gate scenario — project create idempotency.

Build 30A introduced atomic token-claim + project insert to prevent
double-creation when a user double-clicks Submit. The contract:

  1. PM mints a creation token via `mint_creation_token`.
  2. First create_project_with_idempotency call → IdempotencyResult
     with status="created" and a real project row.
  3. Second call with the SAME token → IdempotencyResult with
     status="duplicate" and project_id pointing at the original
     project. Exactly one project row exists.
  4. Call with an empty / wrong token → IdempotencyResult with
     status="invalid". No new project row.
"""
from scenario_contracts.lib import actions, assertions, fixtures

ID = "project_create_idempotency_001"
TITLE = "Idempotent project create: first POST creates; duplicate POST returns the same project_id"
TAGS = ["release_gate", "deterministic", "create", "idempotency"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "Without idempotency, a slow POST + impatient user produces "
    "duplicate projects with the same data — confusing for PMs and "
    "breaking the My Projects scope. Build 30A's atomic UPDATE-rowcount "
    "claim is the contract; if a future refactor swaps it for a "
    "non-atomic check-then-claim, this scenario catches the race."
)


def setup(db):
    admin = fixtures.create_user(db, username="root_idem", role="admin")
    pm = fixtures.create_user(db, username="pm_idem", role="pm",
                              display_name="PM-Idem")
    return {"admin": admin, "pm": pm}


def run(world, db, http):
    pm = world["pm"]
    data = {"name": "Idempotent Project", "product_manager": "pm_idem",
            "status": "active"}

    # 1. Mint a token.
    token = actions.mint_creation_token(db, pm.id)
    world["token"] = token

    # 2. First create_project_with_idempotency call.
    world["first_result"] = actions.create_project_with_idempotency(
        db, data=data, token=token, user_id=pm.id,
    )
    world["after_first_project_count"] = actions.snapshot_table_count(
        db, "projects")

    # 3. Second create call with the SAME token.
    world["second_result"] = actions.create_project_with_idempotency(
        db, data=data, token=token, user_id=pm.id,
    )
    world["after_second_project_count"] = actions.snapshot_table_count(
        db, "projects")

    # 4. Call with empty token.
    world["invalid_result"] = actions.create_project_with_idempotency(
        db, data=data, token="", user_id=pm.id,
    )
    world["after_invalid_project_count"] = actions.snapshot_table_count(
        db, "projects")


def check(db, world):
    # 1. First result is "created" with a real project id.
    first = world["first_result"]
    assertions.assert_equal(
        first.status, "created",
        label="first POST returns IdempotencyResult.status == 'created'",
    )
    assertions.assert_equal(
        first.project is not None, True,
        label="first POST returns a Project on the result",
    )
    assertions.assert_equal(
        world["after_first_project_count"], 1,
        label="exactly 1 project row exists after first POST",
    )

    # 2. Second result with the same token is "duplicate" pointing at
    # the original project_id. No new row inserted.
    second = world["second_result"]
    assertions.assert_equal(
        second.status, "duplicate",
        label="repeat POST with same token returns 'duplicate'",
    )
    assertions.assert_equal(
        second.project_id, first.project.id,
        label="duplicate result.project_id matches the original project",
    )
    assertions.assert_equal(
        world["after_second_project_count"], 1,
        label="still 1 project row after duplicate POST (no insert)",
    )

    # 3. Invalid token result is "invalid"; no project inserted.
    invalid = world["invalid_result"]
    assertions.assert_equal(
        invalid.status, "invalid",
        label="empty-token POST returns 'invalid'",
    )
    assertions.assert_equal(
        world["after_invalid_project_count"], 1,
        label="still 1 project row after invalid POST (no insert)",
    )
