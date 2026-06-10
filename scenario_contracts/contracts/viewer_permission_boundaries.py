"""Release-gate scenario — viewer permission boundaries.

A user with role="viewer" must not be able to:
  - edit any project (`can_edit_project` → False),
  - see costs (`can_view_costs` → False),
  - see journal (`can_view_journal` → False),
  - see factory / engineer / supplier (`can_view_sensitive_fields` → False).

These four checks form the contract for the viewer role. They are static
permission helpers in `app.dependencies`; this scenario asserts each one.
"""
from scenario_contracts.lib import assertions, fixtures

ID = "viewer_permission_boundaries_001"
TITLE = "Viewer cannot edit projects or see costs, journal, or factory data"
TAGS = ["release_gate", "deterministic", "permissions"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "The viewer role exists so partners and stakeholders can see public "
    "project status without supply-chain or financial exposure. Any "
    "regression in these four checks leaks sensitive data to external "
    "viewers — a release-blocking class of bug."
)


def setup(db):
    admin = fixtures.create_user(db, username="root", role="admin")
    pm = fixtures.create_user(db, username="alice", role="pm",
                              display_name="Alice")
    viewer = fixtures.create_user(db, username="guest", role="viewer",
                                  display_name="Guest")
    project = fixtures.create_project(db, name="Confidential Project",
                                      pm_name="alice")
    return {"admin": admin, "pm": pm, "viewer": viewer, "project": project}


def run(world, db, http):
    # No state change — the contract is about static permission helpers.
    # The scenario shape still requires run() to be defined.
    return None


def check(db, world):
    viewer = world["viewer"]
    pm = world["pm"]
    admin = world["admin"]
    project = world["project"]

    # Viewer is denied on all four permissions.
    assertions.assert_permission(
        viewer, "can_edit_project", expected=False, project=project,
        label="viewer cannot edit project",
    )
    assertions.assert_permission(
        viewer, "can_view_costs", expected=False,
        label="viewer cannot view costs",
    )
    assertions.assert_permission(
        viewer, "can_view_journal", expected=False,
        label="viewer cannot view journal",
    )
    assertions.assert_permission(
        viewer, "can_view_sensitive_fields", expected=False,
        label="viewer cannot view factory/engineer fields",
    )

    # Sanity: PM and admin DO have these permissions.
    assertions.assert_permission(
        pm, "can_view_costs", expected=True,
        label="pm can view costs (sanity)",
    )
    assertions.assert_permission(
        admin, "can_edit_project", expected=True, project=project,
        label="admin can edit any project (sanity)",
    )

    # Viewer's My Projects list is empty regardless of project ownership.
    assertions.assert_project_not_visible_to_user(
        db, viewer, project.id,
        label="viewer sees no projects in My Projects",
    )
