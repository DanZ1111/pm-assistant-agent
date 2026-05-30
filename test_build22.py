"""Build 22 — AI-Assisted Create Project (consolidate intake into /projects/new) tests.

Most assertions exercise the live server via requests.Session (no OpenAI calls
needed for the structural checks). One smoke test posts a tiny extract request
to /ai/intake/extract — that one IS a live OpenAI call but it's cheap.
"""
import os
import sys
import sqlite3
import requests

BASE = "http://localhost:8000"
PASS, FAIL = [], []

ADMIN, ADMIN_PWD = "admin", "show me the money"
PM_USER, PM_PWD = "testpm_b8", "pmpassword8!"
VIEWER_USER, VIEWER_PWD = "testviewer_b8", "viewerpass8!"


def ok(n): PASS.append(n); print(f"  ✓  {n}")
def fail(n, r): FAIL.append((n, r)); print(f"  ✗  {n}: {r}")


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


def main():
    admin_s = login(ADMIN, ADMIN_PWD)
    pm_s    = login(PM_USER, PM_PWD)
    viewer_s = login(VIEWER_USER, VIEWER_PWD)
    if not all([admin_s, pm_s, viewer_s]):
        fail("setup", "could not log in all three roles"); _p(); return False
    ok("All three roles can log in")

    # ── /projects/new tab markup ──
    print("\n── Tab structure on /projects/new ──")
    page = admin_s.get(f"{BASE}/projects/new").text
    if 'id="createProjectTabs"' in page and 'id="pane-create-manual"' in page and 'id="pane-create-ai"' in page:
        ok("Both Manual + AI-Assisted tabs render on /projects/new")
    else:
        fail("tabs present", "expected createProjectTabs + pane-create-manual + pane-create-ai in HTML")

    # Default tab is Manual
    idx = page.find('id="pane-create-manual"')
    snippet = page[max(0, idx - 60):idx + 100] if idx >= 0 else ""
    if "show active" in snippet:
        ok("Default initial tab is Manual (pane-create-manual has 'show active')")
    else:
        fail("default tab", f"pane-create-manual snippet: {snippet!r}")

    # ?tab=ai → AI tab active
    page_ai = admin_s.get(f"{BASE}/projects/new?tab=ai").text
    idx = page_ai.find('id="pane-create-ai"')
    snippet = page_ai[max(0, idx - 60):idx + 100] if idx >= 0 else ""
    if "show active" in snippet:
        ok("?tab=ai makes the AI-Assisted pane active")
    else:
        fail("tab=ai active", f"pane-create-ai snippet: {snippet!r}")

    # AI tab contains the intake input form (state 1)
    if 'action="/ai/intake/extract"' in page_ai and 'action="/ai/intake/extract-file"' in page_ai:
        ok("AI tab contains intake extract + extract-file forms")
    else:
        fail("intake forms", "intake form actions missing from /projects/new?tab=ai")

    # ── /ai/intake legacy redirect ──
    print("\n── /ai/intake legacy redirect ──")
    r = admin_s.get(f"{BASE}/ai/intake", allow_redirects=False)
    if r.status_code == 303 and r.headers.get("location", "").endswith("/projects/new?tab=ai"):
        ok("GET /ai/intake → 303 redirect to /projects/new?tab=ai")
    else:
        fail("legacy redirect", f"status={r.status_code} location={r.headers.get('location')}")

    # Anonymous GET /ai/intake also redirects (it's now a public 303 — no auth check)
    r = requests.get(f"{BASE}/ai/intake", allow_redirects=False)
    if r.status_code == 303:
        ok("Anon GET /ai/intake also returns 303 (legacy redirect is public)")
    else:
        fail("anon redirect", f"status={r.status_code}")

    # ── Navbar: AI Intake link is GONE ──
    print("\n── Navbar AI Intake link removed ──")
    page = admin_s.get(f"{BASE}/projects").text
    # The Build 22 navbar should NOT contain an <a> to /ai/intake.
    # (It might still reference /ai/* in URL-path matching for active styling elsewhere — search for the literal nav link.)
    if 'href="/ai/intake"' not in page:
        ok("Admin navbar does NOT contain href=\"/ai/intake\"")
    else:
        fail("nav link still there", "found href=\"/ai/intake\" in admin /projects HTML")
    # Narrow check: no <a class="nav-link"> with /ai/intake. The literal text
    # "AI Intake" still appears in the Help modal content describing the feature —
    # that's fine and not in scope to scrub. The behavioral assertion above is
    # what matters (the link can't be clicked).
    # Bottom chat bar (from Build 21) still there
    if 'id="bottomChatBar"' in page:
        ok("Build 21 bottom chat bar still present")
    else:
        fail("regression: chat bar", "bottomChatBar markup missing")

    # ── Viewer cannot reach /projects/new (existing role guard) ──
    print("\n── Viewer guard on /projects/new ──")
    r = viewer_s.get(f"{BASE}/projects/new", allow_redirects=False)
    if r.status_code == 303 and "/projects" in r.headers.get("location", ""):
        ok("Viewer redirected from /projects/new (existing role guard not regressed)")
    else:
        fail("viewer guard", f"status={r.status_code} loc={r.headers.get('location')}")

    # ── Extract round-trip ──
    # If a valid OPENAI_API_KEY is configured server-side, the response renders
    # State 2 (review form). If the key is invalid/placeholder, the response
    # renders State 1 with an "AI extraction failed" error. EITHER outcome
    # proves the routing + helper + tab wiring works — that's all we need
    # Build 22 to verify. Real-AI accuracy is out of scope here.
    print("\n── /ai/intake/extract round-trip (no crash, AI tab stays active) ──")
    r = admin_s.post(f"{BASE}/ai/intake/extract",
                     data={"raw_text": "Test build22 — a tiny note about a project called Build22 SmokeTest, factory Acme."})
    if r.status_code != 200:
        fail("extract status", f"status={r.status_code}")
    else:
        body = r.text
        rendered_state2 = ('action="/ai/intake/confirm"' in body or
                           'action="/ai/intake/confirm-idea"' in body)
        rendered_state1_with_error = "AI extraction failed" in body
        rendered_state1_clean = "Paste Your Notes" in body and not rendered_state1_with_error
        if rendered_state2:
            ok("Extract response renders State-2 review form (live AI succeeded)")
        elif rendered_state1_with_error:
            ok("Extract response renders State-1 with 'AI extraction failed' (server has placeholder key — Build 22 routing OK)")
        elif rendered_state1_clean:
            ok("Extract response renders State-1 (edge case but no crash)")
        else:
            fail("extract render", "neither State-1 nor State-2 markers found in response")
        # In every case the AI tab should be active
        idx = body.find('id="pane-create-ai"')
        snippet = body[max(0, idx - 60):idx + 100] if idx >= 0 else ""
        if "show active" in snippet:
            ok("Extract response keeps AI tab active")
        else:
            fail("extract tab", "AI pane not shown active after extract")

    # ── Confirm flow still creates a project (regression — no UI change to logic) ──
    print("\n── /ai/intake/confirm still creates a project ──")
    proj_name = f"Build22 Confirm Test {os.getpid()}"
    r = admin_s.post(
        f"{BASE}/ai/intake/confirm",
        data={
            "name": proj_name,
            "brand": "Acme",
            "project_thesis": "Build 22 regression test — this thesis is at least eighty characters so it passes the health check.",
            "prototype_rounds": "single",
        },
        allow_redirects=False,
    )
    if r.status_code in (302, 303):
        loc = r.headers.get("location", "")
        # Should redirect to /projects/{id}
        if loc.startswith("/projects/") and loc.rstrip("/").split("/")[-1].isdigit():
            ok(f"Confirm flow redirects to project detail: {loc}")
            pid = int(loc.rstrip("/").split("/")[-1])
            rows = db_query("SELECT name FROM projects WHERE id=?", (pid,))
            if rows and rows[0][0] == proj_name:
                ok(f"Created project row exists in DB (pid={pid})")
            else:
                fail("confirm db", f"project row missing or name mismatch: {rows}")
        else:
            fail("confirm redirect target", f"location={loc}")
    else:
        fail("confirm status", f"status={r.status_code}")

    # ── Confirm flow with empty name returns the review form with error (no crash) ──
    print("\n── /ai/intake/confirm with empty name handled gracefully ──")
    r = admin_s.post(f"{BASE}/ai/intake/confirm",
                     data={"name": "", "brand": "Acme"},
                     allow_redirects=False)
    # Could be 200 (renders form with error) or 4xx — we just want NO 5xx
    if r.status_code < 500:
        body = r.text if r.status_code == 200 else ""
        if r.status_code == 200 and ("required" in body.lower() or "error" in body.lower()):
            ok("Empty name → 200 with error message (no crash)")
        elif r.status_code == 200:
            ok("Empty name → 200 (handled — no 5xx)")
        else:
            ok(f"Empty name → {r.status_code} (handled — no 5xx)")
    else:
        fail("empty name handling", f"5xx: {r.status_code}")

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
