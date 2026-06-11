"""PM actions callable from scenario run() functions.

User lock 9: run() may only call actions.*; no direct route/DB mutation.

QA-01 ships service-layer actions only. QA-03 adds HTTP/Playwright variants.
"""
from __future__ import annotations

from datetime import date


def adjust_due_date(db, phase_id, new_end_date, reason, changed_by="user"):
    """Adjust a phase's planned_end_date via the real service helper.

    Writes phase_plan_changes + project_changes rows just like the live
    Timeline Command Center action.
    """
    from app import crud

    return crud.update_phase(
        db,
        phase_id=phase_id,
        data={"planned_end_date": new_end_date},
        changed_by=changed_by,
        reason=reason,
    )


def record_event_note(db, project_id, summary, changed_by="user"):
    """Write a plain event_note row via crud.write_change()."""
    from app import crud

    change = crud.write_change(
        db,
        project_id=project_id,
        change_type="event_note",
        changed_by=changed_by,
        summary=summary,
    )
    db.commit()
    return change


def create_project_for_pm(db, name, pm_username, **fields):
    """Create a project owned by the given PM via the real service helper.

    Returns the created Project. The product_manager field is filled with
    the PM's username so get_projects_for_user matches.
    """
    from app import crud

    data = {
        "name": name,
        "product_manager": pm_username,
        "status": "active",
    }
    data.update(fields)
    return crud.create_project(db, data)


def create_variant(db, project_id, variant_name, **fields):
    """Create a project variant via the real service helper."""
    from app import crud

    data = {"variant_name": variant_name}
    data.update(fields)
    return crud.create_variant(db, project_id, data)


def create_sandbox_from_template(db, project_id, template_key, user_id, user_role="pm"):
    """Create a draft sandbox for a project from a seeded template."""
    from app import crud

    return crud.create_sandbox_from_template(
        db, project_id, template_key, user_id, user_role,
    )


def apply_sandbox(db, project_id, sandbox_id, apply_start_date, user_id,
                  update_launch_date=False):
    """Explicitly apply a draft sandbox to the live project plan."""
    from app import crud

    if isinstance(apply_start_date, str):
        apply_start_date = date.fromisoformat(apply_start_date)
    return crud.apply_sandbox_to_project(
        db,
        project_id=project_id,
        sandbox_id=sandbox_id,
        apply_start_date=apply_start_date,
        update_launch_date=update_launch_date,
        user_id=user_id,
    )


def finish_phase(db, phase_id, changed_by="user", user_id=None):
    """Mark a phase done; auto-advance the next phase to in_progress."""
    from app import crud

    return crud.finish_phase(
        db, phase_id=phase_id,
        changed_by=changed_by, changed_by_user_id=user_id,
    )


def create_blocker(db, project_id, title, description=None, severity="medium",
                   phase_id=None, user_id=None, changed_by="user"):
    """Open a project blocker via the real service helper."""
    from app import crud

    return crud.create_blocker(
        db, project_id=project_id, title=title, description=description,
        severity=severity, phase_id=phase_id,
        created_by_user_id=user_id, changed_by=changed_by,
    )


def resolve_blocker(db, blocker_id, user_id=None, changed_by="user"):
    """Resolve a blocker via the real service helper."""
    from app import crud

    return crud.resolve_blocker(
        db, blocker_id=blocker_id,
        resolved_by_user_id=user_id, changed_by=changed_by,
    )


def create_journal_entry(db, project_id, entry_text, entry_type="general",
                         user_id=None, changed_by="user"):
    """Add a project journal entry via the real service helper."""
    from app import crud

    return crud.create_journal_entry(
        db, project_id=project_id, entry_text=entry_text,
        entry_type=entry_type, author_user_id=user_id, changed_by=changed_by,
    )


def delete_project(db, project_id):
    """Hard-delete a project via the real service helper.

    Wraps crud.delete_project, which explicitly cleans
    ai_conversations + project_creation_tokens before the ORM cascade
    to avoid the Marine-bug FK violation under FK enforcement.
    """
    from app import crud

    return crud.delete_project(db, project_id)


def create_project_with_idempotency(db, data, token, user_id,
                                    prototype_rounds="single"):
    """Atomic token-claim + project insert (Build 30A)."""
    from app import crud

    return crud.create_project_with_idempotency(
        db, data, prototype_rounds, token, user_id,
    )


def mint_creation_token(db, user_id):
    """Mint a single-use idempotency token for a user."""
    from app import crud

    return crud.mint_creation_token(db, user_id)


def update_blocker(db, blocker_id, data, user_id=None, changed_by="user"):
    """Update an existing project blocker via the real service helper.

    The crud.update_blocker function enforces an allowlist on the
    fields it accepts; non-allowlisted keys are silently ignored.
    """
    from app import crud

    return crud.update_blocker(
        db, blocker_id=blocker_id, data=data,
        changed_by=changed_by, changed_by_user_id=user_id,
    )


def ai_dispatch(db, tool_name, args, user, confirmed=False):
    """Invoke the real AI tool dispatcher.

    Returns the dispatch result dict (shape: `{"ok": True, ...}` on
    success, `{"ok": False, "error": "<code>", ...}` on failure). This
    is the canonical entry point the HTTP route also uses, so we are
    testing the actual service-layer contract.
    """
    from app.ai.tools import dispatch

    return dispatch(tool_name, args, db, user, confirmed=confirmed)


def snapshot_field(db, table_name, where, field):
    """Read-only snapshot of one field on one row for use inside run().

    Returns the raw value. Dates are returned as ISO strings to match
    how assert_db_field normalizes them.
    """
    from datetime import date as _date
    from sqlalchemy import text

    clause = " AND ".join(f"{c} = :{c}" for c in where)
    sql = f"SELECT {field} FROM {table_name} WHERE {clause} LIMIT 1"
    row = db.execute(text(sql), where).fetchone()
    if row is None:
        return None
    value = row[0]
    if isinstance(value, _date):
        return value.isoformat()
    return value


def snapshot_table_count(db, table_name, where=None):
    """Read-only COUNT snapshot for use inside run().

    Keeps the discipline boundary: any DB interaction inside run() routes
    through actions.* even when it's a read. Result is typically stashed
    into `world` so check() can assert against it.
    """
    from sqlalchemy import text

    sql = f"SELECT COUNT(*) FROM {table_name}"
    params = {}
    if where:
        clause = " AND ".join(f"{c} = :{c}" for c in where)
        sql += f" WHERE {clause}"
        params = where
    return db.execute(text(sql), params).scalar()


# ── Browser actions (QA-03) ────────────────────────────────────────────
#
# These take a Playwright `page` object — passed to UI-tagged scenarios
# by the runner via signature inspection. DB-only scenarios never see
# these; UI scenarios call them inside run().


def open_url(page, path):
    """Navigate the browser to base_url + path; wait for network idle."""
    from scenario_contracts.lib.browser import base_url

    if path.startswith("http://") or path.startswith("https://"):
        target = path
    else:
        if not path.startswith("/"):
            path = "/" + path
        target = base_url() + path
    page.goto(target)
    page.wait_for_load_state("networkidle")


def click(page, selector):
    """Click an element selected by CSS selector."""
    page.click(selector)
    page.wait_for_load_state("networkidle")


def fill_input(page, selector, value):
    """Fill an input element by CSS selector."""
    page.fill(selector, value)


def wait_for_load(page):
    """Wait for the network to go idle."""
    page.wait_for_load_state("networkidle")


def discover_first_project_id(page):
    """Discover any project id from the /projects index for read-only smoke.

    Returns the integer id or None if no project link is found.
    """
    import re

    open_url(page, "/projects")
    html = page.content()
    match = re.search(r'href="/projects/(\d+)"', html)
    return int(match.group(1)) if match else None


def ensure_sandbox_exists(page, project_id, template_key="simple_oem_knife"):
    """Navigate to the sandbox page; if no draft exists, create one from
    the given system template by submitting the picker form.

    Idempotent: re-runs against a project that already has a draft just
    navigate to the canvas view and return.
    """
    open_url(page, f"/projects/{project_id}/sandbox")
    # If picker is visible, no draft exists yet — create from template.
    if page.locator(".sandbox-picker").count() > 0:
        # Pick the specific template-card form whose hidden input
        # matches `template_key`. The picker also renders a
        # "start blank" form (no template_key input) which we skip.
        forms = page.locator(
            f"form[action='/projects/{project_id}/sandbox/create']"
        )
        target_form = None
        for i in range(forms.count()):
            f = forms.nth(i)
            hidden_inputs = f.locator("input[name='template_key']")
            if hidden_inputs.count() == 0:
                continue  # this is the "start blank" form; skip
            hidden_value = hidden_inputs.first.input_value()
            if hidden_value == template_key:
                target_form = f
                break
        if target_form is None:
            # No matching template — fall back to the first form that
            # HAS a template_key input (any system template).
            for i in range(forms.count()):
                f = forms.nth(i)
                if f.locator("input[name='template_key']").count() > 0:
                    target_form = f
                    break
        if target_form is None:
            raise RuntimeError(
                "no usable picker form found for project "
                f"{project_id}; expected a system template form"
            )
        target_form.locator("button[type='submit']").first.click()
        page.wait_for_load_state("networkidle")


def click_add_first_module(page):
    """Click the first `.sandbox-add-module-btn`.

    Triggers the JS `addModule()` function which POSTs to the
    `/sandbox/{sid}/nodes/add` route and refreshes the canvas via
    `refreshFromPayload`.
    """
    button = page.locator(".sandbox-add-module-btn").first
    button.click()


def read_sandbox_node_count(page):
    """Read the current sandbox node count from the DOM.

    Reads `[data-sandbox-node-count]` which the JS updates after every
    sandbox mutation via `updateSummary()`. Returns an int.
    """
    text = page.locator("[data-sandbox-node-count]").first.text_content()
    if text is None:
        return None
    text = text.strip()
    try:
        return int(text)
    except ValueError:
        return None


def wait_for_node_count(page, expected, timeout_ms=5000):
    """Wait until `[data-sandbox-node-count]` equals `expected`.

    Used after click_add_first_module to wait for the JS-driven
    canvas refresh to complete.
    """
    page.wait_for_function(
        """({selector, expected}) => {
            const el = document.querySelector(selector);
            if (!el) return false;
            return el.textContent.trim() === String(expected);
        }""",
        arg={"selector": "[data-sandbox-node-count]", "expected": expected},
        timeout=timeout_ms,
    )
