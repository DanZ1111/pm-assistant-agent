# Feature Design Process

Every major feature OR schema change requires a short Feature Design Review BEFORE coding.

## The 11 Questions

Answer each in one sentence — no essays.

1. **What real workflow problem are we solving?** (concrete user moment, not "people might want this")
2. **Is it repeated or edge-case?** (edge case → defer)
3. **Does it need structured data?** (no → use Journal / notes / metadata)
4. **Could it live first in Journal / notes / metadata?** (yes → ship the lightweight version, watch usage, promote later)
5. **Does it increase intake burden?** (yes → reconsider; per Philosophy §2)
6. **Can AI reduce intake burden?** (extract from text/file/image? classify? confirm?)
7. **What display/reminder does it enable?** (per Philosophy §3 — display is the payoff)
8. **Does it affect migration?** (additive tables/columns OK; column removal or renames need a migration plan)
9. **What is the minimal schema change?** (smallest delta that ships the user value)
10. **What is the minimal UI change?** (one section, one button, one field — not a full redesign)
11. **What should be deferred?** (be explicit about what's NOT in this build)

## Plan Quality Gate (Q12–Q15, added 2026-06-18)

Q12–Q15 catch plan-defect classes that Q1–Q11 are silent on
(discoverability, missing failure-mode priors, prose-only locks).
For a non-dev reviewer, **only Q14 and Q15 are load-bearing** —
agent answers Q12 and Q13 in service of producing better Q14/Q15.

12. **Primary user click-path:** entry point → click sequence → final
    visible state. (Catches the "feature ships unreachable" class —
    e.g. sandbox-not-discoverable bug.)
13. **Reference scan (optional, novel feature classes only,
    time-boxed ~30 min):** one open-source analog + one closed-source
    product with the same UX surface; list 2–3 known failure modes for
    this feature class. Skip for incremental work the codebase already
    has examples of.
14. **Locked behaviors:** bullet list of UX/data/permission behaviors
    that must NOT drift later. One sentence each. *(User's primary
    review surface.)*
15. **Automated lock for each Q14 bullet:** name the test assertion
    that will fail if the behavior drifts. Source-pinned regex for
    structural locks, behavior test for observable ones. *(User's
    second review surface.)* Worked example in CLAUDE.md → Spec Drift
    Gate.

## Required for any new feature that creates structured data

Add an entry in `AI_TOOLS_REGISTRY.md` describing the corresponding AI tool (params, permissions, confirmation rule). If the tool isn't implemented yet, mark it `status: planned` with a TODO. AI must eventually be able to use every feature.

## When to skip this process

- Bug fixes
- Pure refactors with no schema/UI change
- Documentation-only updates

When in doubt, do the review — it's 5 minutes.
