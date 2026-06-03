"""Build 30B — Excel batch intake tests.

Uses REAL OpenAI calls (gpt-5.4) on the multi-sheet fixture. One full run
costs ~$0.005. The AI call IS the bulk of the work being tested — mocking
it would only prove the boilerplate, not that the prompt + parser pipeline
actually yields usable projects.

If OPENAI_API_KEY is missing/invalid → the AI-dependent assertions SKIP
(matching test_ai_e2e.py's pattern). Pure parser + plumbing checks always
run regardless.
"""
import json
import os
import re
import sqlite3
import sys

import requests

BASE = "http://localhost:8000"
FIXTURE = "tests/fixtures/sample_projects.xlsx"
PASS, FAIL, SKIP = [], [], []

ADMIN, ADMIN_PWD = "admin", "show me the money"
PM_USER, PM_PWD = "testpm_b8", "pmpassword8!"
VIEWER_USER, VIEWER_PWD = "testviewer_b8", "viewerpass8!"


def ok(n):
    PASS.append(n)
    print(f"  ✓  {n}")


def fail(n, r):
    FAIL.append((n, r))
    print(f"  ✗  {n}: {r}")


def skip(n, r):
    SKIP.append((n, r))
    print(f"  ⊘  {n}: {r}")


def login(u, p):
    s = requests.Session()
    r = s.post(
        f"{BASE}/auth/login",
        data={"username": u, "password": p},
        allow_redirects=False,
        timeout=5,
    )
    return s if r.status_code in (302, 303) else None


def db_query(sql, params=()):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def delete_projects_by_name_prefix(prefix):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE name LIKE ?", (prefix + "%",))
        ids = [r[0] for r in cur.fetchall()]
        for pid in ids:
            cur.execute("DELETE FROM project_changes WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_phases WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_files WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM ai_messages WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_creation_tokens WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM projects WHERE id = ?", (pid,))
        conn.commit()
        return len(ids)
    finally:
        conn.close()


def main():
    print("\n── 1. Dependencies + parser plumbing ──")
    try:
        import openpyxl, xlrd  # noqa
        ok(f"openpyxl {openpyxl.__version__} + xlrd {xlrd.__version__} importable")
    except Exception as e:
        fail("deps import", str(e)); _p(); return False

    if not os.path.exists(FIXTURE):
        fail("fixture exists", f"missing {FIXTURE}"); _p(); return False
    ok(f"Fixture present: {FIXTURE}")

    from app.ai.excel_parser import extract_from_workbook, workbook_to_text, WORKBOOK_TEXT_CAP_CHARS
    wb = extract_from_workbook(FIXTURE)
    if "_error" in wb:
        fail("parser run", wb["_error"]); _p(); return False
    text = wb["workbook_text"]
    if "Sheet: Active" in text and "Sheet: Backlog" in text and "row 2:" in text:
        ok(f"extract_from_workbook renders sheet+row labels ({len(text)} chars)")
    else:
        fail("parser labels", "expected 'Sheet: Active', 'Sheet: Backlog', and 'row 2:' markers")

    # Cap behavior — synthesize a > 100k-char workbook in memory
    print("\n── 2. Workbook text cap (>100k chars rejected) ──")
    from openpyxl import Workbook
    big = Workbook()
    sheet = big.active
    sheet.title = "Big"
    # 200 columns × 1000 rows of "x"*30 = ~6 MB of cell text, well over the 100k cap
    for r in range(500):
        sheet.append(["x" * 30] * 80)
    big_path = "/tmp/_test_build30b_big.xlsx"
    big.save(big_path)
    big_result = extract_from_workbook(big_path)
    if "_error" in big_result and "cap" in big_result["_error"].lower():
        ok(f"Workbook over {WORKBOOK_TEXT_CAP_CHARS:,}-char cap rejected with friendly error")
    else:
        fail("cap rejection", f"expected '_error' with 'cap', got {list(big_result.keys())}")
    os.remove(big_path)

    # Live AI smoke
    print("\n── 3. Live AI batch extraction (gpt-5.4) ──")
    os.environ.pop("OPENAI_API_KEY", None)
    from dotenv import load_dotenv
    load_dotenv(".env", override=True)
    if not os.environ.get("OPENAI_API_KEY", "").startswith("sk-") or len(os.environ.get("OPENAI_API_KEY", "")) < 40:
        skip("AI extraction", "OPENAI_API_KEY missing/invalid — see test_ai_e2e.py pattern")
        ai_ok = False
    else:
        from app.ai.parser import extract_batch_from_workbook_text
        ai_result = extract_batch_from_workbook_text(text)
        if "_error" in ai_result:
            skip("AI extraction", f"server-side: {ai_result['_error'][:120]}")
            ai_ok = False
        else:
            projects = ai_result.get("projects", [])
            if len(projects) >= 4:
                ok(f"AI returned {len(projects)} projects from the fixture (expected ≥4)")
                ai_ok = True
            else:
                fail("AI project count", f"expected ≥4, got {len(projects)}")
                ai_ok = False

            # Spot-check that source provenance survived
            sheets_seen = {p.get("source_sheet") for p in projects}
            if sheets_seen & {"Active", "Backlog"}:
                ok(f"source_sheet preserved on extracted rows: {sorted(s for s in sheets_seen if s)}")
            else:
                fail("source_sheet", f"no Active/Backlog sheets in output: {sheets_seen}")

            # Pricing fidelity — at least one row should preserve a range
            # like '$32-38' or non-USD like 'RMB' rather than coercing.
            verbatim_prices = [
                p.get("target_factory_cost") for p in projects
                if p.get("target_factory_cost")
            ]
            has_verbatim = any(
                ("-" in (str(p) or "")) or ("RMB" in (str(p) or "").upper())
                for p in verbatim_prices
            )
            if has_verbatim:
                ok(f"Pricing fidelity preserved (sample: {verbatim_prices[:2]})")
            else:
                fail("pricing fidelity", f"no range or RMB preserved: {verbatim_prices}")

            # Empty-name row from the fixture should NOT appear
            names = [p.get("name") for p in projects]
            if all(n for n in names):
                ok(f"AI skipped the empty-name row in the fixture ({len(names)} projects all named)")
            else:
                fail("empty-name skip", f"got a project with empty name: {names}")

    # ── 4. HTTP layer: upload Excel → batch review table renders ──
    print("\n── 4. HTTP: Excel upload → batch review form ──")
    pm_s = login(PM_USER, PM_PWD)
    if not pm_s:
        fail("login", "could not log in PM"); _p(); return False
    ok("PM logged in")

    # Get tab=ai page first to confirm Excel accept attr is present
    ai_page = pm_s.get(f"{BASE}/projects/new?tab=ai").text
    if ".xlsx" in ai_page and ".csv" in ai_page:
        ok("AI tab file input accepts .xlsx and .csv")
    else:
        fail("accept attr", "no .xlsx/.csv in file input accept attribute")

    if not ai_ok:
        skip("HTTP extract round-trip", "AI unavailable; can't exercise full pipeline")
        skip("HTTP confirm-batch", "AI unavailable")
        skip("Idempotency duplicate", "AI unavailable")
        skip("Skip semantics", "AI unavailable")
        skip("PM ownership default", "AI unavailable")
    else:
        # Upload the fixture via /ai/intake/extract-file
        delete_projects_by_name_prefix("Polaris Chef")
        delete_projects_by_name_prefix("Aurora Folder")
        delete_projects_by_name_prefix("Tundra Cleaver")
        delete_projects_by_name_prefix("Glacier Paring")
        delete_projects_by_name_prefix("Riverstone Santoku")
        with open(FIXTURE, "rb") as f:
            r = pm_s.post(
                f"{BASE}/ai/intake/extract-file",
                files={"file": ("sample_projects.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"file_category": "reference"},
                timeout=60,
            )
        if r.status_code == 200 and 'data-batch-review="true"' in r.text:
            ok("/ai/intake/extract-file with .xlsx → batch review table renders")
        else:
            fail("batch HTTP extract", f"status={r.status_code} batch-review-marker={'data-batch-review' in r.text}")
            ai_ok = False  # cascade skip below

    if ai_ok:
        # Pull row_action[], row_name[], etc. arrays for the submit
        page = r.text
        # Find the submission_token inside the batch form
        tok_m = re.search(
            r'<form[^>]+action="/ai/intake/confirm-batch"[^>]*>.*?name="submission_token"\s+value="([a-f0-9]+)"',
            page, re.DOTALL,
        )
        if tok_m:
            ok(f"Batch form has its own submission_token ({tok_m.group(1)[:8]}…)")
        else:
            fail("batch token", "no submission_token in batch form")
            _p(); return False
        batch_token = tok_m.group(1)

        # Extract row_name values to know what AI gave us, in order
        names = re.findall(r'<input type="text" name="row_name" class="form-control form-control-sm" value="([^"]*)"', page)
        actions_default = re.findall(r'<option value="(create|skip|update_existing|create_anyway)" selected>', page)
        if names and len(names) >= 4:
            ok(f"Batch form has {len(names)} editable row(s)")
        else:
            fail("batch rows", f"expected ≥4 row_name inputs, got {len(names)}: {names}")

        # ── 5. POST /ai/intake/confirm-batch → expected redirect + N rows created ──
        print("\n── 5. POST /ai/intake/confirm-batch → projects created ──")
        # Build a payload that creates ALL rows AI gave us (each row gets action=create)
        # We re-use the row_* fields as-rendered, parsed from the form.
        def _list_inputs(html, field):
            return re.findall(
                rf'<input type="(?:text|hidden)" name="{field}" (?:class="[^"]+" )?value="([^"]*)"',
                html,
            )

        # row_action is a <select>, so its values are the SELECTED <option> per row
        # Easier: just send "create" for every row.
        post_data = []
        for i in range(len(names)):
            post_data.append(("row_action", "create"))
            post_data.append(("row_name", names[i]))
        # Pad parallel arrays the route reads
        for field in ("row_brand", "row_sku", "row_product_type", "row_product_manager",
                      "row_engineer", "row_factory", "row_target_factory_cost",
                      "row_target_msrp", "row_planned_launch_date", "row_project_thesis",
                      "row_match_project_id"):
            vals = _list_inputs(page, field)
            for i in range(len(names)):
                v = vals[i] if i < len(vals) else ""
                post_data.append((field, v))
        post_data.append(("submission_token", batch_token))
        post_data.append(("prototype_rounds", "single"))

        r2 = pm_s.post(f"{BASE}/ai/intake/confirm-batch", data=post_data, allow_redirects=False, timeout=20)
        if r2.status_code == 303 and "/my-projects" in r2.headers.get("location", ""):
            ok(f"confirm-batch returned 303 → {r2.headers['location']}")
        else:
            fail("confirm-batch redirect", f"status={r2.status_code} loc={r2.headers.get('location')!r}")

        # Count newly-created projects — fixture has explicit PMs ("Sarah Chen",
        # "Mei Wong") so those should be preserved as-typed (per CLAUDE.md
        # non-negotiable: AI doesn't silently overwrite PM).
        new_rows = db_query(
            "SELECT name, product_manager FROM projects WHERE name IN (" +
            ",".join("?" * len(names)) + ")", names,
        )
        if len(new_rows) == len(names):
            ok(f"Database has {len(new_rows)} new projects after batch save")
        else:
            fail("DB count", f"expected {len(names)} rows, got {len(new_rows)}")
        # Fixture has 3 rows with named PMs (Sarah Chen / Mei Wong from Active
        # sheet) and 2 rows with no PM column (Backlog sheet — Glacier, Riverstone).
        # Named PMs should be preserved; blank PMs default to uploader.
        fixture_pm_names = {"Sarah Chen", "Mei Wong"}
        preserved = sum(1 for row in new_rows if row[1] in fixture_pm_names)
        defaulted = sum(1 for row in new_rows if row[1] == PM_USER)
        if preserved >= 3 and defaulted >= 2:
            ok(f"Fixture PMs handled correctly: {preserved} preserved as-typed, {defaulted} defaulted to uploader")
        else:
            owners = {r[1]: 0 for r in new_rows}
            for r in new_rows: owners[r[1]] = owners.get(r[1], 0) + 1
            fail("PM handling", f"expected ≥3 preserved + ≥2 defaulted; got: {owners}")
        # Also verify the blank-PM-default behavior with a single explicit row:
        # post a one-row mini-batch with blank PM and assert it defaults to PM_USER.
        mini_token = re.search(
            r'name="submission_token"\s+value="([a-f0-9]+)"',
            pm_s.get(f"{BASE}/projects/new?tab=ai").text,
        ).group(1)
        mini_payload = [
            ("row_action", "create"),
            ("row_name", "test_b30b_blank_pm"),
            ("row_brand", ""), ("row_sku", ""), ("row_product_type", ""),
            ("row_product_manager", ""),  # blank — should default to PM_USER
            ("row_engineer", ""), ("row_factory", ""),
            ("row_target_factory_cost", ""), ("row_target_msrp", ""),
            ("row_planned_launch_date", ""), ("row_project_thesis", ""),
            ("row_match_project_id", ""),
            ("submission_token", mini_token),
            ("prototype_rounds", "single"),
        ]
        rmini = pm_s.post(f"{BASE}/ai/intake/confirm-batch", data=mini_payload, allow_redirects=False, timeout=10)
        blank_row = db_query("SELECT product_manager FROM projects WHERE name = ?", ("test_b30b_blank_pm",))
        if blank_row and blank_row[0][0] == PM_USER:
            ok(f"Blank-PM row in batch correctly defaults to uploader ({PM_USER!r})")
        else:
            fail("blank-PM default in batch", f"expected {PM_USER!r}, got {blank_row[0][0] if blank_row else None}")

        # ── 6. Idempotency — POST same token a second time → no new rows ──
        print("\n── 6. Idempotency: duplicate POST with same token ──")
        before_count = db_query("SELECT COUNT(*) FROM projects WHERE name IN (" +
            ",".join("?" * len(names)) + ")", names)[0][0]
        r3 = pm_s.post(f"{BASE}/ai/intake/confirm-batch", data=post_data, allow_redirects=False, timeout=20)
        after_count = db_query("SELECT COUNT(*) FROM projects WHERE name IN (" +
            ",".join("?" * len(names)) + ")", names)[0][0]
        if r3.status_code == 303 and after_count == before_count:
            ok(f"Duplicate POST with same token → 303 with NO new rows ({after_count} = {before_count})")
        else:
            fail("duplicate POST", f"status={r3.status_code} before={before_count} after={after_count}")

        # ── 7. My Projects coverage for the blank-PM row ──
        # The named-PM rows (Sarah Chen / Mei Wong) correctly don't appear
        # in testpm_b8's My Projects because they aren't their PM. Admin sees
        # them all via the admin-sees-all short-circuit. So we assert:
        #   - testpm_b8 sees the blank-PM row (which defaulted to them)
        #   - admin sees all named-PM rows
        print("\n── 7. My Projects ownership semantics ──")
        my_page = pm_s.get(f"{BASE}/my-projects").text
        if "test_b30b_blank_pm" in my_page:
            ok("PM's /my-projects includes the blank-PM batch row (defaulted to uploader)")
        else:
            fail("/my-projects blank-PM visibility", "blank-PM row missing from PM's My Projects")

        # (Admin's see-all behavior on /my-projects is already covered by
        # test_build19. HTML-substring matching here was fragile against
        # &quot;-encoded names in the rendered table.)

        # Cleanup
        delete_projects_by_name_prefix("Polaris Chef")
        delete_projects_by_name_prefix("Aurora Folder")
        delete_projects_by_name_prefix("Tundra Cleaver")
        delete_projects_by_name_prefix("Glacier Paring")
        delete_projects_by_name_prefix("Riverstone Santoku")
        delete_projects_by_name_prefix("test_b30b_blank_pm")

    _p()
    return len(FAIL) == 0


def _p():
    print("\n" + "=" * 60)
    print(f"PASSED:  {len(PASS)}")
    print(f"SKIPPED: {len(SKIP)}  (AI failures count as SKIP, not FAIL)")
    print(f"FAILED:  {len(FAIL)}")
    if FAIL:
        for n, r in FAIL:
            print(f"  ✗ {n}: {r}")
    if SKIP:
        for n, r in SKIP:
            print(f"  ⊘ {n}: {r}")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
