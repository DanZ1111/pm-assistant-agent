# CURRENT_TASK.md

## Task
Build 30B — Excel batch intake. Implementation complete + verified with real AI. **Awaiting user authorization to commit + push.**

Next up: Build 30C (PM draft delete) — still gated on user's policy decision (48h vs "until first phase advance" vs other).

## Handoff rule
Before editing, inspect:
- git status
- git diff
- git log --oneline -5

Git/code is the source of truth. This file is only a short task reminder.

## What changed in Build 30B

### Backend
- New `app/ai/excel_parser.py` — workbook (xlsx/xlsm/xls/csv) → sheet-aware plain text. 100k-char cap. Per-cell 500-char guard. CSV dialect sniffing + encoding fallback.
- New `app/ai/parser.py:extract_batch_from_workbook_text()` — calls `gpt-5.4` with the new `EXCEL_BATCH_INTAKE_PROMPT` and JSON-object response format. Per-row pricing preserved verbatim (the windowed `sanitize_price_fields` was correctly skipped in batch mode because it would match neighboring date columns as prices).
- New `crud.create_projects_batch_with_idempotency()` + `BatchIdempotencyResult` — claims one Build 30A token atomically + builds N projects in one transaction. Per-row validation failures (missing name) are skipped with a reason.
- Extended `app/routes/intake.py`:
  - `SUPPORTED_INTAKE_TYPES` += `"excel"`, `"csv"`.
  - `intake_extract_file` dispatches to the workbook path for excel/csv file_type, calls AI batch extractor, runs `_find_match` per row, builds `proposed_batch` payload for the template.
  - New `POST /ai/intake/confirm-batch` handler — parses parallel form arrays (`row_action[]`, `row_name[]`, ...), applies PM defaulting + display_name normalization (Build 30A pattern), routes per-row to create / update_existing / skip, redirects to `/my-projects?imported=N&updated=M&skipped=K`.
- `app/routes/files.py` — file type detection unchanged (`.xlsx` already mapped to `"excel"`); `.xlsm` and `.csv` work via existing patterns.
- New deps in `requirements.txt`: `openpyxl`, `xlrd<2.0`.

### Frontend
- `app/templates/components/ai_intake_panel.html` — added a batch review table block (renders when `proposed_batch` is set), with editable per-row inputs, action select (Create / Skip / Update Existing / Create Anyway), hidden inputs for non-displayed fields, source-sheet/row provenance column. Restructured the outer `{% if proposed is none %}` so the initial-state forms hide when EITHER `proposed` or `proposed_batch` is set, and the single-project preview section wraps in `{% if proposed %}` so the batch flow (which leaves `proposed=None`) doesn't crash on the preview-only code path.
- File input `accept` attr extended to include `.xlsx,.xlsm,.xls,.csv`.

### Tests + fixtures
- New `tests/fixtures/sample_projects.xlsx` — 3 sheets (Active, Backlog, Notes), 5 valid projects + 1 deliberate empty-name row + 1 noise sheet AI should ignore. Includes pricing edge cases (`$32-38`, `under 28 RMB ex-factory`, `$179-199`).
- New `test_build30b.py` — 19/19 PASS. Real AI call to `gpt-5.4` (~$0.005/run). Covers parser plumbing, 100k-char cap, AI extraction with provenance + pricing fidelity preservation, HTTP upload → batch review form, batch-confirm POST → N projects in DB, idempotency (duplicate POST yields no new rows), PM-preservation semantics (named PMs from spreadsheet kept; blank PM defaults to uploader), and My Projects coverage.

### Docs
- `CHANGELOG.md` — Build 30B entry added to `## Unreleased`.
- `MASTERPLAN.md` — Build 30B detail section above Build 30A.
- `BUILD30B_PLAN.md` — implementation plan written before code, includes the locked-decision table and 11-question Feature Design Review.

No version bump. Joins the existing `## Unreleased` patch list (IME v2 + nixpacks + price strings + layout refactor + Build 30A + Build 30B). v1.2.1 release-hardening will roll them up.

## Verification at this point

- `python3 test_build30b.py` — **19/19** with real AI extraction.
- `python3 test_build30.py` — 23/23 (unchanged).
- `python3 test_build29.py` — 26/26 (unchanged).
- `python3 test_ai_e2e.py` — 15P/2S/0F (unchanged; 2 skips are the 1×1 PNG + empty PDF fixture limits).
- Manual browser smoke:
  - GET `/projects/new?tab=ai` → upload `sample_projects.xlsx` → batch review table renders with 5 editable rows.
  - Click Save Batch → redirected to `/my-projects?imported=5&updated=0&skipped=0`.
  - Browser back + re-submit → no duplicate (idempotency token claimed).

## What's NOT in this build

- **Build 30C** — PM draft delete capability (gated on user policy decision: 48h vs "until first phase advance" vs other).
- v1.2.1 release-proof regression — happens when unreleased patches accumulate enough.
- One-time cleanup of the original 6 admin-linked duplicates from the user's incident — admin manual task, still in the todo list separately from code.

## Next step

Awaiting user authorization to commit + push Build 30B. After that, the natural next moves:

1. **Admin one-time cleanup** of the 6 existing duplicates (manual SQL or admin UI).
2. **Build 30C** — policy decision needed: PM delete window. 48h vs "until first phase advance" vs other.
3. **v1.2.1 release-hardening** — once the queue of unreleased patches feels full.
