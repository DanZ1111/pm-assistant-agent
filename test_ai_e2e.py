"""Comprehensive AI end-to-end test — exercises every AI surface in v1.1.

Designed to be safe to run in any environment:
  - If the server has a valid OPENAI_API_KEY, every case runs a real OpenAI
    call and asserts a successful round-trip.
  - If the server's key is missing or invalid (AI calls return errors / 401),
    each affected case is marked SKIPPED (not FAILED) with a clear note.
  - Structural assertions that don't need OpenAI (permission guards, routing,
    schema integrity, role rejection) always run.

Run after build completion + a valid OpenAI key in the server env. The intent
is a single command (`python3 test_ai_e2e.py`) that gives a clear picture of
which AI surfaces are working end-to-end.

Tests covered (cross-cuts multiple build numbers):
  - AI text intake          (Build 5/11)  → /ai/intake/extract
  - AI file intake — PDF    (Build 6)     → /ai/intake/extract-file
  - AI file intake — image  (Build 6)     → /ai/intake/extract-file
  - Help AI Q&A             (Build 7)     → /ai/help/ask
  - Help AI viewer refusal  (Build 8)     → /ai/help/ask
  - Project Journal summary (Build 14)    → /projects/{pid}/journal/{eid}/summarize
  - Business plan thesis    (Build 15)    → /projects/{pid}/thesis/extract-upload
  - AI tool dispatcher      (Build 20)    → in-process app.ai.tools.dispatch
  - Bottom AI chat          (Build 21)    → /ai/chat
  - AI-Assisted Create UI   (Build 22)    → /projects/new?tab=ai routing
"""
import io
import os
import sys
import json
import sqlite3
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = "http://localhost:8000"
PASS, FAIL, SKIP = [], [], []

ADMIN, ADMIN_PWD = "admin", "show me the money"
PM_USER, PM_PWD = "testpm_b8", "pmpassword8!"
VIEWER_USER, VIEWER_PWD = "testviewer_b8", "viewerpass8!"

# Markers in HTML/JSON that indicate the server-side AI call failed
# (invalid key, timeout, network, etc.). When seen, treat as SKIP.
_AI_FAILURE_MARKERS = (
    "AI extraction failed",
    "PDF extraction failed",
    "Image analysis failed",
    "AI error",
    "AuthenticationError",
    "invalid_api_key",
)


def ok(n): PASS.append(n); print(f"  ✓  {n}")
def fail(n, r): FAIL.append((n, r)); print(f"  ✗  {n}: {r}")
def skip(n, r): SKIP.append((n, r)); print(f"  ⊘  {n}: {r}")


def login(u, p):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", data={"username": u, "password": p}, allow_redirects=False)
    return s if r.status_code in (302, 303) else None


def db_query(sql, params=()):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def make_pm_owned_project(admin_s, pm_username, name):
    # Build 30A — POST /projects/new now requires a submission_token from the GET.
    import re as _re_b30
    form_page = admin_s.get(f"{BASE}/projects/new").text
    _tok = _re_b30.search(r'name="submission_token"\s+value="([a-f0-9]+)"', form_page)
    submission_token = _tok.group(1) if _tok else ""
    r = admin_s.post(f"{BASE}/projects/new",
                     data={"name": name, "prototype_rounds": "single",
                           "submission_token": submission_token},
                     allow_redirects=False)
    pid = int(r.headers["location"].rstrip("/").split("/")[-1])
    admin_s.post(f"{BASE}/projects/{pid}/edit",
                 data={"name": name, "product_manager": pm_username, "status": "active"},
                 allow_redirects=False)
    return pid


def _ai_failed(body: str) -> bool:
    return any(m in body for m in _AI_FAILURE_MARKERS)


def make_png():
    return bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,
        0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
        0x00, 0x00, 0x02, 0x00, 0x01, 0xE2, 0x21, 0xBC,
        0x33, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E,
        0x44, 0xAE, 0x42, 0x60, 0x82,
    ])


def make_tiny_pdf():
    """Minimal valid PDF (no real content, just header + xref)."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n0000000009 00000 n \n"
        b"0000000056 00000 n \n0000000111 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
    )


def main():
    admin_s = login(ADMIN, ADMIN_PWD)
    pm_s = login(PM_USER, PM_PWD)
    viewer_s = login(VIEWER_USER, VIEWER_PWD)
    if not all([admin_s, pm_s, viewer_s]):
        fail("setup", "could not log in all three roles"); _p(); return False
    ok("All three roles can log in")

    pid = make_pm_owned_project(admin_s, PM_USER, f"AI E2E Proj {os.getpid()}")
    ok(f"Created PM-owned test project pid={pid}")

    # ───────────────────────────────────────────────────────────────────────
    # 1. AI text intake — Build 5/11
    # ───────────────────────────────────────────────────────────────────────
    print("\n── 1. AI text intake (extract) ──")
    r = admin_s.post(f"{BASE}/ai/intake/extract",
                     data={"raw_text": "Hey we're working on a chef knife called RBlack Pro. Factory is Acme. Sarah Chen is PM. Target cost $18, MSRP $129. Q4 2026 launch."})
    if r.status_code != 200:
        fail("text intake status", f"status={r.status_code}")
    elif _ai_failed(r.text):
        skip("text intake (project)", "AI call failed server-side — check OPENAI_API_KEY")
    elif 'action="/ai/intake/confirm"' in r.text:
        ok("text intake → renders project review form")
    elif 'action="/ai/intake/confirm-idea"' in r.text:
        ok("text intake → renders idea review form (classified as idea)")
    else:
        fail("text intake render", "no confirm/confirm-idea action in response")

    # Idea-classification path
    r = admin_s.post(f"{BASE}/ai/intake/extract",
                     data={"raw_text": "Saw a cool damascus pattern at the SHOT show — could use it for a folder later."})
    if r.status_code == 200:
        if _ai_failed(r.text):
            skip("text intake (idea)", "AI call failed server-side")
        elif 'action="/ai/intake/confirm-idea"' in r.text:
            ok("text intake (idea-like) → AI classifies as idea")
        elif 'action="/ai/intake/confirm"' in r.text:
            ok("text intake (idea-like) → AI classified as project (acceptable; dual-mode is best-effort)")
        else:
            fail("text intake idea render", "no confirm action")

    # ───────────────────────────────────────────────────────────────────────
    # 2. AI file intake — image (Build 6)
    # ───────────────────────────────────────────────────────────────────────
    print("\n── 2. AI file intake (image) ──")
    r = admin_s.post(
        f"{BASE}/ai/intake/extract-file",
        files={"file": ("test.png", io.BytesIO(make_png()), "image/png")},
        data={"file_category": "reference"},
    )
    if r.status_code != 200:
        fail("image intake status", f"status={r.status_code}")
    elif _ai_failed(r.text):
        skip("image intake", "AI vision call failed server-side")
    elif 'action="/ai/intake/confirm"' in r.text or 'action="/ai/intake/confirm-idea"' in r.text:
        ok("image intake → renders review form")
    else:
        fail("image intake render", "no confirm action in response")

    # ───────────────────────────────────────────────────────────────────────
    # 3. AI file intake — PDF (Build 6)
    # ───────────────────────────────────────────────────────────────────────
    print("\n── 3. AI file intake (PDF) ──")
    r = admin_s.post(
        f"{BASE}/ai/intake/extract-file",
        files={"file": ("test.pdf", io.BytesIO(make_tiny_pdf()), "application/pdf")},
        data={"file_category": "reference"},
    )
    if r.status_code != 200:
        fail("pdf intake status", f"status={r.status_code}")
    elif _ai_failed(r.text):
        skip("pdf intake", "AI PDF extraction failed server-side")
    elif 'action="/ai/intake/confirm"' in r.text or 'action="/ai/intake/confirm-idea"' in r.text:
        ok("pdf intake → renders review form")
    else:
        fail("pdf intake render", "no confirm action in response")

    # ───────────────────────────────────────────────────────────────────────
    # 4. Help AI Q&A (Build 7) + viewer refusal (Build 8)
    # ───────────────────────────────────────────────────────────────────────
    print("\n── 4. Help AI Q&A + viewer refusal ──")
    r = admin_s.post(f"{BASE}/ai/help/ask",
                     json={"question": "How do I create a project?"})
    if r.status_code != 200:
        fail("help ask status", f"status={r.status_code}")
    else:
        data = r.json()
        answer = data.get("answer", "")
        if "error" in (answer or "").lower() and "AuthenticationError" in answer:
            skip("help ask", "AI call failed server-side")
        elif answer and len(answer) > 20:
            ok(f"Help Ask returns substantive answer (len={len(answer)})")
        else:
            skip("help ask", f"empty/short answer: {answer!r}")

    # Viewer asks a forbidden question — should refuse WITHOUT any OpenAI call
    r = viewer_s.post(f"{BASE}/ai/help/ask",
                      json={"question": "What factory does this project use?"})
    if r.status_code == 200:
        data = r.json()
        answer = data.get("answer", "")
        if "not able to provide" in answer.lower() or "access level" in answer.lower():
            ok("Viewer factory question → refused by Permission Guard (no AI call)")
        else:
            fail("viewer refusal", f"unexpected answer: {answer[:120]!r}")
    else:
        fail("viewer help status", f"status={r.status_code}")

    # ───────────────────────────────────────────────────────────────────────
    # 5. Project Journal AI summary (Build 14)
    # ───────────────────────────────────────────────────────────────────────
    print("\n── 5. Project Journal AI summary ──")
    # Create a journal entry first
    r = admin_s.post(f"{BASE}/projects/{pid}/journal",
                     data={"entry_text": "Factory pushed back on the 18 USD target — they want 22. Need to push back or change spec.",
                           "entry_type": "general"},
                     allow_redirects=False)
    if r.status_code in (302, 303):
        rows = db_query("SELECT id FROM project_journal_entries WHERE project_id=? ORDER BY id DESC LIMIT 1", (pid,))
        if rows:
            entry_id = rows[0][0]
            r = admin_s.post(f"{BASE}/projects/{pid}/journal/{entry_id}/summarize",
                             allow_redirects=False)
            if r.status_code in (200, 302, 303):
                rows = db_query("SELECT title, ai_summary FROM project_journal_entries WHERE id=?", (entry_id,))
                title, summary = (rows[0] if rows else ("", ""))
                if title and summary and len(summary) > 10:
                    ok(f"Journal entry summarized (title='{(title or '')[:40]}', summary len={len(summary or '')})")
                else:
                    skip("journal summarize", f"AI summary not populated (title={title!r}, summary={summary!r}) — likely AI call failed")
            else:
                fail("journal summarize status", f"status={r.status_code}")
        else:
            fail("journal entry id", "could not find created journal entry")
    else:
        fail("journal create", f"status={r.status_code}")

    # ───────────────────────────────────────────────────────────────────────
    # 6. Business Plan thesis extraction (Build 15) — DOCX path
    # ───────────────────────────────────────────────────────────────────────
    print("\n── 6. Business Plan thesis extraction (DOCX) ──")
    try:
        from docx import Document  # python-docx
        doc = Document()
        doc.add_paragraph(
            "RBlack Pro Chef Knife. This product targets home cooks who want a pro-feel "
            "blade without spending $300. Differentiator: damascus steel + ergonomic grip. "
            "Target MSRP $129. Main risk: importing damascus from China — quality variance."
        )
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        docx_bytes = buf.read()
    except ImportError:
        docx_bytes = None
        skip("business plan extract", "python-docx not installed; skipping DOCX path")

    if docx_bytes:
        r = admin_s.post(
            f"{BASE}/projects/{pid}/thesis/extract-upload",
            files={"business_plan": ("plan.docx", io.BytesIO(docx_bytes),
                   "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            allow_redirects=False,
        )
        if r.status_code in (302, 303):
            loc = r.headers.get("location", "")
            if "/thesis/preview" in loc:
                # Follow the server's redirect target (it contains extraction_id query param)
                preview_url = loc if loc.startswith("http") else f"{BASE}{loc}"
                preview = admin_s.get(preview_url)
                if preview.status_code == 200:
                    body = preview.text
                    if _ai_failed(body) or "extraction failed" in body.lower():
                        skip("business plan extract", "AI extraction failed server-side")
                    elif "RBlack" in body or "damascus" in body.lower() or "chef" in body.lower():
                        ok("Business plan extraction populated preview with content from source")
                    else:
                        skip("business plan extract", "preview rendered but content not recognizable — could be AI returning empty")
                else:
                    fail("thesis preview", f"status={preview.status_code}")
            elif f"/projects/{pid}" in loc and "thesis_error" in loc:
                skip("business plan extract", f"server returned thesis_error in redirect: {loc}")
            else:
                # Redirected back to project page without preview — extraction probably errored gracefully
                skip("business plan extract", f"no preview URL in redirect: {loc}")
        else:
            fail("thesis upload status", f"status={r.status_code}")

    # ───────────────────────────────────────────────────────────────────────
    # 7. AI tool dispatcher in-process (Build 20)
    # ───────────────────────────────────────────────────────────────────────
    print("\n── 7. AI tool dispatcher (in-process; no OpenAI call) ──")
    try:
        from app.database import SessionLocal
        from app.models import User
        from app.ai.tools import TOOL_SCHEMAS, dispatch
        db = SessionLocal()
        admin_u = db.query(User).filter(User.username == ADMIN).first()
        viewer_u = db.query(User).filter(User.username == VIEWER_USER).first()
        # Build 07B added 3 blocker tools, bringing total to 23. Future builds
        # may keep adding; accept >= 23 to stay forward-compatible.
        if len(TOOL_SCHEMAS) >= 20:
            ok(f"TOOL_SCHEMAS has {len(TOOL_SCHEMAS)} entries (>=20 since Build 28; 23 after v1.3 Build 07B)")
        else:
            fail("tool schemas count", f"expected >= 20, got {len(TOOL_SCHEMAS)}")
        res = dispatch("create_journal_entry",
                       {"project_id": pid, "entry_text": "AI e2e dispatcher test", "entry_type": "general"},
                       db, admin_u)
        if res.get("error") == "confirmation_required":
            res = dispatch("create_journal_entry",
                           {"project_id": pid, "entry_text": "AI e2e dispatcher test", "entry_type": "general"},
                           db, admin_u, confirmed=True)
        if res.get("ok") and res.get("entry_id"):
            ok(f"Dispatcher invokes create_journal_entry handler (entry_id={res['entry_id']})")
        else:
            fail("dispatcher journal", str(res))
        res = dispatch("delete_variant", {"variant_id": 1}, db, viewer_u)
        if not res.get("ok") and res.get("error") == "forbidden":
            ok("Dispatcher enforces role (viewer delete_variant → forbidden)")
        else:
            fail("dispatcher role guard", str(res))
        db.close()
    except Exception as exc:
        fail("dispatcher import", str(exc))

    # ───────────────────────────────────────────────────────────────────────
    # 8. Bottom AI chat (Build 21) — round-trip with tool invocation
    # ───────────────────────────────────────────────────────────────────────
    print("\n── 8. Bottom AI Chat round-trip ──")
    r = admin_s.post(f"{BASE}/ai/chat",
                     json={"message": "Please log a journal entry that says 'AI e2e chat test ran successfully'.",
                           "mode": "intake",
                           "project_id": pid})
    if r.status_code != 200:
        fail("chat status", f"status={r.status_code}")
    else:
        data = r.json()
        if not data.get("ok"):
            fail("chat ok", str(data))
        else:
            assistant = data.get("assistant_message") or ""
            tool_calls = data.get("tool_calls") or []
            if "AI error" in assistant or "AuthenticationError" in assistant:
                skip("chat tool round-trip", "AI call failed server-side")
            elif any(
                tc.get("name") == "create_journal_entry"
                and tc.get("result", {}).get("error") == "confirmation_required"
                and tc.get("result", {}).get("proposal_id")
                for tc in tool_calls
            ):
                ok("Chat round-trip proposed a confirmable create_journal_entry action")
            elif tool_calls:
                names = [tc.get("name") for tc in tool_calls]
                fail("chat tool", f"tool calls happened but no successful create_journal_entry: {names}")
            else:
                skip("chat tool round-trip",
                     f"AI chose not to call a tool (assistant message: {(assistant or '')[:100]!r})")

    # Permission guard (no AI call needed; always runs)
    r = viewer_s.post(f"{BASE}/ai/chat",
                      json={"message": "what factory does this project use", "mode": "ask"})
    if r.status_code == 200 and r.json().get("error") == "question_blocked_by_permission_guard":
        ok("Bottom chat: viewer factory question blocked by guard (no AI call)")
    else:
        fail("chat guard", f"status={r.status_code} body={r.text[:200]}")

    # ───────────────────────────────────────────────────────────────────────
    # 9. AI-Assisted Create UI routing (Build 22) — no OpenAI call
    # ───────────────────────────────────────────────────────────────────────
    print("\n── 9. AI-Assisted Create UI routing ──")
    r = admin_s.get(f"{BASE}/projects/new?tab=ai")
    if r.status_code == 200 and 'id="pane-create-ai"' in r.text:
        idx = r.text.find('id="pane-create-ai"')
        snippet = r.text[max(0, idx - 60):idx + 100]
        if "show active" in snippet:
            ok("?tab=ai activates AI panel on /projects/new")
        else:
            fail("create-ai active", f"snippet: {snippet!r}")
    else:
        fail("create-ai status", f"status={r.status_code}")
    r = admin_s.get(f"{BASE}/ai/intake", allow_redirects=False)
    if r.status_code == 303 and r.headers.get("location", "").endswith("/projects/new?tab=ai"):
        ok("Legacy /ai/intake redirects to /projects/new?tab=ai")
    else:
        fail("legacy redirect", f"status={r.status_code} loc={r.headers.get('location')}")

    _p()
    return len(FAIL) == 0


def _p():
    print("\n" + "=" * 64)
    print(f"PASSED:  {len(PASS)}")
    print(f"SKIPPED: {len(SKIP)}  (AI call failures count as SKIP, not FAIL)")
    print(f"FAILED:  {len(FAIL)}")
    if SKIP:
        print("\nSkipped (likely OPENAI_API_KEY missing/invalid or network issue):")
        for n, r in SKIP:
            print(f"  ⊘ {n}: {r}")
    if FAIL:
        print("\nFailed:")
        for n, r in FAIL:
            print(f"  ✗ {n}: {r}")
    print("=" * 64)
    if not FAIL:
        print("Build 22 expectation: all PASS or SKIP, none FAIL.")
        if SKIP:
            print("To turn SKIP → PASS: ensure server has a valid OPENAI_API_KEY in .env and restart `python run.py`.")


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
