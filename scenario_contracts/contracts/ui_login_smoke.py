"""UI smoke — admin can log in and the projects index renders.

This proves the QA-03 browser path works end-to-end against a live dev
server. If this scenario fails, every other UI scenario is suspect.
"""
from scenario_contracts.lib import actions, assertions

ID = "ui_login_smoke_001"
TITLE = "Admin login lands on /projects with a real project listing"
TAGS = ["ui", "deterministic", "smoke", "release_gate"]
MATURITY = "stable"
WHY_IT_MATTERS = (
    "The most basic browser flow: log in, see your projects list. If this "
    "smoke fails, no UI scenario can be trusted — login or template "
    "rendering is broken at a fundamental level."
)


def setup(db):
    return {}


def run(world, db, http, page):
    # BrowserContext already logged in as admin. Navigate to projects.
    actions.open_url(page, "/projects")


def check(db, world, page):
    # We're on /projects (not redirected back to login).
    assertions.assert_url_path(page, "/projects",
                               label="admin lands on /projects after login")

    # The page rendered at least one project row (admin sees all).
    # The "/projects/<id>" anchor is the load-bearing element of the
    # rendered index page.
    assertions.assert_page_contains(
        page, 'href="/projects/',
        label="projects index renders at least one project link",
    )
