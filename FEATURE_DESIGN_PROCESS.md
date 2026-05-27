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

## Required for any new feature that creates structured data

Add an entry in `AI_TOOLS_REGISTRY.md` describing the corresponding AI tool (params, permissions, confirmation rule). If the tool isn't implemented yet, mark it `status: planned` with a TODO. AI must eventually be able to use every feature.

## When to skip this process

- Bug fixes
- Pure refactors with no schema/UI change
- Documentation-only updates

When in doubt, do the review — it's 5 minutes.
