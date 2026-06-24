"""Acceptance scenario — Planning Sandbox PM usability basics.

This scenario encodes the specific usability failures the user reported:
template controls that feel stuck, templates that appear to do nothing, nodes
that float without a connection path, selected-node state that contradicts the
canvas, and raw/blocking warning UI.
"""
from datetime import datetime

from scenario_contracts.lib import actions, assertions
from scenario_contracts.lib.journey import Step
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

ID = "acceptance_sandbox_usability_001"
TITLE = "PM can operate the sandbox basics without losing orientation"
TAGS = ["acceptance", "release_gate", "ui", "sandbox", "planner", "qa_agent_1_1"]
MATURITY = "candidate"
WHY_IT_MATTERS = (
    "The Planning Sandbox can pass route and data tests while still being "
    "unusable to a PM. This journey guards the visible behaviors a PM needs: "
    "discovering the sandbox, choosing templates, seeing graph changes, "
    "connecting steps, recovering the module library, and reading warnings."
)


def setup(db):
    return {}


def _menu_open(page, selector):
    return page.locator(selector).evaluate("el => el.closest('details').open")


def _wait_for_canvas(page):
    page.wait_for_selector("[data-sandbox-workspace]", timeout=8000)
    try:
        page.wait_for_function(
            "() => window.__planningSandboxQA && window.__planningSandboxQA.nodeCount",
            timeout=8000,
        )
    except PlaywrightTimeoutError as exc:
        has_cytoscape = page.evaluate("() => typeof window.cytoscape !== 'undefined'")
        script_count = page.locator('script[src*="planning_sandbox.js"]').count()
        raise AssertionError(
            "Sandbox workspace rendered but planning_sandbox.js did not initialize "
            f"(cytoscape_loaded={has_cytoscape}, local_script_tags={script_count})."
        ) from exc


def do_create_project_and_enter_sandbox_by_click(world, db, http, page):
    name = f"QA Sandbox Usability {datetime.utcnow().strftime('%H%M%S')}"
    world["project_id"] = actions.create_project_via_form(
        page,
        name=name,
        product_manager="admin",
        brand="QA",
        project_thesis=(
            "A QA project used to prove Planning Sandbox usability checks "
            "follow the PM-visible path instead of bypassing the UI."
        ),
    )
    page.wait_for_selector("a[data-project-sandbox-link]:visible", timeout=8000)
    page.locator("a[data-project-sandbox-link]").first.click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_selector(".sandbox-picker")
    form = page.locator(
        f"form[action='/projects/{world['project_id']}/sandbox/create']:has(input[value='simple_oem_knife'])"
    ).first
    form.locator("button[type='submit']").click()
    page.wait_for_load_state("domcontentloaded")
    _wait_for_canvas(page)
    world["initial_nodes"] = page.evaluate("() => window.__planningSandboxQA.nodeCount()")
    world["initial_edges"] = page.evaluate("() => window.__planningSandboxQA.edgeCount()")


def check_sandbox_discovered_and_template_started(db, world, page):
    assertions.assert_url_path(
        page,
        f"/projects/{world['project_id']}/sandbox",
        label="PM clicked from project detail into sandbox",
    )
    assertions.assert_equal(
        world["initial_nodes"] > 0,
        True,
        label="starting from a template renders canvas nodes",
    )
    assertions.assert_ui_shows(page, "[data-sandbox-action-bar]", label="sandbox action bar visible")
    assertions.assert_ui_shows(page, "[data-sandbox-right-panel]", label="sandbox right panel visible")


def do_exercise_template_controls(world, db, http, page):
    trigger = "[data-sandbox-template-trigger]"
    page.click(trigger)
    world["template_open_first"] = _menu_open(page, trigger)
    page.click(trigger)
    world["template_open_second"] = _menu_open(page, trigger)
    page.click(trigger)
    page.locator("[data-sandbox-right-panel]").click(position={"x": 8, "y": 8})
    world["template_open_after_outside"] = _menu_open(page, trigger)
    page.click(trigger)
    page.keyboard.press("Escape")
    world["template_open_after_escape"] = _menu_open(page, trigger)
    page.click(trigger)
    page.locator('form.sandbox-template-row:has(input[value="standard_folding_knife"]) button').click()
    page.wait_for_load_state("domcontentloaded")
    _wait_for_canvas(page)
    world["template_nodes"] = page.evaluate("() => window.__planningSandboxQA.nodeCount()")
    world["template_edges"] = page.evaluate("() => window.__planningSandboxQA.edgeCount()")
    world["template_labels"] = page.evaluate("() => window.__planningSandboxQA.nodeLabels()")


def check_template_controls_are_usable(db, world, page):
    assertions.assert_equal(world["template_open_first"], True, label="template chooser opens")
    assertions.assert_equal(world["template_open_second"], False, label="template chooser toggles closed")
    assertions.assert_equal(world["template_open_after_outside"], False, label="outside click closes template chooser")
    assertions.assert_equal(world["template_open_after_escape"], False, label="Escape closes template chooser")
    assertions.assert_equal(
        world["template_nodes"] >= 4,
        True,
        label="template replacement loads a multi-step graph",
    )
    assertions.assert_equal(
        world["template_edges"] >= 1,
        True,
        label="template replacement loads dependency arrows",
    )
    assertions.assert_equal(
        bool(world["template_labels"]),
        True,
        label="template graph exposes node labels to QA",
    )


def do_check_module_library_filtering(world, db, http, page):
    page.click("[data-sandbox-tab='modules']")
    page.wait_for_selector("[data-sandbox-panel='modules']:not([hidden])")
    world["search_visible"] = page.locator("[data-sandbox-module-search]").is_visible()
    world["default_visible_cards"] = page.locator(
        "[data-sandbox-module-card]:not([hidden])"
    ).count()
    world["advanced_visible_by_default"] = page.locator(
        "[data-sandbox-module-card][data-module-advanced='true']:not([hidden])"
    ).count()
    page.click("[data-sandbox-module-filter='advanced']")
    world["advanced_visible_after_filter"] = page.locator(
        "[data-sandbox-module-card][data-module-advanced='true']:not([hidden])"
    ).count()


def check_module_library_is_pm_browsable(db, world, page):
    assertions.assert_equal(world["search_visible"], True, label="module search is visible")
    assertions.assert_equal(
        world["default_visible_cards"] > 0,
        True,
        label="default module library has visible PM modules",
    )
    assertions.assert_equal(
        world["advanced_visible_by_default"],
        0,
        label="advanced granular modules are hidden from default library",
    )
    assertions.assert_equal(
        world["advanced_visible_after_filter"] > 0,
        True,
        label="advanced modules remain available through explicit filter",
    )


def do_select_connect_and_recover(world, db, http, page):
    world["selected_source"] = page.evaluate(
        "() => window.__planningSandboxQA.selectNodeByIndex(0)"
    )
    page.wait_for_selector("[data-sandbox-panel='selected']:not([hidden])")
    world["no_node_visible"] = page.locator("[data-no-node]").is_visible()
    world["selected_title"] = page.locator("[data-node-title]").input_value()
    page.click("[data-sandbox-back-to-modules]")
    page.wait_for_selector("[data-sandbox-panel='modules']:not([hidden])")
    world["add_buttons_after_back"] = page.locator(".sandbox-add-module-btn:visible").count()

    world["selected_source_again"] = page.evaluate(
        "() => window.__planningSandboxQA.selectNodeByIndex(0)"
    )
    page.wait_for_selector("[data-sandbox-panel='selected']:not([hidden])")
    world["edge_count_before"] = page.evaluate("() => window.__planningSandboxQA.edgeCount()")
    world["node_count_before_connected_add"] = page.evaluate("() => window.__planningSandboxQA.nodeCount()")
    page.click("[data-sandbox-connect-from]")
    world["connect_button_active"] = page.locator("[data-sandbox-connect-from]").evaluate(
        "el => el.classList.contains('is-connecting')"
    )
    page.click("[data-sandbox-tab='modules']")
    page.wait_for_selector("[data-sandbox-panel='modules']:not([hidden])")
    page.click("[data-sandbox-module-filter='default']")
    page.locator(".sandbox-add-module-btn").first.click()
    page.wait_for_function(
        "oldCount => window.__planningSandboxQA && window.__planningSandboxQA.edgeCount() > oldCount",
        arg=world["edge_count_before"],
        timeout=5000,
    )
    world["edge_count_after"] = page.evaluate("() => window.__planningSandboxQA.edgeCount()")
    world["node_count_after_connected_add"] = page.evaluate("() => window.__planningSandboxQA.nodeCount()")


def check_node_connection_and_recovery(db, world, page):
    assertions.assert_equal(world["selected_source"] is not None, True, label="canvas node selectable")
    assertions.assert_equal(world["selected_source_again"] is not None, True, label="canvas node can be reselected for connect flow")
    assertions.assert_equal(world["no_node_visible"], False, label="selected panel does not show no-node empty state")
    assertions.assert_equal(bool(world["selected_title"]), True, label="selected node form has title")
    assertions.assert_equal(world["connect_button_active"], True, label="visible Connect button enters connect mode")
    assertions.assert_equal(
        world["edge_count_after"] > world["edge_count_before"],
        True,
        label="connect workflow creates a dependency edge",
    )
    assertions.assert_equal(
        world["node_count_after_connected_add"] > world["node_count_before_connected_add"],
        True,
        label="connect workflow adds a fresh next step",
    )
    assertions.assert_equal(
        world["add_buttons_after_back"] > 0,
        True,
        label="Back to Modules restores add-module controls",
    )


def do_create_warning_and_review_issues(world, db, http, page):
    page.evaluate("() => window.__planningSandboxQA.selectNodeByIndex(0)")
    page.wait_for_selector("[data-sandbox-panel='selected']:not([hidden])")
    page.fill("[data-node-owner]", "")
    page.click("[data-sandbox-node-save]")
    page.wait_for_function(
        """() => {
            const strip = document.querySelector('[data-sandbox-warning-strip]');
            return strip && !strip.hidden;
        }""",
        timeout=5000,
    )
    world["warning_strip_in_action_bar"] = page.locator("[data-sandbox-warning-strip]").evaluate(
        "el => !!el.closest('[data-sandbox-action-bar]')"
    )
    world["warning_strip_text"] = page.locator("[data-sandbox-warning-strip]").inner_text()
    page.click("[data-sandbox-tab='issues']")
    page.wait_for_selector("[data-sandbox-panel='issues']:not([hidden])")
    world["issues_text"] = page.locator("[data-sandbox-panel='issues']").inner_text()
    world["issue_message"] = page.locator("[data-sandbox-issue-message]").first.inner_text()


def check_warnings_are_pm_readable(db, world, page):
    assertions.assert_equal(
        world["warning_strip_in_action_bar"],
        True,
        label="warning summary lives in action bar zone",
    )
    assertions.assert_equal(
        "missing_owner" in world["warning_strip_text"],
        False,
        label="warning strip hides raw warning code",
    )
    assertions.assert_equal(
        "missing_owner" in world["issues_text"],
        False,
        label="Issues panel hides raw warning code",
    )
    assertions.assert_equal(
        bool(world["issue_message"]),
        True,
        label="Issues panel shows human-readable warning message",
    )


STEPS = [
    Step(
        "PM enters sandbox from project detail and starts a template",
        do_create_project_and_enter_sandbox_by_click,
        check_sandbox_discovered_and_template_started,
    ),
    Step(
        "PM can open, close, and apply templates without the menu feeling stuck",
        do_exercise_template_controls,
        check_template_controls_are_usable,
    ),
    Step(
        "PM can search/filter modules without advanced checks dominating default view",
        do_check_module_library_filtering,
        check_module_library_is_pm_browsable,
    ),
    Step(
        "PM can select, connect, and recover back to Modules",
        do_select_connect_and_recover,
        check_node_connection_and_recovery,
    ),
    Step(
        "PM can read warnings without raw codes or canvas-blocking strips",
        do_create_warning_and_review_issues,
        check_warnings_are_pm_readable,
    ),
]
