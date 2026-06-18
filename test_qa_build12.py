"""QA Build 12 — PM workflow agent journeys.

Verifies the journey-first revision after the QA Build 11 review:
- no new live-LLM release gate;
- AI prototype approval journey proves no silent mutation before confirmation;
- sandbox parallel planning journey exists and runs/skips through the runner;
- scenario files preserve acceptance/journey metadata and PM-facing assertions.

Run: python3 test_qa_build12.py
"""
from __future__ import annotations

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


def run_runner(path):
    result = subprocess.run(
        [sys.executable, "-m", "scenario_contracts.lib.runner", path],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=900,
    )
    return result.returncode, result.stdout + result.stderr


def main():
    print("\n── 1. QA-12 plan locks journey-first scope ──")
    plan = read("QA_BUILD12_EXECUTION_PLAN.md")
    contains_all(
        "plan rejects meta-tooling detour",
        plan,
        ["No coverage matrix", "No live LLM scenario generation", "journeys first"],
    )
    contains_all(
        "plan names both QA-12 scenarios",
        plan,
        ["AI Prototype Approval Confirmation", "Sandbox Parallel Planning"],
    )

    print("\n── 2. PRD records Claude review revision ──")
    prd = read("QA_AI_WORKFLOW_PRD.md")
    contains_all(
        "PRD revision defers matrix/live generator",
        prd,
        ["Claude reviewed", "Do not start with a coverage matrix", "Do not add live AI scenario generation"],
    )

    print("\n── 3. AI confirmation journey has the required contract ──")
    ai_path = ROOT / "scenario_contracts/journeys/ai_prototype_approval_confirmation.py"
    if ai_path.exists():
        ok("ai_prototype_approval_confirmation.py exists")
    else:
        fail("ai_prototype_approval_confirmation.py", "missing")
    ai_src = ai_path.read_text(encoding="utf-8")
    contains_all(
        "AI journey checks unconfirmed and confirmed paths",
        ai_src,
        [
            "assert_dispatch_required_confirmation",
            "assert_dispatch_succeeded",
            "unconfirmed AI journal did not create a journal row",
            "unconfirmed AI finish leaves Prototype Review in progress",
            "confirmed AI finish advances Pre-production Sample",
        ],
    )
    contains_all(
        "AI journey uses real dispatcher action",
        ai_src,
        ["actions.ai_dispatch", "create_journal_entry", "finish_phase"],
    )

    print("\n── 4. Sandbox parallel journey has the required PM workflow checks ──")
    sandbox_path = ROOT / "scenario_contracts/acceptance/sandbox_parallel_planning_workflow.py"
    if sandbox_path.exists():
        ok("sandbox_parallel_planning_workflow.py exists")
    else:
        fail("sandbox_parallel_planning_workflow.py", "missing")
    sandbox_src = sandbox_path.read_text(encoding="utf-8")
    contains_all(
        "sandbox journey models parallel branches and downstream gate",
        sandbox_src,
        [
            "Design Direction",
            "Engineering Feasibility",
            "Prototype Gate",
            "connectSelectedToIndex",
            "nodeLabels",
            # SB-Rescue-03 lock: scenario must honor stay-on-Modules contract
            # and return to Modules between adds to avoid spurious auto-connect.
            "_add_then_select_latest",
            "_return_to_modules",
            "parallel branches have no edge between them yet",
            "exactly two upstream branches",
        ],
    )
    contains_all(
        "sandbox journey is browser acceptance",
        sandbox_src,
        ['"acceptance"', '"ui"', '"sandbox"', '"planner"'],
    )

    print("\n── 5. AI confirmation journey passes through runner ──")
    code, out = run_runner("scenario_contracts/journeys/ai_prototype_approval_confirmation.py")
    if code == 0 and "PASS: 1" in out and "5 steps OK" in out:
        ok("AI confirmation journey runner PASS")
    else:
        fail("AI confirmation journey runner", f"exit={code}; out={out[-800:]}")

    print("\n── 6. Sandbox parallel journey runs or skips cleanly through runner ──")
    code, out = run_runner("scenario_contracts/acceptance/sandbox_parallel_planning_workflow.py")
    if code == 0 and "PASS: 1" in out and "steps OK" in out:
        ok("sandbox parallel journey runner PASS")
    elif code == 0 and "SKIP: 1" in out and "dev_server_unreachable" in out:
        ok("sandbox parallel journey SKIPs cleanly when dev server unreachable")
    else:
        fail("sandbox parallel journey runner", f"exit={code}; out={out[-1000:]}")

    print("\n── 7. Existing sandbox template workflow remains available ──")
    existing = ROOT / "scenario_contracts/acceptance/sandbox_template_connection_workflow.py"
    if existing.exists():
        ok("sandbox_template_connection_workflow.py still present")
    else:
        fail("sandbox_template_connection_workflow.py", "missing")

    print("\n── 8. Sandbox QA hook exposes canvas labels for non-fragile tests ──")
    sandbox_js = read("app/static/js/planning_sandbox.js")
    contains_all(
        "planning_sandbox.js exposes nodeLabels QA hook",
        sandbox_js,
        ["nodeLabels", "nodeElements().map", "node.data.label"],
    )

    print(f"\nPASSED: {len(PASS)} / FAILED: {len(FAIL)}")
    if FAIL:
        print("\nFailures:")
        for name, reason in FAIL:
            print(f" - {name}: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
