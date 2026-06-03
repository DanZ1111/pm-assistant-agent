# Build 30B — Excel Batch Intake

> **Status:** Implementation plan, executing now.
> **Author:** Claude (2026-06-03)
> **Predecessor:** Build 30A (project creation safety) — shipped at `cab8884` on `origin/main`.
> **Sibling:** Build 30C (PM draft delete) — deferred, gated on user policy decision.

---

## Context

PMs have existing project portfolios in Excel — pre-PM-tracker. Onboarding a new department (e.g. Beauty) requires importing those portfolios without manual one-by-one retyping. A single workbook often has multiple projects across one or more sheets.

This build adds Excel batch intake: upload an `.xlsx` / `.xlsm` / `.xls` / `.csv`, AI extracts a `projects` array, user reviews in a per-row table (edit any field, choose Create / Skip / Update Existing per row), then **one** Save click commits all confirmed rows in a single idempotent batch — atomic with Build 30A's `submission_token` so a double-click doesn't double-import.

## Feature Design Review (11 questions)

1. **What real workflow problem are we solving?** PMs need to migrate existing project Excel sheets into the tracker without manual retyping.
2. **Is it repeated or edge-case?** Repeated — every new department onboards from Excel; ongoing bulk imports continue.
3. **Does it need structured data?** Yes; each row becomes a normal `Project` record with phases, ownership, and change-log entries.
4. **Could it live first in Journal / notes / metadata?** No; projects must become trackable records with phases and My Projects ownership.
5. **Does it increase intake burden?** No; AI batch extraction + review table is dramatically less work than retyping 50 projects.
6. **Can AI reduce intake burden?** Yes — AI classifies rows as projects, maps columns regardless of header naming, normalizes data.
7. **What display/reminder does it enable?** Imported projects appear in Projects, My Projects, Calendar, with health checks and PM ownership.
8. **Does it affect migration?** No; existing `project_creation_tokens` (Build 30A migration 004) is reused for batch idempotency. No new tables.
9. **What is the minimal schema change?** None.
10. **What is the minimal UI change?** Extend the existing `/projects/new?tab=ai` AI panel — same upload area accepts Excel/CSV; post-extraction renders a new batch review table instead of the single-row preview when the response shape is `{"projects": [...]}`.
11. **What should be deferred?** Idea-bulk-import; full column-mapping UI; background async import jobs; OCR for image-of-spreadsheet uploads.

## Architecture Review

1. **Problem:** import N existing-project rows from Excel without losing data, without creating duplicates, and with proper PM ownership.
2. **Affected services:** new `app/ai/excel_parser.py` (workbook → sheet-aware text), new `EXCEL_BATCH_INTAKE_PROMPT` in `prompts.py`, extended `app/routes/intake.py` for Excel acceptance + new `POST /ai/intake/confirm-batch`, extended `ai_intake_panel.html` for the review table. Reuses Build 30A `crud.create_project_with_idempotency` per row.
3. **Storage choice:** rows are normal `Project` records via the existing service layer. No bytes stored for the workbook beyond the standard upload directory.
4. **Service-layer discipline:** route only parses HTTP + dispatches; per-row create logic stays in `crud.create_project_with_idempotency`. Batch loop is a thin orchestrator.
5. **Change log:** every confirmed-and-created row writes a `project_changes` row via the existing service. `source_type="manual_edit"` (initial-create marker); workbook source-sheet/row is preserved in the change-log summary for traceability.
6. **Rollback:** removing the Excel-extension code + the `confirm-batch` route reverts cleanly. No schema rollback needed.

## Locked decisions

| # | Question | Decision |
|---|---|---|
| 1 | File types | `.xlsx`, `.xlsm` (openpyxl); `.xls` (xlrd<2.0); `.csv` (built-in). DOC and DOCX of spreadsheets out of scope. |
| 2 | Match key for "row already exists" | Case-insensitive `name` match within the same `brand`. Blank brand = wildcard so legacy untagged rows match too. Match → row defaults to **Skip**, user can flip to **Update Existing** or **Create Anyway**. |
| 3 | Per-row failure semantics | Commit valid rows. Skip invalid rows. Summary at end: "Created 12, updated 3, skipped 1 (row 7: missing name)." No all-or-nothing rollback — punishes the user for one bad row. |
| 4 | Sheet handling | Process all sheets. Each non-empty row is a project candidate. Preserve `source_sheet` + `source_row` in the AI extraction output so the review table can show provenance. |
| 5 | Batch idempotency | One `submission_token` covers the whole batch (Build 30A pattern reused). Double-clicking "Save Batch" creates the batch once. |
| 6 | Token cap | Reject workbook-to-text > 100k chars at parse time with a friendly "split into smaller files." Real PM Excels are usually well under. |
| 7 | Model | `gpt-5.4` (same as production). Test cost ~$0.005/run. No test/prod divergence. |
| 8 | Blank PM in extracted row | Default to **uploader's username** (consistent with Build 30A). If row's PM matches a User display_name unambiguously → normalize to canonical username. |
| 9 | UI placement | Reuse the existing AI tab panel inside `/projects/new`. After extraction, render the batch review table when AI returns `{"projects": [...]}`; otherwise the existing single-project preview. |

## Scope (strict)

In:
- New `app/ai/excel_parser.py` — workbook (xlsx/xlsm/xls) and csv → sheet/row-aware plain text capped at 100k chars.
- New `EXCEL_BATCH_INTAKE_PROMPT` in `app/ai/prompts.py` returning `{"projects": [...]}` with per-row `source_sheet` + `source_row_hint`.
- Extend `app/routes/intake.py`:
  - `SUPPORTED_INTAKE_TYPES` adds `"excel"` and `"csv"`.
  - `POST /ai/intake/extract-file` dispatches to a new `extract_from_workbook()` when file_type is excel/csv.
  - New `POST /ai/intake/confirm-batch` consumes a single `submission_token` and creates N projects in a loop.
- Extend `app/templates/components/ai_intake_panel.html` with a batch review table (renders when `proposed_batch` is non-empty).
- Update `app/routes/files.py:FILE_TYPE_MAP` for `.xlsm` and `.csv`.
- Add `openpyxl`, `xlrd<2.0` to `requirements.txt`.
- New `tests/fixtures/sample_projects.xlsx` — multi-sheet workbook with ~5 real projects.
- New `test_build30b.py` — real AI extraction (uses `gpt-5.4`, costs ~$0.005/run), batch confirm semantics, idempotency.

Out (explicit):
- Idea bulk-import (project-only).
- Per-cell column-mapping UI (rely on AI's ability to map header variants).
- Background async import jobs (synchronous for this build).
- OCR for image-of-spreadsheet uploads.
- DOC/DOCX of tabular data.
- New deletion capability (Build 30C territory).

## Concrete change set

### New files

- `app/ai/excel_parser.py` — `extract_from_workbook(file_path) -> dict` with shape `{"extracted": {"projects": [...]}, "raw_text": "..."}` or `{"_error": "..."}`. Internally dispatches by extension (.xlsx/.xlsm → openpyxl, .xls → xlrd<2.0, .csv → built-in csv). Helper `_workbook_to_text(file_path)` produces sheet/row labelled text capped at 100k chars.
- `tests/fixtures/sample_projects.xlsx` — ~5 projects across 2 sheets ("Active" and "Backlog"), with columns: Project Name, Brand, SKU, PM, Engineer, Factory, Target Cost, MSRP, Launch Date. One row intentionally missing a name (tests skip-and-report semantics). One row name-matches an existing seed project (tests Skip default).
- `test_build30b.py` — ~12 assertions.

### Modified files

- `requirements.txt` — `openpyxl`, `xlrd<2.0`.
- `app/routes/files.py` — `FILE_TYPE_MAP` adds `"xlsm": "excel"`, `"csv": "csv"`.
- `app/ai/prompts.py` — `EXCEL_BATCH_INTAKE_PROMPT` constant.
- `app/ai/parser.py` — add `extract_batch_from_workbook_text(text)` → calls `chat.completions.create` with the batch prompt and JSON object response format.
- `app/routes/intake.py`:
  - `SUPPORTED_INTAKE_TYPES` += `"excel"`, `"csv"`.
  - `intake_extract_file`: when file_type is excel/csv → call `extract_from_workbook` instead of pdf/image extractor, then call `extract_batch_from_workbook_text` for the AI step.
  - `_ai_panel_response` — accept and pass through `proposed_batch` (list of dicts) + per-row `match` (None or matched Project).
  - New `intake_confirm_batch` handler — takes `submission_token` + a JSON body of `[{action, fields}, ...]` (or form-encoded equivalent), loops calling `create_project_with_idempotency` only on the first row to claim the token, then `_build_project_in_session` for the rest inside the same transaction (single commit). Actually simpler: extend `create_project_with_idempotency` with a `batch` mode that takes N data dicts.
  - Returns 303 redirect to a `/my-projects?imported=12` summary page so the PM sees their new rows immediately.
- `app/templates/components/ai_intake_panel.html` — new batch table block (conditional on `proposed_batch`).
- `app/crud.py` — small extension: `create_projects_batch_with_idempotency(db, rows, token, user)` that claims the token once + builds N projects in one transaction. Single commit. Returns the list of created project IDs.

### Docs

- `CHANGELOG.md` — extend `## Unreleased` with the Build 30B entry.
- `MASTERPLAN.md` — `### Build 30B — Excel batch intake ✓ SHIPPED (unreleased on v1.2.0)`.
- `CURRENT_TASK.md` — point at Build 30B shipped, next-up is Build 30C.

No version bump. Joins the existing `## Unreleased` patch list.

## test_build30b.py shape (~12 assertions)

Modeled on `test_build22.py` (live server + sqlite3 + real AI calls). Skip-on-AI-failure for resilience.

1. `openpyxl` and `xlrd<2.0` importable.
2. `extract_from_workbook` returns text containing "Sheet: Active" / row markers when given `tests/fixtures/sample_projects.xlsx`.
3. Text cap: a > 100k-char workbook returns `{"_error": "too large"}`.
4. Real AI call: `extract_batch_from_workbook_text` on the fixture text returns a `projects` array with at least 4 entries (the fixture has 5, AI may merge or omit the malformed row).
5. `GET /projects/new?tab=ai` renders the file upload form (includes `.xlsx` in accept attr).
6. `POST /ai/intake/extract-file` with the fixture xlsx → 200, response HTML contains a `proposed_batch` table indicator (`data-batch-review="true"` attribute on the table).
7. POST to `/ai/intake/confirm-batch` with the extracted rows + valid `submission_token` → 303 to `/my-projects?imported=N`. Exactly N project rows created.
8. Same `submission_token` posted twice → second POST creates 0 new rows, redirects to the same summary page.
9. One fixture row missing a `name` → skipped (summary reports "skipped 1: row X missing name"), DB never inserts.
10. One fixture row name-matches an existing seed project (same brand) → default action is Skip. If user flips to "Create Anyway", second copy is created.
11. PM-uploader, blank PM in extracted row → `product_manager` = uploader's username on created row.
12. `/my-projects` shows all newly imported rows owned by the uploader.
13. Static check: `test_ai_e2e.py` still green (15P/2S/0F baseline preserved).

## Verification

Automated:
- `pip install -r requirements.txt` succeeds with new deps.
- `python3 test_build30b.py` — target 13/13. Cost ~$0.005 per run.
- Regression: `test_build30`, `test_build29`, `test_build28`, `test_build27`, `test_build22`, `test_build19`, `test_ai_e2e`. All must stay green.
- `node --test tests/composer_ime.test.mjs` — 10/10 (unrelated, just confirming no JS regressions).

Manual:
1. Log in as PM. Upload a small real `.xlsx` (you can construct one in 2 min) via `/projects/new?tab=ai`.
2. Batch review table renders with one row per extracted project.
3. Edit one row's fields inline (e.g., correct a PM name).
4. Toggle one row to Skip.
5. Click "Save Batch" → redirected to `/my-projects?imported=4` (if 4 rows were Create + 1 Skipped).
6. Verify those 4 projects appear in My Projects with you as PM.
7. Browser back-button + re-submit → no duplicate (token claimed).

## What I am NOT doing in this build

- PM draft delete (Build 30C — gated on policy decision).
- Renaming `product_manager` String → User FK.
- Migration of legacy 6 admin-linked duplicates (admin manual task, documented in CURRENT_TASK).
- Per-cell column-mapping UI.
- Async background import jobs.
- v1.2.1 release-proof regression — happens when patches accumulate enough.

## Cost guardrail

Production model `gpt-5.4` used in tests for parity. Test cost ~$0.005 per `test_build30b.py` run. If you want a hard budget cap later, set a project-scoped OpenAI key with a $1 monthly limit.

## Out of scope, version note

No version bump. Joins the existing `## Unreleased` patch list on v1.2.0 with IME v2, nixpacks, price strings, layout refactor, Build 30A. v1.2.1 release-hardening will roll them all up when the queue is full enough.
