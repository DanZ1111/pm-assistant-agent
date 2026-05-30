"""Build 24 — v1.1.0 release documentation + version tests.

Build 24 is a release-hardening build, not a feature build. These tests make
sure the public version source and release docs agree, the user guide covers
the v1.1 feature set, and every build-level test file exists for regression.
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


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def contains_all(label, text, needles):
    missing = [needle for needle in needles if needle not in text]
    if missing:
        fail(label, f"missing: {missing}")
    else:
        ok(label)


def main():
    print("\n── Runtime version source ──")
    from app.version import CURRENT_BUILD_NAME, CURRENT_VERSION, LAST_UPDATED

    if CURRENT_VERSION == "1.1.0":
        ok("app.version CURRENT_VERSION is final v1.1.0")
    else:
        fail("CURRENT_VERSION", CURRENT_VERSION)

    if "Build 24" in CURRENT_BUILD_NAME and "release" in CURRENT_BUILD_NAME.lower():
        ok("app.version CURRENT_BUILD_NAME identifies Build 24 release")
    else:
        fail("CURRENT_BUILD_NAME", CURRENT_BUILD_NAME)

    if LAST_UPDATED == "2026-05-30":
        ok("app.version LAST_UPDATED is 2026-05-30")
    else:
        fail("LAST_UPDATED", LAST_UPDATED)

    print("\n── Release docs ──")
    version_md = read("VERSION.md")
    changelog = read("CHANGELOG.md")
    user_guide = read("USER_GUIDE.md")
    masterplan = read("MASTERPLAN.md")

    contains_all(
        "VERSION.md reflects final release",
        version_md,
        [
            "**Current Version:** v1.1.0",
            "**Current Build:** Build 24",
            "**Status:** v1.1.0 released",
            "## What's new in v1.1.0",
        ],
    )

    contains_all(
        "CHANGELOG.md has v1.1.0 mega entry",
        changelog,
        [
            "## v1.1.0 — Product Development Workspace Release",
            "Project Journal",
            "Timeline 2.0",
            "Chinese i18n",
            "No schema migration in Build 24",
        ],
    )

    contains_all(
        "MASTERPLAN.md marks Build 24 shipped",
        masterplan,
        [
            "### Build 24 — v1.1.0 release tests + USER_GUIDE update + bump ✓ SHIPPED v1.1.0",
            "No database schema change.",
            "python3 test_build24.py",
        ],
    )

    print("\n── USER_GUIDE coverage ──")
    contains_all(
        "USER_GUIDE.md has short Chinese summary",
        user_guide,
        [
            "## v1.1 中文速览",
            "中文界面",
            "项目日志",
            "AI 辅助创建项目",
        ],
    )

    contains_all(
        "USER_GUIDE.md covers v1.1 feature set",
        user_guide,
        [
            "Project Journal",
            "Business Plan Upload + Thesis Extraction",
            "Variants, Packaging, Quotation, and Profit Model",
            "Timeline 2.0",
            "Rendering History",
            "Prototype Photos",
            "My Projects",
            "Bottom AI Chat",
            "AI-Assisted Create Project",
            "Chinese UI",
        ],
    )

    contains_all(
        "USER_GUIDE.md documents intended Profit Model formula",
        user_guide,
        [
            "Margin per unit = MSRP - factory cost - packaging/accessory unit costs",
            "Total profit = margin per unit × forecast volume - overhead",
        ],
    )

    print("\n── Regression inventory ──")
    expected_tests = [
        "test_build1.py",
        "test_build1_5.py",
        "test_build2.py",
        "test_build3.py",
        "test_build4.py",
        "test_build5.py",
        "test_build6.py",
        "test_build7.py",
        "test_build8.py",
        "test_build11.py",
        "test_build12.py",
        "test_build14.py",
        "test_build15.py",
        "test_build16.py",
        "test_build17.py",
        "test_build18.py",
        "test_build19.py",
        "test_build20.py",
        "test_build21.py",
        "test_build22.py",
        "test_build23.py",
        "test_build24.py",
        "test_ai_e2e.py",
    ]
    missing = [name for name in expected_tests if not (ROOT / name).exists()]
    if missing:
        fail("all expected regression test files exist", f"missing: {missing}")
    else:
        ok(f"all expected regression test files exist ({len(expected_tests)})")

    print("\n── i18n bundle parity still locked ──")
    en = json.loads((ROOT / "app/i18n/en.json").read_text(encoding="utf-8"))
    zh = json.loads((ROOT / "app/i18n/zh.json").read_text(encoding="utf-8"))
    if set(en) == set(zh) and len(en) >= 500:
        ok(f"en/zh i18n bundles still have exact parity ({len(en)} keys)")
    else:
        fail(
            "i18n parity",
            f"en={len(en)} zh={len(zh)} missing_zh={sorted(set(en) - set(zh))[:5]} extra_zh={sorted(set(zh) - set(en))[:5]}",
        )

    _print_summary()
    return len(FAIL) == 0


def _print_summary():
    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        for name, reason in FAIL:
            print(f"  ✗ {name}: {reason}")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
