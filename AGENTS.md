# AGENTS.md

This project may be continued by either Claude Code or Codex CLI. They take turns when one hits a token cooldown.

At the start of a session:
1. If `CURRENT_TASK.md` exists, read it for a one-paragraph reminder of what's in flight.
2. Read `CLAUDE.md` for project rules.
3. Inspect `git status`, `git diff`, and `git log --oneline -5` for the actual current state.
4. Open `MASTERPLAN.md` only when you need roadmap context (it is long).

Git/code is the source of truth. Trust git over prose.

Do not push to origin unless the user explicitly asks. Do not auto-commit; prepare a commit and ask. If reviewing, review first and don't edit first.
