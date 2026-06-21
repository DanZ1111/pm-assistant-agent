# AGENTS.md

This project may be continued by either Claude Code or Codex CLI. They take turns when one hits a token cooldown.

At the start of a session:
1. If `CURRENT_TASK.md` exists, read it for a one-paragraph reminder of what's in flight.
2. If `HUMAN_JOURNAL.md` exists, skim the latest entry so the user-facing story stays understandable.
3. Read `CLAUDE.md` for project rules.
4. **Open `QA_OPEN_BUGS.md`** for the curated list of QA-surfaced bugs that need `app/*` fixes. If you're picking up `app/*` work, this is the most direct way to know what's broken from a PM perspective. If a bug is in your domain (UI / sandbox / etc.), consider whether to land the fix before opening new work.
5. Inspect `git status`, `git diff`, and `git log --oneline -5` for the actual current state.
6. Open `MASTERPLAN.md` only when you need roadmap context (it is long).

Git/code is the source of truth. Trust git over prose.

When a plan or wireframe has been approved, stick to it. Do not improvise a different layout, workflow, or scope without calling out the conflict and getting approval first.

Do not push to origin unless the user explicitly asks. Do not auto-commit; prepare a commit and ask. If reviewing, review first and don't edit first.
