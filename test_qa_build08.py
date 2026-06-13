"""QA Build 08 — Disruption library + medium journey proof.

Verifies that:
- lib/disruptions.py exposes the 5 composable disruption helpers.
- The 2 new actions (update_project, add_phase) are present.
- The medium journey passes all 10 steps.
- The discipline boundary widens cleanly: do_* may use actions.* AND
  disruptions.*; check_* still uses only assertions.*.
- A deliberately-broken step in a tmp journey is reported with
  `step N (name)` detail (proves journey failure reporting still
  works with disruptions in the mix).

Run: python3 test_qa_build08.py
"""
from __future__ import annotations

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


def run_runner(scenario_path, extra_args=None):
    cmd = [sys.executable, "-m", "scenario_contracts.lib.runner", str(scenario_path)]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(ROOT),
    )
    return result.returncode, result.stdout + result.stderr


def main():
    print("\n── 1. QA Build 08 plan exists and locks the disruption library scope ──")
    plan = read("QA_BUILD08_EXECUTION_PLAN.md")
    contains_all("plan names the 5 disruption helpers", plan,
                 ["factory_raises_cost_by_pct", "supplier_delays_phase",
                  "prototype_round_added", "variant_color_only",
                  "geopolitical_event"])
    contains_all("plan widens the discipline boundary", plan,
                 ["Discipline boundary widens",
                  "`actions.*` AND `disruptions.*`",
                  "compositions"])
    contains_all("plan locks the 10-step journey shape", plan,
                 ["10 step", "AI PM reacts", "candidate"])

    print("\n── 2. 2 new actions are present ──")
    from scenario_contracts.lib import actions
    import inspect
    for name in ("update_project", "add_phase"):
        if hasattr(actions, name):
            ok(f"actions.{name} present")
        else:
            fail(f"actions.{name}", "missing")
    sig_up = list(inspect.signature(actions.update_project).parameters)
    if sig_up[:3] == ["db", "project_id", "data"]:
        ok("actions.update_project(db, project_id, data, ...) signature")
    else:
        fail("update_project signature", f"got {sig_up}")

    print("\n── 3. lib/disruptions.py exposes the 5 helpers ──")
    from scenario_contracts.lib import disruptions
    for name in ("factory_raises_cost_by_pct", "supplier_delays_phase",
                 "prototype_round_added", "variant_color_only",
                 "geopolitical_event"):
        if hasattr(disruptions, name):
            ok(f"disruptions.{name} present")
        else:
            fail(f"disruptions.{name}", "missing")

    print("\n── 4. Journey loads with required metadata + 10 steps ──")
    import importlib
    try:
        mod = importlib.import_module(
            "scenario_contracts.journeys.journey_pm_with_disruptions")
        for field in ("ID", "TITLE", "TAGS", "MATURITY",
                      "WHY_IT_MATTERS", "STEPS"):
            if not hasattr(mod, field):
                fail(f"journey declares {field}", "missing")
                break
        else:
            tags = set(mod.TAGS)
            if {"journey", "ai_mocked", "disruption"} <= tags:
                ok("journey tagged journey + ai_mocked + disruption")
            else:
                fail("journey tag set", f"got {sorted(tags)}")
            if mod.MATURITY != "candidate":
                fail("MATURITY == 'candidate'", f"got {mod.MATURITY!r}")
            else:
                ok("MATURITY is 'candidate' (first disruption-mixed journey)")
            if len(mod.STEPS) == 10:
                ok("journey declares exactly 10 steps")
            else:
                fail("journey step count", f"got {len(mod.STEPS)}")
    except Exception as exc:
        fail("journey import", str(exc))

    print("\n── 5. Journey passes all 10 steps via subprocess ──")
    code, out = run_runner(
        "scenario_contracts/journeys/journey_pm_with_disruptions.py")
    if code == 0 and "PASS: 1" in out and "10 steps OK" in out:
        ok("medium journey — runner exit 0, PASS: 1, 10 steps OK")
    else:
        fail("medium journey live", f"exit={code}; out: {out[-500:]}")

    print("\n── 6. Discipline boundary holds inside the journey ──")
    journey_src = read(
        "scenario_contracts/journeys/journey_pm_with_disruptions.py")
    # Each do_* function: must call actions.* or disruptions.*; must
    # NOT import from app.*; must NOT call assertions.*.
    # Each check_* function: must call assertions.*; must NOT import
    # from app.*; must NOT call actions.mut* or disruptions.*.
    do_funcs = re.findall(
        r"def (do_\w+)\(.*?\):\s*\n((?:    .*\n)+)", journey_src)
    check_funcs = re.findall(
        r"def (check_\w+)\(.*?\):\s*\n((?:    .*\n)+)", journey_src)

    boundary_ok = True
    for name, body in do_funcs:
        if re.search(r"^\s*from app\.", body, re.MULTILINE):
            fail(f"do_{name} imports app.*", "boundary breach")
            boundary_ok = False
        if "assertions." in body:
            fail(f"{name} calls assertions.*", "boundary breach")
            boundary_ok = False
        if "actions." not in body and "disruptions." not in body:
            fail(f"{name} uses no actions.* or disruptions.*",
                 "no mutation helper")
            boundary_ok = False
    for name, body in check_funcs:
        if re.search(r"^\s*from app\.", body, re.MULTILINE):
            fail(f"check_{name} imports app.*", "boundary breach")
            boundary_ok = False
        if "assertions." not in body:
            fail(f"{name} uses no assertions.*", "no assertion call")
            boundary_ok = False
        # Compose-helpers must not run inside check_*.
        if "disruptions." in body or re.search(
                r"actions\.(create|adjust|finish|resolve|apply|update_project|add_phase|delete_project)",
                body):
            fail(f"{name} calls a mutation helper inside check",
                 "boundary breach")
            boundary_ok = False
    if boundary_ok:
        ok("journey discipline boundary holds (do uses actions/disruptions; check uses assertions only)")

    print("\n── 7. Deliberately-broken step is reported with step N (name) ──")
    broken = ROOT / "scenario_contracts" / "journeys" / "_test_broken_d.py"
    broken_src = '''\
from scenario_contracts.lib import actions, assertions, disruptions, fixtures
from scenario_contracts.lib.journey import Step

ID = "test_broken_d_001"
TITLE = "Deliberately fails after a disruption to prove failure reporting"
TAGS = ["journey", "disruption", "test_fixture"]
MATURITY = "experimental"
WHY_IT_MATTERS = "Used by test_qa_build08 to verify step-N failure reporting with disruptions in the mix."

def setup(db):
    pm = fixtures.create_user(db, "broken_pm_d", role="pm")
    return {"pm": pm}

def do_step_1(world, db, http):
    world["project"] = actions.create_project_for_pm(
        db, "Broken-D", "broken_pm_d", target_factory_cost=10.0)

def check_step_1(db, world):
    assertions.assert_row_count(db, "projects", expected=1)

def do_step_2(world, db, http):
    disruptions.factory_raises_cost_by_pct(
        db, project_id=world["project"].id, pct=10.0, reason="Test")

def check_step_2(db, world):
    # Deliberately wrong.
    assertions.assert_row_count(
        db, "projects", expected=999,
        label="intentionally-wrong step 2 check after disruption")

STEPS = [
    Step("Step one succeeds", do_step_1, check_step_1),
    Step("Step two fails after disruption", do_step_2, check_step_2),
]
'''
    broken.write_text(broken_src, encoding="utf-8")
    try:
        code, out = run_runner(str(broken))
        if (
            code == 1
            and "FAIL: 1" in out
            and "step 2 (Step two fails after disruption)" in out
            and "expected 999" in out
        ):
            ok("broken journey — runner reports 'step 2 (...) check: ...'")
        else:
            fail("broken journey failure reporting",
                 f"exit={code}; out: {out[-500:]}")
    finally:
        broken.unlink(missing_ok=True)

    print("\n── 8. app/* untouched ──")
    from app.version import CURRENT_VERSION
    if CURRENT_VERSION == "1.4.0":
        ok("app/version.py CURRENT_VERSION == '1.4.0' (QA-08 did not bump it)")
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


if __name__ == "__main__":
    sys.exit(main())
