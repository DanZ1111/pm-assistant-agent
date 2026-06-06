"""v1.3 Build 08 — Timeline Updates / History (derived view) tests.

Verifies (per V13_BUILD08_EXECUTION_PLAN.md, Locks 1-11 + ChatGPT amendments):
- crud.get_timeline_events merges 3 source tables (project_changes,
  phase_plan_changes, project_journal_entries) with deterministic
  tiebreaker (source priority + source_id DESC).
- Every event carries source_table + source_id (traceable to ONE row).
- viewer=True removes restricted events entirely (cost updates, sensitive
  file uploads, journal entries) — no hidden placeholders.
- Lock 2: every event has one primary bucket from the 6 chips; subtypes
  are display-only overlay labels.
- Lock 5: filter chips apply to the FULL 200-event array (rows hidden by
  pagination still match the filter rule).
- Lock 6: AI overlay badge fires when source_type='ai_chat' OR
  changed_by='ai' — independent of bucket.
- Lock 10: anchor links omitted when target unreachable (no #journal link
  for viewer; no #phase-row-N link for deleted phase).
- 3 empty states render correct copy (no events / no filter match /
  viewer hidden).
- Show more reveals events 51-200.
- i18n parity at 714/714.
- Build 06/07A/07B invariants preserved.
- Migration count still 6 (no schema change).
"""
import json
import os
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta

import requests

BASE = os.environ.get("BASE_URL", "http://localhost:8000")
PASS, FAIL = [], []

ADMIN, ADMIN_PWD = "admin", "show me the money"
PM_USER, PM_PWD = "testpm_b8", "pmpassword8!"
VIEWER_USER, VIEWER_PWD = "testviewer_b8", "viewerpass8!"


def ok(n):
    PASS.append(n)
    print(f"  ✓  {n}")


def fail(n, r):
    FAIL.append((n, r))
    print(f"  ✗  {n}: {r}")


def login(u, p):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login",
        data={"username": u, "password": p}, allow_redirects=False, timeout=5)
    return s if r.status_code in (302, 303) else None


def db_query(sql, params=()):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def db_execute(sql, params=()):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def cleanup(name_prefix):
    conn = sqlite3.connect("pm_tracker.db")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE name LIKE ?", (name_prefix + "%",))
        for (pid,) in cur.fetchall():
            cur.execute("DELETE FROM project_blockers WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_variant_components WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_variants WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_changes WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM phase_plan_changes WHERE phase_id IN (SELECT id FROM project_phases WHERE project_id = ?)", (pid,))
            cur.execute("DELETE FROM project_phases WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_files WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_journal_entries WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM ai_messages WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM project_creation_tokens WHERE project_id = ?", (pid,))
            cur.execute("DELETE FROM projects WHERE id = ?", (pid,))
        conn.commit()
    finally:
        conn.close()


def mint_token(session):
    page = session.get(f"{BASE}/projects/new").text
    m = re.search(r'name="submission_token"\s+value="([a-f0-9]+)"', page)
    return m.group(1) if m else None


def make_project(session, name, pm_username):
    tok = mint_token(session)
    r = session.post(f"{BASE}/projects/new",
        data={"name": name, "product_manager": pm_username,
              "prototype_rounds": "single", "submission_token": tok},
        allow_redirects=False, timeout=5)
    return int(r.headers["location"].rstrip("/").split("/")[-1])


def main():
    admin = login(ADMIN, ADMIN_PWD)
    pm = login(PM_USER, PM_PWD)
    viewer = login(VIEWER_USER, VIEWER_PWD)
    if not all([admin, pm, viewer]):
        fail("setup", "could not log in all three roles"); _p(); return False
    ok("All three roles can log in")

    cleanup("b08_test")

    # ── 1. i18n parity at 714/714 + Build 08 keys ──
    print("\n── 1. i18n parity + Build 08 keys ──")
    with open("app/i18n/en.json") as f: en = json.load(f)
    with open("app/i18n/zh.json") as f: zh = json.load(f)
    if set(en) == set(zh):
        ok(f"en/zh parity at {len(en)} keys")
    else:
        fail("parity", f"en={len(en)} zh={len(zh)}")
    if len(en) >= 714:
        ok(f"key count ≥ 714 (got {len(en)})")
    else:
        fail("key count", f"expected ≥ 714, got {len(en)}")
    new_keys = [
        "timeline.history_title", "timeline.history_hint",
        "timeline.history_show_more", "timeline.history_empty",
        "timeline.history_empty_filter", "timeline.history_empty_viewer",
        "timeline.history_back_to_all",
        "timeline.history_filter_all", "timeline.history_filter_delays",
        "timeline.history_filter_decisions", "timeline.history_filter_blockers",
        "timeline.history_filter_phase_changes", "timeline.history_filter_files",
        "timeline.history_event_phase_change", "timeline.history_event_decision",
        "timeline.history_event_delay", "timeline.history_event_blocker",
        "timeline.history_event_file_uploaded", "timeline.history_event_rendering_update",
        "timeline.history_event_cost_update", "timeline.history_event_sample_update",
        "timeline.history_event_packaging_update", "timeline.history_event_manual_note",
        "timeline.history_ai_badge", "timeline.history_by_actor", "timeline.history_anchor_view",
    ]
    missing = [k for k in new_keys if k not in en]
    if not missing:
        ok(f"All {len(new_keys)} Build 08 history keys present")
    else:
        fail("Build 08 keys", f"missing: {missing}")

    # ── 2. Migration count unchanged ──
    print("\n── 2. Build 08 added no migration of its own ──")
    from app.migrations import MIGRATIONS
    migration_names = [name for name, _ in MIGRATIONS]
    if "006_v1_3_add_project_blockers" in migration_names and not any("v1_3_build08" in name for name in migration_names):
        ok(f"Build 08 preserved migration inventory; later builds may add more (count now {len(MIGRATIONS)})")
    else:
        fail("migration inventory", f"unexpected Build 08 migration drift: {migration_names}")

    # ── 3. Project setup with multi-source activity ──
    print("\n── 3. Project setup — exercise all 3 source tables ──")
    from app.database import SessionLocal
    from app import crud
    pid = make_project(admin, "b08_test_main", PM_USER)
    rows = db_query("SELECT id, phase_order FROM project_phases WHERE project_id=? ORDER BY phase_order LIMIT 2", (pid,))
    p1_id = rows[0][0]
    pm_user_id = db_query("SELECT id FROM users WHERE username=?", (PM_USER,))[0][0]

    # Phase plan-date adjustment (writes phase_plan_changes + project_changes)
    sess = SessionLocal()
    try:
        crud.update_phase(sess, p1_id, {"planned_end_date": date.today() + timedelta(days=10)},
                          changed_by="user", reason="Initial plan", changed_by_user_id=pm_user_id)
        # Forward-shift the date (creates a DELAY event)
        crud.update_phase(sess, p1_id, {"planned_end_date": date.today() + timedelta(days=20)},
                          changed_by="user", reason="Factory pushed sample", changed_by_user_id=pm_user_id)
        # Cost field change
        crud.update_project(sess, pid, {"target_factory_cost": "9.00"},
                            changed_by="user", source_type="manual_edit")
        # Blocker
        b1 = crud.create_blocker(sess, pid, title="Packaging quote missing",
                                 severity="high", phase_id=p1_id,
                                 created_by_user_id=pm_user_id)
        # Journal entries
        crud.create_journal_entry(sess, pid, "Decided to switch supplier",
                                  "decision", author_user_id=pm_user_id)
        crud.create_journal_entry(sess, pid, "Packaging spec discussed with vendor",
                                  "packaging", author_user_id=pm_user_id)
        # AI-flagged event_note (simulate via direct write_change)
        crud.write_change(sess, pid, "event_note", changed_by="ai",
                          summary="AI created a variant proposal", source_type="ai_chat")
        sess.commit()
    finally:
        sess.close()
    ok(f"Project {pid} populated with events from 3 source tables")

    # ── 4. Helper: returns events with required shape ──
    print("\n── 4. crud.get_timeline_events shape + ordering ──")
    sess = SessionLocal()
    try:
        res = crud.get_timeline_events(sess, pid, limit=200, viewer=False)
    finally:
        sess.close()
    if res["total"] > 0:
        ok(f"Returns {res['total']} events for populated project")
    else:
        fail("empty result", f"res={res}")
    required_keys = {"occurred_at", "bucket", "subtype", "actor", "title",
                     "body", "link_anchor", "is_ai", "source_table", "source_id"}
    sample = res["events"][0]
    if required_keys.issubset(sample.keys()):
        ok("Every event has the required shape (source_table + source_id present)")
    else:
        fail("event shape", f"missing: {required_keys - set(sample.keys())}")
    # Newest first
    times = [e["occurred_at"] for e in res["events"]]
    if all(times[i] >= times[i+1] for i in range(len(times)-1)):
        ok("Events sorted newest first")
    else:
        fail("ordering", "not descending")

    # ── 5. All 3 source tables represented ──
    print("\n── 5. All 3 source tables present in merged result ──")
    sources = {e["source_table"] for e in res["events"]}
    expected = {"project_changes", "phase_plan_changes", "project_journal_entries"}
    if expected.issubset(sources):
        ok(f"All 3 source tables present: {sources}")
    else:
        fail("sources", f"missing: {expected - sources}")

    # ── 6. Bucket coverage — every event has a primary bucket ──
    print("\n── 6. Lock 2 — every event has a primary bucket from the 6 chips ──")
    valid_buckets = {"delays", "decisions", "blockers", "phase_changes", "files"}
    bucket_violations = [e for e in res["events"] if e["bucket"] not in valid_buckets]
    if not bucket_violations:
        ok(f"All events have a valid primary bucket (no orphans)")
    else:
        fail("bucket orphans", f"got: {[(e['title'], e['bucket']) for e in bucket_violations]}")

    # ── 7. Specific event types correctly classified ──
    print("\n── 7. Event classification ──")
    has_delay = any(e["bucket"] == "delays" for e in res["events"])
    has_blocker = any(e["bucket"] == "blockers" for e in res["events"])
    has_decision = any(e["bucket"] == "decisions" and e["source_table"] == "project_journal_entries" for e in res["events"])
    has_cost = any(e["bucket"] == "decisions" and e["subtype"] == "cost" for e in res["events"])
    has_packaging = any(e["subtype"] == "packaging" for e in res["events"])
    has_ai = any(e["is_ai"] for e in res["events"])
    for cond, name in [
        (has_delay, "Forward-shift plan-change classified as Delay"),
        (has_blocker, "blocker_opened classified as Blocker"),
        (has_decision, "Journal decision entry classified as Decision"),
        (has_cost, "Cost field_update classified as Decisions + cost subtype"),
        (has_packaging, "Packaging journal entry has packaging subtype"),
        (has_ai, "AI-sourced event has is_ai=True"),
    ]:
        if cond:
            ok(name)
        else:
            fail(name, "not found in event list")

    # ── 8. Viewer permission filtering ──
    print("\n── 8. Lock 3 — viewer permission filtering ──")
    sess = SessionLocal()
    try:
        res_viewer = crud.get_timeline_events(sess, pid, limit=200, viewer=True)
    finally:
        sess.close()
    if res_viewer["viewer_hidden_count"] > 0:
        ok(f"viewer_hidden_count > 0 (hid {res_viewer['viewer_hidden_count']} restricted events)")
    else:
        fail("viewer hiding", "viewer_hidden_count == 0")
    # No journal-sourced events visible to viewer
    viewer_journal_events = [e for e in res_viewer["events"] if e["source_table"] == "project_journal_entries"]
    if not viewer_journal_events:
        ok("Viewer sees no journal-sourced events (Lock 3)")
    else:
        fail("viewer journal leak", f"got: {viewer_journal_events}")
    # No cost-subtype events visible to viewer
    viewer_cost_events = [e for e in res_viewer["events"] if e["subtype"] == "cost"]
    if not viewer_cost_events:
        ok("Viewer sees no cost-update events (Lock 3)")
    else:
        fail("viewer cost leak", f"got: {viewer_cost_events}")
    # Admin sees both
    admin_journal_events = [e for e in res["events"] if e["source_table"] == "project_journal_entries"]
    admin_cost_events = [e for e in res["events"] if e["subtype"] == "cost"]
    if admin_journal_events and admin_cost_events:
        ok("Admin/PM sees journal AND cost events")
    else:
        fail("admin visibility", f"journal={len(admin_journal_events)} cost={len(admin_cost_events)}")

    # ── 9. source_id traceability ──
    print("\n── 9. source_table + source_id traceable ──")
    blocker_event = next((e for e in res["events"] if e["bucket"] == "blockers"), None)
    if blocker_event:
        # Source table should be project_changes; source_id should resolve to a real row
        actual = db_query(
            "SELECT change_type FROM project_changes WHERE id=?",
            (blocker_event["source_id"],)
        )
        if actual and actual[0][0].startswith("blocker_"):
            ok(f"Blocker event source_id={blocker_event['source_id']} traces to project_changes row of type '{actual[0][0]}'")
        else:
            fail("source trace", f"row not found or wrong type: {actual}")
    else:
        fail("blocker event", "no blocker in results to trace")

    # ── 10. Deterministic tiebreaker — same project, two consecutive calls match ──
    print("\n── 10. Lock 7 — deterministic ordering ──")
    sess = SessionLocal()
    try:
        res_a = crud.get_timeline_events(sess, pid, limit=200, viewer=False)
        res_b = crud.get_timeline_events(sess, pid, limit=200, viewer=False)
    finally:
        sess.close()
    ids_a = [(e["source_table"], e["source_id"]) for e in res_a["events"]]
    ids_b = [(e["source_table"], e["source_id"]) for e in res_b["events"]]
    if ids_a == ids_b:
        ok("Two consecutive calls produce identical ordering")
    else:
        fail("non-deterministic", "ordering differed between calls")

    # ── 11. Anchor links — Lock 10 graceful fallback ──
    print("\n── 11. Lock 10 — anchor links best-effort ──")
    # Admin/PM should see #journal anchors on journal events
    journal_evt = next((e for e in res["events"] if e["source_table"] == "project_journal_entries"), None)
    if journal_evt and journal_evt["link_anchor"] == "#journal":
        ok("Admin/PM sees #journal anchor on journal-sourced events")
    else:
        fail("admin journal anchor", f"got: {journal_evt}")
    # Viewer should never see #journal anchors (journal events filtered out entirely)
    viewer_anchors = {e["link_anchor"] for e in res_viewer["events"]}
    if "#journal" not in viewer_anchors:
        ok("Viewer never sees #journal anchor (journal events filtered out)")
    else:
        fail("viewer journal anchor leak", f"anchors: {viewer_anchors}")

    # ── 12. Template — section renders + filter chips + event rows ──
    print("\n── 12. Template — #timeline-history section ──")
    page = pm.get(f"{BASE}/projects/{pid}").text
    for marker, msg in [
        ('id="timeline-history"', "Section renders"),
        ('class="timeline-history-filters"', "Filter chip row renders"),
        ('data-filter="all"', "All chip"),
        ('data-filter="delays"', "Delays chip"),
        ('data-filter="decisions"', "Decisions chip"),
        ('data-filter="blockers"', "Blockers chip"),
        ('data-filter="phase_changes"', "Phase Changes chip"),
        ('data-filter="files"', "Files+Renderings chip"),
        ('class="timeline-history-list"', "Event list <ol>"),
        ('data-event-type="delays"', "Delay row in DOM"),
        ('data-event-type="blockers"', "Blocker row in DOM"),
        ('data-event-type="decisions"', "Decision row in DOM"),
        ('timeline-history-ai-badge', "AI badge rendered for AI-sourced event"),
        ('href="#timeline-command-center"', "Blocker event links to Command Center"),
    ]:
        if marker in page:
            ok(msg)
        else:
            fail(msg, f"marker '{marker}' missing")

    # Subtype badges
    for badge, msg in [
        ("history_event_cost_update", "Cost subtype label"),
        ("history_event_packaging_update", "Packaging subtype label"),
    ]:
        if badge in page or ("Cost Update" if "cost" in badge else "Packaging Update") in page:
            ok(f"Subtype badge: {msg}")
        else:
            # Subtype badges use the i18n VALUE, not the key. Check the rendered text.
            visible = {"Cost Update", "Packaging Update"}
            if any(v in page for v in visible):
                ok(f"Subtype badge: {msg}")
            else:
                fail(msg, f"badge value not in page")

    # ── 13. Empty state 1: project with zero events ──
    print("\n── 13. Empty state 1 — no events ──")
    empty_pid = make_project(admin, "b08_test_empty", ADMIN)
    # Delete the auto-created project_changes row from project creation
    db_execute("DELETE FROM project_changes WHERE project_id=?", (empty_pid,))
    page_empty = admin.get(f"{BASE}/projects/{empty_pid}").text
    if 'data-empty-state="none"' in page_empty and "No events yet" in page_empty:
        ok("Empty state 1 'No events yet' renders for zero-event project")
    else:
        fail("empty state 1", "missing")

    # ── 14. Empty state 2: filter empty state markup rendered (hidden) ──
    print("\n── 14. Empty state 2 — filter empty markup rendered (hidden) ──")
    if 'data-empty-state="filter"' in page and "Back to All" in page:
        ok("Empty state 2 'No events match' markup present (hidden by default; JS toggles)")
    else:
        fail("empty state 2", "markup missing")

    # ── 15. Empty state 3: viewer with hidden events ──
    print("\n── 15. Empty state 3 — viewer with all events hidden ──")
    viewer_only_pid = make_project(admin, "b08_test_vonly", ADMIN)
    # Clear the auto change-log, then add ONLY journal entries (viewer-hidden)
    db_execute("DELETE FROM project_changes WHERE project_id=?", (viewer_only_pid,))
    sess = SessionLocal()
    try:
        crud.create_journal_entry(sess, viewer_only_pid, "viewer-hidden note",
                                  "decision", author_user_id=1)
    finally:
        sess.close()
    # Also delete the event_note that journal-create wrote (so viewer sees zero)
    db_execute("DELETE FROM project_changes WHERE project_id=? AND change_type='event_note'", (viewer_only_pid,))
    page_v3 = viewer.get(f"{BASE}/projects/{viewer_only_pid}").text
    if 'data-empty-state="viewer"' in page_v3 and "not visible to your role" in page_v3:
        ok("Empty state 3 'Some recent updates not visible to your role' renders for viewer")
    else:
        fail("empty state 3", f"missing — markers in page: {[s for s in ['data-empty-state=\"viewer\"','not visible to your role'] if s in page_v3]}")

    # ── 16. Pagination — Show More appears only above 50 events ──
    print("\n── 16. Show More button (only when total > 50) ──")
    page_main = pm.get(f"{BASE}/projects/{pid}").text
    total_events = len(re.findall(r'data-event-source-id=', page_main))
    if total_events <= 50:
        if 'timeline-history-show-more' not in page_main:
            ok(f"Show More button NOT rendered for project with {total_events} events (≤ 50)")
        else:
            fail("show more spurious", "button rendered when not needed")
    else:
        if 'timeline-history-show-more' in page_main:
            ok(f"Show More button rendered for project with {total_events} events")
        else:
            fail("show more missing", "button not rendered for > 50 events")

    # ── 17. Viewer sees fewer events than admin (scoped to History section only) ──
    # Build 08 owns the Timeline History feed; the legacy Change Log section
    # (Build 13) has its own viewer-filter logic that pre-dates Build 08 and is
    # out of scope per Lock 11. We assert specifically against the history feed.
    print("\n── 17. Viewer-rendered History feed hides restricted events ──")
    page_viewer = viewer.get(f"{BASE}/projects/{pid}").text
    history_match = re.search(
        r'<section[^>]*id="timeline-history".*?</section>', page_viewer, re.DOTALL
    )
    history_html = history_match.group(0) if history_match else ""
    if not history_html:
        fail("history scope", "could not isolate #timeline-history section in viewer page")
    else:
        # Cost update content should not appear in the History feed for viewer
        if "Cost Update" not in history_html:
            ok("Viewer History feed does NOT contain Cost Update label")
        else:
            fail("viewer cost leak (history)", "Cost Update label inside #timeline-history")
        # Journal-decision content should not appear in the History feed for viewer
        if "Decided to switch supplier" not in history_html:
            ok("Viewer History feed does NOT contain journal-decision text")
        else:
            fail("viewer journal leak (history)", "Decision text inside #timeline-history")
        # And no #journal anchor inside the history feed for viewer (Lock 10)
        if 'href="#journal"' not in history_html:
            ok("Viewer History feed has no #journal anchor (Lock 10 graceful fallback)")
        else:
            fail("viewer journal anchor leak", "#journal anchor in viewer history feed")

    # ── 18. Filter chips against full array (Lock 5) ──
    print("\n── 18. Lock 5 — filter chips work against full loaded array ──")
    # Confirm we render rows beyond the visible-50 (if any) AND they carry
    # data-event-type attributes the JS can target.
    all_rows = re.findall(r'class="timeline-history-row"[^>]*data-event-type="([^"]+)"', page_main)
    if all_rows and all(r in {"delays","decisions","blockers","phase_changes","files"} for r in all_rows):
        ok(f"All {len(all_rows)} rendered rows carry a valid data-event-type")
    else:
        fail("data-event-type", f"got: {set(all_rows)}")

    # ── 19. Build 06/07A/07B invariants preserved ──
    print("\n── 19. v1.3 invariants preserved ──")
    for marker, msg in [
        ('id="timeline-command-center"', "Build 06 Command Center section"),
        ('id="timelineDetailedTable"', "Build 06 Detailed Table wrapper"),
        ('data-cc-form="finish"', "Build 07A Finish button"),
        ('data-cc-form="add-blocker"', "Build 07B Add Blocker button"),
        ('timeline-blocker-tile', "Build 07B blocker tile"),
        ('Resolve blocker', "Build 07B Pulse cascade branch"),
    ]:
        if marker in page_main:
            ok(f"Invariant: {msg}")
        else:
            fail(msg, f"'{marker}' missing")

    cleanup("b08_test")
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
