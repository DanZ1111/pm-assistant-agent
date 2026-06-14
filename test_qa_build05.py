"""QA Build 05 — Mocked AI library + 4 confirmation-required contracts proof.

Verifies that the CLAUDE.md non-negotiable
("AI never writes directly to the database without user confirmation")
is locked at dispatch level for all 4 critical intake paths.

Run: python3 test_qa_build05.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

PASS, FAIL = [], []

QA05_SCENARIOS = [
    "ai_proposes_idea",
    "ai_proposes_journal",
    "ai_proposes_due_date_shift",
    "ai_proposes_blocker",
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


def _line_contains_both(text_value, *needles):
    for line in text_value.splitlines():
        if all(needle in line for needle in needles):
            return True
    return False


def main():
    print("\n── 1. QA Build 05 plan exists and locks the dispatch-level decision ──")
    plan = read("QA_BUILD05_EXECUTION_PLAN.md")
    contains_all("plan lists all 4 AI contracts", plan,
                 [f"{name}.py" for name in QA05_SCENARIOS])
    contains_all("plan locks dispatch-level scope", plan,
                 ["app.ai.tools.dispatch", "CONFIRMATION_TOOLS",
                  "Dispatch-level only", "deferred to QA-05b"])
    contains_all("plan locks the 3-path coverage", plan,
                 ["unconfirmed", "confirmed", "viewer", "release_gate"])

    print("\n── 2. lib/fake_ai.py exposes the queue-driven API ──")
    from scenario_contracts.lib import fake_ai
    for sym in ("FakeOpenAIClient", "_FakeChat", "_FakeCompletions",
                "_FakeResponse", "install"):
        if not hasattr(fake_ai, sym):
            fail(f"fake_ai.{sym}", "missing")
            break
    else:
        client = fake_ai.FakeOpenAIClient()
        if (
            hasattr(client.chat.completions, "queue_text")
            and hasattr(client.chat.completions, "queue_tool_call")
        ):
            ok("fake_ai: FakeOpenAIClient + queue_text + queue_tool_call all present")
        else:
            fail("fake_ai queue API", "missing queue_text or queue_tool_call")

    print("\n── 3. fake_ai queue behavior round-trips ──")
    import json as _json
    client = fake_ai.FakeOpenAIClient()
    client.chat.completions.queue_tool_call(
        "create_idea", {"name": "test idea"}, follow_text="Proposing.")
    response = client.chat.completions.create()
    if (
        response.choices
        and response.choices[0].message.tool_calls
        and response.choices[0].message.tool_calls[0].function.name == "create_idea"
    ):
        args = _json.loads(
            response.choices[0].message.tool_calls[0].function.arguments)
        if args.get("name") == "test idea":
            ok("queued tool call round-trips name + JSON-encoded args")
        else:
            fail("queue_tool_call args round-trip", f"got {args}")
    else:
        fail("queue_tool_call shape", "tool_calls not present")

    print("\n── 4. actions.ai_dispatch exists with the expected signature ──")
    from scenario_contracts.lib import actions
    if hasattr(actions, "ai_dispatch"):
        import inspect
        params = list(inspect.signature(actions.ai_dispatch).parameters)
        if params == ["db", "tool_name", "args", "user", "confirmed"]:
            ok("actions.ai_dispatch(db, tool_name, args, user, confirmed)")
        else:
            fail("ai_dispatch signature", f"got {params}")
    else:
        fail("actions.ai_dispatch", "missing")

    print("\n── 5. assertions.assert_dispatch_* exist ──")
    from scenario_contracts.lib import assertions
    for sym in ("assert_dispatch_required_confirmation",
                "assert_dispatch_succeeded",
                "assert_dispatch_blocked"):
        if not hasattr(assertions, sym):
            fail(f"assertions.{sym}", "missing")
            break
    else:
        ok("assertions has the 3 dispatch-result helpers")

    print("\n── 6. All 4 scenarios load with the right metadata ──")
    import importlib
    for name in QA05_SCENARIOS:
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

    print("\n── 7. Each scenario PASSes via subprocess ──")
    for name in QA05_SCENARIOS:
        code, out = run_runner(f"scenario_contracts/contracts/{name}.py")
        if code == 0 and "PASS: 1" in out:
            ok(f"{name} — runner exit 0 with PASS: 1")
        else:
            fail(f"{name} live", f"exit={code}; out: {out[-400:]}")

    print("\n── 8. --tag release_gate aggregates QA-05's 4 contracts ──")
    # The 4 QA-05 scenarios must show as PASS regardless of how many
    # release_gate scenarios exist overall. Other QA builds add more
    # release_gate scenarios over time — don't pin the exact total here.
    code, out = run_runner("scenario_contracts/contracts/",
                           extra_args=["--tag", "release_gate"])
    qa05_ok = all(
        _line_contains_both(out, "PASS", f"{name}_001")
        for name in QA05_SCENARIOS
    )
    if qa05_ok:
        ok("--tag release_gate shows all 4 QA-05 AI contracts as PASS")
    else:
        fail("QA-05 contracts under --tag release_gate",
             f"exit={code}; tail: {out[-400:]}")

    print("\n── 9. Discipline boundary holds for each scenario ──")
    for name in QA05_SCENARIOS:
        text = read(f"scenario_contracts/contracts/{name}.py")
        run_body = _extract_function_body(text, "run")
        check_body = _extract_function_body(text, "check")
        if run_body is None or check_body is None:
            fail(f"{name} discipline parse", "could not extract bodies")
            continue
        ok_flag = True
        if "actions." not in run_body:
            fail(f"{name} run() uses actions.*", "no actions.* call")
            ok_flag = False
        if "assertions." not in check_body:
            fail(f"{name} check() uses assertions.*", "no assertions.* call")
            ok_flag = False
        if re.search(r"^\s*from app\.", run_body, re.MULTILINE):
            fail(f"{name} run() boundary", "imports from app.*")
            ok_flag = False
        if re.search(r"^\s*from app\.", check_body, re.MULTILINE):
            fail(f"{name} check() boundary", "imports from app.*")
            ok_flag = False
        if ok_flag:
            ok(f"{name} discipline boundary holds")

    print("\n── 10. The dispatch contract: viewer is rejected before handler ──")
    # Smoke at unit level (not via runner) — confirms the dispatch path.
    from scenario_contracts.lib import fixtures
    from app.ai.tools import dispatch
    tmp, engine, Session = fixtures.build_db()
    try:
        db = Session()
        viewer = fixtures.create_user(db, "qa05_viewer", role="viewer")
        project = fixtures.create_project(db, "QA-05 dispatch unit",
                                          pm_name="qa05_viewer")
        result = dispatch(
            "create_blocker",
            {"project_id": project.id, "title": "Test"},
            db, viewer, confirmed=False,
        )
        if (
            isinstance(result, dict)
            and result.get("ok") is False
            and result.get("error") == "forbidden"
        ):
            ok("dispatch returns forbidden for viewer (role check runs before confirmation guard)")
        else:
            fail("viewer dispatch result", f"got {result}")
        db.close()
    finally:
        engine.dispose()
        tmp.cleanup()

    print("\n── 11. app version supported by QA contracts ──")
    from app.version import CURRENT_VERSION
    from scenario_contracts.lib.version_compat import app_version_at_least
    if app_version_at_least(CURRENT_VERSION, "1.4.0"):
        ok(f"app/version.py CURRENT_VERSION {CURRENT_VERSION!r} is >= '1.4.0'")
    else:
        fail("app/version.py version compatibility", f"got {CURRENT_VERSION!r}; expected >= '1.4.0'")

    print("\n── 12. lib/runner.py LOC budget unchanged ──")
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
