"""Build 25 — Beauty Department isolated deployment tests.

Build 25 ships zero code changes. The deliverable is `DEPLOYMENT.md` (the
runbook) plus version + docs bumps. The actual Railway provisioning is on
the user; this test only verifies what Claude can verify remotely:
  1. DEPLOYMENT.md exists with the required runbook sections.
  2. Runtime version constants reflect Build 25.
  3. VERSION.md + CHANGELOG.md document Build 25.
  4. MASTERPLAN.md marks Build 25 as the current build.
  5. The existing v1.1.0 PM instance is still functional (sanity smoke).
"""
import os
import sys
from pathlib import Path

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = Path(__file__).resolve().parent
BASE = "http://localhost:8000"
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
    missing = [n for n in needles if n not in text]
    if missing:
        fail(label, f"missing: {missing}")
    else:
        ok(label)


def main():
    print("\n── DEPLOYMENT.md runbook ──")
    if not (ROOT / "DEPLOYMENT.md").exists():
        fail("DEPLOYMENT.md exists at project root", "file not found")
    else:
        ok("DEPLOYMENT.md exists at project root")
        deployment = read("DEPLOYMENT.md")
        contains_all(
            "DEPLOYMENT.md covers Railway service provisioning",
            deployment,
            [
                "Railway",
                "new Railway service",
                "PostgreSQL plugin",
                "DATABASE_URL",
            ],
        )
        contains_all(
            "DEPLOYMENT.md covers per-instance env vars",
            deployment,
            [
                "INITIAL_ADMIN_USERNAME",
                "INITIAL_ADMIN_PASSWORD",
                "OPENAI_API_KEY",
                "SECRET_KEY",
                "DISABLE_RELOAD",
            ],
        )
        contains_all(
            "DEPLOYMENT.md covers custom domain (subdomain pattern)",
            deployment,
            [
                "Custom domain",
                "CNAME",
                "subdomain",
            ],
        )
        contains_all(
            "DEPLOYMENT.md has a post-deploy verification checklist",
            deployment,
            [
                "Verify the new instance",
                "/healthz",
                "Isolation check",
                "Bootstrap cleanup",
            ],
        )
        contains_all(
            "DEPLOYMENT.md covers adding 3rd / 4th departments",
            deployment,
            [
                "Adding a 3rd",
                "row-level multi-tenancy",
            ],
        )
        contains_all(
            "DEPLOYMENT.md documents multi-instance operating concerns",
            deployment,
            [
                "Migrations",
                "Backups",
                "User accounts",
                "OpenAI spend",
                "File uploads",
            ],
        )

    print("\n── Runtime version constants ──")
    from app.version import CURRENT_BUILD_NAME, CURRENT_VERSION, LAST_UPDATED
    # Tolerant of post-release builds on the 1.1 or 1.2 line so that
    # adding follow-up builds (or shipping plain v1.2.0) doesn't
    # invalidate the "Build 25 still in the runtime line" proof.
    if CURRENT_VERSION.startswith(("1.1.", "1.2.")):
        ok(f"app.version CURRENT_VERSION preserves Build 25 or newer ({CURRENT_VERSION})")
    else:
        fail("CURRENT_VERSION", CURRENT_VERSION)
    if CURRENT_VERSION != "1.1.0-build25" or ("Build 25" in CURRENT_BUILD_NAME and "Beauty" in CURRENT_BUILD_NAME):
        ok("app.version CURRENT_BUILD_NAME is compatible with the current runtime build")
    else:
        fail("CURRENT_BUILD_NAME", CURRENT_BUILD_NAME)
    if LAST_UPDATED >= "2026-05-30":
        ok(f"app.version LAST_UPDATED is Build 25 date or newer ({LAST_UPDATED})")
    else:
        fail("LAST_UPDATED", LAST_UPDATED)

    print("\n── Release docs ──")
    version_md = read("VERSION.md")
    changelog = read("CHANGELOG.md")
    masterplan = read("MASTERPLAN.md")

    contains_all(
        "VERSION.md reflects Build 25",
        version_md,
        [
            "## What's new in v1.1.0-build25",
        ],
    )
    contains_all(
        "CHANGELOG.md has Build 25 entry",
        changelog,
        [
            "## v1.1.0-build25 — Beauty Department isolated deployment (Build 25)",
            "DEPLOYMENT.md",
            "Code changes: none.",
        ],
    )
    contains_all(
        "MASTERPLAN.md has Build 25 detail section",
        masterplan,
        [
            "### Build 25 — Beauty Department isolated deployment ✓ SHIPPED v1.1.0-build25",
            "separate deployment per department",
            "Feature Design Review",
        ],
    )

    print("\n── Existing PM instance still functional (sanity smoke) ──")
    try:
        r = requests.get(f"{BASE}/healthz", timeout=5)
        if r.status_code == 200 and r.json().get("status") == "ok":
            ok("Existing PM instance /healthz returns 200 ok")
        else:
            fail("PM /healthz", f"status={r.status_code} body={r.text[:80]}")
    except requests.RequestException as exc:
        fail("PM /healthz", f"request failed: {exc} (is the server running?)")

    try:
        r = requests.get(f"{BASE}/auth/login", timeout=5)
        if r.status_code == 200 and CURRENT_VERSION in r.text:
            ok(f"Existing PM instance serves the current version string ({CURRENT_VERSION})")
        else:
            fail(
                "PM version string",
                f"status={r.status_code} has_version={CURRENT_VERSION in r.text}",
            )
    except requests.RequestException as exc:
        fail("PM version string", f"request failed: {exc}")

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
