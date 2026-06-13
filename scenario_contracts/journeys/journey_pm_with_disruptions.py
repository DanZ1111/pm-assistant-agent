"""Medium journey — PM lifecycle with 2 real-world disruptions and 2 AI proposals.

The first journey that materializes the user's 2026-06-09 framing:

    "PM opens with a couple of ideas... pushes through phases, mixing
    manual edits with AI intake... sometimes the factory did something
    wrong so we need to add another round of prototyping... the factory
    decides it will delay/raise the price because Trump or the Chinese
    government suddenly exploded... PM decides to add one more variant
    but just a different color..."

10 steps total. If any one of:
  - normal PM actions (create_project, finish_phase),
  - mocked AI confirmation flow (ai_dispatch with confirmed=True/False),
  - real-world disruptions (factory cost rise, supplier delay,
    prototype round added, color-only variant),
breaks OR fails to compose, the journey fails at the exact step.
"""
from scenario_contracts.lib import actions, assertions, disruptions, fixtures
from scenario_contracts.lib.journey import Step

ID = "journey_pm_with_disruptions_001"
TITLE = "PM lifecycle with 2 disruptions + 2 mocked-AI proposals (10 steps)"
TAGS = ["journey", "deterministic", "ai_mocked", "disruption"]
MATURITY = "candidate"
WHY_IT_MATTERS = (
    "Atomic contracts catch unit regressions. This journey catches the "
    "integration regressions you can only see when normal PM actions, "
    "mocked AI proposals, factory cost rises, supplier delays, "
    "prototype reworks, and color-only variants all need to compose "
    "in one PM's workday. If any one of them fails to compose with "
    "the rest, this journey fails at the step that broke."
)

# Constants
DESIGN_PHASE = "Design"
ENG_REVIEW_PHASE = "Engineering Review"
MASS_PROD_PHASE = "Mass Production"
JOURNAL_TEXT = (
    "AI-extracted note: initial PM thinking — focus on grip ergonomics "
    "and 0.5mm thinner blade."
)
FACTORY_PCT_RISE = 18.0
GEO_REASON = "Trump tariff: tooling cost jumped 18%; supplier holiday adds 10d"
DELAY_DAYS = 10
SUPPLIER_REASON = "Coating supplier confirmed +10d holiday window"
PROTO_NAME = "Prototype Round 2 (rework)"
VARIANT_NAME = "Matte Black"
BLOCKER_TITLE = "Production-line maintenance window collides with launch"


def setup(db):
    pm = fixtures.create_user(db, username="alice_disrupt", role="pm",
                              display_name="Alice (Disruptions PM)")
    return {"pm": pm}


# ── Step 1: PM creates project (8 default phases auto-seed) ────────────

def do_create_project(world, db, http):
    world["project"] = actions.create_project_for_pm(
        db, name="Marine Knife (disruptions journey)",
        pm_username="alice_disrupt",
        # Seed an initial factory cost so the % rise has a baseline.
        target_factory_cost=10.00,
        target_factory_cost_text="10.00",
        target_msrp=49.99,
        target_msrp_text="49.99",
    )
    world["pid"] = world["project"].id


def check_after_create(world_db, world):
    db = world_db
    assertions.assert_row_count(
        db, "projects", expected=1,
        label="exactly one project after create",
    )
    assertions.assert_row_count(
        db, "project_phases", expected=8,
        where={"project_id": world["pid"]},
        label="8 default phases auto-seeded",
    )
    # Capture phase ids for later steps via direct snapshots.
    world["design_id"] = actions.snapshot_field(
        db, "project_phases",
        where={"project_id": world["pid"], "phase_order": 1}, field="id",
    )
    world["eng_review_id"] = actions.snapshot_field(
        db, "project_phases",
        where={"project_id": world["pid"], "phase_order": 2}, field="id",
    )
    world["mass_prod_id"] = actions.snapshot_field(
        db, "project_phases",
        where={"project_id": world["pid"], "phase_name": MASS_PROD_PHASE},
        field="id",
    )


# ── Step 2: AI proposes a journal entry (unconfirmed → confirmed) ──────

def do_ai_proposes_journal(world, db, http):
    pid = world["pid"]
    args = {"project_id": pid, "entry_text": JOURNAL_TEXT,
            "entry_type": "design_decision"}
    # Snapshot pre-state.
    world["pre_journal_count"] = actions.snapshot_table_count(
        db, "project_journal_entries", where={"project_id": pid})
    # Unconfirmed dispatch — must NOT write.
    world["ai_unconfirmed"] = actions.ai_dispatch(
        db, "create_journal_entry", args, world["pm"], confirmed=False,
    )
    world["after_unconfirmed_journal_count"] = actions.snapshot_table_count(
        db, "project_journal_entries", where={"project_id": pid})
    # Confirmed dispatch — must write.
    world["ai_confirmed"] = actions.ai_dispatch(
        db, "create_journal_entry", args, world["pm"], confirmed=True,
    )


def check_after_ai_journal(db, world):
    pid = world["pid"]
    assertions.assert_dispatch_required_confirmation(
        world["ai_unconfirmed"], "create_journal_entry",
        label="AI journal dispatch unconfirmed → confirmation_required",
    )
    assertions.assert_equal(
        world["after_unconfirmed_journal_count"], world["pre_journal_count"],
        label="unconfirmed AI did NOT write a journal entry",
    )
    assertions.assert_dispatch_succeeded(
        world["ai_confirmed"],
        label="AI journal dispatch confirmed → ok",
    )
    assertions.assert_row_count(
        db, "project_journal_entries", expected=1,
        where={"project_id": pid},
        label="one journal entry exists after confirm",
    )


# ── Step 3: Factory raises cost (geopolitical disruption) ──────────────

def do_factory_raises_cost(world, db, http):
    # Snapshot baseline cost before the disruption.
    world["pre_factory_cost"] = actions.snapshot_field(
        db, "projects", where={"id": world["pid"]},
        field="target_factory_cost",
    )
    disruptions.factory_raises_cost_by_pct(
        db, project_id=world["pid"], pct=FACTORY_PCT_RISE,
        reason=GEO_REASON,
    )
    world["post_factory_cost"] = actions.snapshot_field(
        db, "projects", where={"id": world["pid"]},
        field="target_factory_cost",
    )


def check_after_factory_rise(db, world):
    # Baseline cost was 10.00; 18% rise = 11.80.
    assertions.assert_equal(
        round(float(world["pre_factory_cost"]), 2), 10.00,
        label="baseline target_factory_cost was 10.00",
    )
    assertions.assert_equal(
        round(float(world["post_factory_cost"]), 2), 11.80,
        label="target_factory_cost rose to 11.80 (18% of 10.00)",
    )


# ── Step 4: PM finishes Design ─────────────────────────────────────────

def do_finish_design(world, db, http):
    actions.finish_phase(db, phase_id=world["design_id"],
                         user_id=world["pm"].id)


def check_after_finish_design(db, world):
    assertions.assert_phase_field(
        db, world["design_id"], field="status", expected="done",
        label="Design done after finish",
    )
    assertions.assert_phase_field(
        db, world["eng_review_id"], field="status", expected="in_progress",
        label="Engineering Review auto-advanced to in_progress",
    )


# ── Step 5: AI proposes Engineering Review delay (+10 days) ────────────

def do_ai_proposes_delay(world, db, http):
    # Read current planned_end_date to compute the AI's proposed date.
    current = actions.snapshot_field(
        db, "project_phases", where={"id": world["eng_review_id"]},
        field="planned_end_date",
    )
    from datetime import date as _date, timedelta as _td
    if current:
        base = _date.fromisoformat(current) if isinstance(current, str) else current
    else:
        base = _date.today()
    proposed = base + _td(days=DELAY_DAYS)
    world["proposed_eng_end"] = proposed.isoformat()
    args = {
        "project_id": world["pid"],
        "phase_id": world["eng_review_id"],
        "planned_end_date": proposed.isoformat(),
        "reason": SUPPLIER_REASON,
    }
    world["ai_delay_unconfirmed"] = actions.ai_dispatch(
        db, "adjust_phase_plan", args, world["pm"], confirmed=False,
    )
    world["ai_delay_confirmed"] = actions.ai_dispatch(
        db, "adjust_phase_plan", args, world["pm"], confirmed=True,
    )


def check_after_ai_delay(db, world):
    assertions.assert_dispatch_required_confirmation(
        world["ai_delay_unconfirmed"], "adjust_phase_plan",
        label="AI delay unconfirmed → confirmation_required",
    )
    assertions.assert_dispatch_succeeded(
        world["ai_delay_confirmed"],
        label="AI delay confirmed → ok",
    )
    assertions.assert_phase_field(
        db, world["eng_review_id"], field="planned_end_date",
        expected=world["proposed_eng_end"],
        label="Engineering Review planned_end_date moved to proposed date",
    )
    assertions.assert_phase_plan_change_recorded(
        db, world["eng_review_id"], reason_needle=SUPPLIER_REASON,
        label="phase_plan_changes row records the supplier reason",
    )


# ── Step 6: Prototype Round 2 inserted (disruption) ───────────────────

def do_prototype_round_added(world, db, http):
    world["pre_phase_count"] = actions.snapshot_table_count(
        db, "project_phases", where={"project_id": world["pid"]})
    disruptions.prototype_round_added(
        db, project_id=world["pid"], name=PROTO_NAME, duration_days=14,
    )
    world["post_phase_count"] = actions.snapshot_table_count(
        db, "project_phases", where={"project_id": world["pid"]})


def check_after_prototype(db, world):
    assertions.assert_equal(
        world["post_phase_count"], world["pre_phase_count"] + 1,
        label="phase count grew by 1 after prototype round added",
    )
    # The new phase exists with the expected name + phase_type.
    assertions.assert_row_count(
        db, "project_phases", expected=1,
        where={"project_id": world["pid"], "phase_name": PROTO_NAME},
        label=f"Prototype Round 2 phase exists with name {PROTO_NAME!r}",
    )


# ── Step 7: PM finishes Engineering Review ────────────────────────────

def do_finish_eng_review(world, db, http):
    actions.finish_phase(db, phase_id=world["eng_review_id"],
                         user_id=world["pm"].id)


def check_after_finish_eng_review(db, world):
    assertions.assert_phase_field(
        db, world["eng_review_id"], field="status", expected="done",
        label="Engineering Review done after finish",
    )


# ── Step 8: Color-only variant added (sanity: project costs unchanged) ─

def do_color_only_variant(world, db, http):
    world["pre_project_cost"] = actions.snapshot_field(
        db, "projects", where={"id": world["pid"]},
        field="target_factory_cost",
    )
    world["pre_project_msrp"] = actions.snapshot_field(
        db, "projects", where={"id": world["pid"]},
        field="target_msrp",
    )
    variant = disruptions.variant_color_only(
        db, project_id=world["pid"], variant_name=VARIANT_NAME,
    )
    world["variant_id"] = variant.id
    world["post_project_cost"] = actions.snapshot_field(
        db, "projects", where={"id": world["pid"]},
        field="target_factory_cost",
    )
    world["post_project_msrp"] = actions.snapshot_field(
        db, "projects", where={"id": world["pid"]},
        field="target_msrp",
    )


def check_after_color_variant(db, world):
    assertions.assert_row_count(
        db, "project_variants", expected=1,
        where={"project_id": world["pid"]},
        label="exactly one variant after color-only add",
    )
    assertions.assert_db_field(
        db, "project_variants", where={"id": world["variant_id"]},
        field="variant_name", expected=VARIANT_NAME,
        label="variant has the expected name",
    )
    # The load-bearing assertion: project costs UNCHANGED.
    assertions.assert_equal(
        world["post_project_cost"], world["pre_project_cost"],
        label="project target_factory_cost unchanged by variant add",
    )
    assertions.assert_equal(
        world["post_project_msrp"], world["pre_project_msrp"],
        label="project target_msrp unchanged by variant add",
    )


# ── Step 9: AI proposes a blocker on Mass Production ───────────────────

def do_ai_proposes_blocker(world, db, http):
    args = {
        "project_id": world["pid"],
        "title": BLOCKER_TITLE,
        "description": "Maintenance window overlaps Mass Production start",
        "severity": "high",
        "phase_id": world["mass_prod_id"],
    }
    world["ai_blocker_unconfirmed"] = actions.ai_dispatch(
        db, "create_blocker", args, world["pm"], confirmed=False,
    )
    world["ai_blocker_confirmed"] = actions.ai_dispatch(
        db, "create_blocker", args, world["pm"], confirmed=True,
    )


def check_after_ai_blocker(db, world):
    assertions.assert_dispatch_required_confirmation(
        world["ai_blocker_unconfirmed"], "create_blocker",
        label="AI blocker unconfirmed → confirmation_required",
    )
    assertions.assert_dispatch_succeeded(
        world["ai_blocker_confirmed"],
        label="AI blocker confirmed → ok",
    )
    assertions.assert_active_blocker_count(
        db, world["pid"], expected=1,
        label="one active blocker after AI confirm",
    )


# ── Step 10: Final state snapshot — cumulative integration ────────────

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


def check_after_final_snapshot(db, world):
    assertions.assert_equal(
        world["final_project_count"], 1,
        label="exactly one project at journey end",
    )
    assertions.assert_equal(
        world["final_phase_count"], 9,
        label="9 phases (8 default + 1 rework prototype)",
    )
    assertions.assert_equal(
        world["final_variant_count"], 1,
        label="1 variant (the color-only one)",
    )
    assertions.assert_equal(
        world["final_active_blocker_count"], 1,
        label="1 active blocker (from AI proposal)",
    )
    assertions.assert_equal(
        world["final_journal_count"], 1,
        label="1 journal entry (from AI proposal)",
    )
    # Cumulative change-log count grows with every mutation; not pinning
    # an exact number (defensive against future write_change additions),
    # but it must be at least 8 across the journey's mutation steps.
    assertions.assert_equal(
        world["final_change_count"] >= 8, True,
        label="cumulative project_changes count >= 8",
    )


# ── Journey definition ────────────────────────────────────────────────

STEPS = [
    Step("PM creates project (8 default phases auto-seed)",
         do_create_project, check_after_create),
    Step("AI proposes journal entry — unconfirmed then confirmed",
         do_ai_proposes_journal, check_after_ai_journal),
    Step("Factory raises target_factory_cost by 18% (geopolitical)",
         do_factory_raises_cost, check_after_factory_rise),
    Step("PM finishes Design — Engineering Review auto-advances",
         do_finish_design, check_after_finish_design),
    Step("AI proposes Engineering Review delay (supplier +10 days)",
         do_ai_proposes_delay, check_after_ai_delay),
    Step("Prototype Round 2 added mid-stream (rework disruption)",
         do_prototype_round_added, check_after_prototype),
    Step("PM finishes Engineering Review",
         do_finish_eng_review, check_after_finish_eng_review),
    Step("Color-only variant added — project costs UNCHANGED",
         do_color_only_variant, check_after_color_variant),
    Step("AI proposes blocker on Mass Production — confirmed",
         do_ai_proposes_blocker, check_after_ai_blocker),
    Step("Final state snapshot — cumulative integration",
         do_final_snapshot, check_after_final_snapshot),
]
