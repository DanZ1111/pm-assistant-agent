"""v1.5 Build 10 — Release hardening.

Run: python3 test_v15_build10.py
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = Path(__file__).resolve().parent
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
    print("\n── 1. Version and release docs ──")
    from app.version import CURRENT_BUILD_NAME, CURRENT_VERSION, LAST_UPDATED

    version_md = read("VERSION.md")
    changelog = read("CHANGELOG.md")
    if (
        CURRENT_VERSION == "1.5.0"
        and "Designer Portal MVP" in CURRENT_BUILD_NAME
        and LAST_UPDATED == "2026-06-13"
        and "**Current Version:** v1.5.0" in version_md
        and "## v1.5.0 — Designer Portal MVP" in changelog
    ):
        ok("Runtime version and release docs agree on v1.5.0")
    else:
        fail("version/docs", {
            "version": CURRENT_VERSION,
            "build": CURRENT_BUILD_NAME,
            "updated": LAST_UPDATED,
            "version_doc": "**Current Version:** v1.5.0" in version_md,
            "changelog": "## v1.5.0 — Designer Portal MVP" in changelog,
        })

    contains_all(
        "VERSION.md documents all v1.5 build outcomes",
        version_md,
        [
            "Roles & Portal Shell",
            "Design Quest Data Model",
            "PM Renderings & Design Quest MVP",
            "Designer Portal Quest View",
            "Submissions & Versions",
            "Revision Loop & Review Actions",
            "Select Final & Promote Rendering",
            "Design Status In Timeline/Pulse",
            "Designer Manager Operations",
            "Release Hardening",
            "Migrations 011-015",
            "i18n bundle reaches 927/927",
        ],
    )

    print("\n── 2. Build artifacts and migrations ──")
    missing_artifacts = []
    for number in range(1, 11):
        plan_matches = list(ROOT.glob(f"V15_BUILD{number:02d}*_PLAN.md"))
        if not plan_matches:
            missing_artifacts.append(f"V15_BUILD{number:02d} plan")
        if not (ROOT / f"test_v15_build{number:02d}.py").exists():
            missing_artifacts.append(f"test_v15_build{number:02d}.py")
    if not missing_artifacts:
        ok("v1.5 plan and test artifacts exist for Builds 01-10")
    else:
        fail("missing artifacts", missing_artifacts)

    migrations_py = read("app/migrations.py")
    contains_all(
        "v1.5 migrations 011-015 are registered",
        migrations_py,
        [
            "011_v1_5_create_design_quest_core",
            "012_v1_5_create_design_submissions",
            "013_v1_5_create_design_revision_requests",
            "014_v1_5_select_final_promote_rendering",
            "015_v1_5_design_status_timeline_pulse",
        ],
    )

    print("\n── 3. AI boundary and permission proofs ──")
    registry = read("AI_TOOLS_REGISTRY.md")
    ai_tools = read("app/ai/tools.py")
    contains_all(
        "AI registry marks Designer Portal write tools deferred after v1.5 manual UI",
        registry,
        [
            "draft_design_quest",
            "request_design_revision",
            "select_final_design_submission",
            "mark_design_complete",
            "designer_manager_assign",
            "deferred after v1.5 manual UI",
        ],
    )
    forbidden_ai_markers = [
        "request_design_revision",
        "select_final_design_submission",
        "mark_design_complete",
        "manager_assign_designer_to_quest",
        "manager_reopen_design_submission",
    ]
    leaked = [marker for marker in forbidden_ai_markers if marker in ai_tools]
    if not leaked:
        ok("No v1.5 Designer Portal AI write handlers are registered")
    else:
        fail("AI handler leak", leaked)

    build09 = read("test_v15_build09.py")
    contains_all(
        "Designer manager and project permission boundary regressions are present",
        build09,
        [
            "Manager dashboard is manager-only",
            "Designer manager still cannot access PM project page",
            "manager_reopen_design_submission",
            "no phase mutation",
        ],
    )

    print("\n── 4. Workflow and i18n proof ──")
    workflow_tests = (
        read("test_v15_build05.py")
        + read("test_v15_build06.py")
        + read("test_v15_build07.py")
        + read("test_v15_build08.py")
        + read("test_v15_build09.py")
    )
    contains_all(
        "Release-proof tests cover PM/designer workflow from upload through manager operations",
        workflow_tests,
        [
            "First designer upload creates one submission and version 1",
            "PM can request structured revision with checklist",
            "PM selects a specific version and promotes it to rendering",
            "PM marks design complete with audit and no phase mutation",
            "Manager assigns designer to assigned-only quest",
        ],
    )

    en = json.loads(read("app/i18n/en.json"))
    zh = json.loads(read("app/i18n/zh.json"))
    if set(en) == set(zh) and len(en) == 927:
        ok("i18n parity locked at 927/927 for v1.5.0")
    else:
        fail("i18n parity/count", {"en": len(en), "zh": len(zh), "diff": sorted(set(en) ^ set(zh))[:8]})

    return summary()


def summary():
    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        print("\nFailures:")
        for name, reason in FAIL:
            print(f" - {name}: {reason}")
    print("=" * 60)
    return not FAIL


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
