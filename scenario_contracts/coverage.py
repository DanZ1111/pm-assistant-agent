"""Coverage gap analyzer — find CRUD functions + AI tools without scenario coverage.

Pure offline source-code introspection. NO live LLM call. NO network
access. Reads app/crud.py + app.ai.tools._HANDLERS, scans the existing
scenario files, and reports the load-bearing mutating surface that has
no scenario referencing it.

Output goes to stdout; humans take the list to their own AI of choice
(Claude, Codex, ChatGPT) to draft scenarios into
scenario_contracts/candidates/, where they get reviewed before
promotion to contracts/ or journeys/.

Run:
    python3 scenario_contracts/coverage.py
    python3 scenario_contracts/coverage.py --json    # machine-readable
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Load-bearing mutation prefixes; the gap analyzer focuses on the
# surface AI/PM actions actually touch. Pure read helpers (`get_*`,
# `list_*`) are excluded — they're indirectly covered every time a
# scenario asserts read-back state.
MUTATING_PREFIXES = (
    "create_", "update_", "delete_", "add_", "resolve_",
    "apply_", "finish_", "link_", "mint_", "save_",
    "set_", "archive_",
)


def crud_function_names():
    """Return the set of public mutating function names declared in app/crud.py."""
    src = (REPO_ROOT / "app" / "crud.py").read_text(encoding="utf-8")
    names = set()
    for match in re.finditer(r"^def (\w+)\(", src, re.MULTILINE):
        name = match.group(1)
        if name.startswith("_"):
            continue
        if not any(name.startswith(prefix) for prefix in MUTATING_PREFIXES):
            continue
        names.add(name)
    return names


def ai_tool_names():
    """Return the set of AI tool names registered in app.ai.tools._HANDLERS."""
    try:
        from app.ai.tools import _HANDLERS
    except Exception:
        return set()
    return set(_HANDLERS.keys())


def scenario_text_corpus():
    """Concatenate every scenario file under contracts/ + journeys/."""
    chunks = []
    for sub in ("contracts", "journeys"):
        base = REPO_ROOT / "scenario_contracts" / sub
        if not base.exists():
            continue
        for path in base.glob("*.py"):
            if path.name == "__init__.py":
                continue
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n".join(chunks)


def _wrapper_to_crud_map():
    """Build a map of wrapper-name → set of crud-function-names from
    actions.py and disruptions.py.

    A wrapper covers a crud function transitively if scenarios call the
    wrapper. Uses Python's ast module so blank lines / docstrings /
    nested calls don't break parsing.
    """
    import ast

    lib_dir = REPO_ROOT / "scenario_contracts" / "lib"
    wrappers = {}
    for lib_file in ("actions.py", "disruptions.py"):
        path = lib_dir / lib_file
        if not path.exists():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            crud_refs = set()
            for sub in ast.walk(node):
                # Match patterns like `crud.<name>(...)` and
                # `actions.<name>(...)` / `disruptions.<name>(...)`.
                if isinstance(sub, ast.Attribute):
                    if isinstance(sub.value, ast.Name):
                        if sub.value.id == "crud":
                            crud_refs.add(sub.attr)
                        elif sub.value.id in ("actions", "disruptions"):
                            # Recursive wrapper call; mark for resolution
                            # in a second pass below.
                            crud_refs.add(("__wrapper__", sub.attr))
            if crud_refs:
                wrappers[node.name] = crud_refs

    # Resolve recursive wrapper references one hop (good enough — the
    # codebase doesn't nest beyond actions → disruptions → crud, OR
    # actions → crud directly).
    resolved = {}
    for name, refs in wrappers.items():
        flat = set()
        for ref in refs:
            if isinstance(ref, tuple) and ref[0] == "__wrapper__":
                inner_refs = wrappers.get(ref[1], set())
                for inner in inner_refs:
                    if isinstance(inner, str):
                        flat.add(inner)
            elif isinstance(ref, str):
                flat.add(ref)
        if flat:
            resolved[name] = flat
    return resolved


def referenced_crud(corpus):
    """Return the set of CRUD names with transitive coverage from scenarios.

    A function is covered if:
      - a scenario calls `crud.<name>(` directly (defensive — shouldn't
        normally happen given the discipline boundary), OR
      - a scenario calls a wrapper in actions/disruptions whose body
        references `crud.<name>(`.
    """
    wrapper_map = _wrapper_to_crud_map()
    found = set()
    for match in re.finditer(
        r"(?:actions|disruptions|crud)\.(\w+)\(", corpus,
    ):
        ref = match.group(1)
        # Direct CRUD call (rare; defensive).
        found.add(ref)
        # Wrapper call → transitively covers each crud in its body.
        if ref in wrapper_map:
            found.update(wrapper_map[ref])
    return found


def referenced_ai_tools(corpus):
    """Return AI tool names referenced via `ai_dispatch("<tool_name>"...)`."""
    found = set()
    for match in re.finditer(r'ai_dispatch\(\s*[^,]+,\s*"(\w+)"', corpus):
        found.add(match.group(1))
    for match in re.finditer(r'ai_dispatch\(\s*[^,]+,\s*\'(\w+)\'', corpus):
        found.add(match.group(1))
    return found


def analyze():
    """Return the coverage gap report."""
    corpus = scenario_text_corpus()
    crud_names = crud_function_names()
    ai_names = ai_tool_names()
    crud_refs = referenced_crud(corpus)
    ai_refs = referenced_ai_tools(corpus)

    crud_uncovered = sorted(crud_names - crud_refs)
    crud_covered = sorted(crud_names & crud_refs)
    ai_uncovered = sorted(ai_names - ai_refs)
    ai_covered = sorted(ai_names & ai_refs)

    return {
        "crud": {
            "total": len(crud_names),
            "covered": crud_covered,
            "uncovered": crud_uncovered,
            "coverage_pct": (
                round(100.0 * len(crud_covered) / len(crud_names), 1)
                if crud_names else 0.0
            ),
        },
        "ai_tools": {
            "total": len(ai_names),
            "covered": ai_covered,
            "uncovered": ai_uncovered,
            "coverage_pct": (
                round(100.0 * len(ai_covered) / len(ai_names), 1)
                if ai_names else 0.0
            ),
        },
    }


def render_text(report):
    lines = []
    crud = report["crud"]
    ai = report["ai_tools"]

    lines.append("== QA Coverage Gap Analyzer ==")
    lines.append("")
    lines.append(
        f"CRUD mutating functions: {len(crud['covered'])} / {crud['total']} "
        f"covered ({crud['coverage_pct']}%)"
    )
    if crud["uncovered"]:
        lines.append("")
        lines.append("CRUD functions WITHOUT scenario coverage:")
        for name in crud["uncovered"]:
            lines.append(f"  - app.crud.{name}")
    lines.append("")
    lines.append(
        f"AI tools (CONFIRMATION + others): {len(ai['covered'])} / "
        f"{ai['total']} covered ({ai['coverage_pct']}%)"
    )
    if ai["uncovered"]:
        lines.append("")
        lines.append("AI tools WITHOUT ai_dispatch scenario coverage:")
        for name in ai["uncovered"]:
            lines.append(f"  - {name}")
    lines.append("")
    lines.append(
        "(See STABLE_CREDIBILITY.md for the candidate → stable promotion rule.)"
    )
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="QA coverage gap analyzer (offline; no LLM call).",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON instead of human text.",
    )
    args = parser.parse_args(argv)
    report = analyze()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
