"""QA Build 06 — Tier 1 contract gaps proof.

Verifies:
- The Marine-bug regression scenario passes under SQLite FK enforcement.
- The 4 surrounding bug-class contracts (delete permissions, create
  idempotency, finish_phase advancement, blocker lifecycle) pass.
- All 4 new actions + 2 new fixtures are present.
- Discipline boundary holds.
- SQLite FK enforcement is still wired in app/database.py.

Run: python3 test_qa_build06.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

PASS, FAIL = [], []

QA06_SCENARIOS = [
    "project_delete_ai_intake_cleanup",
    "project_delete_permission_boundary",
    "project_create_idempotency",
    "finish_phase_advancement",
    "blocker_lifecycle",
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


def run_runner(scenario_path, extra_args=None):
    cmd = [sys.executable, "-m", "scenario_contracts.lib.runner", str(scenario_path)]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(ROOT),
    )
    return result.returncode, result.stdout + result.stderr


def main():
    print("\n── 1. QA Build 06 plan exists and locks the 5 scenarios ──")
    plan = read("QA_BUILD06_EXECUTION_PLAN.md")
    contains_all("plan lists all 5 scenarios", plan,
                 [f"{name}.py" for name in QA06_SCENARIOS])
    contains_all("plan names the Marine bug context", plan,
                 ["Marine bug", "b8a9687", "PRAGMA foreign_keys",
                  "ai_conversations", "project_creation_tokens"])
    contains_all("plan locks Backend Honesty Mapping rows", plan,
                 ["can_delete_project", "create_project_with_idempotency",
                  "recalculate_stage_and_delay"])

    print("\n── 2. 4 new actions are present with the expected signatures ──")
    from scenario_contracts.lib import actions
    import inspect
    for name in ("delete_project", "create_project_with_idempotency",
                 "mint_creation_token", "update_blocker"):
        if not hasattr(actions, name):
            fail(f"actions.{name}", "missing")
            break
    else:
        sig_delete = list(inspect.signature(actions.delete_project).parameters)
        sig_idem = list(inspect.signature(actions.create_project_with_idempotency).parameters)
        if sig_delete == ["db", "project_id"]:
            ok("actions.delete_project(db, project_id)")
        else:
            fail("actions.delete_project signature", f"got {sig_delete}")
        # create_project_with_idempotency: db, data, token, user_id, prototype_rounds
        if sig_idem[:4] == ["db", "data", "token", "user_id"]:
            ok("actions.create_project_with_idempotency(db, data, token, user_id, ...)")
        else:
            fail("create_project_with_idempotency signature", f"got {sig_idem}")

    print("\n── 3. 2 new fixtures are present ──")
    from scenario_contracts.lib import fixtures
    for name in ("seed_ai_conversation", "seed_creation_token"):
        if hasattr(fixtures, name):
            ok(f"fixtures.{name} present")
        else:
            fail(f"fixtures.{name}", "missing")

    print("\n── 4. All 5 scenarios load with metadata + release_gate tag + stable ──")
    import importlib
    for name in QA06_SCENARIOS:
        try:
            mod = importlib.import_module(f"scenario_contracts.contracts.{name}")
            for field in ("ID", "TITLE", "TAGS", "MATURITY", "WHY_IT_MATTERS"):
                if not hasattr(mod, field):
                    fail(f"{name} declares {field}", "missing")
                    break
            else:
                if "release_gate" not in mod.TAGS:
                    fail(f"{name} tagged release_gate", f"got {mod.TAGS}")
                elif mod.MATURITY != "stable":
                    fail(f"{name} MATURITY=='stable'", f"got {mod.MATURITY!r}")
                else:
                    ok(f"{name} declares 5 metadata + release_gate + stable")
        except Exception as exc:
            fail(f"{name} import", str(exc))

    print("\n── 5. Each scenario PASSes via subprocess ──")
    for name in QA06_SCENARIOS:
        code, out = run_runner(f"scenario_contracts/contracts/{name}.py")
        if code == 0 and "PASS: 1" in out:
            ok(f"{name} — runner exit 0 with PASS: 1")
        else:
            fail(f"{name} live", f"exit={code}; out: {out[-400:]}")

    print("\n── 6. --tag release_gate aggregates 15 PASS ──")
    code, out = run_runner("scenario_contracts/contracts/",
                           extra_args=["--tag", "release_gate"])
    if "PASS: 15" in out:
        ok("--tag release_gate shows 15 PASS (5 QA-02 + 4 QA-05 + 5 QA-06 + golden_pass)")
    else:
        fail("PASS: 15 aggregation",
             f"exit={code}; tail: {out[-400:]}")

    print("\n── 7. Discipline boundary holds for each scenario ──")
    for name in QA06_SCENARIOS:
        text = read(f"scenario_contracts/contracts/{name}.py")
        run_body = _extract_function_body(text, "run")
        check_body = _extract_function_body(text, "check")
        if run_body is None or check_body is None:
            fail(f"{name} discipline parse", "could not extract bodies")
            continue
        ok_flag = True
        # check() must use assertions.* and must NOT import app.*
        if "assertions." not in check_body:
            fail(f"{name} check() uses assertions.*", "no assertions.* call")
            ok_flag = False
        if re.search(r"^\s*from app\.", check_body, re.MULTILINE):
            fail(f"{name} check() boundary", "imports from app.*")
            ok_flag = False
        # run() must use actions.*; viewer_permission-style empty
        # run() is fine for static contracts but ours all use actions.
        if "actions." not in run_body and name != "project_delete_permission_boundary":
            fail(f"{name} run() uses actions.*", "no actions.* call")
            ok_flag = False
        if re.search(r"^\s*from app\.", run_body, re.MULTILINE):
            fail(f"{name} run() boundary", "imports from app.*")
            ok_flag = False
        if ok_flag:
            ok(f"{name} discipline boundary holds")

    print("\n── 8. SQLite FK enforcement is still wired in app/database.py ──")
    db_src = read("app/database.py")
    if "PRAGMA foreign_keys = ON" in db_src and "@event.listens_for" in db_src:
        ok("app/database.py still installs the SQLite FK enforcement listener")
    else:
        fail("SQLite FK enforcement listener",
             "missing — Marine-bug scenario would silently stop catching regressions")

    print("\n── 9. app/* untouched ──")
    from app.version import CURRENT_VERSION
    if CURRENT_VERSION == "1.4.0":
        ok("app/version.py CURRENT_VERSION == '1.4.0' (QA-06 did not bump it)")
    else:
        fail("app/version.py untouched", f"got {CURRENT_VERSION!r}")

    print("\n── 10. lib/runner.py LOC budget unchanged ──")
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
