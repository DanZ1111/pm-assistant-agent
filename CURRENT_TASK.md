# CURRENT_TASK.md

## Task
Build 23 — Chinese i18n

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder. If anything here disagrees with git, trust git.

## Current state
Build 22 is shipped. `test_ai_e2e.py` is in place (10 PASS / 7 SKIP / 0 FAIL — SKIPs flip to PASS once the server has a valid `OPENAI_API_KEY`). Working tree is clean. No Build 23 work started.

Roadmap scope (MASTERPLAN.md table row 1542, size: L): create `app/i18n.py` + `app/i18n/zh.json`. Add a `t(key)` Jinja2 global. Translate ALL visible UI strings: nav, page titles, section headers, button labels, badges, status labels, form labels. Thoughtful translations (not raw machine translate). Add a language switcher in the navbar. Persist user preference to `users.language` + a cookie fallback. **Deep docs (USER_GUIDE, CHANGELOG, ARCHITECTURE) stay English.**

No detailed Build 23 section exists in MASTERPLAN.md yet — write one in plan mode before coding. Build 23 is "size: L" so expect more sub-pieces than a typical S/M build.

## Remaining work
1. Plan-mode pass: write the Build 23 detail section in MASTERPLAN.md (i18n architecture, key naming convention, switcher UI, persistence model, tests).
2. Add `users.language` column via the existing migration infrastructure (app/migrations.py from Build 13).
3. Create `app/i18n.py` (loader + `t(key, **kwargs)` + locale detection middleware reading user pref or cookie).
4. Create `app/i18n/zh.json` (key → translation map).
5. Register `t` as a Jinja2 global; sweep templates replacing English strings with `{{ t('...') }}`.
6. Language switcher in `base.html` navbar.
7. Tests + docs + version bump.
8. Commit only after user explicitly asks.

## Constraints
- Translations must be thoughtful (especially product/PM domain terms). No "raw translate" placeholders.
- Deep docs stay English (USER_GUIDE, CHANGELOG, ARCHITECTURE, MASTERPLAN). i18n is for the UI only.
- Don't break any existing test by replacing a string the test asserts against — search for asserted strings before replacing.
- Bottom AI Chat (Build 21) UI labels translate; the prompts themselves (CHAT_ASK_SYSTEM_PROMPT etc.) stay English — they're instructions to the model, not user-visible UI.
- Do not push to origin without explicit user instruction.
- If unsure, read the code instead of trusting this file.

## Next step
Enter plan mode to draft the Build 23 detail section.

## Note on test_ai_e2e.py
Single command: `python3 test_ai_e2e.py`. Runs structural tests (always) + live AI round-trips (skip-on-error). Expected shape: all PASS or SKIP, never FAIL. After Build 24 ships and the OpenAI env is fixed, re-run for a clean PASS sweep.
