"""QA Build 03 — Playwright UI Layer proof.

Verifies the browser path: UI scenarios run against the live dev server,
golden_ui_fail produces a real failure with a screenshot, and the runner
SKIPs cleanly when the dev server is unreachable.

Pre-conditions:
- `python run.py` running on http://localhost:8000 (or BASE_URL).
- `playwright install chromium` already done.

Run: python3 test_qa_build03.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

PASS, FAIL = [], []

UI_SCENARIOS = [
    "ui_login_smoke",
    "ui_sandbox_canvas_smoke",
]


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
        fail(label, f"missing: {missing}")
    else:
        ok(label)


def run_runner(scenario_path, env=None):
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    result = subprocess.run(
        [sys.executable, "-m", "scenario_contracts.lib.runner", str(scenario_path)],
        capture_output=True, text=True, cwd=str(ROOT), env=full_env,
    )
    return result.returncode, result.stdout + result.stderr


def main():
    print("\n── 1. QA Build 03 execution plan exists and locks the browser path ──")
    plan = read("QA_BUILD03_EXECUTION_PLAN.md")
    contains_all("plan lists ui_login_smoke and ui_sandbox_canvas_smoke", plan,
                 ["ui_login_smoke.py", "ui_sandbox_canvas_smoke.py"])
    contains_all("plan locks Playwright + dev server requirements", plan,
                 ["is_playwright_available", "is_dev_server_reachable",
                  "BrowserContext", "capture_failure_artifacts"])
    contains_all("plan locks SKIP fallbacks", plan,
                 ["playwright_not_installed", "dev_server_unreachable"])

    print("\n── 2. lib/browser.py exposes required surface ──")
    sys.path.insert(0, str(ROOT))
    try:
        from scenario_contracts.lib import browser
        for sym in ("is_playwright_available", "is_dev_server_reachable",
                    "BrowserContext", "capture_failure_artifacts",
                    "base_url", "admin_credentials"):
            if not hasattr(browser, sym):
                fail(f"browser.{sym}", "missing")
                break
        else:
            ok("scenario_contracts.lib.browser exposes the 6 required symbols")
    except Exception as exc:
        fail("scenario_contracts.lib.browser import", str(exc))

    print("\n── 3. UI actions and assertions exist ──")
    actions_src = read("scenario_contracts/lib/actions.py")
    contains_all("actions.py has UI helpers", actions_src,
                 ["def open_url", "def click", "def fill_input",
                  "def wait_for_load", "def discover_first_project_id"])
    assertions_src = read("scenario_contracts/lib/assertions.py")
    contains_all("assertions.py has UI helpers", assertions_src,
                 ["def assert_ui_shows", "def assert_ui_does_not_show",
                  "def assert_url_path", "def assert_page_contains"])

    print("\n── 4. Runner has UI scenario execution path ──")
    # QA-04 extracted the executors into a helper module. Symbols may
    # live in runner.py OR executors.py.
    runner_src = read("scenario_contracts/lib/runner.py")
    executors_path = ROOT / "scenario_contracts" / "lib" / "executors.py"
    executors_src = executors_path.read_text() if executors_path.exists() else ""
    combined = runner_src + "\n" + executors_src
    contains_all("runner exposes UI scenario branch", combined,
                 ["execute_ui_scenario", "execute_db_scenario",
                  "call_with_optional_page",
                  "is_playwright_available", "is_dev_server_reachable",
                  "BrowserContext", "capture_failure_artifacts"])

    print("\n── 5. UI scenarios load with required metadata + ui tag ──")
    import importlib
    for name in UI_SCENARIOS + ["golden_ui_fail"]:
        try:
            mod = importlib.import_module(f"scenario_contracts.contracts.{name}")
            for field in ("ID", "TITLE", "TAGS", "MATURITY", "WHY_IT_MATTERS"):
                if not hasattr(mod, field):
                    fail(f"{name} declares {field}", "missing")
                    break
            else:
                if "ui" not in mod.TAGS:
                    fail(f"{name} tagged 'ui'", f"got {mod.TAGS}")
                else:
                    ok(f"{name} declares 5 metadata + 'ui' tag")
        except Exception as exc:
            fail(f"{name} import", str(exc))

    print("\n── 6. UI scenarios pass against live dev server ──")
    # Confirm prerequisites once.
    from scenario_contracts.lib import browser
    if not browser.is_playwright_available():
        ok("PRECONDITION SKIPPED — Playwright not installed; UI tests can't run here")
        skip_live = True
    elif not browser.is_dev_server_reachable():
        ok("PRECONDITION SKIPPED — dev server not reachable; UI tests can't run here")
        skip_live = True
    else:
        skip_live = False

    if not skip_live:
        for name in UI_SCENARIOS:
            code, out = run_runner(f"scenario_contracts/contracts/{name}.py")
            if code == 0 and "PASS: 1" in out:
                ok(f"{name} — exit 0 PASS")
            else:
                fail(f"{name} live", f"exit={code}; out: {out[-400:]}")

        print("\n── 7. golden_ui_fail produces FAIL + screenshot ──")
        # Snapshot screenshots dir before
        screenshots_dir = ROOT / "scenario_contracts" / "reports" / "screenshots"
        before = set()
        if screenshots_dir.exists():
            before = set(p.name for p in screenshots_dir.iterdir())

        code, out = run_runner("scenario_contracts/contracts/golden_ui_fail.py")
        after = set()
        if screenshots_dir.exists():
            after = set(p.name for p in screenshots_dir.iterdir())
        new_shots = after - before
        new_for_scenario = [
            s for s in new_shots if s.startswith("golden_ui_fail_001")
        ]
        if (
            code == 1
            and "FAIL: 1" in out
            and "intentionally-wrong UI assertion" in out
            and len(new_for_scenario) >= 1
        ):
            ok("golden_ui_fail — exit 1 + screenshot captured")
        else:
            fail("golden_ui_fail live",
                 f"exit={code}; new shots: {new_for_scenario}; out: {out[-300:]}")

    print("\n── 8. UI scenario SKIPs cleanly when dev server unreachable ──")
    # Point BASE_URL at a known-bad host with a short-circuit return.
    code, out = run_runner(
        "scenario_contracts/contracts/ui_login_smoke.py",
        env={"BASE_URL": "http://127.0.0.1:1"},
    )
    if code == 0 and "SKIP: 1" in out and "dev_server_unreachable" in out:
        ok("UI scenario SKIPs cleanly when dev server unreachable")
    else:
        fail("dev_server_unreachable SKIP behavior",
             f"exit={code}; out: {out[-400:]}")

    print("\n── 9. DB-only scenarios still work after runner refactor ──")
    code, out = run_runner("scenario_contracts/contracts/golden_pass.py")
    if code == 0 and "PASS: 1" in out:
        ok("golden_pass — DB-only path still PASS after UI runner extension")
    else:
        fail("DB-only regression", f"exit={code}; out: {out[-300:]}")

    code, out = run_runner("scenario_contracts/contracts/sandbox_apply_invariant.py")
    if code == 0 and "PASS: 1" in out:
        ok("sandbox_apply_invariant — DB-only path still PASS")
    else:
        fail("DB-only sandbox_apply regression",
             f"exit={code}; out: {out[-300:]}")

    print("\n── 10. Runner LOC budget still under 300 ──")
    runner_loc = len((ROOT / "scenario_contracts" / "lib" / "runner.py")
                     .read_text().splitlines())
    if runner_loc < 300:
        ok(f"runner.py is {runner_loc} LOC (<300)")
    else:
        fail("runner.py LOC budget", f"{runner_loc} >= 300")

    print("\n── 11. Discipline boundary holds for new UI scenarios ──")
    import re
    for name in UI_SCENARIOS + ["golden_ui_fail"]:
        text = read(f"scenario_contracts/contracts/{name}.py")
        run_body = _extract_function_body(text, "run")
        check_body = _extract_function_body(text, "check")
        if run_body is None or check_body is None:
            fail(f"{name} discipline parse", "could not extract bodies")
            continue
        ok_flag = True
        if "actions." not in run_body:
            fail(f"{name} run() uses actions.*", "no actions.* call")
            ok_flag = False
        if "assertions." not in check_body:
            # golden_ui_fail's check uses an intentionally-failing assertion;
            # ui scenarios should call assertions.assert_*. All three do.
            fail(f"{name} check() uses assertions.*", "no assertions.* call")
            ok_flag = False
        if re.search(r"^\s*from app\.", run_body, re.MULTILINE):
            fail(f"{name} run() boundary", "imports from app.*")
            ok_flag = False
        if re.search(r"^\s*from app\.", check_body, re.MULTILINE):
            fail(f"{name} check() boundary", "imports from app.*")
            ok_flag = False
        if ok_flag:
            ok(f"{name} discipline boundary holds")

    print("\n── 12. app/* untouched ──")
    from app.version import CURRENT_VERSION
    if CURRENT_VERSION == "1.4.0":
        ok("app/version.py CURRENT_VERSION == '1.4.0' (QA-03 did not bump it)")
    else:
        fail("app/version.py untouched", f"got {CURRENT_VERSION!r}")

    print(f"\nPassed: {len(PASS)} / {len(PASS) + len(FAIL)}")
    if FAIL:
        print("FAILED:")
        for name, reason in FAIL:
            print(f"  - {name}: {reason}")
        return 1
    return 0


# ── helpers ────────────────────────────────────────────────────────────

def _extract_function_body(text, func_name):
    import re

    pattern = re.compile(
        rf"^def {re.escape(func_name)}\(.*?\):\s*\n",
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        return None
    start = match.end()
    next_def = re.search(r"^(def |class )", text[start:], re.MULTILINE)
    end = start + next_def.start() if next_def else len(text)
    return text[start:end]


if __name__ == "__main__":
    sys.exit(main())
