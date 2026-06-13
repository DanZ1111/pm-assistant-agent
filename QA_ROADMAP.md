# QA Roadmap — PM Scenario Contract System

## Status

Living document. Defines the full ambition (end-to-end PM journey
testing with realistic disruptions) and the small-loop execution path
that gets us there incrementally.

Owner: Claude + Codex (alternating; see `AGENTS.md`).
Approved by user: 2026-06-10 (Path A ambition, Path C execution per
`/Users/Mordred5687/.claude/plans/can-you-still-find-nested-cook.md`).

## Vision

A QA system that can simulate a **complete pseudo-PM project**:

> PM opens with a couple of ideas, links them, drafts a plan via the
> Planning Sandbox, applies it, then pushes the project through 6+
> phases — mixing manual edits with AI intake from three different
> surfaces (top-level chat, project card chat, timeline planner). The
> simulation injects realistic disruptions: the factory makes a
> mistake and a prototype round must be added; the factory raises
> the price because of geopolitical news; the PM decides to add a
> color-only variant late in the cycle. At every step the runner
> **predicts** the expected system reaction and verifies the actual
> reaction matches. Divergences fail the journey.

This catches the integration bugs that no single contract test can
surface — the seven things that all need to work together to ship a
project don't actually compose.

## Two test classes (both required)

| Class | Shape | Catches | Status |
|---|---|---|---|
| **Contract** | `setup → run → check` (atomic) | "you broke X" regressions | QA-01..QA-03 done; gaps remain (see Tier 1 below) |
| **Journey** | `setup → [step, step, step, ...] → final_check` | "X, Y, Z don't compose" integration bugs | Not yet built. Lands in QA-04..QA-09. |

Contracts catch unit regressions cheap and fast. Journeys catch
integration regressions slowly but realistically. **Both layer; neither
replaces the other.**

## Build sequence (ambitious path)

Each QA build is a plan-first, small-loop, committed unit so Codex (or
future-Claude) can trace history. Estimated effort assumes one
contributor working linearly.

### Shipped

| Build | Scope | Status |
|---|---|---|
| **QA-01** | Runner skeleton + 5 golden tests | ✓ `dcd203a` |
| **QA-02** | First 5 hard contract scenarios (ownership / viewer / variants / timeline delay / sandbox apply) | ✓ `8501894` |
| **QA-03** | Playwright UI layer + 2 UI smokes + intentional UI failure proof | ✓ `79cce10` |
| **QA-04** | Journey runner skeleton + first mini-journey (6 steps, deterministic, no AI) | ✓ `a273f74` |
| **QA-05** | Mocked AI library + 4 confirmation-required contracts (idea / journal / due_date_shift / blocker) at dispatch level | ✓ `d24cfec` |
| **QA-06** | Tier 1 contract gaps — Marine-bug regression + delete permission boundary + create idempotency + finish_phase advancement + blocker lifecycle | ✓ `a91bd5e` |
| **QA-07** | Sandbox UI mutation — clicking the palette Add button creates a node and the canvas updates end-to-end | ✓ `162501b` |
| **QA-08** | Disruption library (5 composable helpers) + medium journey (10 steps mixing manual actions + mocked AI + 2 disruptions) | ✓ `d0e491c` |
| **QA-09** | Full Marine Knife journey — 20 steps. Ideas → link → sandbox apply → 6+ phases → all 5 disruption types → multiple AI proposals → 2 color variants → blocker lifecycle → cumulative final state. End-state integration proof of the QA system itself. | ✓ this build |

### Path A — ambition (planned)

| Build | Scope | Why this slice | Effort |
|---|---|---|---|
| **QA-05b** | **HTTP-level AI scenarios.** Add FastAPI TestClient + auth-override scaffolding to the QA stack. Exercise `POST /ai/chat` end-to-end: AI proposal flow surfaces a `proposal_id` in the response; `POST /ai/chat/{cid}/proposals/{pid}/confirm` writes; `cancel` does not. Cover the `/ai/intake/extract` panel surface. Test the `_merge_reviewed_args` edit-then-confirm flow. | Layered on QA-05's dispatch-level proof. Picks up the serialization + route surface QA-05 explicitly deferred. | ~3h |
| **QA-06b** | **Excel batch intake idempotency.** Cover `create_projects_batch_with_idempotency`: review table with per-row create/skip/update semantics, idempotency token reuse, partial-failure rollback. QA-06 deferred this since the basic single-create idempotency contract already locks the atomic-claim mechanism. | Picks up the batch surface introduced in Build 30B. | ~2h |
| **QA-07b** *(Codex domain)* | **Sandbox UI mutation — non-destructive flows.** Node property panel edit, edge create via dependency checkbox, cycle rejection at edit time, Tidy auto-layout. Domain handoff to whoever ships v1.4 sandbox UI iterations (Codex). If they want regression coverage they can author these on top of QA-07's `lib/browser` + UI actions. We don't build it pre-emptively. | — | — |
| **QA-07c** *(Codex domain)* | **Sandbox UI Apply via the confirmation modal.** Destructive — needs a real test-project lifecycle. Same handoff rule: Codex picks this up if/when they want it. We provide the QA infrastructure (runner, browser path, scenario shape); they use it. | — | — |
| **QA-08** | **Disruption library + medium journey**. New `lib/disruptions.py` with composable helpers: `factory_raises_cost(pct)`, `supplier_delays(days)`, `prototype_round_added()`, `geopolitical_event()`, `variant_color_only_added()`. Medium journey: 10-12 steps including 2 disruptions and 2 AI intake interactions. | First taste of "AI PM reacts to a real-world disruption." | ~3h |
| **QA-09** | **Full Marine Knife journey**. 20+ steps. Ideas → link → sandbox → apply → 6 phases → 3 disruptions (factory mistake forcing R2 prototype, supplier delay, color variant added) → multiple AI intake interactions across all 3 surfaces → final state validation. Tags: `journey`, `marathon`. MATURITY starts as `candidate`; promoted to `stable` after 10 consecutive green runs. | The actual thing the user asked for. End-to-end integration proof. | ~4h |
| **QA-10** | **Coverage assistant + release-gate promotion**. AI reads existing scenarios + recent bug reports + plan files; emits Python scenario drafts under `candidates/`. Human reviews + moves to `contracts/` or `journeys/`. Adds a `run_qa_loop.sh N` script that runs the full suite N times and reports flakiness. Defines stable-credibility threshold in code. | Codex's QA-05 role: AI as scenario writer, not judge. | ~3h |

**Total remaining effort to "test the entire process": ~21 hours of focused work across 7 builds.**

## What this earns

After QA-09 ships, we can run:

```bash
bash run_qa_suite.sh             # all contracts + journeys; green = OK to ship
bash run_qa_loop.sh 10           # 10 consecutive runs; surface any flicker
```

And we get:

- **Coverage**: the load-bearing PM CRUD functions (~40 entries) each have at least one contract scenario.
- **Integration**: 1-3 full journeys exercise the whole lifecycle including disruptions.
- **Bug-feedback loop**: every bug filed → at least one new scenario before close.
- **Stable-credibility metric**: 10 consecutive green runs, 0 flaky scenarios in 10-run loop.

## Stable-credibility definition

A scenario is **stable** when:
- `MATURITY = "stable"` (set manually after review).
- It has passed 10 consecutive runs in the loop runner.
- It is referenced by at least one release gate.
- It has not been flagged flaky in the last 30 days.

A scenario is **candidate** when:
- It has been written and reviewed by a human.
- It passes at least once but hasn't earned `stable` yet.

A scenario is **experimental** when:
- AI drafted it; awaiting human review.
- Lives under `candidates/`, not `contracts/`.

The **suite** has stable credibility when:
- All `stable` scenarios pass 10 runs in a row.
- The load-bearing CRUD coverage list is 100% mapped to scenarios.
- The last 30 days of bug reports each map to ≥1 scenario added.

## Execution discipline (Path C — small loops)

Each QA build follows the same per-build discipline as the v1.3 / v1.4
product builds:

1. Write `QA_BUILDNN_EXECUTION_PLAN.md` with Architecture Review,
   Backend Honesty Mapping, locked decisions, test plan, acceptance
   criteria.
2. Implement; keep `lib/runner.py` under 300 LOC (split into a new
   helper module if approaching).
3. Write `test_qa_buildNN.py`; must pass 100%.
4. Run all prior `test_qa_buildNN.py` files; all must remain green.
5. Run `test_v14_build09.py` and `test_build_v121.py` as the v1.x
   release baseline — must remain green.
6. Commit with a message that names the gap closed and the next build.

## Out of scope (deferred indefinitely)

- Auto-promoting AI-drafted scenarios into release gates without human
  review.
- Live LLM as a release-gate judge. Live LLM is informational /
  non-blocking only (per Codex's "Key Rule" + User lock 5).
- Replacing the existing `test_*.py` per-build scripts. The QA system
  is additive; per-build tests remain the per-build regression gate.
- Multi-process / concurrent journey execution. v1 is serial.

## Reference

- Approved plan: `/Users/Mordred5687/.claude/plans/can-you-still-find-nested-cook.md`
- User locks: 10 explicit locks in the approved plan §"User locks"
- Codex's original 6-build sketch: from the user's 2026-06-09 paste
- Build 09 design doc (folded Codex's V14 plan): `V13_BUILD09_PLANNING_SANDBOX_DESIGN.md`
- v1.4 release: `2143a5e` (Build 09 release hardening); origin/main is auto-deployed to Railway

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-06-10 | Path A ambition + Path C execution | User confirmed: ambitious end state but small testable loops; commit at each loop boundary so Codex can trace. |
| 2026-06-10 | Scenarios are Python, not YAML | Project has zero YAML; ~60 self-contained Python test scripts. Avoids inventing a parser that needs its own debugger. |
| 2026-06-10 | Journey class added (`STEPS=[...]`) without breaking contract class (`setup/run/check`) | Backward compatibility; runner detects shape via attribute presence. |
| 2026-06-10 | UI scenarios opt-in via `ui` tag; SKIP cleanly if Playwright or dev server unavailable | Matches existing project convention; no new infra dependency. |
| 2026-06-10 | Mocked AI before live AI; live AI never gates releases in v1 | Codex's "Key Rule" + User lock 5. Live LLM is informational only. |
| TBD | Stable-credibility threshold (10 consecutive green runs?) | Locked in QA-10 plan after we measure flakiness. |
