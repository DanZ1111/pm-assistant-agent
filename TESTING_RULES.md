# TESTING_RULES.md — PM Product Tracker

## Core Rule

**A build is not done until the relevant tests pass.**

Do not report completion with "tested" alone. Always report:
- exact commands run
- headless or headed
- what passed / failed
- what was fixed
- what still needs manual review

---

## Stack

- **Tool:** Playwright (Python sync API)
- **Mode:** headless for routine tests; headed when visual confirmation is useful
- **Setup:** `pip install playwright && python3 -m playwright install chromium`
- **Playwright is a test dependency only** — do not add it to the main app

---

## Before Every Test Run

1. Start the app: `python run.py`
2. Confirm it's up: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/projects` → should return `200`
3. Use fake data only — never real company data in tests
4. Reset DB if needed: `rm pm_tracker.db` then restart

---

## Required Test Script Per Build

Each build has a corresponding test script in the project root:

| Build | Test Script |
|---|---|
| 1 | `test_build1.py` |
| 2 | `test_build2.py` |
| 3 | `test_build3.py` |
| ... | `test_buildN.py` |

Run with: `python3 test_buildN.py`

---

## Build 1 Required Tests

Script: `test_build1.py` (already created, 36 tests, all passing)

**Must verify:**

| Flow | Pass condition |
|---|---|
| Root → /projects redirect | URL is /projects |
| Nav links | Projects + Admin visible |
| Create name-only project | Succeeds, Needs Info badge appears, thesis empty state shown |
| Create fully complete project | No Needs Info banner, Product Thesis box shown, 10 phases for double-prototype |
| Edit project | Updated value in sidebar, change log records the edit |
| Archive project | Disappears from Active, appears in Archived |
| Card view default | Card visible, table hidden |
| Table view toggle | Click → card hides, table shows |
| Filters (all/active/completed/archived) | All return 200 |
| Brand filter dropdown | Visible |
| Search | Returns matching project |
| Database Inspector | Loads, stat cards visible, field usage table visible |
| 404 on unknown project | Returns 404 |
| Empty name submit | Stays on form (validation) |
| Cancel button | Visible on create form |

---

## Build 1.5 Required Tests (Database Inspector)

Add to `test_build1.py` or create `test_build1_5.py`.

| Flow | Pass condition |
|---|---|
| `/admin/database` loads | 200, no 500 |
| Table overview | All 5 tables shown with row counts |
| Field usage report | Non-empty %, bar visible for each nullable field |
| Missing critical fields | Lists projects by missing field name |
| Recent changes feed | Renders gracefully even if empty |

---

## Build 2 Required Tests

Create `test_build2.py`.

| Flow | Pass condition |
|---|---|
| Single prototype project | 8 phases created |
| Double prototype project | 10 phases created |
| Phase edit modal | Opens, saves, page updates |
| Set planned_end_date to past, status=in_progress | Red delay badge on list and detail |
| Delay days calculation | Correct number shown |
| current_stage update | Updates to next unfinished phase after marking one done |
| Needs Attention section | Shows delayed + phases due this week |

---

## Build 3 Required Tests

Create `test_build3.py`.

| Flow | Pass condition |
|---|---|
| Upload PNG rendering | Appears in gallery |
| Click thumbnail | Full-res lightbox opens |
| Escape key | Lightbox closes |
| Upload PDF | Appears as downloadable file |
| Set file_category | Saved, filter works |
| Delete file | Disappears, no broken links |

---

## Build 4 Required Tests

Create `test_build4.py`.

| Flow | Pass condition |
|---|---|
| Edit MSRP | Change log shows old → new value |
| Edit phase | Change log shows phase_update entry |
| Upload file | Change log shows file_upload entry |
| Archive project | Change log shows archive event |

---

## Build 5 Required Tests

Create `test_build5.py`.

| Flow | Pass condition |
|---|---|
| AI text intake | Extracts fields from messy input |
| Preview before save | Proposed fields shown, missing critical fields highlighted |
| Confirm creates project | Project exists in DB with ai_messages record |
| AI does not silently overwrite | Important fields shown as proposals, not auto-saved |

---

## Build 6 Required Tests

Create `test_build6.py`.

| Flow | Pass condition |
|---|---|
| Upload PDF | Text extracted, fields proposed |
| Upload image | Vision summary generated |
| File attached to created project | `project_files` row exists with `ai_summary` |

---

## Build 7 Required Tests

Create `test_build7.py`.

| Flow | Pass condition |
|---|---|
| Fuzzy match on existing project name | AI suggests match |
| User confirms update existing | Project updated, no duplicate created |
| Change log records AI update | `changed_by=ai` entry present |

---

## Bug Fix Rule

If a test fails:
1. Identify root cause — do not guess
2. Fix the issue
3. Rerun the failed test
4. Report the failure, cause, and fix

Do not hide failures. Do not claim completion if core flows are broken.

---

## Required Report Format

```
Testing Report — Build N

Commands run:
  python run.py (background)
  python3 test_buildN.py

Mode: headless

Passed: N / N

Failed: (list with root cause)

Fixes made:
  - Bug: [description]
    Cause: [root cause]
    Fix: [what was changed]

Remaining manual review:
  - (anything that can't be automated)
```
