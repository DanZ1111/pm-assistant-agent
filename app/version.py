"""Single runtime source of truth for the app's current version.

UI labels (navbar Help button, modal footer, page-rendered version) must
read from these constants. VERSION.md and CHANGELOG.md remain the
human-readable documentation; this module is what the running app uses.

When bumping the version: update these three constants AND VERSION.md AND
add a CHANGELOG entry. The canonical mapping lives in VERSION.md.
"""

CURRENT_VERSION = "1.2.0-build28"
CURRENT_BUILD_NAME = "Build 28 — Assistant PDF, DOCX, and image intake"
LAST_UPDATED = "2026-06-01"
