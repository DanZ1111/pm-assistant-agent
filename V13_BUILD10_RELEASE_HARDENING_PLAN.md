# v1.3 Build 10 - v1.3.0 Release Hardening

## Summary

Close the v1.3 Project Detail Command Center series as a real minor release. This build ships no new product behavior; it proves Builds 01-09 are complete, documented, regression-locked, and visible as `v1.3.0`.

## Implementation Changes

- Bump `app/version.py` from the current v1.2 line to `v1.3.0`.
- Update visible release metadata so navbar/help/footer surfaces show v1.3.0.
- Update `VERSION.md`, `CHANGELOG.md`, `USER_GUIDE.md`, and `CURRENT_TASK.md` with the final v1.3 scope.
- Ensure the v1.3 plan files reflect what actually shipped and what stayed deferred.
- Add a release-proof regression file, expected name: `test_v13_build10.py`.
- Do not add new UI behavior, schema, routes, or AI tools in this hardening build.

## Release-Proof Regression

`test_v13_build10.py` should verify:

- `app/version.py` reports `1.3.0`.
- Help/navbar/footer version strings render as v1.3.0.
- `VERSION.md`, `CHANGELOG.md`, and `USER_GUIDE.md` mention the shipped v1.3 command-center scope.
- v1.3 build test files exist for Builds 01-10.
- v1.3 release docs do not claim deferred features shipped.
- i18n key parity remains exact.
- `python3 test_build_v121.py` still passes as the previous minor-line baseline.

## Required Test Runs

- `python3 test_v13_build10.py`
- `python3 test_build_v121.py`
- All available `test_v13_buildNN.py` files from Builds 01-09.
- Any v1.2 regression files touched by shared templates, services, or assistant flows.
- Playwright desktop and mobile smoke for Project Detail Overview and Timeline tabs.

## Acceptance Criteria

- The app visibly identifies itself as v1.3.0.
- All shipped v1.3 behavior is regression-tested.
- Deferred items remain clearly documented as deferred.
- The working tree is clean and commit-ready after generated artifacts are removed.

## Explicit Deferrals

- No Planning Sandbox implementation.
- No new Product Spec schema.
- No Designer Portal backend.
- No timeline template engine.
- No new blocker model unless Build 07 already approved and shipped it.
