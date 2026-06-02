"""Build 29 — v1.2.0 release documentation + version tests.

Build 29 is a release-hardening build for the v1.2 series (Builds 26-28),
not a feature build. These tests make sure the public version source and
release docs agree, the user guide covers the v1.2 feature set, and every
build-level test file exists for regression.

Mirrors test_build24.py (which did the same for v1.1.0).
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

    # Build 29's purpose was to release v1.2.0. We keep this check tolerant
    # of post-release patch / extension builds (e.g. v1.2.0-build30) so that
    # adding a follow-up build doesn't invalidate the "v1.2.0 shipped" proof.
    if CURRENT_VERSION.startswith("1.2.0"):
        ok(f"app.version CURRENT_VERSION is on the v1.2.0 line ({CURRENT_VERSION})")
    else:
        fail("CURRENT_VERSION", CURRENT_VERSION)

    # Build name is point-in-time; just sanity check it's non-empty.
    if CURRENT_BUILD_NAME:
        ok(f"app.version CURRENT_BUILD_NAME is set ({CURRENT_BUILD_NAME!r})")
    else:
        fail("CURRENT_BUILD_NAME", CURRENT_BUILD_NAME)

    # LAST_UPDATED moves on every release; just sanity check the format.
    if LAST_UPDATED and len(LAST_UPDATED) == 10 and LAST_UPDATED.count("-") == 2:
        ok(f"app.version LAST_UPDATED is ISO date format ({LAST_UPDATED})")
    else:
        fail("LAST_UPDATED", LAST_UPDATED)

    print("\n── Release docs ──")
    version_md = read("VERSION.md")
    changelog = read("CHANGELOG.md")
    user_guide = read("USER_GUIDE.md")
    masterplan = read("MASTERPLAN.md")

    # v1.2.0 release proof: the "What's new in v1.2.0" block and the
    # "v1.2.0 released" status line must persist even as later builds
    # (30, 31, ...) update the Current Version / Current Build header.
    contains_all(
        "VERSION.md documents the v1.2.0 release",
        version_md,
        [
            "**Current Version:** v1.2.0",
            "v1.2.0 released",
            "## What's new in v1.2.0",
        ],
    )

    contains_all(
        "CHANGELOG.md has v1.2.0 mega entry",
        changelog,
        [
            "## v1.2.0 — Assistant Workspace Release",
            "Professional assistant workspace",
            "Confirmed daily PM actions",
            "Assistant attachments",
            "No schema migration in Build 29",
        ],
    )

    contains_all(
        "MASTERPLAN.md marks Build 29 shipped",
        masterplan,
        [
            "### Build 29 — v1.2.0 release hardening ✓ SHIPPED v1.2.0",
            "No database schema change.",
            "python3 test_build29.py",
        ],
    )

    # v1.1.0 release proof must still survive — test_build24 also checks
    # this, but doubling it up here means a future cleanup of the v1.1.0
    # block immediately surfaces in two places.
    contains_all(
        "VERSION.md still preserves the v1.1.0 release proof",
        version_md,
        [
            "v1.1.0 released",
            "## What's new in v1.1.0",
        ],
    )

    print("\n── USER_GUIDE coverage ──")
    contains_all(
        "USER_GUIDE.md has short v1.2 Chinese summary",
        user_guide,
        [
            "## v1.2 中文速览",
            "AI 工作区",
            "确认卡",
            "附件",
        ],
    )

    contains_all(
        "USER_GUIDE.md covers v1.2 feature set",
        user_guide,
        [
            "Professional Assistant Workspace",
            "Confirmation Cards",
            "Assistant Attachments",
            "Global Search",
            "Idea Auto-Capture",
            "Duplicate Idea Detection",
        ],
    )

    # v1.1 coverage must still survive — same doubling logic as above.
    contains_all(
        "USER_GUIDE.md still preserves v1.1 coverage",
        user_guide,
        [
            "## v1.1 中文速览",
            "Project Journal",
            "Timeline 2.0",
        ],
    )

    print("\n── Post-release assistant input regression ──")
    main_js = read("app/static/js/main.js")
    contains_all(
        "assistant composers ignore IME candidate-confirmation Enter events",
        main_js,
        [
            "input.addEventListener('compositionstart'",
            "input.addEventListener('compositionend'",
            "!e.isComposing",
            "e.keyCode !== 229",
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
        "test_build25.py",
        "test_build26.py",
        "test_build27.py",
        "test_build28.py",
        "test_build29.py",
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
    if set(en) == set(zh) and len(en) >= 537:
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
