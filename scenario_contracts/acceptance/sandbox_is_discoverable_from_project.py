"""Acceptance scenario — Planning Sandbox is REACHABLE via UI navigation.

The bug class this catches:

    The /projects/{id}/sandbox route works and the page renders. But
    there's no `<a href="/projects/{id}/sandbox">` anywhere in the
    project detail page (or anywhere a PM would naturally browse to).
    Result: a PM cannot find the feature, even though
    `ui_sandbox_canvas_smoke` and `ui_sandbox_add_module` both pass
    (they jump to the URL directly).

This is the navigation-vs-route discoverability gap. Every URL-driven
UI scenario is blind to it. The fix is to test what real PMs do:
land on the project page, look for an entry point to the sandbox,
follow it.

If this scenario fails today, the bug is confirmed: the sandbox is
unreachable through normal UI navigation. If it passes, either the
template has been patched OR the discovery selector was too loose.
"""
from scenario_contracts.lib import actions, assertions
from scenario_contracts.lib.journey import Step

ID = "acceptance_sandbox_discoverable_from_project_001"
TITLE = "PM can reach Planning Sandbox via a visible link on the project detail page"
TAGS = ["acceptance", "release_gate", "navigation", "sandbox", "discoverability"]
MATURITY = "candidate"
WHY_IT_MATTERS = (
    "A feature with a working route but no UI link is invisible to PMs. "
    "Existing UI scenarios pass because they jump straight to the URL, "
    "bypassing the discoverability question entirely. This scenario tests "
    "the PM workflow: land on /projects/{id}, look for a sandbox link, "
    "follow it. Without this, the entire Planning Sandbox feature can "
    "ship dead and no QA scenario will catch it."
)


def setup(db):
    return {}


# ── Step 1: PM lands on a project detail page (the natural entry) ──────


def do_open_project(world, db, http, page):
    pid = actions.discover_first_project_id(page)
    world["project_id"] = pid
    if pid is None:
        return
    actions.open_url(page, f"/projects/{pid}")


def check_after_open_project(db, world, page):
    assertions.assert_equal(
        world["project_id"] is not None, True,
        label="dev DB has at least one project to navigate from",
    )
    # Sanity: we're actually on the project detail page.
    assertions.assert_url_path(
        page, f"/projects/{world['project_id']}",
        label="page settled on /projects/{id}",
    )


# ── Step 2: PM looks for a navigation link to the sandbox ──────────────


def do_search_for_sandbox_link(world, db, http, page):
    # Read the page HTML once and stash whether any link points to the
    # sandbox for THIS project. We accept ANY href that contains
    # `/projects/{id}/sandbox` so a future implementation can use a
    # button-form-link, a tab link, or anything else.
    pid = world["project_id"]
    html = page.content()
    needle = f"/projects/{pid}/sandbox"
    world["sandbox_link_present"] = needle in html
    # Also count anchor elements matching the href explicitly — the
    # most natural PM-clickable affordance. Includes elements with
    # `data-href`-style JS handlers if any.
    world["sandbox_anchor_count"] = page.locator(
        f'a[href*="/projects/{pid}/sandbox"]'
    ).count()


def check_sandbox_link_present(db, world, page):
    # The load-bearing assertion: there must be at least one anchor or
    # equivalent click target leading to /projects/{id}/sandbox.
    #
    # If this fails, the bug is confirmed: the Planning Sandbox is
    # unreachable via normal UI navigation. Per the Codex domain
    # boundary, the fix lives in app/templates (a new nav link), and
    # this scenario is the regression-guard that prevents the same
    # gap from coming back.
    assertions.assert_equal(
        world["sandbox_anchor_count"] >= 1, True,
        label=(
            "project detail page has at least one <a href=*/sandbox> link "
            "(PMs need a clickable entry point to the Planning Sandbox)"
        ),
    )


# ── Step 3: PM clicks the link and the sandbox page loads ──────────────


def do_click_sandbox_link(world, db, http, page):
    pid = world["project_id"]
    # Skip if step 2 already established the link is missing — failing
    # there is enough; clicking a non-existent link would just hang.
    if world.get("sandbox_anchor_count", 0) < 1:
        return
    page.locator(f'a[href*="/projects/{pid}/sandbox"]').first.click()
    page.wait_for_load_state("networkidle")


def check_after_click(db, world, page):
    if world.get("sandbox_anchor_count", 0) < 1:
        # Step 2 already failed; nothing to verify here.
        return
    pid = world["project_id"]
    # URL settled at /projects/{id}/sandbox.
    assertions.assert_url_path(
        page, f"/projects/{pid}/sandbox",
        label="clicking the sandbox link lands on /projects/{id}/sandbox",
    )
    # And the sandbox shell renders (same check as ui_sandbox_canvas_smoke).
    assertions.assert_ui_shows(
        page, ".sandbox-shell",
        label="sandbox shell renders after PM clicks the link",
    )


STEPS = [
    Step("PM lands on a project detail page (the natural entry point)",
         do_open_project, check_after_open_project),
    Step("PM looks for a visible link to the Planning Sandbox",
         do_search_for_sandbox_link, check_sandbox_link_present),
    Step("PM clicks the link and the sandbox loads",
         do_click_sandbox_link, check_after_click),
]
