"""Golden scenario — malformed: missing WHY_IT_MATTERS.

The runner must reject this BEFORE executing setup/run, with exit code 2
and a config-error message naming the missing metadata field.
"""

ID = "golden_missing_metadata_001"
TITLE = "Scenario missing WHY_IT_MATTERS — runner must reject"
TAGS = ["golden"]
MATURITY = "stable"
# WHY_IT_MATTERS is intentionally missing.


def setup(db):
    return {}


def run(world, db, http):
    return None


def check(db, world):
    return None
