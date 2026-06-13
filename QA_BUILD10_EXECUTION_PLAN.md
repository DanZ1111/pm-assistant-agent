# QA Build 10 Execution Plan — Coverage Assistant + Suite Runner + Stable-Credibility Rule

## Status

Execution plan for the tenth and **final** QA Build.

Predecessor: QA Build 09 — Full Marine Knife journey (`2d1d58e`).

Successor: none. QA-10 closes the QA series; further QA work happens
incrementally as scenarios get added during normal product builds.

Canonical roadmap: [QA_ROADMAP.md](QA_ROADMAP.md).

Plan-first commit so Codex can review the scope before any implementation lands.

## Purpose

Close the QA series with the **operational tooling** that turns the
scenario library into a system the team actually uses every day:

- **One command** to run everything (`run_qa_suite.sh`).
- **One command** to measure flakiness (`run_qa_loop.sh N`).
- **A gap analyzer** that shows which `app.crud.*` functions have no
  scenario coverage — the input to "what should we test next?".
- **A written stable-credibility rule** that locks the
  candidate-→stable promotion contract.
- **A scaffolded `candidates/` directory** for AI-drafted scenarios
  that humans review before promotion.

Critically, the AI-assist story stays **offline and informational**:
the gap analyzer is deterministic Python that reads code. It tells
humans *where* coverage is missing; humans (with their own AI of
choice — Claude, Codex, ChatGPT) write the scenarios. The QA system
never calls a live LLM. Lock 5 from the approved plan
("Live LLM tests are non-gating only") stays intact.

## Scope

In:

1. `run_qa_suite.sh` at repo root — one command that runs:
   - all 9 `test_qa_buildNN.py` files (1 → 9)
   - the runner against `scenario_contracts/contracts/` and
     `scenario_contracts/journeys/`
   - reports unified `PASS / FAIL / INVALID / SKIP` counts
   - exits 0 only when everything is green
2. `run_qa_loop.sh N` at repo root — runs the full suite N times back
   to back; tracks per-scenario outcomes across runs; surfaces any
   scenario that flickers (PASS in one run, FAIL in another); reports
   final per-scenario stability.
3. `scenario_contracts/coverage.py` — gap analyzer CLI:
   - introspects `app.crud` for public functions whose name starts
     with `create_`, `update_`, `delete_`, `add_`, `resolve_`,
     `apply_`, `finish_`, `link_`, `mint_` (the load-bearing
     mutating surface)
   - introspects `app.ai.tools._HANDLERS` for AI-confirmable tool
     names
   - scans all `scenario_contracts/contracts/*.py` and
     `scenario_contracts/journeys/*.py` for `actions.<name>` and
     `ai_dispatch("<tool_name>"` references
   - reports the set of CRUD functions and AI tools NOT referenced
     in any scenario
4. `STABLE_CREDIBILITY.md` at repo root — locks the promotion rule:
   - `experimental`: AI-drafted, lives under `candidates/`, not yet
     human-reviewed.
   - `candidate`: human-reviewed, has passed at least once, lives
     under `contracts/` or `journeys/`.
   - `stable`: candidate + ≥10 consecutive green runs in
     `run_qa_loop.sh 10` + has `release_gate` tag + has substantive
     (≥80 char) `WHY_IT_MATTERS`. Promotion is a manual edit of the
     scenario file by a human.
5. `scenario_contracts/candidates/__init__.py` — empty placeholder
   that scaffolds the candidates directory for AI-drafted scenarios.
6. `test_qa_build10.py` regression that:
   - Locks `run_qa_suite.sh` and `run_qa_loop.sh` exist and are
     executable.
   - Locks `coverage.py` runs and emits at least one suggestion.
   - Locks `STABLE_CREDIBILITY.md` contains the 3 maturity tiers +
     the 10-consecutive-runs threshold.
   - Locks the **promotion contract** via a linter assertion:
     every scenario with `MATURITY="stable"` MUST have `release_gate`
     in its TAGS AND a `WHY_IT_MATTERS` of ≥80 characters.
   - Locks that the candidates/ directory exists.

Out:

- Live LLM calls from the QA system (the gap analyzer is offline
  Python).
- A web UI for the suite runner (CLI only in v1).
- Automated promotion (humans manually edit MATURITY).
- New contract scenarios (QA-10 is operational tooling only).
- New disruption helpers.
- `app/*` modifications.
- Version bump.

## Architecture Review

1. **Problem solved.** The scenario library is large enough now (5
   goldens + 5 QA-02 contracts + 4 QA-05 + 5 QA-06 + 1 QA-07 UI smoke
   + 3 UI scenarios from QA-03 + 2 journeys from QA-04/08 + 1
   marathon journey from QA-09 = 26 scenarios). Running them by hand
   one at a time is no longer practical. QA-10 ships the operational
   loop.
2. **Tables touched.** None. QA-10 is purely tooling around the
   existing test surface.
3. **Service layer.** None touched; the gap analyzer just reads
   source files.
4. **Change log.** None; QA-10 does not mutate the DB.
5. **Rollback.** Delete the 6 new files; the QA suite still works
   manually via individual `python3 test_qa_buildNN.py` invocations.

## Backend Honesty Mapping

| Visible behavior | Source of truth | Write path | Derived rule | Permission | Test |
|---|---|---|---|---|---|
| Suite pass/fail summary | per-test stdout | n/a | aggregate of `^Passed:` / `^PASSED:` / `^FAILED:` lines | CLI | `test_qa_build10` runs the suite script |
| Loop flakiness report | per-run outcomes | written to `scenario_contracts/reports/loop_N.json` (gitignored) | scenario flickers when outcome differs across runs | CLI | `test_qa_build10` runs `run_qa_loop.sh 2` and asserts the report exists |
| Coverage gap list | `app.crud` + `app.ai.tools._HANDLERS` source code | n/a | function not referenced anywhere under `scenario_contracts/contracts/` or `/journeys/` | CLI | `test_qa_build10` runs `coverage.py` and asserts non-empty output |
| Stable-credibility promotion | `STABLE_CREDIBILITY.md` | manual scenario file edit | `MATURITY="stable"` requires release_gate tag + substantive WHY_IT_MATTERS | n/a (human action) | `test_qa_build10` lints every scenario file for the rule |

## Locked Implementation Decisions

1. **Bash for the suite + loop runners.** Python is fine too but
   bash composes well with the existing `python3 test_qa_buildNN.py`
   pattern and stays close to how a human would run things manually.
2. **No live LLM in coverage.py.** The gap analyzer is purely
   source-code introspection. AI-assist happens outside the QA
   system — humans take the gap list to their own AI of choice.
3. **`MATURITY="stable"` linter is the promotion enforcement
   mechanism.** Future scenarios can't sneak `MATURITY="stable"`
   past code review without meeting the contract (release_gate tag
   + substantive WHY_IT_MATTERS). `test_qa_build10` runs the linter
   on every commit.
4. **10 consecutive runs threshold is documented, not enforced in
   code.** Tracking "consecutive runs" requires persistent state
   across CI runs which adds infrastructure cost out of scope for
   this build. Document the rule in `STABLE_CREDIBILITY.md`; future
   QA-10b can add automated tracking if needed.
5. **Reports are gitignored.** `scenario_contracts/reports/` already
   is; loop runs write `loop_<ts>.json` there.
6. **The candidates directory is scaffolded but empty.** Humans
   place AI-drafted scenarios there; review moves them to
   `contracts/` or `journeys/`.

## Files Added (new)

- `run_qa_suite.sh`
- `run_qa_loop.sh`
- `scenario_contracts/coverage.py`
- `STABLE_CREDIBILITY.md`
- `scenario_contracts/candidates/__init__.py`
- `test_qa_build10.py`
- `QA_BUILD10_EXECUTION_PLAN.md` (this file)

## Files Modified (additive only)

- `QA_ROADMAP.md` — mark QA-10 as shipped + close the series (after
  implementation commit).

## Test Plan

Run:

```bash
# 1. The suite runner reports unified results
bash run_qa_suite.sh
# Expect: exit 0; final line reports PASS counts per test + overall green

# 2. The loop runner over 2 runs surfaces flakiness (none expected)
bash run_qa_loop.sh 2
# Expect: exit 0; report says "0 flaky scenarios" or similar

# 3. The coverage gap analyzer prints something
python3 scenario_contracts/coverage.py
# Expect: non-empty list of CRUD functions / AI tools without scenario coverage

# 4. QA-10 regression
python3 test_qa_build10.py
# Expect: PASSED: N / FAILED: 0

# 5. Existing regressions still green
python3 test_qa_build09.py        # 15/15 PASS
python3 test_qa_build08.py        # 19/19 PASS
python3 test_qa_build07.py        # 16/16 PASS
python3 test_qa_build06.py        # 26/26 PASS
python3 test_qa_build05.py        # 23/23 PASS
python3 test_qa_build04.py        # 13/13 PASS
python3 test_qa_build03.py        # 21/21 PASS
python3 test_qa_build02.py        # 24/24 PASS
python3 test_qa_build01.py        # 24/24 PASS
python3 test_v14_build09.py       # 15/15 PASS
python3 test_build_v121.py        # 19/19 PASS
```

`test_qa_build10.py` must cover:

- Plan file exists and locks the 6 deliverables.
- `run_qa_suite.sh` exists, is executable, and references all 9
  test_qa_buildNN.py files.
- `run_qa_loop.sh` exists, is executable, accepts an N argument.
- `scenario_contracts/coverage.py` runs without error and emits at
  least one suggestion line.
- `STABLE_CREDIBILITY.md` contains: "experimental", "candidate",
  "stable", "10 consecutive", "release_gate",
  "WHY_IT_MATTERS".
- `candidates/__init__.py` exists.
- **Promotion-rule linter**: every scenario file with
  `MATURITY = "stable"` has `release_gate` in TAGS AND a
  `WHY_IT_MATTERS` string of length ≥ 80 characters.
- `app/*` is untouched; `app/version.py` stays at `1.4.0`.
- `lib/runner.py` LOC budget unchanged.

## Acceptance Criteria

- `bash run_qa_suite.sh` exits 0 and prints unified summary.
- `bash run_qa_loop.sh 2` exits 0 and emits a stability report.
- `python3 scenario_contracts/coverage.py` exits 0 and prints
  ≥ 1 uncovered CRUD function.
- `test_qa_build10.py` exits 0.
- All earlier QA + v1.4 + v1.2.1 regressions stay green.
- All current `MATURITY="stable"` scenarios pass the promotion-rule
  linter (the linter must not fail any of the 16 currently-stable
  scenarios).
- No `app/*` modification.

## What QA Build 10 is NOT

- Not introducing a live LLM coverage assistant (Codex's original
  sketch had AI generate scenarios; QA-10 ships the offline gap
  analyzer instead; the AI step happens outside the QA system).
- Not introducing automated stable-promotion (humans edit MATURITY
  manually; 10-runs threshold is documented).
- Not introducing CI configuration (the suite runner is the
  foundation a future CI build can hook into).
- Not changing the runner, the journey shape, scenarios, or
  contracts.
- Not bumping the product version.

## Closing the QA series

After QA-10 ships, the QA series is **complete as a system**:

- 26 scenarios across 4 maturity-tagged buckets.
- 1 marathon journey that exercises the full PM lifecycle.
- 1 medium journey + 1 mini journey for narrower integration cuts.
- 16 release-gate-tagged scenarios that any CI build can run.
- A gap analyzer to identify what's untested.
- A loop runner to measure stability over time.
- A written promotion rule for stable credibility.

Future QA work happens **incrementally**: each product build adds
its own contract scenarios; the gap analyzer surfaces what's
missing; humans (with AI help) author new scenarios into
`candidates/` → reviewed → moved to `contracts/` or `journeys/` →
gradually promoted to `stable` via the documented rule.

## Open questions

None blocking. If the gap analyzer surfaces a flood of untested
CRUD functions, the team triages by priority — QA-10 does not
demand any threshold of coverage to "pass." The gap list is
informational.
