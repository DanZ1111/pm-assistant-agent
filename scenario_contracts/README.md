# PM Scenario Contract System

A deterministic runner for PM-workflow scenarios. AI helps write scenarios;
this runner executes them; humans decide which scenarios become release
gates.

## Layout

```
scenario_contracts/
  lib/
    runner.py         CLI entrypoint; loads + validates + runs scenarios
    fixtures.py       build_db / create_user / create_project / seed_phases
    actions.py        PM actions callable from run()
    assertions.py     DB + UI assertion helpers callable from check()
    reporter.py       markdown + JSON report writer
  contracts/          *.py — one scenario per file
  reports/            gitignored; per-run artifacts
```

## Running

```bash
# One scenario
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/golden_pass.py

# Whole directory
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/

# Tag filter
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ --tag release_gate
```

Exit codes:
- `0` all scenarios passed
- `1` at least one assertion failed
- `2` at least one scenario was malformed

## Scenario shape

Every scenario MUST declare 5 metadata fields and 3 functions. The runner
rejects scenarios missing any of them.

```python
# scenario_contracts/contracts/my_scenario.py
from scenario_contracts.lib import actions, assertions, fixtures

# --- Required metadata ---
ID = "my_scenario_001"
TITLE = "Short human description"
TAGS = ["release_gate", "deterministic"]
MATURITY = "stable"  # stable | candidate | experimental
WHY_IT_MATTERS = "One sentence on what regresses if this breaks."

# --- Required functions ---
def setup(db):
    # Ad-hoc fixture writes are OK here.
    pm = fixtures.create_user(db, "pm", role="pm")
    project = fixtures.create_project(db, "Demo", pm.display_name)
    return {"pm": pm, "project": project}

def run(world, db, http):
    # Only actions.* — no direct route or DB mutation.
    # `db` is used by service-layer actions (QA-01).
    # `http` is used by HTTP / Playwright actions (QA-03+).
    actions.record_event_note(db, world["project"].id, summary="Something happened")

def check(db, world):
    # Only assertions.* — no inline asserts.
    assertions.assert_row_count(db, "project_changes", expected=1,
                                where={"project_id": world["project"].id})
```

## Discipline boundary

Why the strict separation between `setup` / `run` / `check`?

- **setup** is where the world is built. Ad-hoc DB writes are fine.
- **run** is the system-under-test exercise. It must call only `actions.*`
  so the same code path runs in tests as in production.
- **check** is the contract. It must call only `assertions.*` so failures
  carry structured `expected` vs `actual` rather than bare `assert`s.

This keeps scenarios reviewable and forces reusable logic into the library.

## Tags

- `release_gate` — must pass before any v1.x release.
- `deterministic` — no LLM, no time-based flakiness.
- `ui` — requires Playwright. Skipped until QA-03 lands.
- `mocked_ai` — uses a queued fake LLM. Available from QA-04.

## Reports

Each run writes both `run_<timestamp>.md` (human) and `run_<timestamp>.json`
(machine-readable) to `reports/`. The directory is gitignored.
