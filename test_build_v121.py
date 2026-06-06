"""v1.2.1 — Release-hardening regression for the v1.2 patch series rollup.

Mirrors test_build29.py (the v1.2.0 release proof). Asserts the public
version source, VERSION.md / CHANGELOG.md / MASTERPLAN.md / USER_GUIDE.md
all agree that v1.2.1 shipped, and the full test-file inventory exists
including the 7 patches that rolled up into this release:
  - IME composer fix v2 (commit 7d56198)
  - Nixpacks Python-only (commit 2bd82bf)
  - PM-facing price strings (commit 1465265)
  - Project detail layout refactor (commit 36a787e)
  - Build 30A — project creation safety (commit cab8884)
  - Build 30B — Excel batch intake (commit 1d811b9)
  - Build 30C — PM draft delete (commit b0f6ad3)

Why we need this on top of test_build29: the v1.2.0 proof is preserved
unchanged (test_build29 still passes after the v1.2.1 bump because its
version check is now `startswith("1.2.")`). This file asserts the v1.2.1
delta: the new release proof string, the rollup CHANGELOG mega entry, the
USER_GUIDE summary of the 7 patches, and a couple of behavior locks that
prove the underlying features survived.
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

    # v1.2.1 release proof — tolerant of any post-v1.2.0 line (1.2.1-buildNN,
    # 1.2.2, 1.3.x, ...). The release-proof markers in VERSION.md / CHANGELOG.md /
    # MASTERPLAN.md / USER_GUIDE.md still locked below; this file's job is to
    # prove v1.2.1 shipped at some point in the past and its content survived.
    # As of v1.3.0 (2026-06-06) CURRENT_VERSION moved off the 1.2.x line.
    if CURRENT_VERSION and CURRENT_VERSION != "1.2.0":
        ok(f"app.version CURRENT_VERSION is past v1.2.0 ({CURRENT_VERSION})")
    else:
        fail("CURRENT_VERSION", f"expected post-v1.2.0, got {CURRENT_VERSION}")

    # CURRENT_BUILD_NAME no longer required to mention v1.2.1 — v1.3.0 ships
    # without it. The release-proof v1.2.1 marker lives in VERSION.md / CHANGELOG.md.
    if CURRENT_BUILD_NAME:
        ok(f"app.version CURRENT_BUILD_NAME is set ({CURRENT_BUILD_NAME!r})")
    else:
        fail("CURRENT_BUILD_NAME", f"empty — should be set")

    if LAST_UPDATED and len(LAST_UPDATED) == 10 and LAST_UPDATED.count("-") == 2:
        ok(f"app.version LAST_UPDATED is ISO date format ({LAST_UPDATED})")
    else:
        fail("LAST_UPDATED", LAST_UPDATED)

    print("\n── Release docs ──")
    version_md = read("VERSION.md")
    changelog = read("CHANGELOG.md")
    user_guide = read("USER_GUIDE.md")
    masterplan = read("MASTERPLAN.md")

    # v1.2.1 release proof — these strings must persist even as later patches
    # update the Current Version / Current Build header.
    # v1.2.1 release-proof markers — the historic v1.2.1 narrative must persist
    # in VERSION.md even after the version bumps past v1.2.1. The
    # "**Current Version:** v1.2.1" header was correct at ship time; future
    # bumps overwrite it, so we no longer assert it here. The narrative section
    # + "v1.2.1 released" status line are the load-bearing release proof.
    contains_all(
        "VERSION.md documents the v1.2.1 release",
        version_md,
        [
            "v1.2.1 released",
            "## What's new in v1.2.1",
        ],
    )

    contains_all(
        "CHANGELOG.md has v1.2.1 rollup entry",
        changelog,
        [
            "## v1.2.1 — Workflow polish + Excel batch intake + draft delete",
            "Chinese IME chat fix",
            "Excel batch intake",
            "Project creation safety",
            "PM draft delete",
            "Project detail layout",
            "PM-facing price strings",
        ],
    )

    contains_all(
        "MASTERPLAN.md marks v1.2.1 shipped",
        masterplan,
        [
            "### v1.2.1 — Release-hardening rollup ✓ SHIPPED v1.2.1",
            "python3 test_build_v121.py",
            "No database schema change",
        ],
    )

    # v1.2.0 release proof must still survive (test_build29 also covers this;
    # doubling it here means a future cleanup of v1.2.0 content surfaces in two places)
    contains_all(
        "VERSION.md still preserves the v1.2.0 release proof",
        version_md,
        [
            "v1.2.0 released",
            "## What's new in v1.2.0",
        ],
    )

    print("\n── USER_GUIDE coverage ──")
    contains_all(
        "USER_GUIDE.md has v1.2.1 summary block",
        user_guide,
        [
            "## v1.2.1 速览",
            "Excel",
            "PM 草稿删除",
        ],
    )

    contains_all(
        "USER_GUIDE.md v1.2.1 English summary covers the 7 patches",
        user_guide,
        [
            "Excel batch intake",
            "PM draft delete",
            "Chinese IME",
            "PM-facing price strings",
            "Project creation safety",
        ],
    )

    contains_all(
        "USER_GUIDE.md still preserves v1.2 coverage",
        user_guide,
        [
            "Professional Assistant Workspace",
            "Confirmation Cards",
            "Assistant Attachments",
        ],
    )

    print("\n── Regression inventory ──")
    expected_tests = [
        "test_build1.py", "test_build1_5.py", "test_build2.py", "test_build3.py",
        "test_build4.py", "test_build5.py", "test_build6.py", "test_build7.py",
        "test_build8.py", "test_build11.py", "test_build12.py",
        "test_build14.py", "test_build15.py", "test_build16.py", "test_build17.py",
        "test_build18.py", "test_build19.py", "test_build20.py", "test_build21.py",
        "test_build22.py", "test_build23.py", "test_build24.py", "test_build25.py",
        "test_build26.py", "test_build27.py", "test_build28.py", "test_build29.py",
        "test_build30.py", "test_build30b.py", "test_build30c.py",
        "test_build_v121.py",
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

    print("\n── Behavior locks for the rollup patches ──")
    # Each lock proves a single bit of the patch survived the rollup. Cheap
    # static / module-level checks; full behavior is already covered by the
    # per-build test files in the regression inventory above.

    # 1. IME composer controller module exists with the named constant
    composer = (ROOT / "app/static/js/composer_controller.js").read_text()
    contains_all(
        "IME composer controller present with named constant",
        composer,
        ["IME_CONFIRM_ENTER_SUPPRESS_MS = 80", "createComposerController"],
    )

    # 2. Nixpacks override pins Python-only
    if (ROOT / "nixpacks.toml").exists():
        nixp = (ROOT / "nixpacks.toml").read_text()
        if 'providers = ["python"]' in nixp:
            ok("nixpacks.toml pins Python-only provider")
        else:
            fail("nixpacks providers", "providers = [\"python\"] missing from nixpacks.toml")
    else:
        fail("nixpacks.toml", "file missing")

    # 3. Price-strings VARCHAR fields still in models
    from app.models import Project
    if hasattr(Project, "target_factory_cost_text") and hasattr(Project, "target_msrp_text"):
        ok("Project.target_factory_cost_text and target_msrp_text columns present")
    else:
        fail("price-text columns", "missing on Project model")

    # 4. Project creation safety: idempotency token table + helper
    from app.crud import (
        create_project_with_idempotency, create_projects_batch_with_idempotency,
        mint_creation_token, normalize_pm_value,
    )
    ok("Build 30A + 30B crud helpers importable")

    # 5. Excel batch intake module + prompt
    from app.ai.excel_parser import workbook_to_text, extract_from_workbook, WORKBOOK_TEXT_CAP_CHARS
    from app.ai.parser import extract_batch_from_workbook_text
    from app.ai.prompts import EXCEL_BATCH_INTAKE_PROMPT
    if WORKBOOK_TEXT_CAP_CHARS == 100_000 and "projects" in EXCEL_BATCH_INTAKE_PROMPT:
        ok("Build 30B Excel parser + batch prompt present")
    else:
        fail("Excel batch wiring", "parser cap or prompt drift")

    # 6. PM draft delete helper
    from app.dependencies import can_delete_project
    ok("Build 30C can_delete_project helper importable")

    # 7. Project detail layout refactor — sidebar removed, header facts present
    detail_html = (ROOT / "app/templates/project_detail.html").read_text()
    if ".detail-sidebar" not in detail_html and "project-header-facts" in detail_html:
        ok("Project detail layout refactor: sidebar gone, header-facts present")
    else:
        fail("layout refactor", ".detail-sidebar still rendered OR project-header-facts missing")

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
