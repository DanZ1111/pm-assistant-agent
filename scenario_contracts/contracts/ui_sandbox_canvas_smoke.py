"""UI smoke — Planning Sandbox page renders for an existing project.

This is the Codex Timeline planner / v1.4 Planning Sandbox UI smoke.
It proves /projects/{id}/sandbox is reachable end-to-end and that the
sandbox-shell renders (either the template picker for projects without
a sandbox, or the canvas + module palette for projects with one).

If this fails, every other sandbox UI scenario is suspect.
"""
from scenario_contracts.lib import actions, assertions

ID = "ui_sandbox_canvas_smoke_001"
TITLE = "Planning Sandbox page loads + shell renders"
TAGS = ["ui", "deterministic", "smoke", "sandbox", "release_gate"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "The v1.4 Planning Sandbox is the largest UI surface Codex added. "
    "If the page does not render, no PM can plan workflows visually. "
    "This smoke catches template/CSS/JS regressions that would otherwise "
    "ship silently because no per-build test renders the live page."
)


def setup(db):
    return {}


def run(world, db, http, page):
    # Discover any project from the dev DB; navigate to its sandbox.
    project_id = actions.discover_first_project_id(page)
    world["project_id"] = project_id
    if project_id is None:
        # Smoke can't continue without a project; runner will detect
        # the missing assertion target and FAIL with a clear reason.
        return
    actions.open_url(page, f"/projects/{project_id}/sandbox")


def check(db, world, page):
    project_id = world.get("project_id")
    # The smoke requires at least one project to exist in the dev DB.
    assertions.assert_equal(
        project_id is not None, True,
        label="dev DB has at least one project for the smoke to target",
    )

    # Whether the page shows the template picker (no sandbox yet) or the
    # canvas (sandbox exists), the outer .sandbox-shell always renders.
    assertions.assert_ui_shows(
        page, ".sandbox-shell",
        label="sandbox page shell renders",
    )

    # URL ends at the sandbox route (the route handler returned a 200,
    # not a redirect back to /login or somewhere else).
    assertions.assert_url_path(
        page, f"/projects/{project_id}/sandbox",
        label="page settled at /projects/{id}/sandbox",
    )
