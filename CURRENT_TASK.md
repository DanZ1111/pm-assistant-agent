# CURRENT_TASK.md

## Task
Build 18 — Rendering History + Prototype Photos

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder. If anything here disagrees with git, trust git.

## Current state
Build 17 is shipped. Build 18 appears functionally complete in the working tree but is not committed yet. Last known local verification passed for Build 18 plus Build 17 and Build 16 regressions — re-check if code changes.

## Remaining work
1. Inspect git status / diff and confirm the Build 18 changes look expected.
2. Commit Build 18 only if the user explicitly asks.
3. After Build 18 ships, replace this file with the next build's relay note (Build 19 per MASTERPLAN.md).

## Constraints
- Do not change Build 18 code unless a test fails or the user asks.
- Do not push to origin without explicit user instruction.
- If unsure, read the code instead of trusting this file.

## Next step
Review the uncommitted Build 18 diff and prepare a commit summary for the user.
