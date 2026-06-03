# v1.3 Masterplan - Project Detail Command Center

## Purpose

v1.3 turns Project Detail from a database-style record page into a daily PM command center for knife product development.

The page should support two distinct work modes:

- **Overview:** understand the product, concept, visuals, variants, files, and commercial context.
- **Timeline:** push execution forward with phase pressure, next actions, blockers, and history.

This is a planning series only until reviewed. Do not implement code from these files until the user explicitly approves a build.

## Build Naming

v1.3 resets build numbering for this minor-version series:

- `v1.3 Build 01`, `v1.3 Build 02`, etc.
- Test files use `test_v13_build01.py`, `test_v13_build02.py`, etc.
- Do not reuse old `test_build1.py` naming.

## Build Sequence

| Build | Name | Core outcome |
|---|---|---|
| v1.3 Build 01 | Workspace Shell | Add Overview/Timeline tabs, move existing timeline, remove Commercial Snapshot. |
| v1.3 Build 02 | Overview Project Pulse v1 (Rules-Based) | Add rules-based derived status/attention/next-action section; defer richer intelligence. |
| v1.3 Build 03 | Overview Product Concept | Rework thesis and inspired-by into a readable concept area. |
| v1.3 Build 04 | Overview Renderings Section | Add standalone renderings section after Product Concept. |
| v1.3 Build 05 | Variant Command Cards | Redesign variants as expandable PM-facing option cards. |
| v1.3 Build 06 | Timeline Command Center Shell | Replace timeline first impression with command center shell. |
| v1.3 Build 07 | Timeline Command Actions Backend | Wire timeline actions only after backend honesty mapping. |
| v1.3 Build 08 | Timeline History | Derive typed timeline history from existing records. |
| v1.3 Build 09 | Planning Sandbox Design Only | Document future template/dependency sandbox; no implementation. |
| v1.3 Build 10 | v1.3.0 Release Hardening | Bump version/docs and ship release-proof regression after Builds 01-09. |

## Non-Negotiable Product Decisions

- Renderings is a standalone section after Product Concept, not inside Product Concept.
- Commercial Snapshot is removed as a promoted first section.
- Cost/MSRP are not first-screen commercial trophies; long-term commercial context belongs mainly inside Variant Command Cards.
- Product Thesis remains high in Overview and is not buried.
- Project Pulse in Build 02 is v1 rules-based display, not final AI/velocity intelligence.
- Timeline first screen must feel like an execution workspace, not a static planned/actual table.
- Add Blocker must have an architecture decision before Build 07 implementation begins.
- Planning Sandbox is design-only in initial v1.3.
- v1.3.0 requires Build 10 release-hardening; the version must not remain v1.2.1 after the v1.3 series ships.

## Backend Honesty Requirement

Before every Timeline implementation build, create a mapping table for each visible field:

| Visible field | Source of truth | Write path | Derived-state rule | Permission rule | Test coverage |
|---|---|---|---|---|---|

No Timeline UI may present fake intelligence. If a field cannot be honestly sourced yet, render it as an explicit placeholder or defer it.

Before wiring any Timeline action, create an action mapping:

| UI action | Route/service | DB write | Derived state refresh | History/audit entry | Test |
|---|---|---|---|---|---|

If existing backend routes cannot satisfy the mapping, leave the action as a placeholder.

### Add Blocker Decision Gate

Before v1.3 Build 07 begins, complete an Architecture Review for Add Blocker and choose one source of truth:

| Option | When acceptable | Risk |
|---|---|---|
| `project_blockers` table | Blockers are active state with owner/status/resolution and must affect Project Pulse, Timeline pressure, and cross-phase aggregation. | Requires schema, migration, service functions, permissions, audit, and rollback plan. |
| `ProjectJournalEntry.entry_type = "blocker"` | Blockers are narrative updates only and do not need active state, resolution tracking, or command-center aggregation. | Easy to ship but may lose the PM command-center behavior v1.3 is trying to create. |

Default expectation: if blockers need to drive Pulse/Timeline status, use a first-class blocker model. If the Architecture Review is not complete, Add Blocker stays a visible placeholder.

## Feature Design Review

1. **Real workflow problem:** PMs need one daily command center to understand and move knife projects forward quickly.
2. **Repeated or edge-case:** Repeated; Project Detail is the core screen used during daily product work.
3. **Structured data:** Early builds use existing data; later Timeline actions may need structure only after mapping proves it.
4. **Could live in notes first:** Timeline history should derive from Journal/change log/phase changes before adding a new event table.
5. **Intake burden:** The redesign should reduce scanning and manual table editing, not add more form burden.
6. **AI reduce burden:** AI can suggest next actions and capture updates, but every write stays confirmation-gated.
7. **Display payoff:** PMs see status, concept, visuals, variants, execution pressure, and history faster.
8. **Migration impact:** Builds 01-06 should avoid schema; Build 07 requires architecture review if new action structure is needed.
9. **Minimal schema:** None until existing tables cannot honestly represent the required Timeline action or state.
10. **Minimal UI change:** Split into tabs first, then improve one section/workspace per build.
11. **Deferred:** Sandbox implementation, detailed product-spec schema, designer portal backend, full timeline template engine, and richer Project Pulse intelligence such as peer velocity and conversation-derived nudges.

## Testing Standard

- Each build gets `test_v13_buildNN.py`.
- Every build runs `python3 test_build_v121.py` as the release baseline.
- UI builds require Playwright desktop and mobile screenshots.
- Timeline builds require state-transition tests, not only UI presence checks.
- Build 10 adds a release-proof regression such as `test_v13_build10.py` that verifies `app/version.py`, visible version strings, docs rollup, v1.3 regression inventory, and the v1.2.1 baseline still pass.
- i18n bundle parity must remain exact for all new visible labels.

## Review Workflow

1. Commit this plan series only.
2. Have ChatGPT and Claude review the plan files.
3. Revise plan files if review finds scope or ordering problems.
4. Implement only the approved next v1.3 build.
5. Stop after each build for report, review, and commit.
