"""Regression: display-only Chinese localization for default phase names.

Run: python3 test_phase_name_i18n.py
"""
import json
from pathlib import Path

PASS, FAIL = [], []
ROOT = Path(__file__).resolve().parent


def ok(name):
    PASS.append(name)
    print(f"  ✓  {name}")


def fail(name, reason):
    FAIL.append((name, reason))
    print(f"  ✗  {name}: {reason}")


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def main():
    print("\n── Phase display helper ──")
    from app.i18n import translate_phase_name

    expected = {
        "Design": "设计",
        "Engineering Review": "工程评审",
        "Prototype Sample": "手板样",
        "Prototype 1": "手板样",
        "Prototype 2": "手板样二轮",
        "Pre-production Sample": "产前样",
        "Pilot Run": "小批量试产",
        "Small Batch Trial": "小批量试产",
        "Mass Production": "量产",
        "Launch Prep": "上市准备",
        "Launch": "上市",
    }
    mismatches = {
        source: translate_phase_name(source, "zh")
        for source, zh in expected.items()
        if translate_phase_name(source, "zh") != zh
    }
    if not mismatches:
        ok("Default phase names translate to Chinese knife PM labels")
    else:
        fail("Chinese phase name map", mismatches)

    if translate_phase_name("Factory Feedback Round", "zh") == "Factory Feedback Round":
        ok("Custom phase names remain untouched")
    else:
        fail("Custom phase fallback", translate_phase_name("Factory Feedback Round", "zh"))

    if translate_phase_name("Prototype 1", "en") == "Prototype 1":
        ok("English locale keeps canonical phase names")
    else:
        fail("English phase fallback", translate_phase_name("Prototype 1", "en"))

    print("\n── Template and sandbox wiring ──")
    from app.main import _GLOBALS
    from app.routes.projects import _localize_sandbox_payload

    if "phase_name" in _GLOBALS:
        ok("phase_name Jinja helper is registered globally")
    else:
        fail("Jinja helper registration", "phase_name missing from app globals")

    payload = {
        "elements": [
            {"data": {"id": "node-1", "label": "Prototype Sample"}},
            {"data": {"id": "edge-1", "label": "Dependency"}},
        ],
        "modules": [
            {"title": "Pre-production Sample"},
            {"title": "Custom Factory Gate"},
        ],
    }
    localized = _localize_sandbox_payload(payload, "zh")
    node_data = localized["elements"][0]["data"]
    modules = localized["modules"]
    if (
        node_data["label"] == "Prototype Sample"
        and node_data["display_label"] == "手板样"
        and modules[0]["title"] == "Pre-production Sample"
        and modules[0]["display_title"] == "产前样"
        and modules[1]["display_title"] == "Custom Factory Gate"
    ):
        ok("Sandbox payload gets display labels without rewriting canonical titles")
    else:
        fail("Sandbox payload localization", localized)

    project_detail = read("app/templates/project_detail.html")
    sandbox_template = read("app/templates/planning_sandbox.html")
    sandbox_js = read("app/static/js/planning_sandbox.js")
    if (
        "phase_name(current_phase.phase_name)" in project_detail
        and "phase_name(phase.phase_name)" in project_detail
        and "module.display_title or module.title" in sandbox_template
        and "'label': 'data(display_label)'" in sandbox_js
    ):
        ok("Timeline and sandbox templates use display-localized labels")
    else:
        fail("Template wiring", "expected phase_name/display_label markers missing")

    print("\n── i18n bundle parity ──")
    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    if set(en) == set(zh):
        ok(f"EN/ZH key parity preserved ({len(en)} keys)")
    else:
        fail("i18n parity", sorted(set(en) ^ set(zh))[:12])

    print(f"\nPassed: {len(PASS)}")
    print(f"Failed: {len(FAIL)}")
    if FAIL:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
