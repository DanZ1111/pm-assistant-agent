"""PM-facing assertions for Acceptance Journey scenarios.

The discipline of QA-11:

    Existing scenarios test DB truth. PM Acceptance Journeys test
    THREE more kinds of truth on top of that:

    - UI truth         (does what the PM sees match the DB?)
    - History truth    (can the PM reconstruct WHY the state changed?)
    - PM comprehension (could the PM look at the page and know what to do next?)

Each assertion here uses **stable `data-*` attributes or load-bearing
semantic classes only**. No `text=...` matches, no i18n-fragile
selectors, no `:nth-child` position assertions. When a stable selector
isn't available, the assertion is NOT in this file — see
UI_TESTABILITY_GAPS.md for the catalog of what's still missing and the
proposed app/* patches.

All assertions raise `AssertionFailure` (from `assertions.py`) on
mismatch so the journey runner reports them with the same
expected/actual structure as DB assertions.

Per User lock 9: every load-bearing assertion here must catch a bug
that DB-only assertions would miss. If a check can be done from the DB
alone, it belongs in `assertions.py`, not here.
"""
from __future__ import annotations

from scenario_contracts.lib.assertions import AssertionFailure
from scenario_contracts.lib.actions import open_url


# ── Helpers ─────────────────────────────────────────────────────────────


def _text(page, selector):
    """Read trimmed text content of the first element matching `selector`.
    Returns None if no element matches (lets callers distinguish "absent"
    from "empty string")."""
    locator = page.locator(selector).first
    try:
        if locator.count() == 0:
            return None
        raw = locator.text_content()
        return raw.strip() if raw else ""
    except Exception:
        return None


def _count(page, selector):
    """Count elements matching `selector`."""
    try:
        return page.locator(selector).count()
    except Exception:
        return 0


# ── Timeline Command Center (the PM-comprehension load-bearer) ──────────


def assert_command_center_current_phase(page, project_id, expected_phase_name,
                                         label=None):
    """Open `/projects/{id}#timeline` and verify the Command Center
    "Current phase" tile shows the expected phase name.

    Selectors:
      - `.timeline-tile.timeline-tile-current .timeline-tile-primary`
        is the PM-visible primary value of the current-phase tile.

    This is the PM-comprehension check: a PM scanning the page should
    immediately see which phase is in progress. If the tile is empty,
    stale, or shows the wrong phase, the PM is misled.
    """
    open_url(page, f"/projects/{project_id}")
    actual = _text(
        page,
        ".timeline-tile.timeline-tile-current .timeline-tile-primary",
    )
    if actual != expected_phase_name:
        raise AssertionFailure(
            label or "Command Center current phase",
            expected_phase_name,
            actual,
        )


def assert_command_center_next_action(page, project_id, expected_substring,
                                       label=None):
    """Verify the "Next action" tile's primary text contains the
    expected substring.

    Selectors:
      - `.timeline-tile.timeline-tile-next-action .timeline-tile-primary`

    Substring match (not exact) because the next-action copy is
    i18n-templated with phase name; the substring asserts the
    LOAD-BEARING fact (it mentions moving the phase forward) without
    locking the exact translation.
    """
    open_url(page, f"/projects/{project_id}")
    actual = _text(
        page,
        ".timeline-tile.timeline-tile-next-action .timeline-tile-primary",
    )
    if actual is None or expected_substring not in actual:
        raise AssertionFailure(
            label or "Command Center next action",
            f"text containing {expected_substring!r}",
            actual,
        )


def assert_command_center_health_band(page, project_id, expected_band,
                                       label=None):
    """Verify the health-band element with the expected class is present
    in the current-phase tile.

    Selectors:
      - `.timeline-tile.timeline-tile-current .timeline-health-{band}`
        where {band} ∈ {on_track, at_risk, delayed, not_scheduled}.
    """
    open_url(page, f"/projects/{project_id}")
    selector = (
        f".timeline-tile.timeline-tile-current "
        f".timeline-health-{expected_band}"
    )
    if _count(page, selector) == 0:
        raise AssertionFailure(
            label or "Command Center health band",
            f"element matching {selector}",
            "absent",
        )


def assert_active_blocker_count_on_phase_strip(page, project_id, expected,
                                                 label=None):
    """Count phases on the strip with `data-blocker="active"`.

    Selectors:
      - `.timeline-phase-block[data-blocker="active"]`

    This is the PM-comprehension check that the phase strip visually
    flags blocked phases (the dot + class). A blocker that exists in
    the DB but doesn't show on the strip is a regression class the
    existing `ai_proposes_blocker` contract doesn't catch.
    """
    open_url(page, f"/projects/{project_id}")
    actual = _count(page, '.timeline-phase-block[data-blocker="active"]')
    if actual != expected:
        raise AssertionFailure(
            label or "active-blocker count on phase strip",
            expected,
            actual,
        )


# ── Timeline History (the audit-truth load-bearer) ──────────────────────


def assert_history_row_with_type_contains(page, project_id, event_type,
                                            needle, label=None):
    """Find a Timeline History row of the given event_type whose
    visible title OR body text contains `needle`.

    Selectors:
      - `.timeline-history-row[data-event-type="{event_type}"]`
        with descendant `.timeline-history-title` and `.timeline-history-body`.

    `event_type` ∈ {delays, decisions, blockers, phase_changes, files, ...}.

    This catches the "history is missing the WHY" class of bug — the
    DB row exists (the existing contract scenarios assert that), but
    the rendered Timeline History doesn't explain it to the PM.
    """
    open_url(page, f"/projects/{project_id}")
    rows = page.locator(
        f'.timeline-history-row[data-event-type="{event_type}"]'
    )
    count = rows.count()
    if count == 0:
        raise AssertionFailure(
            label or f"timeline-history row with type={event_type}",
            "at least one row",
            "none",
        )
    for i in range(count):
        row = rows.nth(i)
        title = ""
        body = ""
        try:
            title_loc = row.locator(".timeline-history-title").first
            if title_loc.count() > 0:
                title = (title_loc.text_content() or "").strip()
        except Exception:
            pass
        try:
            body_loc = row.locator(".timeline-history-body").first
            if body_loc.count() > 0:
                body = (body_loc.text_content() or "").strip()
        except Exception:
            pass
        if needle in title or needle in body:
            return
    raise AssertionFailure(
        label or f"timeline-history {event_type} row containing {needle!r}",
        f"a row of type={event_type} mentions {needle!r}",
        f"{count} rows; none mention it",
    )


# ── Variant section (cross-section consistency load-bearer) ─────────────


def assert_variant_card_present(page, project_id, variant_id, label=None):
    """Verify the variant card with the given id is rendered.

    Selectors:
      - `#variant-{variant_id}`

    Stable because the template uses `id="variant-{{ v.id }}"`.
    """
    open_url(page, f"/projects/{project_id}")
    if _count(page, f"#variant-{variant_id}") == 0:
        raise AssertionFailure(
            label or f"variant card #{variant_id} present",
            "rendered",
            "absent",
        )


def assert_project_findable_on_index_and_detail(page, project_id,
                                                 expected_name, label=None):
    """Cross-page consistency check (v1): the project appears in both
    /projects index AND /projects/{id} detail with the same name.

    Selectors:
      - On `/projects` index: `a.project-card[href="/projects/{project_id}"]`
        is the load-bearing element each project card uses.
      - On `/projects/{id}` detail: page text contains the name.

    This is the WEAK form of cross-page consistency — it doesn't
    check current_stage because freshly-created projects have
    current_stage=None (no phase is in_progress yet). A STRONGER
    check (current_stage matches across pages) requires a later step
    in the journey that finishes a phase first, which a follow-up
    acceptance journey can add.
    """
    # 1. /projects index — verify the card exists and contains the name.
    open_url(page, "/projects")
    card = page.locator(
        f'a.project-card[href="/projects/{project_id}"]').first
    if card.count() == 0:
        raise AssertionFailure(
            label or f"project {project_id} card on /projects",
            f"<a.project-card href=/projects/{project_id}>",
            "absent",
        )
    card_text = (card.text_content() or "").strip()
    if expected_name not in card_text:
        raise AssertionFailure(
            label or f"project {project_id} card shows name",
            f"card text containing {expected_name!r}",
            card_text[:200],
        )

    # 2. /projects/{id} detail — verify the page contains the name.
    open_url(page, f"/projects/{project_id}")
    if expected_name not in page.content():
        raise AssertionFailure(
            label or "/projects/{id} shows the name",
            f"page HTML containing {expected_name!r}",
            "absent",
        )


def assert_overview_and_list_stage_consistent(page, project_id,
                                                 expected_stage, label=None):
    """Cross-page consistency check (v2 — requires a phase to be
    in_progress): the project's current stage shown on `/projects`
    index MUST match the stage shown on `/projects/{id}` Overview.

    Selectors:
      - On `/projects` index card: `.stage-pill` inside the card with
        `href="/projects/{project_id}"`.
      - On `/projects/{id}`: `.pulse-stage` text.

    Both classes are load-bearing. Reads text content normalized of
    whitespace and compares both against `expected_stage`. ONLY
    meaningful after a phase has been started — fresh projects don't
    show a stage pill.
    """
    # 1. Read from /projects index card.
    open_url(page, "/projects")
    card = page.locator(
        f'a.project-card[href="/projects/{project_id}"]').first
    if card.count() == 0:
        raise AssertionFailure(
            label or f"project {project_id} card on /projects",
            "rendered",
            "absent",
        )
    pill = card.locator(".stage-pill, .stage-pill-sm").first
    list_stage = (pill.text_content() or "").strip() if pill.count() > 0 else None

    # 2. Read from /projects/{id} Overview pulse.
    open_url(page, f"/projects/{project_id}")
    detail_stage = _text(page, ".pulse-stage")

    if list_stage != expected_stage:
        raise AssertionFailure(
            label or "/projects index stage pill",
            expected_stage,
            list_stage,
        )
    if detail_stage != expected_stage:
        raise AssertionFailure(
            label or "/projects/{id} pulse-stage",
            expected_stage,
            detail_stage,
        )


# ── Viewer privacy (must hit the actual rendered page) ──────────────────


def assert_viewer_cannot_see_variant_costs(page, project_id, label=None):
    """Open the project page (assumes the calling page is already logged
    in as a viewer) and assert no variant cost line is rendered.

    Selectors:
      - `.variant-command-cost-line` is wrapped in
        `{% if can_view_costs %}` in variants_section.html, so the
        element only exists for admin/PM. A viewer should see zero.

    This is the load-bearing viewer-privacy check: the existing
    `viewer_permission_boundaries` contract checks the permission
    helper returns False; this checks the rendered HTML actually
    hides the field.

    CAVEAT: the caller is responsible for the viewer login. This
    assertion does NOT switch context.
    """
    open_url(page, f"/projects/{project_id}")
    count = _count(page, ".variant-command-cost-line")
    if count != 0:
        raise AssertionFailure(
            label or "viewer cannot see variant cost lines",
            "0 .variant-command-cost-line elements",
            f"{count} found",
        )
