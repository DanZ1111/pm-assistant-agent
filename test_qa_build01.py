"""QA Build 01 — PM Scenario Contract Runner Skeleton + Golden Tests proof.

Verifies the runner enforces the 10 user locks from the approved plan and
behaves correctly for the 5 golden scenarios.

Run: python3 test_qa_build01.py
"""
from __future__ import annotations

import os
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
    """Invoke the runner as a CLI subprocess. Returns (exit_code, stdout)."""
    result = subprocess.run(
        [sys.executable, "-m", "scenario_contracts.lib.runner", str(scenario_path)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    return result.returncode, result.stdout + result.stderr


def _line_contains_both(text_value, *needles):
    for line in text_value.splitlines():
        if all(needle in line for needle in needles):
            return True
    return False


def main():
    print("\n── 1. QA Build 01 execution plan exists and locks user locks ──")
    plan = read("QA_BUILD01_EXECUTION_PLAN.md")
    contains_all("plan §Status mentions predecessor v1.4.0", plan,
                 ["v1.4.0 release hardening"])
    contains_all("plan locks 5 metadata fields", plan,
                 ["ID", "TITLE", "TAGS", "MATURITY", "WHY_IT_MATTERS"])
    contains_all("plan locks 3 required functions", plan,
                 ["setup(db)", "run(world, http)", "check(db, world)"])
    contains_all("plan locks discipline boundary", plan,
                 ["User lock 9", "`actions.*`", "`assertions.*`"])
    contains_all("plan locks small runner target", plan, ["<300 LOC"])
    contains_all("plan locks exit codes", plan,
                 ["exit code 2", "assertion fail", "config error"])

    print("\n── 2. scenario_contracts package is importable ──")
    try:
        import scenario_contracts  # noqa
        import scenario_contracts.lib.runner as runner_mod
        import scenario_contracts.lib.fixtures as fixtures_mod  # noqa
        import scenario_contracts.lib.actions as actions_mod  # noqa
        import scenario_contracts.lib.assertions as assertions_mod  # noqa
        import scenario_contracts.lib.reporter as reporter_mod  # noqa
        ok("scenario_contracts.lib.* all import")
    except Exception as exc:
        fail("scenario_contracts.lib.* import", str(exc))

    print("\n── 3. Runner stays small (User lock 4: <300 LOC) ──")
    runner_path = ROOT / "scenario_contracts" / "lib" / "runner.py"
    line_count = len(runner_path.read_text().splitlines())
    if line_count < 300:
        ok(f"runner.py is {line_count} LOC (<300)")
    else:
        fail("runner.py LOC budget", f"{line_count} LOC >= 300")

    print("\n── 4. Each golden scenario declares 5 metadata + 3 functions ──")
    contracts_dir = ROOT / "scenario_contracts" / "contracts"
    goldens = sorted(p for p in contracts_dir.glob("golden_*.py"))
    if len(goldens) != 5:
        fail("5 golden scenarios exist", f"found {len(goldens)}")
    else:
        ok("5 golden scenarios exist")

    for golden in goldens:
        text = golden.read_text()
        name = golden.stem
        # Each scenario must declare ID + TITLE + TAGS + MATURITY at minimum.
        # WHY_IT_MATTERS is missing on purpose for one of them.
        for field in ("ID", "TITLE", "TAGS", "MATURITY"):
            if f"{field} =" not in text:
                fail(f"{name} declares {field}", "field not found")
                break
        else:
            ok(f"{name} declares ID/TITLE/TAGS/MATURITY")

    print("\n── 5. Runner enforces metadata + shape (User locks 7, 8) ──")
    # 5a — golden_pass behaves as PASS, exit 0
    code, out = run_runner("scenario_contracts/contracts/golden_pass.py")
    if code == 0 and "PASS: 1" in out and "FAIL: 0" in out:
        ok("golden_pass — exit 0, PASS: 1")
    else:
        fail("golden_pass behavior", f"exit={code}; out: {out[-300:]}")

    # 5b — golden_db_fail behaves as FAIL, exit 1, structured diff visible
    code, out = run_runner("scenario_contracts/contracts/golden_db_fail.py")
    if code == 1 and "FAIL: 1" in out and "expected 5, got 1" in out:
        ok("golden_db_fail — exit 1 with structured expected/actual diff")
    else:
        fail("golden_db_fail behavior", f"exit={code}; out: {out[-300:]}")

    # 5c — golden_ui_fail behavior moved to QA-03. QA-01's contract for
    # this scenario is just "the runner doesn't crash on a ui-tagged file".
    # The runner either SKIPs (Playwright/server unavailable) or FAILs
    # intentionally (QA-03 flipped it to a real UI failure). Either is
    # acceptable for QA-01's purposes.
    code, out = run_runner("scenario_contracts/contracts/golden_ui_fail.py")
    if code in (0, 1) and ("SKIP: 1" in out or "FAIL: 1" in out):
        ok("golden_ui_fail — runner handled ui scenario without crashing (SKIP or FAIL)")
    else:
        fail("golden_ui_fail behavior", f"exit={code}; out: {out[-300:]}")

    # 5d — golden_invalid_shape rejected as INVALID, exit 2
    code, out = run_runner("scenario_contracts/contracts/golden_invalid_shape.py")
    if code == 2 and "INVALID: 1" in out and "missing check()" in out:
        ok("golden_invalid_shape — exit 2 with 'missing check()' reason")
    else:
        fail("golden_invalid_shape behavior", f"exit={code}; out: {out[-300:]}")

    # 5e — golden_missing_metadata rejected as INVALID, exit 2
    code, out = run_runner("scenario_contracts/contracts/golden_missing_metadata.py")
    if code == 2 and "INVALID: 1" in out and "missing WHY_IT_MATTERS" in out:
        ok("golden_missing_metadata — exit 2 with 'missing WHY_IT_MATTERS' reason")
    else:
        fail("golden_missing_metadata behavior", f"exit={code}; out: {out[-300:]}")

    print("\n── 6. Directory mode runs all goldens with correct outcomes ──")
    # Directory mode discovers all scenarios in contracts/. QA-01's
    # contract covers the 4 non-UI goldens — their outcomes are
    # environment-independent. The ui golden moved to QA-03's contract.
    code, out = run_runner("scenario_contracts/contracts/")
    expected_lines = [
        ("PASS", "golden_pass_001"),
        ("FAIL", "golden_db_fail_001"),
        ("INVALID", "golden_invalid_shape_001"),
        ("INVALID", "golden_missing_metadata_001"),
    ]
    missing = [
        f"{outcome} {sid}"
        for outcome, sid in expected_lines
        if not _line_contains_both(out, outcome, sid)
    ]
    if code == 2 and not missing:
        ok("directory mode — 4 QA-01 goldens behave as designed; exit 2 (invalid > fail > pass)")
    else:
        fail("directory mode aggregation",
             f"exit={code}; missing={missing}; tail: {out[-300:]}")

    print("\n── 7. Reports directory exists and is gitignored ──")
    reports_dir = ROOT / "scenario_contracts" / "reports"
    if reports_dir.exists() and reports_dir.is_dir():
        ok("reports/ directory exists")
    else:
        fail("reports/ directory", "not created")
    gitignore = read(".gitignore")
    if "scenario_contracts/reports/" in gitignore:
        ok("reports/ listed in .gitignore")
    else:
        fail(".gitignore", "scenario_contracts/reports/ not listed")

    print("\n── 8. Runner refuses to run when given a missing file ──")
    code, out = run_runner("scenario_contracts/contracts/does_not_exist.py")
    # Missing file is a config error → exit 2
    if code == 2 and "INVALID" in out:
        ok("missing-file path — exit 2 INVALID")
    else:
        fail("missing-file behavior", f"exit={code}; out: {out[-200:]}")

    print("\n── 9. Existing per-build tests still importable (app version supported) ──")
    # Sanity: the QA series originally launched on v1.4.0. Later product
    # releases are valid as long as they remain compatible with the QA suite.
    from app.version import CURRENT_VERSION
    from scenario_contracts.lib.version_compat import app_version_at_least
    if app_version_at_least(CURRENT_VERSION, "1.4.0"):
        ok(f"app/version.py CURRENT_VERSION {CURRENT_VERSION!r} is >= '1.4.0'")
    else:
        fail("app/version.py version compatibility", f"got {CURRENT_VERSION!r}; expected >= '1.4.0'")

    print(f"\nPassed: {len(PASS)} / {len(PASS) + len(FAIL)}")
    if FAIL:
        print("FAILED:")
        for name, reason in FAIL:
            print(f"  - {name}: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
