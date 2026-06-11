"""Release-gate UI scenario — clicking the palette Add button creates a node.

This is the single most common PM action in the v1.4 Planning Sandbox
UI (Codex Timeline planner). Clicking `.sandbox-add-module-btn`
triggers the JS `addModule()` function which POSTs to
`/projects/{pid}/sandbox/{sid}/nodes/add`. The route handler calls
`crud.create_sandbox_node_from_module` and returns a fresh sandbox
payload; the JS then refreshes the canvas + summary.

The scenario verifies the end-to-end loop: button click → HTTP POST
→ DB write → JSON response → DOM update of `[data-sandbox-node-count]`.

If a regression breaks ANY link in that chain — JS click binding,
route handler, service helper, sandbox payload renderer, or summary
update — the node count after click will not match the predicted
value and this scenario fails.
"""
from scenario_contracts.lib import actions, assertions

ID = "ui_sandbox_add_module_001"
TITLE = "Clicking the palette Add button creates a sandbox node and updates the canvas"
TAGS = ["ui", "release_gate", "deterministic", "sandbox", "mutation"]
MATURITY = "candidate"
WHY_IT_MATTERS = (
    "Adding a module from the palette is the single most common PM "
    "action in the v1.4 Planning Sandbox UI. If this end-to-end loop "
    "breaks — JS handler, HTTP route, service helper, payload "
    "renderer, or summary update — the sandbox is unusable. This "
    "scenario locks the entire chain in one click."
)


def setup(db):
    # UI scenarios run against the live dev server; the in-memory db
    # is unused but the runner still provides it for uniformity.
    return {}


def run(world, db, http, page):
    # Discover a project to work with.
    project_id = actions.discover_first_project_id(page)
    world["project_id"] = project_id
    if project_id is None:
        return

    # Make sure the project has a draft sandbox; create one if not.
    actions.ensure_sandbox_exists(
        page, project_id=project_id,
        template_key="simple_oem_knife",
    )

    # Snapshot the canvas node count BEFORE the add.
    world["pre_count"] = actions.read_sandbox_node_count(page)

    # Click the first palette Add button.
    actions.click_add_first_module(page)

    # Wait for the JS-driven refresh to complete (node count goes up).
    if world["pre_count"] is not None:
        actions.wait_for_node_count(
            page, expected=world["pre_count"] + 1, timeout_ms=5000,
        )

    # Capture the post-click count for the assertion.
    world["post_count"] = actions.read_sandbox_node_count(page)


def check(db, world, page):
    # The scenario requires at least one project in the dev DB.
    assertions.assert_equal(
        world["project_id"] is not None, True,
        label="dev DB has at least one project for the smoke",
    )

    # Pre-state was readable (sandbox page rendered correctly).
    assertions.assert_equal(
        world["pre_count"] is not None, True,
        label="pre-click sandbox node count was readable",
    )

    # The Add button must be visible (sanity — sandbox is editable).
    assertions.assert_ui_shows(
        page, ".sandbox-add-module-btn",
        label="palette Add button is present in the DOM",
    )

    # The summary reflects the new node count.
    assertions.assert_canvas_node_count_equals(
        page, expected=world["pre_count"] + 1,
        label="canvas node count incremented by 1 after Add click",
    )

    # Post-snapshot also matches (paranoia: confirms our capture
    # logic matched the rendered DOM).
    assertions.assert_equal(
        world["post_count"], world["pre_count"] + 1,
        label="post-click snapshot matches expected count",
    )
