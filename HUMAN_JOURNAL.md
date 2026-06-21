# HUMAN_JOURNAL.md

This file is for the human project owner. It is not a full technical
changelog. Keep it short enough to read when several Claude/Codex sessions
have happened in a row.

## How Agents Should Use This

- Sort work by natural-language small projects, not by every file or commit.
- For each small project, record:
  - Why the user wanted the change.
  - The simple plan/method.
  - What has landed.
  - What is postponed or still uncertain.
- Keep a short timeline showing where Codex left off and where Claude picked up.
- Do not replace `CURRENT_TASK.md`, `QA_OPEN_BUGS.md`, tests, or git history.
  This journal explains the story; git remains the source of truth.

---

## 2026-06-18 - Current Story After Sandbox + QA Handoffs

### Small Project 1: QA Agent That Finds Real PM Workflow Problems

**Why this exists:** The user found that QA missed obvious sandbox failures.
The old tests could prove buttons existed, but they did not behave enough like
a PM trying to use the system.

**Simple plan/method:** Use deterministic PM journey scenarios first. The QA
agent should simulate meaningful workflows, such as AI intake proposing a
prototype update, sandbox template use, connecting timeline modules, and
parallel planning. Avoid live LLM randomness for now.

**What has landed:** `0841b9c` added QA Build 12:
- AI prototype approval confirmation journey.
- Sandbox parallel planning journey.
- Sandbox template/connection journey.
- `test_qa_build12.py`.

**Postponed:** A live LLM scenario generator, AI release-gate judge, and broad
coverage matrix were explicitly deferred. The current QA is stronger, but it
is not yet a fully autonomous AI tester.

### Small Project 2: Fix Existing Sandbox UI/UX Bugs Found By The User

**Why this exists:** The user found the sandbox confusing and partly broken:
templates did not appear to apply, nodes floated without obvious connections,
the right panel trapped the user, the canvas jumped, and the module library was
not PM-friendly enough.

**Simple plan/method:** First rescue the mechanics that block use:
template replacement, connect mode, predictable panel behavior, QA hooks for
canvas testing, and PM journey tests. Then manually review whether the sandbox
is actually intuitive enough.

**What has landed:** `fa74c1a` added:
- Template picker replacement via `replace_existing`.
- Connect button mode.
- One-shot edge creation from selected source to newly added module.
- QA hooks for Cytoscape canvas.
- Restored the SB-Rescue-03 rule: after adding a module, stay on Modules tab
  instead of jumping into Selected Node.

**Postponed/uncertain:** The core bugs are covered by tests, but the sandbox
may still need product UX review. Passing QA does not automatically mean the
canvas now feels natural to a PM.

### Small Project 3: Rules For Better Agent Planning And Execution

**Why this exists:** A later coding session drifted away from an approved
sandbox UX lock because it made a QA scenario easier. The user also asked
agents to stick to approved plans and wireframes.

**Simple plan/method:** Turn important plan/wireframe decisions into explicit
locks and require automated tests for those locks.

**What has landed:** `18c40b5` added:
- Plan Quality Gate Q12-Q15 in `FEATURE_DESIGN_PROCESS.md`.
- Spec Drift Gate in `CLAUDE.md`.
- Back-ported QA-11 veto and Rule 6 checks.
- `CURRENT_TASK.md` was compacted into a shorter relay note.

**Postponed:** A broader markdown audit is deferred. No file moves without
explicit approval.

---

## Handoff Timeline

- User complained that the sandbox and QA did not behave like real PM work.
- Codex wrote the AI-assisted QA PRD and sandbox rescue direction.
- Sandbox rescue work landed earlier in `2108527`.
- Follow-up sandbox mechanics landed in `fa74c1a`.
- QA Build 12 PM journey scenarios landed in `0841b9c`.
- Claude/Codex process locks landed in `18c40b5`.
- Current git state at this journal entry: branch is ahead of origin by 4
  commits. These commits are local and not pushed yet.
- Tracked working tree is clean. One untracked local file exists:
  `.claude/scheduled_tasks.lock`.

