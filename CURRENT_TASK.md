# CURRENT_TASK.md

## Task
Unreleased post-v1.2.0 bug fix — Chinese IME composer controller (v2 mature fix). Implementation complete in working tree; awaiting manual cross-IME verification before commit / push.

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder.

## What changed

The v1 IME fix (still uncommitted) layered three guards onto the existing keydown handler. It did NOT solve the bug because on Chrome + Sogou Pinyin and Edge + Microsoft Pinyin the event sequence is `compositionend` → `keydown(Enter, keyCode=13, isComposing=false)`, meaning all three guards are already FALSE by the time the Enter handler runs.

v2 (this fix, also uncommitted):
- New ES module `app/static/js/composer_controller.js` with `createComposerController` + named `IME_CONFIRM_ENTER_SUPPRESS_MS = 80` constant.
- Four defense layers including the new one-shot `suppressNextEnterUntil` window seeded on every `compositionend`. The window self-clears after blocking one Enter so deliberate rapid follow-up Enters still send.
- Both composers (dock + panel) refactored onto the shared controller.
- Single `maybeSubmitComposer()` entry point — keyboard Enter AND send-button click route through it.
- `app/templates/base.html` now loads `main.js` as `type="module"`.
- Locked by 10 JSDOM behavioral tests in `tests/composer_ime.test.mjs` (run via `npm run test:composer` or `node --test`).
- `test_build29.py` extended with 6 named grep assertions + a JSDOM subprocess assertion (skip-on-missing-Node). Now 20/20.

## Setup (one time)

```
npm install
```

Installs `jsdom` (single devDep, ~17 MB). On systems with a permission-broken global npm cache, `npm install --cache "$(pwd)/.npm-cache"` works around it without sudo.

## Verification at this point
- `node --test tests/composer_ime.test.mjs` — 10/10 PASS (one-shot semantics included).
- `python3 test_build29.py` — 20/20 PASS (was 12/12 pre-fix).
- Browser smoke (English-only): dev server still serves chat at `localhost:8000`; module loads cleanly.

## Manual verification (gating before commit / push)

| Scenario | Chrome + Sogou (Win) | Edge + MS Pinyin (Win) | Safari + macOS 拼音 |
|---|---|---|---|
| Active composition + Enter doesn't send | | | |
| Plain English Enter sends | | | |
| Shift+Enter inserts newline | | | |
| Exact `LC200N` pattern: textarea reads `LC200N`, no message sent until final Enter | | | |
| Deliberate rapid Enter after IME confirm (within 80ms of last block) — does send (one-shot proof) | | | |
| Final Enter (>80ms after last composition) sends `LC200N` | | | |
| Send-button click while composing sends what's there (explicit intent) | | | |

The Chrome + Sogou column is the actual reported failing case and MUST be fully green before commit. Other columns are best-effort based on machine access — mark cells `N/A` with rationale if a setup isn't available.

## Commit plan (once manual matrix is green)

Single commit on top of v1.2.0:
```
Chinese IME composer controller (v2 mature fix, unreleased)
```

Files: `app/static/js/composer_controller.js` (new), `app/static/js/main.js` (refactor), `app/templates/base.html` (type=module), `tests/composer_ime.test.mjs` (new), `package.json` (new), `.gitignore` (add node_modules/, .npm-cache/), `test_build29.py` (expanded), `CHANGELOG.md` (Unreleased entry), `CURRENT_TASK.md` (this file).

No version bump. Stays `v1.2.0`. A `v1.2.1` release-proof regression can come when more small fixes accumulate.

## What's NOT in v1.2 (deferred candidates for v1.3)

- Native-speaker Chinese review of strings added in Builds 26-28.
- AI prompt translation, Help modal body translation, `/admin/*` page translation.
- Full Profit Model implementation (placeholder still ships).
- Row-level multi-tenancy (`Organization` table + `org_id` everywhere). Deployment-level isolation (Build 25) remains the answer for ≤3 departments.
- Wiring `delete_variant`, `delete_variant_component` through chat (currently manual-UI-only with admin gate).
- Auto-provisioning script for Railway (the DEPLOYMENT.md runbook is still manual).
- Adding JSDOM composer tests to CI (no CI configured today).
- Pruning the now-historical "Claude Review Request" block at the end of `BUILD26_CODEX_PLAN.md`.

## Next step

Fill in the Chrome + Sogou (Win) column of the manual matrix above, then ask for explicit commit / push instruction.
