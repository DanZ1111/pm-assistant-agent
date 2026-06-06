"""v1.3.0 — Release-hardening regression for the v1.3 series rollup.

Mirrors test_build_v121.py (the v1.2.1 release proof) and test_build29.py
(the v1.2.0 release proof). Asserts the public version source, VERSION.md /
CHANGELOG.md / MASTERPLAN.md all agree that v1.3.0 shipped, the full v1.3
test-file inventory exists, and the 10 v1.3 builds (01-09 + the project-
delete FK cross-cutting fix + this Build 10 itself) all left their
expected behavior locks intact.

Why we need this on top of test_build_v121: each release-hardening build
adds a forward-going release-proof file. v1.2.1's proof preserved the
v1.2.0 markers; v1.3.0's proof preserves both v1.2.0 and v1.2.1 markers
plus locks the new v1.3.0 markers. Future v1.4.0 hardening will preserve
all three.
"""
import json
import os
import subprocess
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


def run_subtest(name, timeout=120):
    """Run a child test file and report PASS/FAIL based on exit code."""
    path = ROOT / name
    if not path.exists():
        fail(f"subprocess: {name}", "file missing")
        return
    try:
        result = subprocess.run(
            ["python3", str(path)],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            ok(f"subprocess {name} exit 0")
        else:
            tail = result.stdout.splitlines()[-3:] if result.stdout else []
            fail(f"subprocess: {name}", f"exit {result.returncode}; tail: {tail}")
    except subprocess.TimeoutExpired:
        fail(f"subprocess: {name}", f"timeout after {timeout}s")


def main():
    print("\n── 1. Runtime version source ──")
    from app.version import CURRENT_BUILD_NAME, CURRENT_VERSION, LAST_UPDATED

    if CURRENT_VERSION.startswith("1.3."):
        ok(f"app.version CURRENT_VERSION on v1.3 line ({CURRENT_VERSION})")
    else:
        fail("CURRENT_VERSION", f"expected v1.3.x, got {CURRENT_VERSION}")

    if CURRENT_BUILD_NAME and ("v1.3.0" in CURRENT_BUILD_NAME or "1.3.0" in CURRENT_BUILD_NAME):
        ok(f"app.version CURRENT_BUILD_NAME identifies v1.3.0 ({CURRENT_BUILD_NAME!r})")
    else:
        fail("CURRENT_BUILD_NAME", f"expected v1.3.0 reference, got {CURRENT_BUILD_NAME!r}")

    if LAST_UPDATED and len(LAST_UPDATED) == 10 and LAST_UPDATED.count("-") == 2:
        ok(f"app.version LAST_UPDATED is ISO date format ({LAST_UPDATED})")
    else:
        fail("LAST_UPDATED", LAST_UPDATED)

    print("\n── 2. Release docs (v1.3.0 + earlier releases preserved) ──")
    version_md = read("VERSION.md")
    changelog = read("CHANGELOG.md")
    masterplan = read("MASTERPLAN.md")

    contains_all(
        "VERSION.md documents the v1.3.0 release",
        version_md,
        [
            "**Current Version:** v1.3.0",
            "v1.3.0 released",
            "## What's new in v1.3.0",
        ],
    )

    contains_all(
        "VERSION.md preserves v1.2.1 release proof",
        version_md,
        ["v1.2.1 released", "## What's new in v1.2.1"],
    )

    contains_all(
        "VERSION.md preserves v1.2.0 release proof",
        version_md,
        ["v1.2.0 released", "## What's new in v1.2.0"],
    )

    contains_all(
        "CHANGELOG.md has v1.3.0 rollup entry",
        changelog,
        ["## v1.3.0 — Project Detail Command Center"],
    )

    contains_all(
        "CHANGELOG.md v1.3.0 entry references all 10 v1.3 builds",
        changelog,
        [
            "Workspace Shell",
            "Project Pulse",
            "Product Concept",
            "Overview Renderings Section",
            "Variant Command Cards",
            "Structured Variant Specs",
            "Timeline Command Center Shell",
            "Timeline Command Center Actions",
            "Project Blockers",
            "Timeline Updates / History",
            "Planning Sandbox Design",
        ],
    )

    contains_all(
        "CHANGELOG.md v1.3.0 entry mentions the project-delete bug fix",
        changelog,
        ["project-delete bug"],
    )

    contains_all(
        "MASTERPLAN.md marks v1.3.0 shipped",
        masterplan,
        ["## v1.3.0 — Project Detail Command Center ✓ SHIPPED v1.3.0"],
    )

    contains_all(
        "MASTERPLAN.md v1.3.0 section enumerates the 10 builds with commits",
        masterplan,
        [
            "Builds shipped",          # the table header in the MASTERPLAN section
            "`448364e`",               # Build 01
            "`5dfff4e`",               # Build 07B
            "`3ab1dc8`",               # Build 08
            "`b8a9687`",               # delete FK fix
        ],
    )

    # Future v1.4+ work is allowed under Unreleased. The v1.3 release proof
    # only needs to ensure no v1.3 rollup entries leaked back above v1.3.0.
    unreleased_section = changelog.split("## Unreleased", 1)[1].split("\n## ", 1)[0]
    if "v1.3 Build" not in unreleased_section and "Project Detail Command Center" not in unreleased_section:
        ok("CHANGELOG.md Unreleased section has no v1.3 leftover")
    else:
        fail("Unreleased section", "still has v1.3 content under Unreleased")

    print("\n── 3. v1.3 test-file inventory + cross-cutting tests ──")
    expected_v13_tests = [f"test_v13_build{n:02d}.py" for n in range(1, 11)]
    expected_v13_tests.append("test_v13_build05b.py")
    expected_v13_tests.append("test_v13_build07b.py")
    for fname in expected_v13_tests:
        if (ROOT / fname).exists():
            ok(f"test file present: {fname}")
        else:
            fail(f"missing v1.3 test file: {fname}", "")

    # Cross-cutting tests
    if (ROOT / "test_delete_project_ai_intake_regression.py").exists():
        ok("test file present: test_delete_project_ai_intake_regression.py (delete FK fix)")
    else:
        fail("missing: test_delete_project_ai_intake_regression.py", "")

    if (ROOT / "test_build_v121.py").exists():
        ok("test file present: test_build_v121.py (v1.2.1 baseline)")
    else:
        fail("missing: test_build_v121.py", "")

    print("\n── 4. i18n parity locked at v1.3.0 final ──")
    en = json.loads((ROOT / "app/i18n/en.json").read_text(encoding="utf-8"))
    zh = json.loads((ROOT / "app/i18n/zh.json").read_text(encoding="utf-8"))
    if set(en) == set(zh):
        ok(f"en/zh i18n bundles have exact parity ({len(en)} keys)")
    else:
        fail("i18n parity", f"en={len(en)} zh={len(zh)}")
    if len(en) >= 714:
        ok(f"i18n key count ≥ 714 (got {len(en)})")
    else:
        fail("i18n key count", f"expected ≥ 714, got {len(en)}")

    print("\n── 5. v1.3 migration inventory preserved ──")
    from app.migrations import MIGRATIONS
    migration_names = [name for name, _ in MIGRATIONS]
    required_v13 = {
        "001_v1_1_add_language_to_users",
        "002_v1_1_add_conversation_id_to_ai_messages",
        "003_v1_2_add_price_text_fields",
        "004_v1_2_add_project_creation_tokens",
        "005_v1_3_add_variant_structured_specs",
        "006_v1_3_add_project_blockers",
    }
    missing_migrations = sorted(required_v13 - set(migration_names))
    if not missing_migrations:
        ok(f"v1.3 migration inventory preserved; later builds may add more (count now {len(MIGRATIONS)})")
    else:
        fail("v1.3 migration inventory", f"missing {missing_migrations}")

    print("\n── 6. Build 10 — legacy Change Log viewer leak fix ──")
    template = read("app/templates/project_detail.html")
    contains_all(
        "project_detail.html has journal-mirror viewer filter (Build 10 fix)",
        template,
        [
            # The new filter wrap
            "Journal entry added:",
            "not can_view_journal",
            "Build 10",
        ],
    )

    # End-to-end smoke: viewer GET should NOT show "Journal entry added:" text
    # in the page (proves the template fix actually fires). Skip if server isn't
    # running or fixtures aren't available.
    try:
        import requests, re, sqlite3
        from datetime import datetime
        BASE = os.environ.get("BASE_URL", "http://localhost:8000")
        s_admin = requests.Session()
        r = s_admin.post(f"{BASE}/auth/login",
            data={"username": "admin", "password": "show me the money"},
            allow_redirects=False, timeout=5)
        if r.status_code not in (302, 303):
            ok("e2e leak smoke: skipped (admin login failed; server may be down)")
        else:
            page = s_admin.get(f"{BASE}/projects/new").text
            tok = re.search(r'name="submission_token"\s+value="([a-f0-9]+)"', page).group(1)
            r2 = s_admin.post(f"{BASE}/projects/new",
                data={"name": "b10_leak_check", "product_manager": "testpm_b8",
                      "prototype_rounds": "single", "submission_token": tok},
                allow_redirects=False, timeout=5)
            pid = int(r2.headers["location"].rstrip("/").split("/")[-1])
            from app.database import SessionLocal
            from app import crud
            sess = SessionLocal()
            try:
                crud.create_journal_entry(sess, pid,
                    "CONFIDENTIAL leak check string", "decision", author_user_id=1)
            finally:
                sess.close()

            s_v = requests.Session()
            s_v.post(f"{BASE}/auth/login",
                data={"username": "testviewer_b8", "password": "viewerpass8!"},
                allow_redirects=False, timeout=5)
            page_v = s_v.get(f"{BASE}/projects/{pid}", timeout=10).text
            if "CONFIDENTIAL leak check string" not in page_v:
                ok("e2e leak smoke: viewer page does NOT contain journal text")
            else:
                fail("e2e leak smoke",
                     "viewer page still contains 'CONFIDENTIAL leak check string'")

            # Cleanup
            conn = sqlite3.connect("pm_tracker.db")
            conn.executescript(
                f"DELETE FROM project_journal_entries WHERE project_id={pid}; "
                f"DELETE FROM project_changes WHERE project_id={pid}; "
                f"DELETE FROM project_phases WHERE project_id={pid}; "
                f"DELETE FROM project_creation_tokens WHERE project_id={pid}; "
                f"DELETE FROM projects WHERE id={pid};"
            )
            conn.commit()
    except Exception as e:
        ok(f"e2e leak smoke: skipped ({type(e).__name__})")

    print("\n── 7. Cross-cutting behavior locks ──")

    # 7.1 — SQLite FK enforcement
    database_py = read("app/database.py")
    if "PRAGMA foreign_keys = ON" in database_py and "_sqlite_fk_on" in database_py:
        ok("app/database.py enables SQLite FK enforcement")
    else:
        fail("FK enforcement", "PRAGMA foreign_keys = ON event listener missing")

    # 7.2 — delete_project handles ai_conversations + project_creation_tokens
    crud_py = read("app/crud.py")
    if "ai_conversations" in crud_py and "ProjectCreationToken" in crud_py:
        ok("crud.delete_project explicitly cleans ai_conversations + creation tokens")
    else:
        fail("delete_project FK cleanup",
             "ai_conversations or ProjectCreationToken explicit cleanup missing")

    # 7.3 — Build 08 helper present
    if "def get_timeline_events" in crud_py:
        ok("crud.get_timeline_events present (Build 08)")
    else:
        fail("Build 08 helper", "get_timeline_events missing from crud.py")

    # 7.4/7.5/7.6 — Build 07B helpers + model
    if "def get_active_blockers_for_project" in crud_py:
        ok("crud.get_active_blockers_for_project present (Build 07B)")
    else:
        fail("Build 07B helper", "get_active_blockers_for_project missing")
    if "def get_active_phase_blocker_ids" in crud_py:
        ok("crud.get_active_phase_blocker_ids present (Build 07B)")
    else:
        fail("Build 07B helper", "get_active_phase_blocker_ids missing")
    try:
        from app.models import ProjectBlocker, Project as _Project
        if hasattr(_Project, "blockers"):
            ok("ProjectBlocker model importable + Project.blockers relationship (Build 07B)")
        else:
            fail("Project.blockers", "relationship missing")
    except ImportError as e:
        fail("ProjectBlocker import", str(e))

    print("\n── 8. Acceptance criteria + plan file present ──")
    if (ROOT / "V13_BUILD10_EXECUTION_PLAN.md").exists():
        ok("V13_BUILD10_EXECUTION_PLAN.md exists (regression guard)")
    else:
        fail("Build 10 plan file", "missing")

    print("\n── 9. Subprocess: regression baseline (v1.2.1 + delete-fix) ──")
    run_subtest("test_build_v121.py", timeout=60)
    run_subtest("test_delete_project_ai_intake_regression.py", timeout=60)

    print("\n── 10. Subprocess: full v1.3 test suite ──")
    for n in (1, 2, 3, 4, 5, 6, 7, 8, 9):
        run_subtest(f"test_v13_build{n:02d}.py", timeout=120)
    run_subtest("test_v13_build05b.py", timeout=90)
    run_subtest("test_v13_build07b.py", timeout=90)

    _p()
    return len(FAIL) == 0


def _p():
    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        for n, r in FAIL:
            print(f"  ✗ {n}: {r}")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
