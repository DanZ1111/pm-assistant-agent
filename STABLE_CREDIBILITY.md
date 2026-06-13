# Stable Credibility — Promotion Rule for QA Scenarios

This document locks the **maturity contract** for every scenario in
`scenario_contracts/`. Promotion from one tier to the next is a
**manual** action (a human edits the `MATURITY` field of a scenario
file); the operational tooling shipped in QA-10 produces the data
humans use to decide.

The structural requirements for the `stable` tier are also enforced
by a linter in [test_qa_build10.py](test_qa_build10.py) — every
scenario with `MATURITY="stable"` must satisfy the checklist below
or the QA-10 regression fails.

---

## The 3 Maturity Tiers

### `experimental`

- **Where it lives:** `scenario_contracts/candidates/`
- **Origin:** AI-drafted from PRDs, bug reports, plan files, or
  product spec discussions. The drafter could be Claude, Codex,
  ChatGPT, or any other tool.
- **Promotion to candidate requires:** human review of the scenario
  code by a project contributor with QA context. The reviewer
  confirms:
  - The scenario shape is valid (5 metadata fields + 3 functions for
    a contract, or 5 metadata fields + `setup` + `STEPS` for a journey).
  - The discipline boundary holds (`run()`/`do_*()` uses `actions.*`
    /`disruptions.*` only; `check()`/`check_*()` uses `assertions.*`
    only; no raw `app.*` imports).
  - The scenario's `WHY_IT_MATTERS` is honest and meaningful — not
    a placeholder.
  - The scenario passes via the runner at least once.
- **On promotion:** move the file from `candidates/` to
  `contracts/` or `journeys/`; change `MATURITY` to `"candidate"`.

### `candidate`

- **Where it lives:** `scenario_contracts/contracts/` or
  `scenario_contracts/journeys/`.
- **Origin:** promoted from `experimental` after human review.
- **Promotion to stable requires:** all of the following:
  1. **10 consecutive green runs** in `run_qa_loop.sh 10`. The
     scenario must appear in the loop report's `tests` map with
     `{"pass": 10, "fail": 0}` and the report's overall `flaky`
     count must be 0.
  2. **The `release_gate` tag** in `TAGS`. Scenarios that don't
     gate release stay `candidate` indefinitely (it's a fine
     end-state).
  3. **Substantive `WHY_IT_MATTERS` text** — at least 80
     characters of *why this contract matters*. Boilerplate fails
     the QA-10 linter.
  4. **Human sign-off** that the scenario tests a load-bearing
     contract, not a transient feature flag or a tactical fix that
     will be reverted soon.
- **On promotion:** change `MATURITY` to `"stable"` in the
  scenario file. No other changes.

### `stable`

- **Where it lives:** `scenario_contracts/contracts/` or
  `scenario_contracts/journeys/`.
- **Origin:** promoted from `candidate` after the 4-condition rule
  above.
- **Demotion:** if a stable scenario starts flickering in
  `run_qa_loop.sh`, the human action is to **demote** it back to
  `candidate` (edit MATURITY) and investigate. Stable scenarios
  that flicker hide real regressions; the failure mode of "ignore
  the flake" is worse than the failure mode of "demote and inspect."

---

## What the QA-10 tooling provides

| Tool | What it gives you | What it doesn't do |
|---|---|---|
| `bash run_qa_suite.sh` | One-shot green/red signal across the whole QA system | Does not measure flakiness — that's the loop runner's job |
| `bash run_qa_loop.sh 10` | The data needed to decide on stable promotion: per-scenario pass/fail counts across 10 runs + a `flaky` count | Does not auto-promote anything |
| `python3 scenario_contracts/coverage.py` | The list of `app.crud.*` mutating functions and AI tools with no scenario coverage | Does not write scenarios — humans take the gap list to their own AI |
| `test_qa_build10.py` linter | Hard-fails CI if any `MATURITY="stable"` scenario lacks `release_gate` tag or has too-short `WHY_IT_MATTERS` | Does not check the 10-runs threshold (that's a humans-look-at-the-report decision; automation would require persistent state across CI runs which is out of scope) |

---

## Why the 10-runs threshold isn't auto-enforced

Tracking "consecutive green runs" requires persistent state across
CI runs — a stable scenario should not have to start its 10-count
over every time a new commit lands. The simplest auto-enforcement
needs a database (or a checked-in JSON file the CI updates), which
adds CI complexity and a place for the state to drift out of sync
with reality.

QA-10's pragmatic stance: humans review `run_qa_loop.sh 10` output
before promoting a scenario to stable. The data is unambiguous; the
human cost is one decision per promotion. If the project grows to
the point where automation is worth the cost, that's a future QA
build — likely "QA-10b: automated stable tracking via a
checked-in MATURITY ledger."

---

## What "release_gate" means

Tagging a scenario `release_gate` means: **if this scenario fails,
no release ships until the failure is understood**.

Adding the tag is a deliberate choice. Many useful scenarios are
not release gates — they catch regressions but don't block ship.
The release gate set is intentionally small enough that humans can
review every failure.

Current release-gate count is reported by:
```
python3 -m scenario_contracts.lib.runner scenario_contracts/contracts/ --tag release_gate
```

---

## What's NOT a stable-credibility input

- **Test runtime.** A slow scenario that catches real regressions is
  more valuable than a fast scenario that catches nothing.
- **Cyclomatic complexity** of the scenario code. Long but readable
  scenarios are fine.
- **Whether the scenario is in `contracts/` or `journeys/`.** Both
  can be stable.
- **Whether the scenario uses mocked AI, real CRUD, or disruptions.**
  All three compose freely; stability is about reliability across
  runs, not about which library functions a scenario uses.
- **Author identity.** AI-drafted scenarios that get human-reviewed
  and pass the 4 conditions are first-class stable scenarios.

---

## Cross-references

- [QA_ROADMAP.md](QA_ROADMAP.md) — full QA series plan and decision log
- [QA_BUILD10_EXECUTION_PLAN.md](QA_BUILD10_EXECUTION_PLAN.md) — the
  build that locked this rule in code
- [scenario_contracts/coverage.py](scenario_contracts/coverage.py) —
  offline gap analyzer
- [run_qa_suite.sh](run_qa_suite.sh) — one-shot suite runner
- [run_qa_loop.sh](run_qa_loop.sh) — N-run flakiness measurer
