# CLAUDE.md — Working Rules for This Project

## Read First

Before any significant work, read:
- `ARCHITECTURE.md` — what this system is and how it must be built
- `TESTING_RULES.md` — how to prove work is done

Before designing a new feature or proposing a schema change, also read:
- `PRODUCT_DEVELOPMENT_PHILOSOPHY.md` — 10 product principles
- `FEATURE_DESIGN_PROCESS.md` — the 11-question Feature Design Review

Produce a Feature Design Review (the 11 questions answered in 1 sentence each) before writing any code for a non-trivial feature.

For any feature that creates structured data, add a corresponding tool entry in `AI_TOOLS_REGISTRY.md` — AI must eventually be able to use every feature, not just chat about them.

If a request conflicts with these files, explain the conflict before proceeding.

---

## Build Discipline

- Implement only the approved build. Do not jump ahead.
- After finishing, stop and report (see Report Format below).
- If a build is large, ask to confirm scope before starting.

**Current build order:**
Build 1 → Build 1.5 → Build 2 → Build 3 → Build 4 → Build 5 → Build 6 → Build 7

---

## Before Changing the Database Schema

Write a short Architecture Review first:
1. What problem is this solving?
2. Which tables and service functions are affected?
3. Should this be a real column or handled in notes/thesis/change log?
4. Does this bypass the service layer?
5. Does it require change-log recording?
6. What is the rollback plan?

Do not add columns casually. See `ARCHITECTURE.md §14`.

---

## Testing Requirement

**Do not say a build is done without testing it.**

After every build or significant change:
1. Start the app: `python run.py`
2. Run Playwright tests: `python3 test_build1.py` (or equivalent for the build)
3. Fix all failures before reporting complete

See `TESTING_RULES.md` for required test flows per build.

---

## AI Behavior Rules

- AI proposes. User confirms.
- AI must not silently overwrite: factory, cost, MSRP, PM, engineer, launch date, thesis, phase status.
- All AI writes must go through the confirmation flow and be recorded in the change log.

---

## Report Format (required after every build)

```
Files created/modified:
Routes added:
Service functions added/changed:
DB tables affected:
What is placeholder (not yet implemented):

Tests run: python3 test_build1.py (headless)
Passed: N / N
Failed: (list any)
Fixes made: (list any)
Remaining manual review: (list anything that can't be automated)
```

---

## Common Commands

```bash
python run.py                          # start app at http://localhost:8000
pip install -r requirements.txt        # install deps
python3 test_build1.py                 # run Build 1 tests
pip install playwright && python3 -m playwright install chromium  # setup Playwright
```

---

## Non-negotiable Rules

1. Routes stay thin — business logic in service functions in `crud.py`
2. `write_change()` called inside every mutating service function
3. `delayed` is never a project status — it is calculated
4. `needs_info` is never stored — it is calculated by `get_project_health()`
5. `current_stage` is derived from phases, never manually maintained as a separate truth
6. Product Thesis is the first section on the project detail page, not a buried field
7. AI never writes directly to the database without user confirmation
