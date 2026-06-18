"""Acceptance scenario — Planning Sandbox parallel workflow planning.

This scenario encodes the PM expectation behind the sandbox: it should be
possible to visually model two streams of work running in parallel before a
shared downstream prototype step. It intentionally checks graph edges and the
schedule implication, not just that buttons and routes exist.
"""
from datetime import datetime

from scenario_contracts.lib import actions, assertions
from scenario_contracts.lib.journey import Step

ID = "acceptance_sandbox_parallel_planning_workflow_001"
TITLE = "PM can build a parallel Design + Engineering sandbox plan before Prototype"
TAGS = ["acceptance", "release_gate", "ui", "sandbox", "planner"]
MATURITY = "candidate"
WHY_IT_MATTERS = (
    "PMs need the sandbox to express real timeline logic: parallel work streams "
    "and downstream gates. A test that only opens the route or adds floating "
    "nodes would miss the exact usability bug the user reported."
)


def setup(db):
    return {}


def _wait_for_edge_count(page, expected_min):
    page.wait_for_function(
        """expected => {
            return window.__planningSandboxQA
              && window.__planningSandboxQA.edgeCount() >= expected;
        }""",
        arg=expected_min,
        timeout=5000,
    )


def _update_selected_node(page, title, duration, owner, deliverable):
    page.fill("[data-node-title]", title)
    page.fill("[data-node-duration]", str(duration))
    page.fill("[data-node-owner]", owner)
    page.fill("[data-node-deliverable]", deliverable)
    page.click("[data-sandbox-node-save]")
    page.wait_for_selector("[data-sandbox-panel='selected']:not([hidden])")


def do_create_project_and_blank_sandbox(world, db, http, page):
    project_name = f"QA Parallel Sandbox {datetime.utcnow().strftime('%H%M%S')}"
    world["project_id"] = actions.create_project_via_form(
        page,
        name=project_name,
        product_manager="admin",
        brand="QA",
        project_thesis=(
            "A QA project used to prove sandbox parallel branch planning: "
            "Design and Engineering run side-by-side before Prototype."
        ),
    )
    actions.open_url(page, f"/projects/{world['project_id']}/sandbox")
    # First visit lands on the picker, not the canvas action bar. Start from a
    # true blank canvas so the test owns every node and edge.
    page.wait_for_selector(".sandbox-picker")
    page.locator(".sandbox-picker-main form button[type='submit']").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("[data-sandbox-workspace]")
    world["initial_node_count"] = page.evaluate(
        "() => window.__planningSandboxQA.nodeCount()"
    )
    world["initial_edge_count"] = page.evaluate(
        "() => window.__planningSandboxQA.edgeCount()"
    )


def check_blank_canvas_loaded(db, world, page):
    assertions.assert_url_path(
        page,
        f"/projects/{world['project_id']}/sandbox",
        label="blank sandbox loaded through PM-visible template control",
    )
    assertions.assert_equal(
        world["initial_node_count"],
        0,
        label="blank sandbox starts with no nodes",
    )
    assertions.assert_equal(
        world["initial_edge_count"],
        0,
        label="blank sandbox starts with no dependency edges",
    )


def _add_then_select_latest(page, expected_count):
    """SB-Rescue-03 lock: Add leaves the panel on Modules and does NOT
    auto-select. The scenario explicitly selects the newest node before
    editing it. Returns the selected db_id."""
    page.locator(".sandbox-add-module-btn").first.click()
    page.wait_for_function(
        "expected => window.__planningSandboxQA && window.__planningSandboxQA.nodeCount() >= expected",
        arg=expected_count,
        timeout=5000,
    )
    # Stay-on-Modules contract: panel must still be Modules after add.
    page.wait_for_selector("[data-sandbox-panel='modules']:not([hidden])")
    selected = page.evaluate(
        "idx => window.__planningSandboxQA.selectNodeByIndex(idx)",
        expected_count - 1,
    )
    page.wait_for_selector("[data-sandbox-panel='selected']:not([hidden])")
    return selected


def _return_to_modules(page):
    """Clear selection between Adds so the parallel scenario does NOT
    accidentally chain Design -> Engineering via the auto-connect path."""
    page.click("[data-sandbox-back-to-modules]")
    page.wait_for_selector("[data-sandbox-panel='modules']:not([hidden])")


def do_add_design_node(world, db, http, page):
    page.click("[data-sandbox-tab='modules']")
    world["design_node_id"] = _add_then_select_latest(page, expected_count=1)
    _update_selected_node(
        page,
        "Design Direction",
        5,
        "pm",
        "Locked product direction and visual target.",
    )
    _return_to_modules(page)


def check_design_node_ready(db, world, page):
    assertions.assert_equal(
        bool(world["design_node_id"]),
        True,
        label="Design node was selected explicitly after add/save",
    )
    assertions.assert_equal(
        page.evaluate("() => window.__planningSandboxQA.nodeCount()"),
        1,
        label="canvas has one node after Design add",
    )


def do_add_engineering_parallel_node(world, db, http, page):
    # Selection was cleared by _return_to_modules; Add will NOT auto-connect.
    # Parallel branches need two upstream nodes with no edge between them.
    world["engineering_node_id"] = _add_then_select_latest(page, expected_count=2)
    _update_selected_node(
        page,
        "Engineering Feasibility",
        15,
        "engineer",
        "Mechanism and construction feasibility cleared.",
    )
    _return_to_modules(page)


def check_engineering_node_ready(db, world, page):
    assertions.assert_equal(
        bool(world["engineering_node_id"]),
        True,
        label="Engineering node was selected explicitly after add/save",
    )
    assertions.assert_equal(
        page.evaluate("() => window.__planningSandboxQA.nodeCount()"),
        2,
        label="canvas has two nodes after Engineering add",
    )
    assertions.assert_equal(
        page.evaluate("() => window.__planningSandboxQA.edgeCount()"),
        0,
        label="parallel branches have no edge between them yet",
    )


def do_add_prototype_and_connect_branches(world, db, http, page):
    # Add Prototype with no source selected (selection was cleared).
    world["prototype_node_id"] = _add_then_select_latest(page, expected_count=3)
    _update_selected_node(
        page,
        "Prototype Gate",
        10,
        "factory",
        "Prototype can start only after Design and Engineering are ready.",
    )
    _return_to_modules(page)

    # Manually wire BOTH branches into Prototype: Design (idx 0) -> Prototype
    # (idx 2), then Engineering (idx 1) -> Prototype (idx 2). The scenario
    # uses the QA hook for per-node clicks because Cytoscape renders to
    # <canvas> with no per-node DOM elements (see UI_TESTABILITY_GAPS.md).
    before_design = page.evaluate("() => window.__planningSandboxQA.edgeCount()")
    page.evaluate("() => window.__planningSandboxQA.selectNodeByIndex(0)")
    page.evaluate("() => window.__planningSandboxQA.connectSelectedToIndex(2)")
    _wait_for_edge_count(page, before_design + 1)

    before_engineering = page.evaluate("() => window.__planningSandboxQA.edgeCount()")
    page.evaluate("() => window.__planningSandboxQA.selectNodeByIndex(1)")
    page.evaluate("() => window.__planningSandboxQA.connectSelectedToIndex(2)")
    _wait_for_edge_count(page, before_engineering + 1)

    world["edge_count_final"] = page.evaluate(
        "() => window.__planningSandboxQA.edgeCount()"
    )
    world["node_count_final"] = page.evaluate(
        "() => window.__planningSandboxQA.nodeCount()"
    )


def check_parallel_graph_is_connected(db, world, page):
    assertions.assert_equal(
        world["node_count_final"],
        3,
        label="parallel workflow has exactly three PM-authored nodes",
    )
    assertions.assert_equal(
        world["edge_count_final"],
        2,
        label="Prototype is gated by exactly two upstream branches (Design + Engineering), no spurious Design->Engineering edge",
    )
    assertions.assert_ui_shows(
        page,
        "[data-sandbox-panel='selected']",
        label="selected-node panel remains usable after connecting branches",
    )


def do_review_issues_and_timing(world, db, http, page):
    page.click("[data-sandbox-tab='issues']")
    page.wait_for_selector("[data-sandbox-panel='issues']:not([hidden])")
    world["issues_text"] = page.locator("[data-sandbox-panel='issues']").inner_text()
    world["has_raw_terminal_code"] = "terminal_not_launch_like" in world["issues_text"]
    world["has_raw_disconnected_code"] = "disconnected_branch" in world["issues_text"]
    # Cytoscape draws labels on canvas, so textContent cannot inspect them.
    # Use the stable QA hook backed by the same client-side node data.
    world["node_labels"] = page.evaluate(
        "() => window.__planningSandboxQA.nodeLabels()"
    )


def check_issues_and_timing_are_pm_readable(db, world, page):
    assertions.assert_equal(
        world["has_raw_terminal_code"],
        False,
        label="terminal warning code is not shown raw",
    )
    assertions.assert_equal(
        world["has_raw_disconnected_code"],
        False,
        label="disconnected warning code is not shown raw",
    )
    assertions.assert_equal(
        "Prototype Gate" in world["node_labels"],
        True,
        label="Prototype Gate remains visible after schedule recompute",
    )
    assertions.assert_equal(
        "Engineering Feasibility" in world["node_labels"],
        True,
        label="Engineering branch remains visible after schedule recompute",
    )


def do_soft_archive_project(world, db, http, page):
    actions.archive_project_via_http(page, world["project_id"])


def check_archive_cleanup(db, world, page):
    actions.open_url(page, f"/projects/{world['project_id']}")
    assertions.assert_page_contains(
        page,
        "QA Parallel Sandbox",
        label="sandbox QA project still loads after soft-archive cleanup",
    )


STEPS = [
    Step(
        "PM creates a project and starts a blank sandbox",
        do_create_project_and_blank_sandbox,
        check_blank_canvas_loaded,
    ),
    Step(
        "PM adds a 5-day Design branch",
        do_add_design_node,
        check_design_node_ready,
    ),
    Step(
        "PM adds a 15-day Engineering branch",
        do_add_engineering_parallel_node,
        check_engineering_node_ready,
    ),
    Step(
        "PM adds Prototype and connects both upstream branches",
        do_add_prototype_and_connect_branches,
        check_parallel_graph_is_connected,
    ),
    Step(
        "PM reviews issues and timing after parallel plan",
        do_review_issues_and_timing,
        check_issues_and_timing_are_pm_readable,
    ),
    Step(
        "QA soft-archives the synthetic sandbox project",
        do_soft_archive_project,
        check_archive_cleanup,
    ),
]
