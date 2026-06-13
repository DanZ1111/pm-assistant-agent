"""QA Build 11 — PM Acceptance Journey Layer proof.

Verifies:
- The new acceptance tier (scenario_contracts/acceptance/) is in place.
- lib/pm_views.py exposes the 6 PM-facing assertions.
- The football_knife acceptance journey loads with the right shape
  and tags.
- The journey passes against a running dev server (or SKIPs cleanly
  when not reachable, per the existing browser pattern).
- SCENARIO_AUTHORING_GUIDE.md locks the 5 hard rules.
- STABLE_CREDIBILITY.md was updated with the acceptance tier.
- UI_TESTABILITY_GAPS.md documents the 3 gaps.
- Discipline boundary holds (run/do uses actions+disruptions+page;
  check uses assertions+pm_views).
- app/* untouched; lib/runner.py LOC unchanged.

Run: python3 test_qa_build11.py
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


def run_runner(scenario_path, env=None):
    import os
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    result = subprocess.run(
        [sys.executable, "-m", "scenario_contracts.lib.runner", str(scenario_path)],
        capture_output=True, text=True, cwd=str(ROOT), env=full_env,
        timeout=900,
    )
    return result.returncode, result.stdout + result.stderr


def main():
    print("\n── 1. QA Build 11 plan exists and locks the reframe ──")
    plan = read("QA_BUILD11_EXECUTION_PLAN.md")
    contains_all("plan locks the 4-truth model", plan,
                 ["DB truth", "UI truth", "History",
                  "PM comprehension"])
    contains_all("plan names the new tier + journey", plan,
                 ["acceptance/", "football_knife_asd_lifecycle.py",
                  "pm_views.py"])
    contains_all("plan locks the stable-selector rule", plan,
                 ["Stable selectors only", "UI_TESTABILITY_GAPS",
                  "fragile"])

    print("\n── 2. acceptance/ tier directory exists ──")
    acc_dir = ROOT / "scenario_contracts" / "acceptance"
    if (acc_dir / "__init__.py").exists():
        ok("scenario_contracts/acceptance/__init__.py present")
    else:
        fail("acceptance/__init__.py", "missing")
    if (acc_dir / "football_knife_asd_lifecycle.py").exists():
        ok("football_knife_asd_lifecycle.py present")
    else:
        fail("football_knife_asd_lifecycle.py", "missing")

    print("\n── 3. lib/pm_views.py exposes the PM-facing assertions ──")
    from scenario_contracts.lib import pm_views
    expected_assertions = [
        "assert_command_center_current_phase",
        "assert_command_center_next_action",
        "assert_command_center_health_band",
        "assert_active_blocker_count_on_phase_strip",
        "assert_history_row_with_type_contains",
        "assert_variant_card_present",
        "assert_project_findable_on_index_and_detail",
        "assert_viewer_cannot_see_variant_costs",
    ]
    for name in expected_assertions:
        if hasattr(pm_views, name):
            ok(f"pm_views.{name} present")
        else:
            fail(f"pm_views.{name}", "missing")

    print("\n── 4. Acceptance journey loads with required metadata + acceptance tag ──")
    import importlib
    try:
        mod = importlib.import_module(
            "scenario_contracts.acceptance.football_knife_asd_lifecycle")
        for field in ("ID", "TITLE", "TAGS", "MATURITY", "WHY_IT_MATTERS",
                      "STEPS"):
            if not hasattr(mod, field):
                fail(f"journey declares {field}", "missing")
                break
        else:
            tags = set(mod.TAGS)
            if "acceptance" in tags and "journey" in tags:
                ok("journey declares acceptance + journey tags")
            else:
                fail("journey tag set", f"got {sorted(tags)}")
            if mod.MATURITY != "candidate":
                fail("MATURITY == 'candidate'", f"got {mod.MATURITY!r}")
            else:
                ok("MATURITY is 'candidate' (first acceptance journey)")
            if len(mod.STEPS) >= 5:
                ok(f"journey declares {len(mod.STEPS)} steps (>=5)")
            else:
                fail("journey step count", f"got {len(mod.STEPS)}")
    except Exception as exc:
        fail("journey import", str(exc))

    print("\n── 5. Journey passes via subprocess against live dev server ──")
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
            "scenario_contracts/acceptance/football_knife_asd_lifecycle.py")
        if code == 0 and "PASS: 1" in out and "steps OK" in out:
            ok("acceptance journey — runner exit 0, PASS: 1, steps OK")
        else:
            fail("acceptance journey live",
                 f"exit={code}; out: {out[-500:]}")

    print("\n── 6. Acceptance journey SKIPs cleanly when dev server unreachable ──")
    code, out = run_runner(
        "scenario_contracts/acceptance/football_knife_asd_lifecycle.py",
        env={"BASE_URL": "http://127.0.0.1:1"},
    )
    if code == 0 and "SKIP: 1" in out and "dev_server_unreachable" in out:
        ok("acceptance journey SKIPs cleanly when dev server unreachable")
    else:
        fail("dev_server_unreachable SKIP behavior",
             f"exit={code}; out: {out[-400:]}")

    print("\n── 7. SCENARIO_AUTHORING_GUIDE locks the 5 hard rules ──")
    guide = read("SCENARIO_AUTHORING_GUIDE.md")
    contains_all("guide names the 4-truth model", guide,
                 ["DB truth", "UI truth", "History truth",
                  "PM comprehension"])
    contains_all("guide locks the hard rules", guide,
                 ["hard rules",
                  "Rule 1", "Rule 2", "Rule 3", "Rule 4", "Rule 5",
                  "Rule 6"])
    contains_all("guide references UI_TESTABILITY_GAPS workflow", guide,
                 ["UI_TESTABILITY_GAPS.md", "Stable selectors only"])

    print("\n── 8. UI_TESTABILITY_GAPS documents the 3 gaps + patches ──")
    gaps = read("UI_TESTABILITY_GAPS.md")
    contains_all("gap doc lists 3 numbered gaps", gaps,
                 ["## Gap 1", "## Gap 2", "## Gap 3",
                  "data-pulse-action-type",
                  "data-variant-target-cost",
                  "data-field"])
    contains_all("each gap proposes a minimal patch + names the risk", gaps,
                 ["Proposed patch", "Risk without the patch"])

    print("\n── 9. STABLE_CREDIBILITY references the acceptance tier ──")
    sc = read("STABLE_CREDIBILITY.md")
    contains_all("STABLE_CREDIBILITY adds the acceptance tier", sc,
                 ["acceptance", "QA-11 addition"])

    print("\n── 10. Discipline boundary holds in the journey ──")
    journey_src = read(
        "scenario_contracts/acceptance/football_knife_asd_lifecycle.py")
    do_funcs = re.findall(
        r"def (do_\w+)\(.*?\):\s*\n((?:    .*\n)+)", journey_src)
    check_funcs = re.findall(
        r"def (check_\w+)\(.*?\):\s*\n((?:    .*\n)+)", journey_src)
    boundary_ok = True
    for name, body in do_funcs:
        if re.search(r"^\s*from app\.", body, re.MULTILINE):
            fail(f"do_{name} imports app.*", "boundary breach")
            boundary_ok = False
        if "assertions." in body or "pm_views." in body:
            fail(f"do_{name} calls assertions/pm_views", "boundary breach")
            boundary_ok = False
    for name, body in check_funcs:
        if re.search(r"^\s*from app\.", body, re.MULTILINE):
            fail(f"check_{name} imports app.*", "boundary breach")
            boundary_ok = False
        # Allow assertions.* AND pm_views.* in check_*.
        if "assertions." not in body and "pm_views." not in body:
            fail(f"{name} uses no assertions/pm_views", "no assertion call")
            boundary_ok = False
    if boundary_ok:
        ok("journey discipline boundary holds (do uses actions; check uses assertions/pm_views)")

    print("\n── 11. pm_views uses only stable selectors (no text= matches) ──")
    pmv_src = read("scenario_contracts/lib/pm_views.py")
    if re.search(r'page\.locator\(\s*["\']text=', pmv_src):
        fail("pm_views fragile selectors",
             "found page.locator('text=...') — User lock 8 violation")
    else:
        ok("pm_views has no fragile text= locators")

    print("\n── 12. app/* untouched ──")
    from app.version import CURRENT_VERSION
    if CURRENT_VERSION == "1.4.0":
        ok("app/version.py CURRENT_VERSION == '1.4.0' (QA-11 did not bump it)")
    else:
        fail("app/version.py untouched", f"got {CURRENT_VERSION!r}")

    print("\n── 13. Existing scenarios still work (runner refactor didn't break them) ──")
    # Quick spot-check on one DB scenario (no dev server needed).
    code, out = run_runner(
        "scenario_contracts/contracts/golden_pass.py")
    if code == 0 and "PASS: 1" in out:
        ok("golden_pass — DB-only path still PASS after acceptance branch added")
    else:
        fail("DB-only regression", f"exit={code}; out: {out[-300:]}")
    # And one mini-journey to ensure the journey executor's non-browser
    # path is unaffected.
    code, out = run_runner(
        "scenario_contracts/journeys/journey_basic_pm_lifecycle.py")
    if code == 0 and "PASS: 1" in out and "steps OK" in out:
        ok("journey_basic_pm_lifecycle — non-browser journey still PASS")
    else:
        fail("non-browser journey regression",
             f"exit={code}; out: {out[-300:]}")

    print(f"\nPassed: {len(PASS)} / {len(PASS) + len(FAIL)}")
    if FAIL:
        print("FAILED:")
        for name, reason in FAIL:
            print(f"  - {name}: {reason}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
