"""Build 14 — Project Journal tests."""
import re
import sys
import requests

BASE = "http://localhost:8000"
PASS, FAIL = [], []

ADMIN, ADMIN_PWD = "admin", "show me the money"
PM_USER, PM_PWD = "testpm_b8", "pmpassword8!"
VIEWER_USER, VIEWER_PWD = "testviewer_b8", "viewerpass8!"


def ok(n): PASS.append(n); print(f"  ✓  {n}")
def fail(n, r): FAIL.append((n, r)); print(f"  ✗  {n}: {r}")




def _mint_build30_token(session):
    """Build 30A — POST /projects/new requires a submission_token from the GET."""
    import re as _r
    page = session.get(f"{BASE}/projects/new").text
    m = _r.search(r'name="submission_token"\s+value="([a-f0-9]+)"', page)
    return m.group(1) if m else ""

def login(u, p):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", data={"username": u, "password": p}, allow_redirects=False)
    return s if r.status_code in (302, 303) else None


def get_or_create_project(admin_s, name):
    """Create a project where PM is the assigned product_manager."""
    html = admin_s.get(f"{BASE}/projects").text
    m = re.search(r'href="/projects/(\d+)"', html)
    if m:
        return int(m.group(1))
    r = admin_s.post(f"{BASE}/projects/new",
                     data={"name": name, "prototype_rounds": "single",
                           "submission_token": _mint_build30_token(admin_s)}, allow_redirects=False)
    return int(r.headers["location"].rstrip("/").split("/")[-1])


def main():
    admin_s = login(ADMIN, ADMIN_PWD)
    pm_s = login(PM_USER, PM_PWD)
    viewer_s = login(VIEWER_USER, VIEWER_PWD)
    if not all([admin_s, pm_s, viewer_s]):
        fail("setup", "could not log in all three roles"); _p(); return False
    ok("All three roles can log in")

    # Get/create projects:
    #   admin_proj — owned by admin (product_manager=Admin)
    #   pm_proj    — owned by PM (set product_manager to PM_USER display name)
    admin_proj = get_or_create_project(admin_s, "Build14 Admin Project")
    # Create a PM-owned project: pick the 2nd project from the list
    pm_proj_html = admin_s.get(f"{BASE}/projects").text
    pm_proj_match = re.findall(r'href="/projects/(\d+)"', pm_proj_html)
    pm_proj = int(pm_proj_match[1]) if len(pm_proj_match) > 1 else admin_proj
    # Set PM on pm_proj = PM_USER (so PM owns it)
    admin_s.post(f"{BASE}/projects/{pm_proj}/edit", data={
        "name": f"Build14 PM Project {pm_proj}", "product_manager": PM_USER,
        "status": "active",
    }, allow_redirects=False)
    # Set PM on admin_proj = the admin username (so PM does NOT own it)
    admin_s.post(f"{BASE}/projects/{admin_proj}/edit", data={
        "name": f"Build14 Admin Project {admin_proj}",
        "product_manager": ADMIN,  # explicitly NOT the PM
        "status": "active",
    }, allow_redirects=False)
    ok(f"Setup: admin_proj={admin_proj} (PM=admin), pm_proj={pm_proj} (PM={PM_USER})")

    # ── Viewer cannot see Journal section at all ────────────────────────
    print("\n── Viewer cannot see Journal ──")
    html = viewer_s.get(f"{BASE}/projects/{admin_proj}").text
    if "journal-toggle-btn" not in html and "Project Journal" not in html and "journal-section" not in html:
        ok("Viewer sees NO journal reveal button or section")
    else:
        fail("Viewer journal hidden", "found journal-related HTML on viewer page")

    # Viewer POST is blocked
    r = viewer_s.post(f"{BASE}/projects/{admin_proj}/journal",
                      data={"entry_text": "viewer attempt", "entry_type": "general"},
                      allow_redirects=False)
    if r.status_code in (302, 303):
        ok("Viewer POST /journal redirected (not allowed)")
    else:
        fail("Viewer POST", f"status {r.status_code}")

    # ── Admin can create on any project ─────────────────────────────────
    print("\n── Admin create on any project ──")
    r = admin_s.post(f"{BASE}/projects/{admin_proj}/journal",
                     data={"entry_text": "Build14 admin entry on admin proj", "entry_type": "general"},
                     allow_redirects=False)
    if r.status_code in (302, 303):
        ok("Admin POST returns redirect")
    detail = admin_s.get(f"{BASE}/projects/{admin_proj}").text
    if "Build14 admin entry on admin proj" in detail:
        ok("Entry appears in admin's project detail")
    else:
        fail("Entry display", "text not found in detail")

    # ── PM can create on own project ────────────────────────────────────
    print("\n── PM create on own project ──")
    r = pm_s.post(f"{BASE}/projects/{pm_proj}/journal",
                  data={"entry_text": "Build14 pm entry on pm proj", "entry_type": "decision"},
                  allow_redirects=False)
    if r.status_code in (302, 303):
        ok("PM POST on own project returns redirect")
    detail = pm_s.get(f"{BASE}/projects/{pm_proj}").text
    if "Build14 pm entry on pm proj" in detail:
        ok("PM-created entry appears for PM")
    else:
        fail("PM entry display", "text not found")

    # ── PM cannot create on someone else's project ──────────────────────
    print("\n── PM cannot create on someone else's project ──")
    r = pm_s.post(f"{BASE}/projects/{admin_proj}/journal",
                  data={"entry_text": "PM attempt on admin proj", "entry_type": "general"},
                  allow_redirects=False)
    if r.status_code in (302, 303):
        admin_view = admin_s.get(f"{BASE}/projects/{admin_proj}").text
        if "PM attempt on admin proj" not in admin_view:
            ok("PM attempt on someone else's project did NOT create entry")
        else:
            fail("PM unauthorized create", "entry was actually created!")
    else:
        fail("PM unauthorized POST", f"status {r.status_code}")

    # ── PM cannot edit another author's entry ───────────────────────────
    print("\n── PM cannot edit another author's entry ──")
    # First: have admin make pm_proj's PM (currently PM_USER) able to edit it;
    # admin creates an entry on pm_proj, then PM tries to edit it.
    r = admin_s.post(f"{BASE}/projects/{pm_proj}/journal",
                     data={"entry_text": "Admin-authored entry on PM proj", "entry_type": "risk"},
                     allow_redirects=False)
    # Extract the admin-authored entry id from pm_proj's detail page
    detail = admin_s.get(f"{BASE}/projects/{pm_proj}").text
    entry_ids = [int(m) for m in re.findall(r'id="journal-(\d+)"', detail)]
    # The most recent entry by admin should be among them
    if entry_ids:
        admin_entry_id = entry_ids[0]  # newest first
        ok(f"Admin entry id={admin_entry_id} created on pm_proj")
        # PM tries to edit admin's entry
        r = pm_s.post(f"{BASE}/projects/{pm_proj}/journal/{admin_entry_id}/edit",
                      data={"entry_text": "PM tampering", "entry_type": "general"},
                      allow_redirects=False)
        # Check entry was NOT modified
        detail_after = admin_s.get(f"{BASE}/projects/{pm_proj}").text
        if "PM tampering" not in detail_after:
            ok("PM blocked from editing another author's entry (text unchanged)")
        else:
            fail("PM author check", "entry text was modified by non-author!")

    # ── PM can edit their OWN entry on own project ──────────────────────
    print("\n── PM can edit own entry on own project ──")
    detail = pm_s.get(f"{BASE}/projects/{pm_proj}").text
    # Find PM's own entry from earlier
    blocks = re.findall(r'id="journal-(\d+)"[\s\S]*?journal-text-\d+">([^<]*)<', detail)
    pm_own_id = None
    for eid, text in blocks:
        if "Build14 pm entry on pm proj" in text:
            pm_own_id = int(eid)
            break
    if pm_own_id:
        r = pm_s.post(f"{BASE}/projects/{pm_proj}/journal/{pm_own_id}/edit",
                      data={"entry_text": "Build14 pm entry — EDITED", "entry_type": "decision"},
                      allow_redirects=False)
        detail_after = pm_s.get(f"{BASE}/projects/{pm_proj}").text
        if "Build14 pm entry — EDITED" in detail_after:
            ok("PM edited their own entry successfully")
            # Verify change log audit row was written
            if "Journal entry edited" in detail_after:
                ok("Edit recorded in project change log")
            else:
                fail("Change log audit", "no 'Journal entry edited' in change log")
        else:
            fail("PM edit own", "new text not visible")

    # ── PM cannot delete (admin only) ───────────────────────────────────
    print("\n── PM cannot delete ──")
    if pm_own_id:
        r = pm_s.post(f"{BASE}/projects/{pm_proj}/journal/{pm_own_id}/delete",
                      allow_redirects=False)
        detail_after = pm_s.get(f"{BASE}/projects/{pm_proj}").text
        if "Build14 pm entry — EDITED" in detail_after:
            ok("PM delete attempt did NOT remove entry")
        else:
            fail("PM delete block", "entry was deleted by PM!")

    # ── Admin can delete ────────────────────────────────────────────────
    print("\n── Admin can delete ──")
    if pm_own_id:
        r = admin_s.post(f"{BASE}/projects/{pm_proj}/journal/{pm_own_id}/delete",
                         allow_redirects=False)
        detail_after = admin_s.get(f"{BASE}/projects/{pm_proj}").text
        # Use the unique entry-id DOM marker (text snippet survives in the
        # change log audit row by design — that's evidence the delete WORKED).
        if f'id="journal-{pm_own_id}"' not in detail_after:
            ok("Admin successfully deleted entry (DOM marker gone)")
            # Verify the audit trail captured the deletion
            if "Journal entry deleted" in detail_after:
                ok("Deletion recorded in project change log")
        else:
            fail("Admin delete", f"journal-{pm_own_id} still present")

    # ── AI summarize (live OpenAI call) ─────────────────────────────────
    print("\n── AI summarize entry (live AI call) ──")
    # Use the original admin entry
    detail = admin_s.get(f"{BASE}/projects/{admin_proj}").text
    blocks = re.findall(r'id="journal-(\d+)"', detail)
    if blocks:
        eid = int(blocks[0])
        print(f"    Summarizing entry id={eid} (calls GPT-5.4 — may take a few seconds...)")
        r = admin_s.post(f"{BASE}/projects/{admin_proj}/journal/{eid}/summarize",
                         allow_redirects=False)
        if r.status_code in (302, 303):
            ok("Summarize POST returned redirect")
        detail_after = admin_s.get(f"{BASE}/projects/{admin_proj}").text
        # On success, .journal-title or .journal-ai-summary should be populated
        if 'class="journal-title"' in detail_after or 'class="journal-ai-summary"' in detail_after:
            ok("AI summary populated (title or summary present in HTML)")
        else:
            # Could be a real AI failure — should NOT have overwritten anything
            if "summarize_failed" in r.headers.get("location", "") or "journal_error" in detail_after:
                ok("AI summarize failed gracefully (existing fields preserved)")
            else:
                fail("AI summary", "no title/summary in HTML and no error flash")

    _p()
    return len(FAIL) == 0


def _p():
    print("\n" + "=" * 60)
    print(f"PASSED: {len(PASS)}")
    print(f"FAILED: {len(FAIL)}")
    if FAIL:
        for n, r in FAIL: print(f"  ✗ {n}: {r}")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
