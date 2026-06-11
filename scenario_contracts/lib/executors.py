"""Per-scenario execution branches: db / ui / journey.

Extracted from runner.py so the runner stays the small, scannable
CLI + validation entry point. Each executor returns the same result
dict shape: id / title / tags / maturity / outcome / detail.

Discipline: these executors do not import app.* directly; they go
through the shared library (actions.py, assertions.py, fixtures.py,
browser.py, journey.py).
"""
from __future__ import annotations

import inspect

from scenario_contracts.lib import fixtures
from scenario_contracts.lib.assertions import AssertionFailure


def call_with_optional_page(func, *args, page=None, **kwargs):
    """Call `func(*args, **kwargs)` plus `page=page` if the signature accepts it.

    Backward-compatible bridge for contract scenarios that don't declare
    a `page` parameter and UI scenarios that do.
    """
    sig = inspect.signature(func)
    if "page" in sig.parameters:
        kwargs["page"] = page
    return func(*args, **kwargs)


def execute_db_scenario(module, result):
    """In-memory DB only — no Playwright."""
    tmp = engine = Session = None
    try:
        tmp, engine, Session = fixtures.build_db()
        db = Session()
        try:
            world = module.setup(db)
            call_with_optional_page(module.run, world, db=db, http=None, page=None)
            call_with_optional_page(module.check, db, world, page=None)
        finally:
            db.close()
            engine.dispose()
        result["outcome"] = "pass"
        result["detail"] = ""
    except AssertionFailure as exc:
        result["outcome"] = "fail"
        result["detail"] = str(exc)
    except Exception as exc:  # noqa: BLE001
        result["outcome"] = "fail"
        result["detail"] = f"{type(exc).__name__}: {exc}"
    finally:
        if tmp is not None:
            tmp.cleanup()
    return result


def execute_journey_scenario(module, result):
    """Walk module.STEPS one at a time. Report failures with step name."""
    tmp = engine = Session = None
    try:
        tmp, engine, Session = fixtures.build_db()
        db = Session()
        try:
            world = module.setup(db)
            for i, step in enumerate(module.STEPS, 1):
                try:
                    step.do(world, db=db, http=None)
                except Exception as exc:  # noqa: BLE001
                    result["outcome"] = "fail"
                    result["detail"] = (
                        f"step {i} ({step.name}) do() raised: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    return result
                try:
                    step.check(db, world)
                except AssertionFailure as exc:
                    result["outcome"] = "fail"
                    result["detail"] = f"step {i} ({step.name}) check: {exc}"
                    return result
                except Exception as exc:  # noqa: BLE001
                    result["outcome"] = "fail"
                    result["detail"] = (
                        f"step {i} ({step.name}) check raised: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    return result
            result["outcome"] = "pass"
            result["detail"] = f"{len(module.STEPS)} steps OK"
        finally:
            db.close()
            engine.dispose()
    except Exception as exc:  # noqa: BLE001  — pre-step setup error
        result["outcome"] = "fail"
        result["detail"] = f"setup_error: {type(exc).__name__}: {exc}"
    finally:
        if tmp is not None:
            tmp.cleanup()
    return result


def execute_ui_scenario(module, result):
    """UI scenario — requires Playwright and a reachable dev server."""
    from scenario_contracts.lib import browser

    if not browser.is_playwright_available():
        result["outcome"] = "skip"
        result["detail"] = "playwright_not_installed"
        return result
    if not browser.is_dev_server_reachable():
        result["outcome"] = "skip"
        result["detail"] = f"dev_server_unreachable ({browser.base_url()})"
        return result

    tmp = engine = Session = None
    try:
        tmp, engine, Session = fixtures.build_db()
        db = Session()
        try:
            world = module.setup(db)
            with browser.BrowserContext(role="admin") as page:
                # Capture failures while the page is still alive so we
                # can drop a screenshot before BrowserContext.__exit__
                # closes the browser.
                try:
                    call_with_optional_page(
                        module.run, world, db=db, http=None, page=page)
                    call_with_optional_page(
                        module.check, db, world, page=page)
                except AssertionFailure as exc:
                    result["outcome"] = "fail"
                    result["detail"] = str(exc)
                    result["screenshot"] = browser.capture_failure_artifacts(
                        page, module.ID)
                except Exception as exc:  # noqa: BLE001
                    result["outcome"] = "fail"
                    result["detail"] = f"{type(exc).__name__}: {exc}"
                    result["screenshot"] = browser.capture_failure_artifacts(
                        page, module.ID)
                else:
                    result["outcome"] = "pass"
                    result["detail"] = ""
        finally:
            db.close()
            engine.dispose()
    except Exception as exc:  # noqa: BLE001  — pre-browser setup error
        result["outcome"] = "fail"
        result["detail"] = f"setup_error: {type(exc).__name__}: {exc}"
    finally:
        if tmp is not None:
            tmp.cleanup()
    return result
