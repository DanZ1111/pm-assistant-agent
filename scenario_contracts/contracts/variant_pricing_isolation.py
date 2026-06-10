"""Release-gate scenario — variant pricing stays variant-level.

Creating a variant with its own target_factory_cost / target_msrp must not
mutate the parent project's target_factory_cost / target_msrp.

If this breaks, variant pricing leaks back onto the project row and the PM
loses the ability to compare variants against the project's original
targets. Build 16 introduced variants specifically to avoid this leak.
"""
from scenario_contracts.lib import actions, assertions, fixtures

ID = "variant_pricing_isolation_001"
TITLE = "Variant costs do not mutate project-level cost fields"
TAGS = ["release_gate", "deterministic", "variants"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "Project costs are leadership/launch targets. Variant costs are the "
    "per-SKU reality. Mixing them lets a single variant's price discovery "
    "silently rewrite the project's intent and destroy the PM's ability "
    "to compare against the original plan."
)

PROJECT_TARGET_FACTORY_COST = 12.50
PROJECT_TARGET_MSRP = 49.99
VARIANT_TARGET_FACTORY_COST = 18.00
VARIANT_TARGET_MSRP = 59.99


def setup(db):
    pm = fixtures.create_user(db, username="pm_v", role="pm",
                              display_name="PM-V")
    project = fixtures.create_project_with_costs(
        db, name="Marine Knife Mk1", pm_name="pm_v",
        target_factory_cost=PROJECT_TARGET_FACTORY_COST,
        target_msrp=PROJECT_TARGET_MSRP,
    )
    return {"pm": pm, "project": project}


def run(world, db, http):
    variant = actions.create_variant(
        db, world["project"].id, variant_name="Mk1 Gift Pack",
        target_factory_cost=VARIANT_TARGET_FACTORY_COST,
        target_msrp=VARIANT_TARGET_MSRP,
    )
    world["variant_id"] = variant.id


def check(db, world):
    project_id = world["project"].id
    variant_id = world["variant_id"]

    # Variant carries its own (different) cost values.
    assertions.assert_db_field(
        db, "project_variants", where={"id": variant_id},
        field="target_factory_cost", expected=VARIANT_TARGET_FACTORY_COST,
        label="variant target_factory_cost set to variant value",
    )
    assertions.assert_db_field(
        db, "project_variants", where={"id": variant_id},
        field="target_msrp", expected=VARIANT_TARGET_MSRP,
        label="variant target_msrp set to variant value",
    )

    # Project's cost fields are UNCHANGED — variant did not leak upward.
    assertions.assert_db_field(
        db, "projects", where={"id": project_id},
        field="target_factory_cost", expected=PROJECT_TARGET_FACTORY_COST,
        label="project target_factory_cost unchanged by variant create",
    )
    assertions.assert_db_field(
        db, "projects", where={"id": project_id},
        field="target_msrp", expected=PROJECT_TARGET_MSRP,
        label="project target_msrp unchanged by variant create",
    )

    # One audit row should exist: the variant-created event_note.
    assertions.assert_row_count(
        db, "project_changes", expected=1,
        where={"project_id": project_id},
        label="variant create produced exactly one change-log row",
    )
