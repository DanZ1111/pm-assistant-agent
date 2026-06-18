"""v1.4 Planning Sandbox UI rescue regression.

This test intentionally avoids localhost sockets; Playwright acceptance still
covers the live browser path when local network access is available.
Run: python3 test_v14_sandbox_ui_rescue.py
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = Path(__file__).resolve().parent
PASS, FAIL = [], []


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, reason):
    FAIL.append((name, reason))
    print(f"  ✗  {name}: {reason}")


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def contains_all(label, text_value, needles):
    missing = [needle for needle in needles if needle not in text_value]
    if missing:
        fail(label, f"missing {missing}")
    else:
        ok(label)


def test_source_locks():
    template = read("app/templates/planning_sandbox.html")
    js = read("app/static/js/planning_sandbox.js")
    css = read("app/static/css/styles.css")
    routes = read("app/routes/projects.py")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))

    contains_all(
        "Sandbox IA zones and stable hooks exist",
        template,
        [
            "data-sandbox-action-bar",
            "data-sandbox-right-panel",
            "data-sandbox-tab=\"modules\"",
            "data-sandbox-tab=\"selected\"",
            "data-sandbox-tab=\"issues\"",
            "data-sandbox-back-to-modules",
            "data-sandbox-connect-from",
            "data-sandbox-module-search",
            "data-sandbox-module-filter",
            "data-sandbox-apply-button",
            "data-sandbox-warning-chip",
            "data-sandbox-fit",
            "data-sandbox-reset-view",
            "data-sandbox-zoom",
        ],
    )
    contains_all(
        "Canvas rescue JS preserves graph instead of rebuilding on refresh",
        js,
        [
            "function applyElementDiff",
            "cy.add(el)",
            "ele.remove()",
            "existing.data(el.data || {})",
            "userZoomingEnabled: false",
            "dataset.sandboxZoom",
            "connectSourceNodeId",
            "created_node_id",
            "endpoint('/edges')",
            "setConnectSource",
            "__planningSandboxQA",
            "selectFirstNode",
            "duration_bin",
        ],
    )
    if "function refreshFromPayload" in js and "renderCanvas();" not in js:
        ok("Refresh path no longer calls destructive renderCanvas()")
    else:
        fail("Refresh path", "refresh still appears to call renderCanvas")
    contains_all(
        "PM module filtering and warning copy live route-side",
        routes,
        [
            "_SANDBOX_ADVANCED_MODULE_KEYS",
            "blade_steel_validation",
            "handle_material_validation",
            "_SANDBOX_WARNING_COPY_KEYS",
            "replace_existing=True",
            '"created_node_id": node.id',
            "sandbox.warning_missing_owner",
            "sandbox_warning_copy_json",
        ],
    )
    contains_all(
        "Sandbox rescue CSS styles the planner zones",
        css,
        [
            ".sandbox-action-bar",
            ".sandbox-planner-grid",
            ".sandbox-panel-tabs",
            ".sandbox-filter-chip",
            ".sandbox-issue-card",
            ".sandbox-module-card-main",
            ".sandbox-property-actions .is-connecting",
        ],
    )
    required_keys = [
        "sandbox.choose_template",
        "sandbox.draft_autosaves",
        "sandbox.tab_modules",
        "sandbox.tab_selected",
        "sandbox.tab_issues",
        "sandbox.search_modules",
        "sandbox.filter_advanced",
        "sandbox.back_to_modules",
        "sandbox.connect_from_node",
        "sandbox.connect_ready",
        "sandbox.connect_saved",
        "sandbox.connect_error",
        "sandbox.warning_missing_owner",
        "sandbox.warning_terminal_not_launch_like",
    ]
    missing = [key for key in required_keys if key not in en or key not in zh]
    if not missing and set(en) == set(zh):
        ok(f"i18n parity preserved with rescue keys ({len(en)}/{len(zh)})")
    else:
        fail("i18n parity/rescue keys", f"missing={missing} diff={sorted(set(en) ^ set(zh))[:8]}")


def test_route_smoke():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import SessionLocal
    from app.models import PlanningSandbox, Project
    import app.crud as crud

    client = TestClient(app)
    db = SessionLocal()
    project = None
    try:
        project = Project(
            name="v14 sandbox rescue smoke",
            status="active",
            product_manager="admin",
            project_thesis=(
                "Route smoke project for the sandbox rescue layout and warning copy render path."
            ),
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        crud.create_sandbox_from_template(db, project.id, "simple_oem_knife", None, "admin")

        login = client.post(
            "/auth/login",
            data={"username": "admin", "password": "show me the money"},
            follow_redirects=False,
        )
        if login.status_code not in (302, 303):
            fail("TestClient login", f"status {login.status_code}")
            return
        response = client.get(f"/projects/{project.id}/sandbox", cookies=login.cookies)
        html = response.text
        if response.status_code == 200 and all(
            needle in html
            for needle in [
                "data-sandbox-workspace",
                "data-sandbox-action-bar",
                "data-sandbox-panel=\"modules\"",
                "data-sandbox-panel=\"issues\"",
                "data-warning-copy",
                "data-module-advanced=\"true\"",
            ]
        ):
            ok("In-process sandbox route renders rescued workspace")
        else:
            fail("In-process sandbox route", f"status={response.status_code}")

        before = (
            db.query(PlanningSandbox)
            .filter(PlanningSandbox.project_id == project.id, PlanningSandbox.status == "draft")
            .first()
        )
        before_key = before.base_template_key if before else None
        before_node_count = len(before.nodes) if before else None
        reset = client.post(
            f"/projects/{project.id}/sandbox/create",
            data={"template_key": "standard_folding_knife"},
            cookies=login.cookies,
            follow_redirects=False,
        )
        db.expire_all()
        after = (
            db.query(PlanningSandbox)
            .filter(PlanningSandbox.project_id == project.id, PlanningSandbox.status == "draft")
            .first()
        )
        if (
            reset.status_code in (302, 303)
            and after
            and before_key != "standard_folding_knife"
            and after.base_template_key == "standard_folding_knife"
            and len(after.nodes) != before_node_count
            and len(after.nodes) > 0
            and len(after.edges) > 0
        ):
            ok("Template picker route replaces the current draft with the chosen template graph")
        else:
            fail(
                "Template picker reset",
                {
                    "status": reset.status_code,
                    "before_key": before_key,
                    "before_node_count": before_node_count,
                    "after_id": after.id if after else None,
                    "base_template_key": after.base_template_key if after else None,
                    "nodes": len(after.nodes) if after else None,
                    "edges": len(after.edges) if after else None,
                },
            )
    finally:
        if project is not None:
            db.delete(project)
            db.commit()
        db.close()


def test_sb_rescue_03_stay_on_modules_lock():
    """SB-Rescue-03 lock: Add Module must leave the panel on the Modules
    tab and must NOT auto-select the newly-created node. This lock exists
    because the QA-12 session previously drifted from the SB-Rescue-03
    plan by switching the JS to `selectNode(createdNodeId)` after add,
    which made the QA-12 scenario shorter but broke the user-facing
    workflow. See CLAUDE.md "Spec Drift Gate" for the full case study.
    """
    import re

    js = read("app/static/js/planning_sandbox.js")
    match = re.search(
        r"function addModule\([^)]*\)\s*\{(.+?)\n  \}",
        js,
        re.DOTALL,
    )
    if not match:
        fail("addModule body extractable", "could not locate addModule function")
        return
    body = match.group(1)
    if "setActiveTab('modules')" in body:
        ok("addModule body calls setActiveTab('modules') after add (SB-Rescue-03 lock)")
    else:
        fail(
            "SB-Rescue-03 lock: addModule must end on Modules tab",
            "missing setActiveTab('modules') in addModule body",
        )
    if "selectNode(createdNodeId)" in body:
        fail(
            "SB-Rescue-03 lock: addModule must NOT auto-select created node",
            "selectNode(createdNodeId) present in addModule body — drift re-introduced",
        )
    else:
        ok("addModule body does not auto-select created node (no SB-Rescue-03 drift)")


def main():
    print("\n── 1. Source locks ──")
    test_source_locks()
    print("\n── 2. In-process route smoke ──")
    test_route_smoke()
    print("\n── 3. SB-Rescue-03 stay-on-Modules lock ──")
    test_sb_rescue_03_stay_on_modules_lock()
    print("\n── Summary ──")
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    return not FAIL


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
