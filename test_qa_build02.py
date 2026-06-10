"""QA Build 02 — First 5 hard contract scenarios proof.

Verifies the 5 release-gate scenarios pass deterministically and that each
preserves the discipline boundary (run() uses only actions.*, check() uses
only assertions.*).

Run: python3 test_qa_build02.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

PASS, FAIL = [], []

SCENARIOS = [
    "pm_project_ownership",
    "viewer_permission_boundaries",
    "variant_pricing_isolation",
    "timeline_delay_reason_audit",
    "sandbox_apply_invariant",
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


def run_runner(scenario_path):
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
    print("\n── 1. QA Build 02 execution plan exists and lists the 5 scenarios ──")
    plan = read("QA_BUILD02_EXECUTION_PLAN.md")
    contains_all("plan lists all 5 scenarios", plan,
                 [f"{name}.py" for name in SCENARIOS])
    contains_all("plan locks discipline boundary", plan,
                 ["`actions.*`", "`assertions.*`", "User locks 7"])
    contains_all("plan lists the 4 new actions", plan,
                 ["create_project_for_pm", "create_variant",
                  "create_sandbox_from_template", "apply_sandbox"])
    contains_all("plan lists Backend Honesty Mapping rows", plan,
                 ["PM \"My Projects\" list", "Sandbox draft isolation",
                  "Phase due-date adjustment audit"])

    print("\n── 2. All 5 scenarios load with required metadata ──")
    sys.path.insert(0, str(ROOT))
    import importlib
    for name in SCENARIOS:
        module_path = f"scenario_contracts.contracts.{name}"
        try:
            mod = importlib.import_module(module_path)
            for field in ("ID", "TITLE", "TAGS", "MATURITY", "WHY_IT_MATTERS"):
                if not hasattr(mod, field):
                    fail(f"{name} declares {field}", "missing")
                    break
            else:
                if not callable(getattr(mod, "setup", None)):
                    fail(f"{name} declares setup()", "missing/non-callable")
                elif not callable(getattr(mod, "run", None)):
                    fail(f"{name} declares run()", "missing/non-callable")
                elif not callable(getattr(mod, "check", None)):
                    fail(f"{name} declares check()", "missing/non-callable")
                elif "release_gate" not in mod.TAGS:
                    fail(f"{name} tagged release_gate", f"got TAGS={mod.TAGS}")
                elif mod.MATURITY != "stable":
                    fail(f"{name} MATURITY=='stable'", f"got {mod.MATURITY!r}")
                else:
                    ok(f"{name} declares 5 metadata + 3 functions + release_gate + stable")
        except Exception as exc:
            fail(f"{name} import", str(exc))

    print("\n── 3. Each scenario passes via the runner subprocess ──")
    for name in SCENARIOS:
        path = f"scenario_contracts/contracts/{name}.py"
        code, out = run_runner(path)
        if code == 0 and "PASS: 1" in out and "FAIL: 0" in out:
            ok(f"{name} — runner exit 0 with PASS: 1")
        else:
            fail(f"{name} runner behavior",
                 f"exit={code}; out: {out[-400:]}")

    print("\n── 4. Directory mode confirms QA-02 scenarios passed ──")
    # Each of the 5 QA-02 scenarios must show as PASS. Other scenarios'
    # outcomes (UI, goldens) are owned by other QA builds — don't lock
    # exact totals here, just confirm QA-02's 5 are PASS.
    code, out = run_runner("scenario_contracts/contracts/")
    qa02_lines_ok = all(
        _line_contains_both(out, "PASS", f"{name}_001")
        for name in SCENARIOS
    )
    if qa02_lines_ok and code in (0, 1, 2):
        ok("directory mode — all 5 QA-02 scenarios show as PASS")
    else:
        fail("directory mode QA-02 scenarios",
             f"exit={code}; out: {out[-500:]}")

    print("\n── 5. Discipline boundary — run() uses actions.*; check() uses assertions.* ──")
    forbidden_in_run = [r"\bdb\.add\(", r"\bdb\.commit\(", r"^\s*from app\."]
    forbidden_in_check = [r"^\s*assert\s+", r"^\s*from app\."]
    for name in SCENARIOS:
        text = read(f"scenario_contracts/contracts/{name}.py")
        run_body = _extract_function_body(text, "run")
        check_body = _extract_function_body(text, "check")
        if run_body is None or check_body is None:
            fail(f"{name} discipline parse", "could not parse run/check bodies")
            continue
        violations = []
        for pattern in forbidden_in_run:
            if re.search(pattern, run_body, re.MULTILINE):
                violations.append(f"run() contains {pattern!r}")
        for pattern in forbidden_in_check:
            if re.search(pattern, check_body, re.MULTILINE):
                violations.append(f"check() contains {pattern!r}")
        # Positive: run must call actions.*; check must call assertions.*
        if "actions." not in run_body:
            # The viewer scenario has an effectively empty run(); allow that.
            if name != "viewer_permission_boundaries":
                violations.append("run() does not call any actions.*")
        if "assertions." not in check_body:
            violations.append("check() does not call any assertions.*")
        if violations:
            fail(f"{name} discipline boundary", "; ".join(violations))
        else:
            ok(f"{name} discipline boundary holds")

    print("\n── 6. Library extensions are present ──")
    actions_src = read("scenario_contracts/lib/actions.py")
    contains_all("actions.py has QA-02 helpers", actions_src,
                 ["create_project_for_pm", "create_variant",
                  "create_sandbox_from_template", "apply_sandbox",
                  "snapshot_table_count"])
    assertions_src = read("scenario_contracts/lib/assertions.py")
    contains_all("assertions.py has QA-02 helpers", assertions_src,
                 ["assert_project_visible_to_user",
                  "assert_project_not_visible_to_user",
                  "assert_permission",
                  "assert_phase_field",
                  "assert_phase_plan_change_recorded",
                  "assert_no_rows",
                  "assert_equal"])
    fixtures_src = read("scenario_contracts/lib/fixtures.py")
    contains_all("fixtures.py has QA-02 helpers", fixtures_src,
                 ["create_project_with_costs"])

    print("\n── 7. app/* untouched (no version bump) ──")
    from app.version import CURRENT_VERSION
    if CURRENT_VERSION == "1.4.0":
        ok("app/version.py CURRENT_VERSION == '1.4.0' (QA-02 did not bump it)")
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
    """Extract the body of `def func_name(...)` until the next top-level def
    or EOF. Returns None if not found."""
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
