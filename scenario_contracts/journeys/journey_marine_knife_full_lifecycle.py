"""Marathon journey — full Marine Knife PM lifecycle (20 steps).

The end-state integration proof for the QA system itself. Materializes
the user's 2026-06-09 framing:

    "ideas → link → create plan → sandbox template → push through
    phases mixing manual edits + AI intake → factory mistakes (extra
    prototype round) → factory delays/cost rises (Trump tariff,
    Chinese government) → AI PM changes plan in different ways →
    add a color-only variant late"

If the QA system's internal layers stop composing — disruptions
with AI dispatch, sandbox apply with finish_phase, color-only
variant with mid-stream cost rise — this journey fails at the exact
composition step that broke.
"""
from scenario_contracts.lib import actions, assertions, disruptions, fixtures
from scenario_contracts.lib.journey import Step

ID = "journey_marine_knife_full_lifecycle_001"
TITLE = "Marine Knife full PM lifecycle — 20 steps with all 5 disruption types"
TAGS = [
    "journey", "deterministic", "ai_mocked",
    "disruption", "marathon", "marine_knife",
]
MATURITY = "candidate"
WHY_IT_MATTERS = (
    "Atomic contracts catch unit regressions. The medium journey "
    "(QA-08) catches small integration regressions. This marathon "
    "catches the regressions you only see when the FULL PM workday "
    "composes — ideas → sandbox apply → 6+ phases → all 5 disruption "
    "types → multiple AI proposals → 2 variants → blocker lifecycle "
    "→ cumulative final state. If any pair of features fails to "
    "compose, the runner pinpoints the exact step."
)

# Constants
IDEA_1_NAME = "Ambidextrous thumb stud"
IDEA_2_NAME = "Ergonomic G10 grip with finger groove"
TEMPLATE_KEY = "simple_oem_knife"
INITIAL_FACTORY_COST = 10.00
INITIAL_MSRP = 49.99
PCT_RISE = 18.0
PCT_RISE_FACTOR = 1.18
SUPPLIER_DELAY_DAYS = 12
SUPPLIER_REASON = "Coating supplier holiday +12 days"
GEO_PCT = 8.0
GEO_FACTOR = 1.08
GEO_DELAY = 5
GEO_REASON = "Chinese government holiday + tariff bump"
PROTO_NAME = "Prototype Round 2 (rework)"
VARIANT_1 = "Matte Black"
VARIANT_2 = "Forest Green"
JOURNAL_TEXT_1 = "AI note: coating delay narrows margin on the launch SKU."
JOURNAL_TEXT_2 = "AI note: variants signed off for Q4 catalog."
BLOCKER_TITLE = "Mass Production line maintenance collides with launch"


def setup(db):
    pm = fixtures.create_user(
        db, username="alice_marathon", role="pm",
        display_name="Alice (Marathon PM)",
    )
    return {"pm": pm}


# ── Step 1: PM creates 2 ideas ─────────────────────────────────────────

def do_create_ideas(world, db, http):
    idea_1 = actions.create_idea(
        db,
        data={
            "name": IDEA_1_NAME,
            "description": "Switch-based opening on both sides for left/right-handed users.",
            "idea_type": "feature",
            "source": "internal",
        },
        contributor_user_id=world["pm"].id,
    )
    idea_2 = actions.create_idea(
        db,
        data={
            "name": IDEA_2_NAME,
            "description": "G10 handle scale with a single finger groove for index control.",
            "idea_type": "feature",
            "source": "internal",
        },
        contributor_user_id=world["pm"].id,
    )
    world["idea_1_id"] = idea_1.id
    world["idea_2_id"] = idea_2.id


def check_after_create_ideas(db, world):
    assertions.assert_row_count(
        db, "ideas", expected=2,
        label="two ideas created",
    )
    assertions.assert_db_field(
        db, "ideas", where={"id": world["idea_1_id"]},
        field="name", expected=IDEA_1_NAME,
        label="idea 1 name persisted",
    )


# ── Step 2: PM creates Marine Knife project ────────────────────────────

def do_create_project(world, db, http):
    world["project"] = actions.create_project_for_pm(
        db,
        name="Marine Knife (full lifecycle)",
        pm_username="alice_marathon",
        target_factory_cost=INITIAL_FACTORY_COST,
        target_factory_cost_text=str(INITIAL_FACTORY_COST),
        target_msrp=INITIAL_MSRP,
        target_msrp_text=str(INITIAL_MSRP),
    )
    world["pid"] = world["project"].id


def check_after_create_project(db, world):
    assertions.assert_row_count(
        db, "projects", expected=1,
        label="exactly one project after create",
    )
    assertions.assert_row_count(
        db, "project_phases", expected=8,
        where={"project_id": world["pid"]},
        label="8 default phases auto-seeded",
    )


# ── Step 3: PM links both ideas to the project ─────────────────────────

def do_link_ideas(world, db, http):
    actions.link_idea_to_project(
        db, project_id=world["pid"], idea_id=world["idea_1_id"],
        user_id=world["pm"].id,
        note="Top-priority opening mechanism",
    )
    actions.link_idea_to_project(
        db, project_id=world["pid"], idea_id=world["idea_2_id"],
        user_id=world["pm"].id,
        note="Grip ergonomics line item",
    )


def check_after_link_ideas(db, world):
    assertions.assert_row_count(
        db, "project_ideas", expected=2,
        where={"project_id": world["pid"]},
        label="two ideas linked to this project",
    )


# ── Step 4: PM creates a sandbox from simple_oem_knife template ────────

def do_create_sandbox(world, db, http):
    sandbox = actions.create_sandbox_from_template(
        db, project_id=world["pid"], template_key=TEMPLATE_KEY,
        user_id=world["pm"].id, user_role=world["pm"].role,
    )
    world["sandbox_id"] = sandbox.id
    world["sandbox_node_count"] = actions.snapshot_table_count(
        db, "planning_sandbox_nodes",
        where={"sandbox_id": sandbox.id},
    )


def check_after_create_sandbox(db, world):
    assertions.assert_row_count(
        db, "planning_sandboxes", expected=1,
        where={"project_id": world["pid"], "status": "draft"},
        label="one draft sandbox exists for this project",
    )
    # The template was non-empty.
    assertions.assert_equal(
        world["sandbox_node_count"] > 0, True,
        label=f"simple_oem_knife template seeded > 0 sandbox nodes",
    )


# ── Step 5: PM applies sandbox → replaces auto-seeded phases ───────────

def do_apply_sandbox(world, db, http):
    from datetime import date
    world["pre_apply_phase_count"] = actions.snapshot_table_count(
        db, "project_phases", where={"project_id": world["pid"]})
    world["pre_apply_event_count"] = actions.snapshot_table_count(
        db, "planning_apply_events", where={"project_id": world["pid"]})
    apply_event = actions.apply_sandbox(
        db, project_id=world["pid"], sandbox_id=world["sandbox_id"],
        apply_start_date=date(2026, 7, 1), user_id=world["pm"].id,
    )
    world["apply_event_id"] = apply_event.id
    world["post_apply_phase_count"] = actions.snapshot_table_count(
        db, "project_phases", where={"project_id": world["pid"]})


def check_after_apply(db, world):
    # Cross-checks the QA-02 sandbox_apply_invariant contract: pre-apply
    # had auto-seeded phases (8); post-apply matches sandbox node count.
    assertions.assert_equal(
        world["pre_apply_phase_count"], 8,
        label="pre-apply phases = 8 (auto-seeded defaults)",
    )
    assertions.assert_equal(
        world["pre_apply_event_count"], 0,
        label="pre-apply: no planning_apply_events row yet",
    )
    assertions.assert_equal(
        world["post_apply_phase_count"], world["sandbox_node_count"],
        label="post-apply phases = sandbox node count",
    )
    assertions.assert_row_count(
        db, "planning_apply_events", expected=1,
        where={"project_id": world["pid"]},
        label="one planning_apply_events row after apply",
    )
    assertions.assert_row_count(
        db, "project_changes", expected=1,
        where={"project_id": world["pid"], "change_type": "plan_applied"},
        label="one plan_applied change-log row after apply",
    )


# ── Step 6: PM finishes first applied phase ───────────────────────────

def do_finish_phase_1(world, db, http):
    # Capture all post-apply phase ids ordered by phase_order.
    from sqlalchemy import text
    rows = db.execute(
        text("""
            SELECT id, phase_name, phase_order
            FROM project_phases
            WHERE project_id = :pid
            ORDER BY phase_order
        """),
        {"pid": world["pid"]},
    ).fetchall()
    world["phases_in_order"] = [(r[0], r[1], r[2]) for r in rows]
    first_id = world["phases_in_order"][0][0]
    world["phase_1_id"] = first_id
    actions.finish_phase(db, phase_id=first_id, user_id=world["pm"].id)


def check_after_finish_phase_1(db, world):
    assertions.assert_phase_field(
        db, world["phase_1_id"], field="status", expected="done",
        label="phase 1 done after finish",
    )


# ── Step 7: Factory raises cost 18% (Trump-tariff disruption) ─────────

def do_factory_rise(world, db, http):
    world["pre_factory_cost"] = actions.snapshot_field(
        db, "projects", where={"id": world["pid"]},
        field="target_factory_cost",
    )
    disruptions.factory_raises_cost_by_pct(
        db, project_id=world["pid"], pct=PCT_RISE,
        reason="Trump tariff: tooling cost jumped 18%",
    )
    world["post_factory_cost"] = actions.snapshot_field(
        db, "projects", where={"id": world["pid"]},
        field="target_factory_cost",
    )


def check_after_factory_rise(db, world):
    expected = round(INITIAL_FACTORY_COST * PCT_RISE_FACTOR, 2)
    assertions.assert_equal(
        round(float(world["post_factory_cost"]), 2), expected,
        label=f"target_factory_cost rose to {expected}",
    )


# ── Step 8: PM finishes second phase ───────────────────────────────────

def do_finish_phase_2(world, db, http):
    second_id = world["phases_in_order"][1][0]
    world["phase_2_id"] = second_id
    actions.finish_phase(db, phase_id=second_id, user_id=world["pm"].id)


def check_after_finish_phase_2(db, world):
    assertions.assert_phase_field(
        db, world["phase_2_id"], field="status", expected="done",
        label="phase 2 done after finish",
    )


# ── Step 9: Supplier delays third phase (+12 days) ─────────────────────

def do_supplier_delay(world, db, http):
    third_id = world["phases_in_order"][2][0]
    world["phase_3_id"] = third_id
    world["pre_delay_plan_change_count"] = actions.snapshot_table_count(
        db, "phase_plan_changes")
    disruptions.supplier_delays_phase(
        db, phase_id=third_id, days=SUPPLIER_DELAY_DAYS,
        reason=SUPPLIER_REASON,
    )
    world["post_delay_plan_change_count"] = actions.snapshot_table_count(
        db, "phase_plan_changes")


def check_after_supplier_delay(db, world):
    assertions.assert_equal(
        world["post_delay_plan_change_count"]
        - world["pre_delay_plan_change_count"], 1,
        label="exactly one phase_plan_changes row after supplier delay",
    )
    assertions.assert_phase_plan_change_recorded(
        db, world["phase_3_id"], reason_needle=SUPPLIER_REASON,
        label="phase_plan_changes records the supplier reason",
    )


# ── Step 10: AI proposes journal entry about delay → confirmed ─────────

def do_ai_journal_1(world, db, http):
    args = {
        "project_id": world["pid"], "entry_text": JOURNAL_TEXT_1,
        "entry_type": "design_decision",
    }
    world["ai_j1_unconfirmed"] = actions.ai_dispatch(
        db, "create_journal_entry", args, world["pm"], confirmed=False,
    )
    world["pre_journal_count"] = actions.snapshot_table_count(
        db, "project_journal_entries", where={"project_id": world["pid"]})
    world["ai_j1_confirmed"] = actions.ai_dispatch(
        db, "create_journal_entry", args, world["pm"], confirmed=True,
    )
    world["after_journal_count_1"] = actions.snapshot_table_count(
        db, "project_journal_entries", where={"project_id": world["pid"]})


def check_after_ai_journal_1(db, world):
    assertions.assert_dispatch_required_confirmation(
        world["ai_j1_unconfirmed"], "create_journal_entry",
        label="AI journal #1 unconfirmed → confirmation_required",
    )
    assertions.assert_dispatch_succeeded(
        world["ai_j1_confirmed"],
        label="AI journal #1 confirmed → ok",
    )
    assertions.assert_equal(
        world["after_journal_count_1"], world["pre_journal_count"] + 1,
        label="journal count grew by 1 after AI confirm",
    )


# ── Step 11: PM finishes third phase ───────────────────────────────────

def do_finish_phase_3(world, db, http):
    actions.finish_phase(db, phase_id=world["phase_3_id"],
                         user_id=world["pm"].id)


def check_after_finish_phase_3(db, world):
    assertions.assert_phase_field(
        db, world["phase_3_id"], field="status", expected="done",
        label="phase 3 done after finish",
    )


# ── Step 12: Prototype Round 2 added (factory-mistake disruption) ──────

def do_prototype_round_2(world, db, http):
    world["pre_proto_phase_count"] = actions.snapshot_table_count(
        db, "project_phases", where={"project_id": world["pid"]})
    disruptions.prototype_round_added(
        db, project_id=world["pid"], name=PROTO_NAME, duration_days=14,
    )
    world["post_proto_phase_count"] = actions.snapshot_table_count(
        db, "project_phases", where={"project_id": world["pid"]})


def check_after_prototype_round_2(db, world):
    assertions.assert_equal(
        world["post_proto_phase_count"],
        world["pre_proto_phase_count"] + 1,
        label="phase count grew by 1 after prototype round added",
    )
    assertions.assert_row_count(
        db, "project_phases", expected=1,
        where={"project_id": world["pid"], "phase_name": PROTO_NAME},
        label=f"phase named {PROTO_NAME!r} exists",
    )


# ── Step 13: PM finishes fourth phase ──────────────────────────────────

def do_finish_phase_4(world, db, http):
    fourth_id = world["phases_in_order"][3][0]
    world["phase_4_id"] = fourth_id
    actions.finish_phase(db, phase_id=fourth_id, user_id=world["pm"].id)


def check_after_finish_phase_4(db, world):
    assertions.assert_phase_field(
        db, world["phase_4_id"], field="status", expected="done",
        label="phase 4 done after finish",
    )


# ── Step 14: Geopolitical event (composite cost rise + delay) ──────────

def do_geo_event(world, db, http):
    world["pre_geo_cost"] = actions.snapshot_field(
        db, "projects", where={"id": world["pid"]},
        field="target_factory_cost",
    )
    world["pre_geo_plan_change_count"] = actions.snapshot_table_count(
        db, "phase_plan_changes")
    # Reuse phase_3_id which was already delayed once — tests that
    # the same phase can be delayed multiple times (phase_plan_changes
    # accumulates rows).
    disruptions.geopolitical_event(
        db, project_id=world["pid"], factory_pct=GEO_PCT,
        delay_phase_id=world["phase_3_id"], delay_days=GEO_DELAY,
        reason=GEO_REASON,
    )
    world["post_geo_cost"] = actions.snapshot_field(
        db, "projects", where={"id": world["pid"]},
        field="target_factory_cost",
    )
    world["post_geo_plan_change_count"] = actions.snapshot_table_count(
        db, "phase_plan_changes")


def check_after_geo_event(db, world):
    expected = round(float(world["pre_geo_cost"]) * GEO_FACTOR, 2)
    assertions.assert_equal(
        round(float(world["post_geo_cost"]), 2), expected,
        label=f"factory_cost rose another {GEO_PCT}% to {expected}",
    )
    assertions.assert_equal(
        world["post_geo_plan_change_count"]
        - world["pre_geo_plan_change_count"], 1,
        label="one new phase_plan_changes row from geopolitical delay",
    )


# ── Step 15: PM adds first color-only variant ─────────────────────────

def do_variant_1(world, db, http):
    world["pre_variant_project_cost"] = actions.snapshot_field(
        db, "projects", where={"id": world["pid"]},
        field="target_factory_cost",
    )
    variant = disruptions.variant_color_only(
        db, project_id=world["pid"], variant_name=VARIANT_1,
    )
    world["variant_1_id"] = variant.id
    world["post_variant_project_cost"] = actions.snapshot_field(
        db, "projects", where={"id": world["pid"]},
        field="target_factory_cost",
    )


def check_after_variant_1(db, world):
    assertions.assert_row_count(
        db, "project_variants", expected=1,
        where={"project_id": world["pid"]},
        label="one variant after first color-only add",
    )
    assertions.assert_equal(
        world["post_variant_project_cost"],
        world["pre_variant_project_cost"],
        label="project target_factory_cost UNCHANGED by variant 1",
    )


# ── Step 16: AI proposes blocker on a remaining phase → confirmed ──────

def do_ai_blocker(world, db, http):
    # Pick a phase that is NOT done — phase 5 (the first remaining one).
    not_done_id = world["phases_in_order"][4][0] if len(
        world["phases_in_order"]) > 4 else world["phases_in_order"][-1][0]
    world["blocker_phase_id"] = not_done_id
    args = {
        "project_id": world["pid"], "title": BLOCKER_TITLE,
        "description": "Production line is down for maintenance during planned start week.",
        "severity": "high", "phase_id": not_done_id,
    }
    world["ai_b_unconfirmed"] = actions.ai_dispatch(
        db, "create_blocker", args, world["pm"], confirmed=False,
    )
    world["ai_b_confirmed"] = actions.ai_dispatch(
        db, "create_blocker", args, world["pm"], confirmed=True,
    )
    # Pull the blocker id from the result.
    world["blocker_id"] = world["ai_b_confirmed"].get("blocker_id")


def check_after_ai_blocker(db, world):
    assertions.assert_dispatch_required_confirmation(
        world["ai_b_unconfirmed"], "create_blocker",
        label="AI blocker unconfirmed → confirmation_required",
    )
    assertions.assert_dispatch_succeeded(
        world["ai_b_confirmed"],
        label="AI blocker confirmed → ok",
    )
    assertions.assert_active_blocker_count(
        db, world["pid"], expected=1,
        label="one active blocker after AI confirm",
    )


# ── Step 17: PM resolves the blocker ───────────────────────────────────

def do_resolve_blocker(world, db, http):
    # Snapshot blocker id from DB by title (in case AI didn't return it).
    from sqlalchemy import text
    row = db.execute(
        text("""
            SELECT id FROM project_blockers
            WHERE project_id = :pid AND title = :title
            ORDER BY id DESC LIMIT 1
        """),
        {"pid": world["pid"], "title": BLOCKER_TITLE},
    ).fetchone()
    if row:
        world["blocker_id"] = row[0]
    actions.resolve_blocker(
        db, blocker_id=world["blocker_id"], user_id=world["pm"].id,
    )


def check_after_resolve_blocker(db, world):
    assertions.assert_active_blocker_count(
        db, world["pid"], expected=0,
        label="zero active blockers after resolve",
    )
    assertions.assert_db_field(
        db, "project_blockers", where={"id": world["blocker_id"]},
        field="status", expected="resolved",
        label="blocker status is 'resolved'",
    )


# ── Step 18: AI proposes second journal entry → confirmed ──────────────

def do_ai_journal_2(world, db, http):
    args = {
        "project_id": world["pid"], "entry_text": JOURNAL_TEXT_2,
        "entry_type": "general",
    }
    world["ai_j2_confirmed"] = actions.ai_dispatch(
        db, "create_journal_entry", args, world["pm"], confirmed=True,
    )


def check_after_ai_journal_2(db, world):
    assertions.assert_dispatch_succeeded(
        world["ai_j2_confirmed"],
        label="AI journal #2 confirmed → ok",
    )
    assertions.assert_row_count(
        db, "project_journal_entries", expected=2,
        where={"project_id": world["pid"]},
        label="two journal entries after both AI confirms",
    )


# ── Step 19: PM adds second color-only variant ─────────────────────────

def do_variant_2(world, db, http):
    variant = disruptions.variant_color_only(
        db, project_id=world["pid"], variant_name=VARIANT_2,
    )
    world["variant_2_id"] = variant.id


def check_after_variant_2(db, world):
    assertions.assert_row_count(
        db, "project_variants", expected=2,
        where={"project_id": world["pid"]},
        label="two variants after second color-only add",
    )


# ── Step 20: Final state snapshot — cumulative integration ────────────

def do_final_snapshot(world, db, http):
    pid = world["pid"]
    world["final_project_count"] = actions.snapshot_table_count(
        db, "projects")
    world["final_phase_count"] = actions.snapshot_table_count(
        db, "project_phases", where={"project_id": pid})
    world["final_variant_count"] = actions.snapshot_table_count(
        db, "project_variants", where={"project_id": pid})
    world["final_active_blocker_count"] = actions.snapshot_table_count(
        db, "project_blockers",
        where={"project_id": pid, "status": "active"})
    world["final_journal_count"] = actions.snapshot_table_count(
        db, "project_journal_entries", where={"project_id": pid})
    world["final_change_count"] = actions.snapshot_table_count(
        db, "project_changes", where={"project_id": pid})
    world["final_idea_link_count"] = actions.snapshot_table_count(
        db, "project_ideas", where={"project_id": pid})
    world["final_apply_event_count"] = actions.snapshot_table_count(
        db, "planning_apply_events", where={"project_id": pid})
    world["final_applied_sandbox_count"] = actions.snapshot_table_count(
        db, "planning_sandboxes",
        where={"project_id": pid, "status": "applied"})


def check_after_final_snapshot(db, world):
    assertions.assert_equal(
        world["final_project_count"], 1,
        label="exactly one project at journey end",
    )
    # Phases: sandbox-applied count + 1 (rework prototype). Use >= bound
    # in case the simple_oem_knife template seed changes in the future.
    expected_min_phases = world["sandbox_node_count"] + 1
    assertions.assert_equal(
        world["final_phase_count"] >= expected_min_phases, True,
        label=(f"final phase count >= {expected_min_phases} "
               f"(sandbox-applied + prototype rework)"),
    )
    assertions.assert_equal(
        world["final_variant_count"], 2,
        label="two variants at journey end",
    )
    assertions.assert_equal(
        world["final_active_blocker_count"], 0,
        label="no active blockers at journey end (resolved in step 17)",
    )
    assertions.assert_equal(
        world["final_journal_count"], 2,
        label="two journal entries (steps 10 + 18)",
    )
    assertions.assert_equal(
        world["final_change_count"] >= 18, True,
        label="cumulative project_changes count >= 18 across the journey",
    )
    assertions.assert_equal(
        world["final_idea_link_count"], 2,
        label="two ideas remain linked to the project",
    )
    assertions.assert_equal(
        world["final_apply_event_count"], 1,
        label="exactly one planning_apply_events row",
    )
    assertions.assert_equal(
        world["final_applied_sandbox_count"], 1,
        label="sandbox is in 'applied' status at journey end",
    )


# ── Journey definition ────────────────────────────────────────────────

STEPS = [
    Step("PM creates 2 ideas",
         do_create_ideas, check_after_create_ideas),
    Step("PM creates Marine Knife project (8 default phases auto-seed)",
         do_create_project, check_after_create_project),
    Step("PM links both ideas to the project",
         do_link_ideas, check_after_link_ideas),
    Step("PM creates sandbox from simple_oem_knife template",
         do_create_sandbox, check_after_create_sandbox),
    Step("PM applies sandbox — replaces auto-seeded phases",
         do_apply_sandbox, check_after_apply),
    Step("PM finishes first applied phase",
         do_finish_phase_1, check_after_finish_phase_1),
    Step("Factory raises cost 18% (Trump-tariff disruption)",
         do_factory_rise, check_after_factory_rise),
    Step("PM finishes second phase",
         do_finish_phase_2, check_after_finish_phase_2),
    Step("Supplier delays third phase +12 days (disruption)",
         do_supplier_delay, check_after_supplier_delay),
    Step("AI proposes journal entry about delay — confirmed",
         do_ai_journal_1, check_after_ai_journal_1),
    Step("PM finishes third phase",
         do_finish_phase_3, check_after_finish_phase_3),
    Step("Prototype Round 2 added mid-stream (factory-mistake disruption)",
         do_prototype_round_2, check_after_prototype_round_2),
    Step("PM finishes fourth phase",
         do_finish_phase_4, check_after_finish_phase_4),
    Step("Geopolitical event — composite cost rise + phase delay",
         do_geo_event, check_after_geo_event),
    Step("PM adds first color-only variant (Matte Black)",
         do_variant_1, check_after_variant_1),
    Step("AI proposes blocker on remaining phase — confirmed",
         do_ai_blocker, check_after_ai_blocker),
    Step("PM resolves the blocker",
         do_resolve_blocker, check_after_resolve_blocker),
    Step("AI proposes second journal entry — confirmed",
         do_ai_journal_2, check_after_ai_journal_2),
    Step("PM adds second color-only variant (Forest Green)",
         do_variant_2, check_after_variant_2),
    Step("Final state snapshot — cumulative integration validation",
         do_final_snapshot, check_after_final_snapshot),
]
