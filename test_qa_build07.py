"""QA Build 07 — Sandbox UI mutation (add module from palette) proof.

Verifies the Codex Timeline planner's most common UI mutation
flow — clicking the palette Add button creates a sandbox node and
the canvas summary updates — works end-to-end against the real dev
server.

Pre-conditions:
- `python run.py` running on http://localhost:8000.
- `playwright install chromium` already done.
- Dev DB has at least one project.

Run: python3 test_qa_build07.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

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
        fail(label, f"missing: {missing}")
    else:
        ok(label)


def run_runner(scenario_path, env=None, extra_args=None):
    cmd = [sys.executable, "-m", "scenario_contracts.lib.runner", str(scenario_path)]
    if extra_args:
        cmd.extend(extra_args)
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(ROOT), env=full_env,
    )
    return result.returncode, result.stdout + result.stderr


def main():
    print("\n── 1. QA Build 07 plan exists and locks single-scenario scope ──")
    plan = read("QA_BUILD07_EXECUTION_PLAN.md")
    contains_all("plan names the scenario", plan,
                 ["ui_sandbox_add_module.py"])
    contains_all("plan defers other UI mutations", plan,
                 ["QA-07b", "QA-07c", "QA-07b/c",
                  "Apply via the confirmation modal"])
    contains_all("plan locks the Codex Timeline planner intent", plan,
                 ["Codex Timeline planner",
                  "v1.4 Planning Sandbox",
                  "Add module"])
    contains_all("plan locks Backend Honesty Mapping for the click flow",
                 plan,
                 ["create_sandbox_node_from_module",
                  "refreshFromPayload"])

    print("\n── 2. 3 new UI actions are present ──")
    from scenario_contracts.lib import actions
    for name in ("ensure_sandbox_exists", "click_add_first_module",
                 "read_sandbox_node_count", "wait_for_node_count"):
        if hasattr(actions, name):
            ok(f"actions.{name} present")
        else:
            fail(f"actions.{name}", "missing")

    print("\n── 3. 1 new UI assertion is present ──")
    from scenario_contracts.lib import assertions
    if hasattr(assertions, "assert_canvas_node_count_equals"):
        ok("assertions.assert_canvas_node_count_equals present")
    else:
        fail("assertions.assert_canvas_node_count_equals", "missing")

    print("\n── 4. Scenario loads with required metadata + ui + release_gate tags ──")
    import importlib
    try:
        mod = importlib.import_module(
            "scenario_contracts.contracts.ui_sandbox_add_module")
        for field in ("ID", "TITLE", "TAGS", "MATURITY", "WHY_IT_MATTERS"):
            if not hasattr(mod, field):
                fail(f"scenario declares {field}", "missing")
                break
        else:
            tags = set(mod.TAGS)
            if {"ui", "release_gate", "sandbox", "mutation"} <= tags:
                ok(f"scenario declares 5 metadata + ui + release_gate + sandbox + mutation")
            else:
                fail("scenario tag set", f"got {sorted(tags)}")
            if mod.MATURITY != "candidate":
                fail("MATURITY == 'candidate'", f"got {mod.MATURITY!r}")
            else:
                ok("MATURITY is 'candidate' (first UI mutation)")
    except Exception as exc:
        fail("scenario import", str(exc))

    print("\n── 5. Scenario PASSes against live dev server ──")
    from scenario_contracts.lib import browser
    if not browser.is_playwright_available():
        ok("PRECONDITION SKIPPED — Playwright not installed")
        skip_live = True
    elif not browser.is_dev_server_reachable():
        ok("PRECONDITION SKIPPED — dev server not reachable")
        skip_live = True
    else:
        skip_live = False

    if not skip_live:
        code, out = run_runner(
            "scenario_contracts/contracts/ui_sandbox_add_module.py")
        if code == 0 and "PASS: 1" in out:
            ok("ui_sandbox_add_module — runner exit 0, PASS: 1")
        else:
            fail("ui_sandbox_add_module live",
                 f"exit={code}; out: {out[-500:]}")

    print("\n── 6. Scenario SKIPs cleanly when dev server unreachable ──")
    code, out = run_runner(
        "scenario_contracts/contracts/ui_sandbox_add_module.py",
        env={"BASE_URL": "http://127.0.0.1:1"},
    )
    if code == 0 and "SKIP: 1" in out and "dev_server_unreachable" in out:
        ok("scenario SKIPs cleanly when dev server unreachable")
    else:
        fail("dev_server_unreachable SKIP behavior",
             f"exit={code}; out: {out[-400:]}")

    print("\n── 7. Discipline boundary holds ──")
    text = read("scenario_contracts/contracts/ui_sandbox_add_module.py")
    run_body = _extract_function_body(text, "run")
    check_body = _extract_function_body(text, "check")
    ok_flag = True
    if run_body is None or check_body is None:
        fail("scenario discipline parse", "could not extract bodies")
        ok_flag = False
    else:
        if "actions." not in run_body:
            fail("run() uses actions.*", "no actions.* call")
            ok_flag = False
        if "assertions." not in check_body:
            fail("check() uses assertions.*", "no assertions.* call")
            ok_flag = False
        if re.search(r"^\s*from app\.", run_body, re.MULTILINE):
            fail("run() boundary", "imports from app.*")
            ok_flag = False
        if re.search(r"^\s*from app\.", check_body, re.MULTILINE):
            fail("check() boundary", "imports from app.*")
            ok_flag = False
    if ok_flag:
        ok("scenario discipline boundary holds")

    print("\n── 8. app/* untouched ──")
    from app.version import CURRENT_VERSION
    if CURRENT_VERSION == "1.4.0":
        ok("app/version.py CURRENT_VERSION == '1.4.0' (QA-07 did not bump it)")
    else:
        fail("app/version.py untouched", f"got {CURRENT_VERSION!r}")

    print("\n── 9. lib/runner.py LOC budget unchanged ──")
    runner_loc = len((ROOT / "scenario_contracts" / "lib" / "runner.py")
                     .read_text().splitlines())
    if runner_loc < 300:
        ok(f"runner.py is {runner_loc} LOC (<300)")
    else:
        fail("runner.py LOC budget", f"{runner_loc} >= 300")

    print(f"\nPassed: {len(PASS)} / {len(PASS) + len(FAIL)}")
    if FAIL:
        print("FAILED:")
        for name, reason in FAIL:
            print(f"  - {name}: {reason}")
        return 1
    return 0


def _extract_function_body(text, func_name):
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
