"""PM Scenario Contract runner.

Deterministic execution of one scenario file or a directory of them.

User locks enforced here:
- Lock 7: every scenario must declare ID, TITLE, TAGS, MATURITY, WHY_IT_MATTERS.
- Lock 8: every scenario must define setup, run, check.
- Lock 4: keep this file small — target <300 LOC.

Exit codes:
  0  all scenarios passed
  1  at least one assertion failed
  2  at least one scenario was malformed (config error)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scenario_contracts.lib import executors, reporter
from scenario_contracts.lib.assertions import AssertionFailure  # noqa: F401 — re-export

REQUIRED_METADATA = ("ID", "TITLE", "TAGS", "MATURITY", "WHY_IT_MATTERS")
REQUIRED_CONTRACT_FUNCTIONS = ("setup", "run", "check")  # contract shape
REQUIRED_JOURNEY_FUNCTIONS = ("setup",)                  # journey shape
VALID_MATURITY = {"stable", "candidate", "experimental"}


def is_journey(module):
    """Journey shape: has `setup` and `STEPS=[Step, ...]`. No `run`/`check`."""
    return hasattr(module, "STEPS") and callable(getattr(module, "setup", None))


class ScenarioConfigError(Exception):
    """Scenario file is malformed (missing metadata or shape)."""


def load_scenario(path):
    """Load a scenario module from a file path."""
    path = Path(path).resolve()
    if not path.exists():
        raise ScenarioConfigError(f"scenario file not found: {path}")
    if path.suffix != ".py":
        raise ScenarioConfigError(f"scenario file is not .py: {path}")
    name = f"scenario_contracts._loaded.{path.stem}"
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ScenarioConfigError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_scenario(module):
    """Validate metadata + shape. Raise ScenarioConfigError if invalid."""
    for field in REQUIRED_METADATA:
        if not hasattr(module, field):
            raise ScenarioConfigError(f"missing {field}")
    if is_journey(module):
        required = REQUIRED_JOURNEY_FUNCTIONS
    else:
        required = REQUIRED_CONTRACT_FUNCTIONS
    for func in required:
        if not hasattr(module, func) or not callable(getattr(module, func)):
            raise ScenarioConfigError(f"missing {func}()")
    if is_journey(module):
        from scenario_contracts.lib.journey import Step
        if not isinstance(module.STEPS, list) or not module.STEPS:
            raise ScenarioConfigError("STEPS must be a non-empty list")
        for i, step in enumerate(module.STEPS):
            if not isinstance(step, Step):
                raise ScenarioConfigError(
                    f"STEPS[{i}] must be a journey.Step, got {type(step).__name__}"
                )
    if module.MATURITY not in VALID_MATURITY:
        raise ScenarioConfigError(
            f"MATURITY must be one of {sorted(VALID_MATURITY)}; got {module.MATURITY!r}"
        )
    if not isinstance(module.TAGS, list) or not all(isinstance(t, str) for t in module.TAGS):
        raise ScenarioConfigError("TAGS must be a list[str]")
    if not isinstance(module.ID, str) or not module.ID.strip():
        raise ScenarioConfigError("ID must be a non-empty str")
    if not isinstance(module.WHY_IT_MATTERS, str) or not module.WHY_IT_MATTERS.strip():
        raise ScenarioConfigError("WHY_IT_MATTERS must be a non-empty str")


def execute_scenario(module):
    """Dispatch to the right executor based on scenario shape + tags."""
    result = {
        "id": module.ID,
        "title": module.TITLE,
        "tags": list(module.TAGS),
        "maturity": module.MATURITY,
    }
    if is_journey(module):
        return executors.execute_journey_scenario(module, result)
    if "ui" in module.TAGS:
        return executors.execute_ui_scenario(module, result)
    return executors.execute_db_scenario(module, result)


def run_path(path, tag_filter=None):
    """Run one scenario file OR every .py file in a directory.

    Returns (results, exit_code).
    """
    path = Path(path).resolve()
    if path.is_dir():
        files = sorted(
            p for p in path.glob("*.py")
            if p.name != "__init__.py" and not p.name.startswith("_")
        )
    else:
        files = [path]

    results = []
    for file in files:
        module = None
        try:
            module = load_scenario(file)
            validate_scenario(module)
        except ScenarioConfigError as exc:
            results.append({
                "id": getattr(module, "ID", file.stem) if module else file.stem,
                "title": getattr(module, "TITLE", file.stem) if module else file.stem,
                "outcome": "invalid",
                "detail": str(exc),
                "tags": [],
                "maturity": "?",
            })
            continue

        if tag_filter and not any(t in module.TAGS for t in tag_filter):
            continue
        results.append(execute_scenario(module))

    if any(r["outcome"] == "invalid" for r in results):
        return results, 2
    if any(r["outcome"] == "fail" for r in results):
        return results, 1
    return results, 0


def _print_summary(results):
    pass_count = sum(1 for r in results if r["outcome"] == "pass")
    fail_count = sum(1 for r in results if r["outcome"] == "fail")
    invalid_count = sum(1 for r in results if r["outcome"] == "invalid")
    skip_count = sum(1 for r in results if r["outcome"] == "skip")
    print()
    for r in results:
        glyph = {
            "pass": "✓",
            "fail": "✗",
            "invalid": "?",
            "skip": "·",
        }.get(r["outcome"], "?")
        print(f"  {glyph}  [{r['outcome'].upper():7s}] {r['id']} — {r['title']}")
        if r.get("detail"):
            print(f"          {r['detail']}")
    print()
    print(
        f"PASS: {pass_count} | FAIL: {fail_count} | "
        f"INVALID: {invalid_count} | SKIP: {skip_count}"
    )


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    if not argv:
        print("usage: python -m scenario_contracts.lib.runner <path> [--tag TAG]")
        return 2

    tag_filter = None
    if "--tag" in argv:
        idx = argv.index("--tag")
        tag_filter = [argv[idx + 1]]
        del argv[idx:idx + 2]

    path = argv[0]
    results, code = run_path(path, tag_filter=tag_filter)
    _print_summary(results)
    md_path, json_path = reporter.write_report(results)
    print(f"\nReport: {md_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
