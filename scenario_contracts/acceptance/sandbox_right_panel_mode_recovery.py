"""Acceptance scenario — Planning Sandbox side-panel recovery and canvas stability.

This catches the sandbox usability bug class where a PM selects/edits a node,
loses the module library, and the canvas jumps after saving. It also verifies
that warnings render as human-readable PM copy instead of raw codes.
"""
from datetime import datetime

from scenario_contracts.lib import actions, assertions
from scenario_contracts.lib.journey import Step

ID = "acceptance_sandbox_right_panel_mode_recovery_001"
TITLE = "PM can edit a sandbox node, keep canvas position, return to modules, and read issues"
TAGS = ["acceptance", "release_gate", "ui", "sandbox", "planner"]
MATURITY = "candidate"
WHY_IT_MATTERS = (
    "The Planning Sandbox is only useful if a PM can move between adding "
    "modules, editing a selected node, and reviewing issues without losing "
    "their place. This scenario guards the specific regression where node "
    "editing hides the module library and save refreshes refit the canvas."
)


def setup(db):
    return {}


def do_create_project_and_sandbox(world, db, http, page):
    name = f"QA Sandbox Recovery {datetime.utcnow().strftime('%H%M%S')}"
    project_id = actions.create_project_via_form(
        page,
        name=name,
        product_manager="admin",
        brand="QA",
        project_thesis=(
            "A compact QA project used to verify planning sandbox mode "
            "recovery, warning copy, and viewport stability for PM workflows."
        ),
    )
    world["project_id"] = project_id
    actions.ensure_sandbox_exists(page, project_id, template_key="simple_oem_knife")
    page.wait_for_selector("[data-sandbox-workspace]")


def check_initial_workspace(db, world, page):
    assertions.assert_url_path(
        page,
        f"/projects/{world['project_id']}/sandbox",
        label="sandbox route loaded for new QA project",
    )
    assertions.assert_ui_shows(page, "[data-sandbox-action-bar]", label="action bar visible")
    assertions.assert_ui_shows(page, "[data-sandbox-right-panel]", label="right panel visible")
    assertions.assert_ui_shows(page, "[data-sandbox-panel='modules']", label="modules panel visible")
    assertions.assert_ui_shows(page, "[data-sandbox-module-search]", label="module search visible")


def do_select_node_and_save_warning(world, db, http, page):
    selected = page.evaluate("() => window.__planningSandboxQA && window.__planningSandboxQA.selectFirstNode()")
    world["selected_node_id"] = selected
    page.wait_for_selector("[data-sandbox-panel='selected']:not([hidden])")
    world["viewport_before"] = page.locator("[data-sandbox-workspace]").first.evaluate(
        """el => ({
            zoom: el.dataset.sandboxZoom,
            panX: el.dataset.sandboxPanX,
            panY: el.dataset.sandboxPanY
        })"""
    )
    page.fill("[data-node-title]", "QA Concept Check")
    page.fill("[data-node-owner]", "")
    page.click("[data-sandbox-node-save]")
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-sandbox-workspace]');
            return el && el.dataset.sandboxSelectedNodeId;
        }""",
        timeout=5000,
    )
    world["viewport_after"] = page.locator("[data-sandbox-workspace]").first.evaluate(
        """el => ({
            zoom: el.dataset.sandboxZoom,
            panX: el.dataset.sandboxPanX,
            panY: el.dataset.sandboxPanY,
            selectedNodeId: el.dataset.sandboxSelectedNodeId
        })"""
    )


def check_save_keeps_context(db, world, page):
    assertions.assert_equal(
        world["selected_node_id"] is not None,
        True,
        label="QA hook selected a sandbox node",
    )
    assertions.assert_equal(
        {
            "zoom": world["viewport_after"]["zoom"],
            "panX": world["viewport_after"]["panX"],
            "panY": world["viewport_after"]["panY"],
        },
        world["viewport_before"],
        label="saving a node preserves canvas zoom and pan",
    )
    assertions.assert_equal(
        world["viewport_after"]["selectedNodeId"],
        str(world["selected_node_id"]),
        label="selected node remains selected after save",
    )
    assertions.assert_ui_shows(page, "[data-sandbox-panel='selected']", label="selected panel remains visible")


def do_back_to_modules(world, db, http, page):
    page.click("[data-sandbox-back-to-modules]")
    page.wait_for_selector("[data-sandbox-panel='modules']:not([hidden])")


def check_modules_recovered(db, world, page):
    assertions.assert_ui_shows(page, "[data-sandbox-panel='modules']", label="Back to Modules restores library")
    assertions.assert_ui_does_not_show(page, "[data-sandbox-panel='selected']:not([hidden])", label="selected panel hidden after back")
    assertions.assert_ui_shows(page, ".sandbox-add-module-btn", label="add module affordance visible again")


def do_open_issues(world, db, http, page):
    page.click("[data-sandbox-tab='issues']")
    page.wait_for_selector("[data-sandbox-panel='issues']:not([hidden])")
    world["issues_inner_text"] = page.locator("[data-sandbox-panel='issues']").inner_text()
    world["issue_message"] = page.locator("[data-sandbox-issue-message]").first.inner_text()


def check_issues_are_human(db, world, page):
    assertions.assert_equal(
        "Some steps do not have an owner." in world["issue_message"],
        True,
        label="missing_owner renders as human-readable warning",
    )
    assertions.assert_equal(
        "missing_owner" in world["issues_inner_text"],
        False,
        label="raw warning code is not visible in Issues panel",
    )


STEPS = [
    Step("PM creates a project and opens a sandbox draft",
         do_create_project_and_sandbox, check_initial_workspace),
    Step("PM selects a node and saves an edit without canvas refit",
         do_select_node_and_save_warning, check_save_keeps_context),
    Step("PM returns from Selected Node to Modules",
         do_back_to_modules, check_modules_recovered),
    Step("PM reviews human-readable Issues",
         do_open_issues, check_issues_are_human),
]
