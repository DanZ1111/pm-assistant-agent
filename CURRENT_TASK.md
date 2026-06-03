# CURRENT_TASK.md

## Task
Unreleased post-v1.2.0 fix — PM-facing project price strings.

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder.

## Current state

`origin/main` already contains:
- `7d56198` — Chinese IME composer controller (v2 mature fix)
- `2bd82bf` — Force Nixpacks Python-only provider after `package.json`

The current working tree contains an uncommitted project-price modeling fix.

## Problem

Project Target Factory Cost and Target MSRP were modeled as USD-only floats, but PM notes often use planning expressions:
- `MSRP $70-100`
- `under 120 RMB`
- `约 120 RMB 出厂`

Forcing those into floats made AI intake either guess, clear, or collapse the value incorrectly.

## Architecture Choice

- Add `projects.target_factory_cost_text` and `projects.target_msrp_text` as the PM-facing display/edit source of truth.
- Keep legacy `projects.target_factory_cost` and `projects.target_msrp` floats as optional derived/simple-USD values for old rows and future profit math.
- Variant cost/MSRP fields stay numeric because they belong to the future Profit Model calculation layer.
- No destructive column conversion.

## Implemented

- Model properties display text prices with fallback to old numeric values.
- Migration `003_v1_2_add_price_text_fields` adds text columns and backfills old numeric rows as strings.
- Manual project forms and AI-assisted review forms use text inputs.
- Manual create/edit and AI confirm preserve the entered string and only mirror one clean USD amount into the legacy float.
- AI extraction prompts now preserve ranges, currencies, and qualifiers instead of requiring USD-only numbers.
- Parser normalization extracts field-specific price strings such as `约 120 RMB 出厂` and `$70-100`.
- Project list/detail/sidebar display price strings.
- Chat project-field updates accept string prices and mirror simple USD only when possible.
- Role-filtered project context returns display strings.

## Verification So Far

- `python3 test_build29.py` — 24/24 PASS.
- `python3 test_build22.py` — 15/15 PASS.
- `python3 test_build23.py` — 24/24 PASS.
- `python3 test_build27.py` — 29/29 PASS.
- Static checks: `python3 -m compileall -q app`, `node --check app/static/js/main.js`, `git diff --check` PASS.
- Local migration applied successfully.
- Smoke: `/ai/intake/confirm` saved `under 120 RMB` and `$70-100`, left legacy numeric columns empty, and rendered both strings on project detail.

## Remaining

- Run final `git status` / optional broader regression.
- Await explicit commit / push instruction.
