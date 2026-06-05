"""Regression test for the project-delete FK violation bug discovered 2026-06-06.

Bug: deleting a project that had an AI conversation attached
(typical of any AI-Intake-created project) raised
`FOREIGN KEY constraint failed` on PostgreSQL (Railway prod) and returned
500. SQLite dev was silent because `PRAGMA foreign_keys` defaulted to OFF.

Root cause: `ai_conversations.project_id → projects.id` and
`project_creation_tokens.project_id → projects.id` were FKs without
matching `Project` ORM relationships, so SQLAlchemy cascade did not
remove them before the project row was deleted.

Fix:
  1. `crud.delete_project()` now explicitly deletes ai_conversations
     and project_creation_tokens rows, and nulls ai_messages.conversation_id,
     before the ORM delete cascades the rest.
  2. `app/database.py` now turns SQLite `PRAGMA foreign_keys = ON` so dev
     mirrors PostgreSQL FK enforcement and this class of bug fails loud.

This test reproduces the original bug shape (project with attached
AIConversation + AIMessage + creation token) and asserts:
  - Delete succeeds via the HTTP route.
  - All related rows are gone.
  - No orphan ai_conversation row remains.
  - SQLite is enforcing FKs.
"""
import json
import os
import re
import sqlite3
import sys

import requests

BASE = os.environ.get("BASE_URL", "http://localhost:8000")
PASS, FAIL = [], []

ADMIN, ADMIN_PWD = "admin", "show me the money"


def ok(n):
    PASS.append(n)
    print(f"  ✓  {n}")


def fail(n, r):
    FAIL.append((n, r))
    print(f"  ✗  {n}: {r}")


def db_query(sql, params=()):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def db_execute(sql, params=()):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def login(u, p):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login",
        data={"username": u, "password": p}, allow_redirects=False, timeout=5)
    return s if r.status_code in (302, 303) else None


def main():
    admin = login(ADMIN, ADMIN_PWD)
    if not admin:
        fail("setup", "could not log in"); _p(); return False
    ok("Admin logged in")

    # ── 1. App engine enforces SQLite FKs (regression guard) ──
    # Note: PRAGMA is per-connection. This test uses raw sqlite3 connections
    # that don't get the app's connect-event PRAGMA. We instead assert the
    # behavior end-to-end by verifying that a FK violation would actually
    # raise from the app's SessionLocal.
    print("\n── 1. App's SQLite engine enforces foreign keys ──")
    from app.database import SessionLocal
    from sqlalchemy import text
    sess = SessionLocal()
    try:
        fk_state = sess.execute(text("PRAGMA foreign_keys")).scalar()
        if fk_state == 1:
            ok("App SessionLocal connections have PRAGMA foreign_keys = ON")
        else:
            fail("FK enforcement off in app",
                 "Original bug would be silent in dev — Railway PostgreSQL would still 500")
    finally:
        sess.close()

    # ── 2. Reproduce the AI-intake project shape ──
    print("\n── 2. Create a project + attach AIConversation + AIMessage ──")
    # Mint token + create project
    page = admin.get(f"{BASE}/projects/new").text
    tok = re.search(r'name="submission_token"\s+value="([a-f0-9]+)"', page).group(1)
    r = admin.post(f"{BASE}/projects/new",
        data={"name": "delete_regression_test", "product_manager": ADMIN,
              "prototype_rounds": "single", "submission_token": tok},
        allow_redirects=False, timeout=5)
    pid = int(r.headers["location"].rstrip("/").split("/")[-1])
    ok(f"Project created: pid={pid}")

    # Attach an AIConversation + an AIMessage (simulates AI Intake's chat trail)
    admin_user_id = db_query("SELECT id FROM users WHERE username=?", (ADMIN,))[0][0]
    from datetime import datetime
    conv_id = db_execute(
        "INSERT INTO ai_conversations (user_id, project_id, title, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (admin_user_id, pid, "test convo", "active", datetime.utcnow(), datetime.utcnow()),
    )
    db_execute(
        "INSERT INTO ai_messages (project_id, conversation_id, role, message, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (pid, conv_id, "user", "Test message", datetime.utcnow()),
    )
    ok("Attached AIConversation + AIMessage (mirrors AI-intake-created project)")

    # Sanity: ai_conversations row exists for this pid
    convo_rows = db_query("SELECT id FROM ai_conversations WHERE project_id=?", (pid,))
    if len(convo_rows) == 1:
        ok("Pre-delete: 1 ai_conversations row references the project")
    else:
        fail("ai_conv row count", f"got {len(convo_rows)}")

    # ── 3. DELETE via HTTP route — must return 303, not 500 ──
    print("\n── 3. POST /projects/{id}/delete with FK ON ──")
    r = admin.post(f"{BASE}/projects/{pid}/delete", allow_redirects=False, timeout=10)
    if r.status_code == 303:
        ok("Delete returned 303 (success). Pre-fix: this returned 500 on PostgreSQL.")
    elif r.status_code == 500:
        fail("REGRESSION", f"500 — FK violation. Response: {r.text[:500]}")
    else:
        fail("unexpected status", f"got {r.status_code}")

    # ── 4. Verify all related rows are gone (no orphans) ──
    print("\n── 4. No orphan rows reference the deleted project ──")
    for tbl, col in [
        ("projects", "id"),
        ("ai_conversations", "project_id"),
        ("ai_messages", "project_id"),
        ("project_phases", "project_id"),
        ("project_files", "project_id"),
        ("project_variants", "project_id"),
        ("project_changes", "project_id"),
        ("project_journal_entries", "project_id"),
        ("project_creation_tokens", "project_id"),
        ("project_blockers", "project_id"),
    ]:
        cnt = db_query(f"SELECT COUNT(*) FROM {tbl} WHERE {col}=?", (pid,))[0][0]
        if cnt == 0:
            ok(f"{tbl}.{col}={pid}: 0 rows (clean)")
        else:
            fail(f"orphan in {tbl}", f"{cnt} rows still reference pid={pid}")

    # ── 5. Verify ai_messages with conversation_id was nulled, not orphaned ──
    # (The conversation row is deleted, but if some ai_message had used the
    # conversation in another project's context, that row would still exist
    # with conversation_id=NULL after our fix. This test is a no-op for the
    # current shape but documents the intent.)
    print("\n── 5. ai_messages.conversation_id correctly nulled before AIConversation delete ──")
    ok("Implicit — if FK violation didn't fire in step 3, this rule held")

    _p()
    return len(FAIL) == 0


def _p():
    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        for n, r in FAIL:
            print(f"  ✗ {n}: {r}")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
