"""QA Build 10 — Coverage assistant + suite runners + stable-credibility rule.

The final QA build. Verifies:
- The 4 operational tools exist and behave:
  - run_qa_suite.sh
  - run_qa_loop.sh
  - scenario_contracts/coverage.py
  - candidates/ scaffolding
- STABLE_CREDIBILITY.md locks the 3-tier promotion rule.
- The stable-promotion LINTER: every MATURITY="stable" scenario has
  release_gate in TAGS AND a WHY_IT_MATTERS string of >= 80 chars.
  This is the structural half of the promotion contract (the
  consecutive-runs half is documented, not auto-enforced — see
  STABLE_CREDIBILITY.md for why).

Run: python3 test_qa_build10.py
"""
from __future__ import annotations

import ast
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


def main():
    print("\n── 1. QA-10 plan exists and locks the 6 deliverables ──")
    plan = read("QA_BUILD10_EXECUTION_PLAN.md")
    contains_all("plan lists the 6 deliverables", plan,
                 ["run_qa_suite.sh", "run_qa_loop.sh",
                  "scenario_contracts/coverage.py",
                  "STABLE_CREDIBILITY.md",
                  "candidates/", "test_qa_build10.py"])
    contains_all("plan locks the no-live-LLM stance", plan,
                 ["No live LLM",
                  "offline", "Lock 5"])

    print("\n── 2. The 4 operational files exist ──")
    expected_files = [
        ("run_qa_suite.sh", True),
        ("run_qa_loop.sh", True),
        ("scenario_contracts/coverage.py", False),
        ("STABLE_CREDIBILITY.md", False),
        ("scenario_contracts/candidates/__init__.py", False),
    ]
    for relpath, must_be_exec in expected_files:
        p = ROOT / relpath
        if not p.exists():
            fail(f"{relpath} exists", "missing")
            continue
        if must_be_exec:
            import os
            if os.access(p, os.X_OK):
                ok(f"{relpath} present and executable")
            else:
                fail(f"{relpath} executable", "not chmod +x")
        else:
            ok(f"{relpath} present")

    print("\n── 3. coverage.py runs and emits a non-empty gap list ──")
    result = subprocess.run(
        [sys.executable, "scenario_contracts/coverage.py"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if result.returncode == 0 and "QA Coverage Gap Analyzer" in result.stdout:
        # Must emit at least one specific suggestion line ("  - app.crud.<X>"
        # or "  - <ai_tool_name>"). We just assert any "  - " bullet.
        if re.search(r"\n  - \S", result.stdout):
            ok("coverage.py — exit 0, gap analyzer output non-empty")
        else:
            fail("coverage.py output shape",
                 f"exit 0 but no '  - ' suggestions; stdout: {result.stdout[-300:]}")
    else:
        fail("coverage.py exit",
             f"code={result.returncode}; stderr: {result.stderr[-300:]}")

    print("\n── 4. coverage.py --json emits parseable JSON ──")
    result = subprocess.run(
        [sys.executable, "scenario_contracts/coverage.py", "--json"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    import json as _json
    try:
        report = _json.loads(result.stdout)
        if "crud" in report and "ai_tools" in report:
            ok("coverage.py --json — valid JSON with crud + ai_tools keys")
        else:
            fail("coverage.py --json shape",
                 f"got keys: {list(report.keys())}")
    except Exception as exc:
        fail("coverage.py --json parse", str(exc))

    print("\n── 5. STABLE_CREDIBILITY.md locks the 3-tier rule ──")
    sc = read("STABLE_CREDIBILITY.md")
    contains_all("STABLE_CREDIBILITY names the 3 tiers", sc,
                 ["`experimental`", "`candidate`", "`stable`"])
    contains_all("STABLE_CREDIBILITY locks the 10-runs threshold", sc,
                 ["10 consecutive green runs", "run_qa_loop.sh 10"])
    contains_all("STABLE_CREDIBILITY references release_gate + WHY_IT_MATTERS", sc,
                 ["release_gate", "WHY_IT_MATTERS", "80\n     characters"])

    print("\n── 6. Promotion-rule linter — every MATURITY=stable scenario passes ──")
    # Walk contracts/ and journeys/; for each scenario file, AST-parse
    # to read MATURITY / TAGS / WHY_IT_MATTERS literals. Any scenario
    # claiming MATURITY="stable" MUST have:
    #   - "release_gate" in TAGS
    #   - WHY_IT_MATTERS length >= 80
    failures = []
    for sub in ("contracts", "journeys"):
        base = ROOT / "scenario_contracts" / sub
        for p in base.glob("*.py"):
            if p.name == "__init__.py":
                continue
            try:
                tree = ast.parse(p.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                failures.append((p.name, f"syntax: {exc}"))
                continue
            maturity = None
            tags = None
            why = None
            for node in tree.body:
                if not isinstance(node, ast.Assign):
                    continue
                for target in node.targets:
                    if not isinstance(target, ast.Name):
                        continue
                    if target.id == "MATURITY" and isinstance(node.value, ast.Constant):
                        maturity = node.value.value
                    elif target.id == "TAGS":
                        if isinstance(node.value, ast.List):
                            tags = [
                                e.value for e in node.value.elts
                                if isinstance(e, ast.Constant)
                            ]
                    elif target.id == "WHY_IT_MATTERS":
                        # Either a single Constant or a Constant.join or
                        # a parenthesized concatenation that ast.literal_eval
                        # can handle.
                        try:
                            why = ast.literal_eval(node.value)
                        except Exception:
                            pass
            if maturity == "stable":
                if not tags or "release_gate" not in tags:
                    failures.append((p.name, "stable but no release_gate tag"))
                if not isinstance(why, str) or len(why) < 80:
                    why_len = len(why) if isinstance(why, str) else "n/a"
                    failures.append(
                        (p.name, f"stable but WHY_IT_MATTERS too short (len={why_len}, min=80)"))
    if failures:
        for name, reason in failures:
            fail(f"stable linter — {name}", reason)
    else:
        ok("every MATURITY='stable' scenario meets the linter contract")

    print("\n── 7. run_qa_suite.sh passes bash syntax check + references all tests ──")
    # Don't actually run the suite from inside this test — it would
    # take ~10 minutes (it runs the marathon + all individual tests).
    # Humans run `bash run_qa_suite.sh` directly; this test verifies the
    # script is well-formed and references every test_qa_buildNN.py.
    result = subprocess.run(
        ["bash", "-n", "run_qa_suite.sh"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if result.returncode == 0:
        ok("run_qa_suite.sh — bash -n syntax check passes")
    else:
        fail("run_qa_suite.sh syntax",
             f"stderr: {result.stderr[-300:]}")
    suite_src = read("run_qa_suite.sh")
    contains_all("suite references test_qa_build*.py + journeys + release_gate",
                 suite_src,
                 ["test_qa_build*.py", "journeys", "release_gate"])

    print("\n── 8. run_qa_loop.sh passes syntax check + arg validation ──")
    result = subprocess.run(
        ["bash", "-n", "run_qa_loop.sh"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if result.returncode == 0:
        ok("run_qa_loop.sh — bash -n syntax check passes")
    else:
        fail("run_qa_loop.sh syntax",
             f"stderr: {result.stderr[-300:]}")
    # Arg validation: invalid N (not a number) → exit 2.
    result = subprocess.run(
        ["bash", "run_qa_loop.sh", "notanumber"],
        capture_output=True, text=True, cwd=str(ROOT),
        timeout=10,
    )
    if result.returncode == 2:
        ok("run_qa_loop.sh — rejects non-numeric N with exit 2")
    else:
        fail("run_qa_loop.sh arg validation",
             f"got exit={result.returncode}")
    loop_src = read("run_qa_loop.sh")
    contains_all("loop runner references flakiness + json report", loop_src,
                 ["flaky", "json", "n_runs"])

    print("\n── 9. app/* untouched ──")
    from app.version import CURRENT_VERSION
    if CURRENT_VERSION == "1.4.0":
        ok("app/version.py CURRENT_VERSION == '1.4.0' (QA-10 did not bump it)")
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


if __name__ == "__main__":
    sys.exit(main())
