# `candidates/` — Scaffolding for AI-Drafted Scenarios

This directory holds **experimental** scenario drafts authored by AI
(Claude, Codex, ChatGPT, or anything else). Files here are not run
by the suite — humans **review** them, then **promote** them by
moving them to `../contracts/` or `../journeys/` and updating the
`MATURITY` field to `"candidate"`.

See [STABLE_CREDIBILITY.md](../../STABLE_CREDIBILITY.md) for the
full promotion contract.

## How to draft a new scenario via AI

1. Run the gap analyzer:
   ```
   python3 scenario_contracts/coverage.py
   ```
2. Take an uncovered CRUD function or AI tool from the output and
   feed it to your AI of choice, along with:
   - The text of one existing similar scenario as a template
     (e.g. `contracts/ai_proposes_journal.py` for AI-confirmation
     scenarios, `contracts/timeline_delay_reason_audit.py` for
     phase-mutation contracts).
   - The dispatch / handler signature from `app/crud.py` or
     `app/ai/tools.py`.
   - The discipline boundary rules from
     [STABLE_CREDIBILITY.md](../../STABLE_CREDIBILITY.md).
3. Save the AI's draft as `candidates/<descriptive_name>.py`.
4. Run it through the runner to confirm it parses and produces a
   reasonable PASS/FAIL:
   ```
   python3 -m scenario_contracts.lib.runner scenario_contracts/candidates/<name>.py
   ```
5. **Review the code** — the AI may have hallucinated function
   signatures, made wrong assumptions about state, or used `app.*`
   imports directly (boundary violation). Fix anything that
   breaks the contract.
6. Move the file to `contracts/` or `journeys/` and change
   `MATURITY` to `"candidate"`.

## Why a separate directory

The discipline is that **the suite runner does not execute
experimental scenarios**. Drafts are inert until a human reviews
them. Putting them under `candidates/` keeps the review step
explicit — you can't accidentally make an AI-drafted scenario a
release gate.
