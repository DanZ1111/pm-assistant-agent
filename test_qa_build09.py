"""QA Build 09 — Full Marine Knife journey (20 steps) proof.

Verifies the end-state journey that integrates every QA layer:
- runner + journey shape (QA-01, QA-04)
- contracts cross-checked inside steps (QA-02, QA-06)
- mocked AI dispatch (QA-05)
- disruption library — all 5 types (QA-08)
- ideas + project linking (new QA-09 actions)

Run: python3 test_qa_build09.py
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


def run_runner(scenario_path):
    cmd = [sys.executable, "-m", "scenario_contracts.lib.runner", str(scenario_path)]
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(ROOT),
    )
    return result.returncode, result.stdout + result.stderr


def main():
    print("\n── 1. QA Build 09 plan exists and locks the 20-step Marine Knife scope ──")
    plan = read("QA_BUILD09_EXECUTION_PLAN.md")
    contains_all("plan locks the 20-step shape", plan,
                 ["20 step", "Marine Knife", "marathon"])
    contains_all("plan names ideas + sandbox apply as load-bearing", plan,
                 ["create_idea", "link_idea_to_project",
                  "create_sandbox_from_template", "apply_sandbox"])
    contains_all("plan locks all 5 disruption types", plan,
                 ["factory_raises_cost_by_pct",
                  "supplier_delays_phase",
                  "prototype_round_added",
                  "variant_color_only",
                  "geopolitical_event"])

    print("\n── 2. 2 new actions are present ──")
    from scenario_contracts.lib import actions
    import inspect
    for name in ("create_idea", "link_idea_to_project"):
        if hasattr(actions, name):
            ok(f"actions.{name} present")
        else:
            fail(f"actions.{name}", "missing")
    sig_ci = list(inspect.signature(actions.create_idea).parameters)
    if sig_ci[:2] == ["db", "data"]:
        ok("actions.create_idea(db, data, contributor_user_id) signature")
    else:
        fail("create_idea signature", f"got {sig_ci}")
    sig_li = list(inspect.signature(actions.link_idea_to_project).parameters)
    if sig_li[:3] == ["db", "project_id", "idea_id"]:
        ok("actions.link_idea_to_project(db, project_id, idea_id, ...) signature")
    else:
        fail("link_idea_to_project signature", f"got {sig_li}")

    print("\n── 3. Journey loads with required metadata + 20 steps ──")
    import importlib
    try:
        mod = importlib.import_module(
            "scenario_contracts.journeys.journey_marine_knife_full_lifecycle")
        for field in ("ID", "TITLE", "TAGS", "MATURITY",
                      "WHY_IT_MATTERS", "STEPS"):
            if not hasattr(mod, field):
                fail(f"journey declares {field}", "missing")
                break
        else:
            tags = set(mod.TAGS)
            expected_tags = {"journey", "ai_mocked", "disruption",
                             "marathon", "marine_knife"}
            if expected_tags <= tags:
                ok(f"journey declares all {len(expected_tags)} expected tags")
            else:
                missing = expected_tags - tags
                fail("journey tag set", f"missing {sorted(missing)}")
            if mod.MATURITY != "candidate":
                fail("MATURITY == 'candidate'", f"got {mod.MATURITY!r}")
            else:
                ok("MATURITY is 'candidate' (marathon journey)")
            if len(mod.STEPS) == 20:
                ok("journey declares exactly 20 steps")
            else:
                fail("journey step count", f"got {len(mod.STEPS)}")
    except Exception as exc:
        fail("journey import", str(exc))

    print("\n── 4. Marathon journey passes all 20 steps via subprocess ──")
    code, out = run_runner(
        "scenario_contracts/journeys/journey_marine_knife_full_lifecycle.py")
    if code == 0 and "PASS: 1" in out and "20 steps OK" in out:
        ok("marathon journey — runner exit 0, PASS: 1, 20 steps OK")
    else:
        fail("marathon journey live", f"exit={code}; out: {out[-600:]}")

    print("\n── 5. Discipline boundary holds across all 40 functions ──")
    journey_src = read(
        "scenario_contracts/journeys/journey_marine_knife_full_lifecycle.py")
    do_funcs = re.findall(
        r"def (do_\w+)\(.*?\):\s*\n((?:    .*\n)+)", journey_src)
    check_funcs = re.findall(
        r"def (check_\w+)\(.*?\):\s*\n((?:    .*\n)+)", journey_src)

    if len(do_funcs) != 20 or len(check_funcs) != 20:
        fail("journey has 20 do_ and 20 check_ functions",
             f"got {len(do_funcs)} do_, {len(check_funcs)} check_")
    else:
        ok(f"journey has 20 do_* and 20 check_* functions")

    boundary_ok = True
    for name, body in do_funcs:
        if re.search(r"^\s*from app\.", body, re.MULTILINE):
            fail(f"{name} imports app.*", "boundary breach")
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
            fail(f"{name} imports app.*", "boundary breach")
            boundary_ok = False
        if "assertions." not in body:
            fail(f"{name} uses no assertions.*", "no assertion call")
            boundary_ok = False
        if "disruptions." in body or re.search(
                r"actions\.(create|adjust|finish|resolve|apply|update_project|add_phase|delete_project|link_idea)",
                body):
            fail(f"{name} calls a mutation helper inside check",
                 "boundary breach")
            boundary_ok = False
    if boundary_ok:
        ok("discipline boundary holds across all 40 functions")

    print("\n── 6. app/* untouched ──")
    from app.version import CURRENT_VERSION
    if CURRENT_VERSION == "1.4.0":
        ok("app/version.py CURRENT_VERSION == '1.4.0' (QA-09 did not bump it)")
    else:
        fail("app/version.py untouched", f"got {CURRENT_VERSION!r}")

    print("\n── 7. lib/runner.py LOC budget unchanged ──")
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
