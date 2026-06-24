#!/usr/bin/env python3
"""QA Agent 1.1 regression — Sandbox usability acceptance."""
from __future__ import annotations

import pathlib
import py_compile
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
PASS, FAIL = [], []


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, detail):
    FAIL.append((name, detail))
    print(f"  ✗  {name}: {detail}")


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def run(cmd, timeout=120):
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout + proc.stderr


def test_plan_exists_and_locks_scope():
    plan = read("QA_AGENT_1_1_SANDBOX_USABILITY_PLAN.md")
    required = [
        "QA Agent 1.1",
        "Primary user click-path",
        "Locked behaviors",
        "Automated locks",
        "No new product data",
        "Live LLM",
        "Deferred",
    ]
    missing = [needle for needle in required if needle not in plan]
    if missing:
        fail("QA Agent 1.1 plan locks deterministic sandbox scope", missing)
    else:
        ok("QA Agent 1.1 plan locks deterministic sandbox scope")


def test_scenario_source_locks():
    scenario = read("scenario_contracts/acceptance/sandbox_usability_acceptance.py")
    required = [
        "acceptance_sandbox_usability_001",
        '"release_gate"',
        '"qa_agent_1_1"',
        "[data-project-sandbox-link]",
        "[data-sandbox-template-trigger]",
        "template_open_after_outside",
        "template_open_after_escape",
        "[data-sandbox-module-search]",
        "[data-sandbox-module-filter='advanced']",
        "[data-sandbox-connect-from]",
        "connect_button_active",
        "[data-sandbox-back-to-modules]",
        "[data-sandbox-warning-strip]",
        "missing_owner",
    ]
    missing = [needle for needle in required if needle not in scenario]
    if missing:
        fail("sandbox usability scenario encodes user complaints", missing)
    else:
        ok("sandbox usability scenario encodes user complaints")

    forbidden = [
        "actions.ensure_sandbox_exists(",
        "actions.open_url(page, f\"/projects/{world['project_id']}/sandbox\")",
    ]
    found = [needle for needle in forbidden if needle in scenario]
    if found:
        fail("sandbox usability scenario does not bypass PM click path", found)
    else:
        ok("sandbox usability scenario does not bypass PM click path")


def test_py_compile():
    files = [
        "scenario_contracts/acceptance/sandbox_usability_acceptance.py",
        "test_qa_agent_1_1.py",
    ]
    try:
        for file in files:
            py_compile.compile(str(ROOT / file), doraise=True)
    except py_compile.PyCompileError as exc:
        fail("QA Agent 1.1 files compile", str(exc))
    else:
        ok("QA Agent 1.1 files compile")


def test_runner_passes_or_skips_cleanly():
    code, out = run([
        sys.executable,
        "-m",
        "scenario_contracts.lib.runner",
        "scenario_contracts/acceptance/sandbox_usability_acceptance.py",
    ])
    if code != 0:
        fail("sandbox usability scenario runner exits cleanly", out[-1200:])
        return
    if "PASS: 1" in out and "5 steps OK" in out:
        ok("sandbox usability scenario runner PASS")
    elif "SKIP: 1" in out and "dev_server_unreachable" in out:
        ok("sandbox usability scenario SKIPs cleanly when dev server unreachable")
    else:
        fail("sandbox usability scenario runner result is understood", out[-1200:])


def main():
    print("\n── 1. Plan locks ──")
    test_plan_exists_and_locks_scope()
    print("\n── 2. Scenario source locks ──")
    test_scenario_source_locks()
    print("\n── 3. Compile ──")
    test_py_compile()
    print("\n── 4. Runner ──")
    test_runner_passes_or_skips_cleanly()

    print(f"\nPASSED: {len(PASS)} / FAILED: {len(FAIL)}")
    if FAIL:
        for name, detail in FAIL:
            print(f" - {name}: {detail}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
