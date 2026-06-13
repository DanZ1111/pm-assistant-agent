"""Composable real-world disruption helpers for journeys.

Disruptions are bundled compositions of `actions.*` that express
common "the world changed" events PMs react to:
  - factory cost rises (geopolitical, supply-chain, tooling)
  - supplier delays
  - extra prototype rounds needed
  - last-minute color-only variants
  - geopolitical events (combinations of the above)

Discipline boundary (User lock 9, widened in QA-08):
  - `run()` / `do_*()` may call `actions.*` AND `disruptions.*`
  - `check()` / `check_*()` may call only `assertions.*`
  - disruptions themselves call only `actions.*` internally
    (so the boundary contract is recursive — no raw app.* imports
    anywhere downstream)
"""
from __future__ import annotations

from datetime import date, timedelta

from scenario_contracts.lib import actions


def factory_raises_cost_by_pct(db, project_id, pct, reason):
    """Factory raises target_factory_cost by `pct` percent.

    Reads the current target_factory_cost, multiplies by (1 + pct/100),
    persists via actions.update_project, and lets the service helper
    write the audit row.

    Returns the updated Project.
    """
    current = actions.snapshot_field(
        db, "projects", where={"id": project_id},
        field="target_factory_cost",
    )
    if current is None:
        # Project never had a target_factory_cost; seed a reasonable
        # baseline so the percentage change is meaningful.
        current = 10.00
    new_cost = round(float(current) * (1.0 + pct / 100.0), 2)
    return actions.update_project(
        db,
        project_id=project_id,
        data={
            "target_factory_cost": new_cost,
            "target_factory_cost_text": str(new_cost),
        },
        changed_by="user",
        source_type="manual_edit",
    )


def supplier_delays_phase(db, phase_id, days, reason):
    """Supplier delays a phase by `days` days.

    Reads current planned_end_date, adds N days, persists via
    actions.adjust_due_date with the supplied reason. The reason lands
    in `phase_plan_changes.reason` and `project_changes.summary`.
    """
    current = actions.snapshot_field(
        db, "project_phases", where={"id": phase_id},
        field="planned_end_date",
    )
    if not current:
        # Phase had no planned_end_date yet; pick a sensible default
        # so the disruption still produces a visible date shift.
        base = date.today()
    else:
        base = date.fromisoformat(current) if isinstance(current, str) else current
    new_end = base + timedelta(days=days)
    return actions.adjust_due_date(
        db,
        phase_id=phase_id,
        new_end_date=new_end,
        reason=reason,
    )


def prototype_round_added(db, project_id, name="Prototype Round 2 (rework)",
                          duration_days=14):
    """Add an extra prototype phase to the project mid-stream.

    Uses actions.add_phase which appends at phase_order = max + 1.
    Naming reflects "we needed another round" because the factory got
    something wrong; the disruption does NOT attempt to insert the
    phase between existing phases (crud.add_phase does not support
    insertion). For journey-test purposes "phase count grew by 1"
    is sufficient.
    """
    return actions.add_phase(
        db,
        project_id=project_id,
        data={
            "phase_name": name,
            "phase_type": "prototype",
            "planned_start_date": None,
            "planned_end_date": None,
            "notes": "Added mid-stream because the factory's previous prototype missed spec.",
        },
    )


def variant_color_only(db, project_id, variant_name="Matte Black"):
    """Add a color-only variant — same costs as the project, only the
    name (and implicitly the color in the name) differs.

    This sanity-locks the variant_pricing_isolation contract from
    inside a journey: if a future commit lets variant.target_*_cost
    leak onto the parent project, the journey's later "project costs
    unchanged" assertion catches it.
    """
    return actions.create_variant(
        db,
        project_id=project_id,
        variant_name=variant_name,
        # NO cost overrides; variant inherits whatever project has.
    )


def geopolitical_event(db, project_id, factory_pct, delay_phase_id,
                       delay_days, reason):
    """Bundled "Trump tariff" / "China holiday" composite disruption.

    Combines:
      1. factory_raises_cost_by_pct  (price impact)
      2. supplier_delays_phase       (schedule impact)
    Both write their own audit rows. Returns a dict with both result
    references so callers can verify.
    """
    project = factory_raises_cost_by_pct(
        db, project_id=project_id, pct=factory_pct, reason=reason,
    )
    phase = supplier_delays_phase(
        db, phase_id=delay_phase_id, days=delay_days, reason=reason,
    )
    return {"project": project, "phase": phase}
