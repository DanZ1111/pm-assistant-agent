# Build 29 — v1.2.0 Release Hardening (Plan)

> **Author:** Claude (2026-06-02)
> **Session goal:** push Build 27, commit + push Build 28, then ship Build 29 in one session.
> **Predecessor:** Build 28 (`1.2.0-build28`) — code complete in working tree, awaiting commit.
> **Reference:** [BUILD26_CODEX_PLAN.md:314-333](BUILD26_CODEX_PLAN.md#L314-L333) — Codex's original Build 29 spec, absorbed here.

---

## Context

The v1.2 series — Build 26 (assistant workspace), Build 27 (daily PM actions + Global search), Build 28 (assistant attachments) — is finished and tested. Build 29 is a release-hardening build, not a feature build. Its job is the same as Build 24 did for v1.1.0: bump the version constants from `1.2.0-build28` to plain `1.2.0`, write a release-proof test, update the release docs, and prove the regression suite still passes end-to-end.

No schema change. No new features. No new tools.

---

## Pre-Build-29 git hygiene

Two outstanding git operations before Build 29 starts:

### Step 1 — Push Build 27

Build 27 (`4e0c0aa`) is committed locally but `main` is one ahead of `origin/main`. Single command:

```bash
git push origin main
```

Expected: `dfb454a..4e0c0aa  main -> main` (actually `830bfd9..4e0c0aa` since plan commit pushed earlier).

### Step 2 — Commit + push Build 28

Build 28 is 23 modified files + 2 new files in the working tree. Codex was explicitly told not to commit without user authorization, which is why it's still dirty.

Stage everything Build 28 touched:

```bash
git add .gitignore AI_TOOLS_REGISTRY.md BUILD26_CODEX_PLAN.md CHANGELOG.md \
        CURRENT_TASK.md MASTERPLAN.md TESTING_RULES.md USER_GUIDE.md VERSION.md \
        app/ai/prompts.py app/ai/tools.py app/ai/attachments.py app/crud.py \
        app/i18n/en.json app/i18n/zh.json app/routes/ai_chat.py \
        app/static/css/styles.css app/static/js/main.js \
        app/templates/components/bottom_chat.html app/version.py \
        test_ai_e2e.py test_build20.py test_build26.py test_build27.py test_build28.py
```

Commit message:

```
Build 28 — Assistant PDF, DOCX, and image intake (v1.2.0-build28)

Adds pending file/image discussion to the assistant workspace. Bytes live
in ignored app/pending_uploads/ (outside the public /uploads mount) with
JSON sidecars carrying owner, type, and extracted text. PDF + DOCX text
is extracted locally for chat; images are sent as image content while
pending. Confirmed save_pending_attachment proposals move bytes into
project_files through the normal audited service with changed_by="ai"
and source_type="ai_chat". Request-time 24-hour cleanup; no worker, no
migration. Viewers cannot upload.

Tests: test_build28.py 23/23. Build 20-27 regressions pass.
test_ai_e2e.py 10P/7S/0F. EN/zh parity at 537/537.

Co-Authored-By: Codex <noreply@openai.com>
```

(Codex is co-author here, not Claude — Codex wrote the code. Claude just commits on Codex's behalf and signs the message.)

Then push: `git push origin main`.

After step 2, `main` is 3 commits ahead of where this session started (push 27, plus 1 new commit for 28, plus the eventual Build 29 commit).

---

## Build 29 implementation

Five concrete tasks. Order matters — version bump goes last so test files don't break mid-edit.

### Task A — Write `test_build29.py`

Model on [test_build24.py](test_build24.py) (the v1.1.0 release-proof test). The pattern is: persistent assertions about the *release artifact* (VERSION.md says "v1.2.0 released", CHANGELOG.md has the v1.2.0 mega entry, MASTERPLAN.md marks Build 29 shipped, all test files exist, i18n parity holds) using tolerant version checks (`startswith("1.2.0")`) so future post-release patches don't invalidate the proof.

Required assertion blocks:

1. **Runtime version source** — `from app.version import ...`
   - `CURRENT_VERSION.startswith("1.2.0")` — tolerant
   - `CURRENT_BUILD_NAME` non-empty
   - `LAST_UPDATED` is ISO date format
2. **Release docs**
   - VERSION.md contains `**Current Version:** v1.2.0`, `v1.2.0 released`, `## What's new in v1.2.0`
   - CHANGELOG.md contains `## v1.2.0 — Assistant Workspace Release` (or similar), plus all four series headlines: `Professional assistant workspace`, `Confirmed daily PM actions`, `Assistant attachments`, `No schema migration in Build 29`
   - MASTERPLAN.md marks Build 29 shipped with `### Build 29 — v1.2.0 release hardening ✓ SHIPPED v1.2.0`, `No database schema change.`, `python3 test_build29.py`
3. **USER_GUIDE coverage**
   - Short Chinese summary block: `## v1.2 中文速览`, key terms (`AI 工作区`, `确认卡`, `附件`)
   - English feature list covers: Professional Assistant Workspace, Confirmation Cards, Assistant Attachments, Global Search, Idea Auto-Capture, Duplicate Idea Detection
4. **Regression inventory** — list of expected test files including `test_build29.py`
5. **i18n bundle parity** — `set(en) == set(zh)` and `len(en) >= 537`

Target: ~18-20 assertions, mirroring test_build24's shape.

### Task B — Loosen prior-build version assertions

Per the same logic test_build24 was loosened for Build 25's bump: when Build 29 changes `CURRENT_VERSION` from `"1.2.0-build28"` to `"1.2.0"`, any test that strictly asserts `CURRENT_VERSION == "1.2.0-buildNN"` will fail.

Files to inspect + likely edit:
- `test_build26.py` — change `CURRENT_VERSION == "1.2.0-build26"` → `CURRENT_VERSION.startswith("1.2.0")`
- `test_build27.py` — same pattern
- `test_build28.py` — same pattern

Pattern: convert hard equality to `.startswith("1.2.0")`, document with a comment explaining the loosening (mirrors what test_build24 already does).

### Task C — Update release docs

In order of authority:

**[VERSION.md](VERSION.md)** — set header to:
```markdown
**Current Version:** v1.2.0
**Current Build:** Build 29 — v1.2.0 release hardening
**Last updated:** 2026-06-02
**Status:** v1.2.0 released
```
Add a `## What's new in v1.2.0` section summarizing the assistant workspace + confirmation cards + attachments + global search + idea auto-capture.

**[CHANGELOG.md](CHANGELOG.md)** — top of file, add:
```markdown
## v1.2.0 — Assistant Workspace Release

The v1.2.0 release packages Builds 26-28 plus this hardening build (29).

- Professional assistant workspace (Build 26): resizable split panel, compact dock, project-aware Idea capture with duplicate detection and human labels.
- Confirmed daily PM actions (Build 27): editable proposal cards in chat for journal entries, variants, components, file comments, allowlisted project-field edits, phase plan changes, finish phase. Plus read-only Global search across accessible projects.
- Assistant attachments (Build 28): PDF, DOCX, and image discussion with bytes held in pending storage outside /uploads until the user confirms save through the normal audited file service.
- No schema migration in Build 29 (release hardening only).
```

**[MASTERPLAN.md](MASTERPLAN.md)** — append to the build detail tree:
```markdown
### Build 29 — v1.2.0 release hardening ✓ SHIPPED v1.2.0

No database schema change.

Bumped runtime to 1.2.0; wrote test_build29.py release proof; updated VERSION.md / CHANGELOG.md / USER_GUIDE.md / AI_TOOLS_REGISTRY.md to describe the shipped v1.2 series; verified Build 20-28 regressions pass.

Tests: python3 test_build29.py
```

Also update the Build List table header so Build 29 is the last `✓ SHIPPED` row.

**[USER_GUIDE.md](USER_GUIDE.md)** — add sections for the new v1.2 capabilities (assistant workspace, confirmation cards, attachments, global search, idea workflow). Add a `## v1.2 中文速览` short Chinese block (same pattern as the existing `## v1.1 中文速览`).

**[AI_TOOLS_REGISTRY.md](AI_TOOLS_REGISTRY.md)** — confirm all newly wired tools (idea + journal + project-field + variant + component + file-comment + phase + finish_phase + save_pending_attachment + global search) are marked with their wire-build number. Codex did most of this in Builds 26-28; Build 29 just confirms the table is current.

### Task D — Bump `app/version.py`

Last edit:

```python
CURRENT_VERSION = "1.2.0"
CURRENT_BUILD_NAME = "Build 29 — v1.2.0 release hardening"
LAST_UPDATED = "2026-06-02"
```

After this edit, the dev server's navbar should show `v1.2.0`. Hot reload will pick it up if `DISABLE_RELOAD` is not set.

### Task E — Verification sweep

Run in order, fix any failures before moving on:

1. `python3 test_build29.py` — must pass all assertions.
2. Regression: `python3 test_build28.py`, `test_build27.py`, `test_build26.py`, `test_build25.py`, `test_build24.py`, `test_build23.py`, `test_build22.py`, `test_build21.py`, `test_build20.py`. All must stay green.
3. `python3 test_ai_e2e.py` — expected `10 passed, 7 skipped, 0 failed`.
4. `curl http://localhost:8000/healthz` — `{"status": "ok"}`.
5. Browser hard-refresh, confirm navbar shows `v1.2.0` (not `v1.2.0-build28`).

If any earlier-build regression fails, the most likely cause is a missed strict-version assertion (see Task B). Loosen and retry.

### Task F — Commit + push Build 29

```
Build 29 — v1.2.0 release hardening (v1.2.0)

Release-hardening build for the v1.2 series (Builds 26-28). Bumps
runtime to 1.2.0, adds test_build29.py release proof modeled on
test_build24, loosens prior-build version assertions to startswith
pattern, and updates VERSION.md / CHANGELOG.md / MASTERPLAN.md /
USER_GUIDE.md / AI_TOOLS_REGISTRY.md to describe the shipped series.

Tests: test_build29.py NN/NN. Builds 20-28 regressions pass.
test_ai_e2e.py 10P/7S/0F.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```

Then `git push origin main`. Final `main` HEAD should be the v1.2.0 release commit.

After commit, update [CURRENT_TASK.md](CURRENT_TASK.md): mark Build 29 shipped, point at next planning step (TBD — likely a v1.3 planning session, but no commitment yet).

---

## Critical files

Read first:
- [test_build24.py](test_build24.py) — the canonical release-proof shape; test_build29.py is a parallel rewrite
- [VERSION.md](VERSION.md) — current header format
- [CHANGELOG.md](CHANGELOG.md) — confirm `## v1.1.0` entry format
- [MASTERPLAN.md](MASTERPLAN.md) — Build List table shape + per-build detail section convention
- [USER_GUIDE.md](USER_GUIDE.md) — find the `## v1.1 中文速览` block to mirror format

Modify:
- `app/version.py` (LAST step)
- `VERSION.md`, `CHANGELOG.md`, `MASTERPLAN.md`, `USER_GUIDE.md`, `AI_TOOLS_REGISTRY.md`
- `test_build26.py`, `test_build27.py`, `test_build28.py` (loosen version assertions)
- New: `test_build29.py`
- `CURRENT_TASK.md` (mark Build 29 shipped at the end)

---

## Verification (end-to-end acceptance)

1. `python3 test_build29.py` passes.
2. `python3 test_build20.py` through `python3 test_build28.py` all pass.
3. `python3 test_ai_e2e.py` 10P/7S/0F.
4. `app.version.CURRENT_VERSION == "1.2.0"`.
5. Browser confirms `v1.2.0` rendered in navbar.
6. `git log -1 --oneline` shows the Build 29 commit on `origin/main`.

---

## Out of scope (defer to v1.3 if proposed)

- New features. This build is purely release-hardening.
- Schema changes (`Organization` table for row-level multi-tenancy still deferred; deployment-level isolation remains the v1.2 answer for the Beauty department per Build 25).
- Native-speaker review of `app/i18n/zh.json` strings added in Builds 26-28.
- Full Profit Model implementation (placeholder still ships in v1.2).
- AI prompt translation, Help modal body translation, `/admin/*` page translation.
- Wiring any remaining stubbed AI tools.
- Pruning the now-historical "Claude Review Request" block at the end of BUILD26_CODEX_PLAN.md — light cleanup, can wait for v1.3 planning.

---

## Risks and failure modes

- **Strict version assertions in prior-build tests** (most likely failure cause). Mitigation: do Task B before Task D — bump version AFTER loosening the strict checks, so the regression sweep is clean on first try.
- **i18n key drift**. CURRENT_TASK reports 537/537 parity. If USER_GUIDE.md adds any new translation keys (unlikely — the Chinese summary is static markdown), parity must hold. Mitigation: don't add new translation keys in this build; keep new prose in the doc files only.
- **Dev server hot-reload caching the old version string**. Mitigation: hard-refresh browser; if needed, restart `python run.py`.
- **MASTERPLAN.md insertion order**. Past mistake: anchor-on-Build-N inserted Build N+1 BEFORE it. Mitigation: use Edit with sufficient context to anchor at the correct insertion point. Verify the section ordering after the edit.

---

## One-session ordering summary

1. `git push origin main` (Build 27 push) ← Step 1
2. `git add … && git commit -m "Build 28 …" && git push origin main` ← Step 2
3. Build 29 Task A — write `test_build29.py`
4. Build 29 Task B — loosen test_build26/27/28 version assertions
5. Build 29 Task C — update VERSION/CHANGELOG/MASTERPLAN/USER_GUIDE/AI_TOOLS_REGISTRY
6. Build 29 Task D — bump `app/version.py` to `1.2.0`
7. Build 29 Task E — full verification sweep
8. Build 29 Task F — commit + push Build 29
9. Update CURRENT_TASK.md to point at v1.3 planning (next session)

Total operations: 2 pushes + 1 commit-and-push + 1 final commit-and-push = 3 pushes, 2 new commits, plus all the file edits in between.
