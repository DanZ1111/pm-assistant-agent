"""Acceptance scenario — Planning Sandbox template and connection workflow.

This catches the bug class where the sandbox route renders, but real PM
interactions do not work: choosing a template appears to do nothing, selected
nodes show stale "no node selected" copy, and newly added modules float without
any obvious dependency connection.
"""
from datetime import datetime

from scenario_contracts.lib import actions, assertions
from scenario_contracts.lib.journey import Step

ID = "acceptance_sandbox_template_connection_workflow_001"
TITLE = "PM can switch templates, select a node, and create connected workflow steps"
TAGS = ["acceptance", "release_gate", "ui", "sandbox", "planner"]
MATURITY = "candidate"
WHY_IT_MATTERS = (
    "The sandbox is only valuable if PMs can use a template and visually build "
    "a connected workflow. Route-level tests are not enough because they miss "
    "dropdown behavior, selected-node state, and canvas edge creation."
)


def setup(db):
    return {}


def do_create_project_and_open_sandbox(world, db, http, page):
    name = f"QA Sandbox Template {datetime.utcnow().strftime('%H%M%S')}"
    project_id = actions.create_project_via_form(
        page,
        name=name,
        product_manager="admin",
        brand="QA",
        project_thesis=(
            "A compact QA project used to verify Planning Sandbox template "
            "replacement and visual connection workflow."
        ),
    )
    world["project_id"] = project_id
    actions.ensure_sandbox_exists(page, project_id, template_key="simple_oem_knife")
    page.wait_for_selector("[data-sandbox-workspace]")


def check_initial_sandbox(db, world, page):
    assertions.assert_url_path(
        page,
        f"/projects/{world['project_id']}/sandbox",
        label="sandbox route loaded for template workflow QA",
    )
    assertions.assert_ui_shows(page, "[data-sandbox-template-trigger]", label="template picker visible")
    assertions.assert_ui_shows(page, "[data-sandbox-panel='modules']", label="modules panel visible")


def do_toggle_template_menu_and_apply_template(world, db, http, page):
    page.click("[data-sandbox-template-trigger]")
    world["menu_open_after_first_click"] = page.locator("[data-sandbox-template-trigger]").evaluate(
        "el => el.closest('details').open"
    )
    page.click("[data-sandbox-template-trigger]")
    world["menu_open_after_second_click"] = page.locator("[data-sandbox-template-trigger]").evaluate(
        "el => el.closest('details').open"
    )
    page.click("[data-sandbox-template-trigger]")
    page.locator('form.sandbox-template-row:has(input[value="standard_folding_knife"]) button').click()
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("[data-sandbox-workspace]")
    world["template_node_count"] = page.evaluate("() => window.__planningSandboxQA.nodeCount()")
    world["template_edge_count"] = page.evaluate("() => window.__planningSandboxQA.edgeCount()")


def check_template_loaded(db, world, page):
    assertions.assert_equal(
        world["menu_open_after_first_click"],
        True,
        label="Choose Template opens on first click",
    )
    assertions.assert_equal(
        world["menu_open_after_second_click"],
        False,
        label="Choose Template closes on second click",
    )
    assertions.assert_equal(
        world["template_node_count"] >= 4,
        True,
        label="chosen template loads multiple canvas nodes",
    )
    assertions.assert_equal(
        world["template_edge_count"] >= 1,
        True,
        label="chosen template loads visible dependency edges",
    )


def do_select_node_and_add_connected_module(world, db, http, page):
    world["selected_node_id"] = page.evaluate(
        "() => window.__planningSandboxQA.selectNodeByIndex(0)"
    )
    page.wait_for_selector("[data-sandbox-panel='selected']:not([hidden])")
    world["no_node_visible_after_select"] = page.locator("[data-no-node]").is_visible()
    world["selected_title"] = page.locator("[data-node-title]").input_value()
    world["edge_count_before_add"] = page.evaluate("() => window.__planningSandboxQA.edgeCount()")
    page.click("[data-sandbox-tab='modules']")
    page.locator(".sandbox-add-module-btn").first.click()
    page.wait_for_function(
        """oldCount => {
            return window.__planningSandboxQA && window.__planningSandboxQA.edgeCount() > oldCount;
        }""",
        arg=world["edge_count_before_add"],
        timeout=5000,
    )
    world["edge_count_after_add"] = page.evaluate("() => window.__planningSandboxQA.edgeCount()")
    world["node_count_after_add"] = page.evaluate("() => window.__planningSandboxQA.nodeCount()")


def check_node_selection_and_connection(db, world, page):
    assertions.assert_equal(
        world["selected_node_id"] is not None,
        True,
        label="QA hook selected a real canvas node",
    )
    assertions.assert_equal(
        world["no_node_visible_after_select"],
        False,
        label="selected node panel does not show 'No node selected'",
    )
    assertions.assert_equal(
        bool(world["selected_title"]),
        True,
        label="selected node form is populated",
    )
    assertions.assert_equal(
        world["edge_count_after_add"] > world["edge_count_before_add"],
        True,
        label="adding a module after a selected node creates a dependency arrow",
    )
    assertions.assert_equal(
        world["node_count_after_add"] > world["template_node_count"],
        True,
        label="new module is added to the canvas",
    )


STEPS = [
    Step("PM creates a project and opens a sandbox draft",
         do_create_project_and_open_sandbox, check_initial_sandbox),
    Step("PM toggles template menu and applies a different template",
         do_toggle_template_menu_and_apply_template, check_template_loaded),
    Step("PM selects a node and adds a connected module",
         do_select_node_and_add_connected_module, check_node_selection_and_connection),
]
