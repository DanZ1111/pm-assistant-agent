"""Single runtime source of truth for the app's current version.

UI labels (navbar Help button, modal footer, page-rendered version) must
read from these constants. VERSION.md and CHANGELOG.md remain the
human-readable documentation; this module is what the running app uses.

When bumping the version: update these three constants AND VERSION.md AND
add a CHANGELOG entry. The canonical mapping lives in VERSION.md.
"""

CURRENT_VERSION = "1.5.0"
CURRENT_BUILD_NAME = "v1.5.0 — Designer Portal MVP (v1.5 Builds 01-10)"
LAST_UPDATED = "2026-06-13"
