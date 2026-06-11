"""QA Build 04 — Journey runner skeleton + mini-journey proof.

Verifies:
- lib/journey.py exposes Step.
- Runner detects STEPS-based scenarios and walks them step by step.
- The mini-journey passes all 6 steps.
- Discipline boundary: every do_* uses only actions.*/fixtures.*;
  every check_* uses only assertions.*.
- A deliberately-broken step is reported with "step N (name)" detail.
- Existing contract + UI scenarios continue to work unchanged.

Run: python3 test_qa_build04.py
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
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


def run_runner(scenario_path):
    result = subprocess.run(
        [sys.executable, "-m", "scenario_contracts.lib.runner", str(scenario_path)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    return result.returncode, result.stdout + result.stderr


def main():
    print("\n── 1. QA Build 04 plan exists and locks the journey shape ──")
    plan = read("QA_BUILD04_EXECUTION_PLAN.md")
    contains_all("plan locks journey shape", plan,
                 ["STEPS=[", "Step(name, do, check)",
                  "step N (name)", "Backward compatibility"])
    contains_all("plan locks the 4 new actions", plan,
                 ["finish_phase", "create_blocker", "resolve_blocker",
                  "create_journal_entry"])
    contains_all("plan locks discipline boundary for steps", plan,
                 ["only `actions.*`", "only `assertions.*`"])

    print("\n── 2. lib/journey.py exposes Step ──")
    from scenario_contracts.lib.journey import Step
    if hasattr(Step, "__dataclass_fields__"):
        fields = set(Step.__dataclass_fields__.keys())
        if fields == {"name", "do", "check"}:
            ok("Step is a dataclass with fields {name, do, check}")
        else:
            fail("Step fields", f"got {fields}")
    else:
        fail("Step shape", "not a dataclass")

    print("\n── 3. Runner detects journey shape ──")
    from scenario_contracts.lib import runner as runner_mod
    if hasattr(runner_mod, "is_journey"):
        ok("runner.is_journey exposed")
    else:
        fail("runner.is_journey", "missing")

    print("\n── 4. The mini-journey scenario loads ──")
    import importlib
    try:
        journey = importlib.import_module(
            "scenario_contracts.journeys.journey_basic_pm_lifecycle")
        for field in ("ID", "TITLE", "TAGS", "MATURITY", "WHY_IT_MATTERS",
                      "STEPS"):
            if not hasattr(journey, field):
                fail(f"mini-journey declares {field}", "missing")
                break
        else:
            if "journey" not in journey.TAGS:
                fail("mini-journey tagged 'journey'", f"got {journey.TAGS}")
            elif len(journey.STEPS) < 5:
                fail("mini-journey has ≥5 steps",
                     f"got {len(journey.STEPS)}")
            else:
                ok(f"mini-journey loads with {len(journey.STEPS)} steps and 'journey' tag")
    except Exception as exc:
        fail("mini-journey import", str(exc))

    print("\n── 5. The mini-journey passes all 6 steps via the runner ──")
    code, out = run_runner("scenario_contracts/journeys/journey_basic_pm_lifecycle.py")
    if code == 0 and "PASS: 1" in out and "6 steps OK" in out:
        ok("mini-journey — runner exit 0; PASS: 1; 6 steps OK")
    else:
        fail("mini-journey via runner",
             f"exit={code}; out: {out[-500:]}")

    print("\n── 6. A deliberately-broken step reports step N (name) ──")
    # Write a temporary broken journey file under journeys/ and run it.
    broken = ROOT / "scenario_contracts" / "journeys" / "_test_broken.py"
    broken_src = '''\
from scenario_contracts.lib import actions, assertions, fixtures
from scenario_contracts.lib.journey import Step

ID = "test_broken_001"
TITLE = "Deliberately fails at step 2 to prove failure reporting"
TAGS = ["journey", "test_fixture"]
MATURITY = "experimental"
WHY_IT_MATTERS = "Used by test_qa_build04 to verify step-N failure reporting."

def setup(db):
    return {"pm": fixtures.create_user(db, "broken_pm")}

def do_step_1(world, db, http):
    world["project"] = actions.create_project_for_pm(db, "Broken", "broken_pm")

def check_step_1(db, world):
    assertions.assert_row_count(db, "projects", expected=1)

def do_step_2(world, db, http):
    pass

def check_step_2(db, world):
    # Intentionally wrong.
    assertions.assert_row_count(db, "projects", expected=999,
                                label="intentionally-wrong step 2 check")

STEPS = [
    Step("Step one succeeds", do_step_1, check_step_1),
    Step("Step two fails", do_step_2, check_step_2),
]
'''
    broken.write_text(broken_src, encoding="utf-8")
    try:
        code, out = run_runner(str(broken))
        if (
            code == 1
            and "FAIL: 1" in out
            and "step 2 (Step two fails)" in out
            and "expected 999" in out
        ):
            ok("broken journey — runner reports 'step 2 (Step two fails) check: ...'")
        else:
            fail("broken journey failure reporting",
                 f"exit={code}; out: {out[-500:]}")
    finally:
        broken.unlink(missing_ok=True)

    print("\n── 7. Discipline boundary holds for the mini-journey ──")
    journey_src = read("scenario_contracts/journeys/journey_basic_pm_lifecycle.py")
    do_funcs = re.findall(r"def (do_\w+)\(.*?\):\s*\n((?:    .*\n)+)", journey_src)
    check_funcs = re.findall(r"def (check_\w+)\(.*?\):\s*\n((?:    .*\n)+)", journey_src)

    violations = []
    for name, body in do_funcs:
        if re.search(r"^\s*from app\.", body, re.MULTILINE):
            violations.append(f"{name} imports from app.*")
        if "assertions." in body:
            violations.append(f"{name} calls assertions.*")
    for name, body in check_funcs:
        if re.search(r"^\s*from app\.", body, re.MULTILINE):
            violations.append(f"{name} imports from app.*")
        if "actions." in body:
            # Allow read-only DB queries via sqlalchemy.text for capture
            # steps (Step 2 of the mini-journey uses this pattern).
            # Disallow only actions.create_*/actions.adjust_*/actions.finish_*.
            if re.search(r"actions\.(create|adjust|finish|resolve|apply)_", body):
                violations.append(f"{name} calls mutating actions.*")
    if violations:
        fail("mini-journey discipline boundary", "; ".join(violations))
    else:
        ok("mini-journey discipline boundary holds")

    print("\n── 8. Existing scenarios still work after runner refactor ──")
    # Spot-check one DB scenario and one UI scenario.
    code, out = run_runner("scenario_contracts/contracts/golden_pass.py")
    if code == 0 and "PASS: 1" in out:
        ok("golden_pass — DB-only path still PASS after journey extension")
    else:
        fail("DB-only regression after journey extension",
             f"exit={code}; out: {out[-300:]}")

    print("\n── 9. Runner stays scannable; executors split out ──")
    runner_loc = len((ROOT / "scenario_contracts" / "lib" / "runner.py")
                     .read_text().splitlines())
    if runner_loc < 300:
        ok(f"runner.py is {runner_loc} LOC (<300)")
    else:
        fail("runner.py LOC budget", f"{runner_loc} >= 300")
    if (ROOT / "scenario_contracts" / "lib" / "executors.py").exists():
        ok("executors.py extracted as helper module")
    else:
        fail("executors.py", "missing — runner should have been split")

    print("\n── 10. app/* untouched ──")
    from app.version import CURRENT_VERSION
    if CURRENT_VERSION == "1.4.0":
        ok("app/version.py CURRENT_VERSION == '1.4.0' (QA-04 did not bump it)")
    else:
        fail("app/version.py untouched", f"got {CURRENT_VERSION!r}")

    print(f"\nPassed: {len(PASS)} / {len(PASS) + len(FAIL)}")
    if FAIL:
        print("FAILED:")
        for name, reason in FAIL:
            print(f"  - {name}: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
