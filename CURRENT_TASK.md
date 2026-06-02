# CURRENT_TASK.md

## Task
Unreleased post-v1.2.0 bug fix — make the assistant dock and panel composers safe for Chinese IME candidate-confirmation Enter events.

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder.

## What just shipped (Builds 26-29 = v1.2.0)

- **Build 26** — Professional assistant workspace + project-aware Idea capture
- **Build 27** — Confirmed daily PM actions + Global read-only search
- **Build 28** — Assistant PDF, DOCX, and image intake
- **Build 29** — v1.2.0 release hardening (this commit): runtime bumped to plain `1.2.0`, `test_build29.py` written as the release-proof regression, VERSION.md / CHANGELOG.md / MASTERPLAN.md / USER_GUIDE.md updated with the v1.2 series summary + Chinese block, `test_build25.py` strict version check loosened to the `(1.1.0, 1.2.0)` pattern.

## Verification at ship time
- `test_build29.py` 12/12.
- Regression: `test_build20-28` all green; `test_build24.py` v1.1.0 release proof still passes; `test_build25.py` 15/15 after loosening.
- `test_ai_e2e.py` 10 passed / 7 external-AI skips / 0 failed.
- Browser: navbar serves `v1.2.0` (verified at `localhost:8000/auth/login`).
- i18n parity: 537/537.

## Unreleased IME fix

- Root cause: the shared assistant textarea keydown handler submitted on every unshifted Enter, including Enter events used to confirm Chinese input-method candidates.
- Fix: track `compositionstart` / `compositionend` for both assistant composers and ignore Enter while composing, including the Safari legacy `keyCode 229` path.
- Regression: `test_build29.py` now locks the composition guards.

## What's NOT in v1.2 (deferred candidates for v1.3)

- Native-speaker Chinese review of strings added in Builds 26-28.
- AI prompt translation, Help modal body translation, `/admin/*` page translation.
- Full Profit Model implementation (placeholder still ships).
- Row-level multi-tenancy (`Organization` table + `org_id` everywhere). Deployment-level isolation (Build 25) remains the answer for ≤3 departments.
- Wiring `delete_variant`, `delete_variant_component` through chat (currently manual-UI-only with admin gate).
- Auto-provisioning script for Railway (the DEPLOYMENT.md runbook is still manual).
- Pruning the now-historical "Claude Review Request" block at the end of `BUILD26_CODEX_PLAN.md` (light cleanup, can wait).

## Next step

Verify the IME fix, then await explicit user instruction before commit or push. After that, wait for the user to start v1.3 planning. Suggested directions to weigh:
1. Native-speaker zh review pass (small but valuable for the Beauty dept rollout).
2. AI prompt + Help modal translation (medium, completes the i18n story).
3. Profit Model real implementation (medium-large, the only major v1.1 placeholder still outstanding).
4. v1.3 architecture: row-level multi-tenancy if a 4th department appears.
