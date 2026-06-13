"""Golden scenario — malformed: missing check().

The runner must reject this BEFORE executing setup/run, with exit code 2
and a config-error message naming the missing function.
"""

ID = "golden_invalid_shape_001"
TITLE = "Scenario missing check() — runner must reject as config error"
TAGS = ["golden"]
MATURITY = "candidate"
WHY_IT_MATTERS = (
    "If the runner silently runs scenarios that are missing required "
    "functions, malformed scenarios can pass by doing nothing. The runner "
    "must reject them with a clean config-error exit code (2)."
)


def setup(db):
    return {}


def run(world, db, http):
    return None


# check() is intentionally missing.
