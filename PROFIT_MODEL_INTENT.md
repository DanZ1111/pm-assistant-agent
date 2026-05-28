# Profit Model — Design Intent (placeholder, ships in v1.2)

Build 16 introduces the data scaffolding (variants, packaging/accessory components, quotation files) that a real Profit Model would compute against. The placeholder section on the project detail page surfaces the inputs and a naive per-unit margin preview; the full model lands in v1.2.

## Why placeholder now

We need the data shape to settle (Variants v Components v Quotations) before we calculate against it. Shipping a "Profit Model" with no real inputs would create a misleading number. The placeholder makes the intent visible and gives us a slot to fill once the model is real.

## Inputs the model needs

Per project:
- **Primary variant** — the SKU we model by default. Service-layer enforced: exactly zero or one variant per project may be `is_primary=True`.
- **Variant costs** — `target_factory_cost`, `actual_factory_cost`, `target_msrp` from `ProjectVariant`. Actual wins over target when both are present.
- **Components scoped to the variant or project-wide** — `ProjectVariantComponent` rows where `variant_id == primary.id` OR `variant_id IS NULL`. Sum their `actual_cost or target_cost`.
- **Forecast volume** — NOT in schema yet. Needs a new column on `Project` or a new `project_forecasts` table. Design decision deferred to v1.2.
- **Overhead** — NOT in schema yet. Could be a per-brand setting or per-project field. Defer.

## Formula (target)

```
unit_cost          = primary_variant.actual_factory_cost or primary_variant.target_factory_cost
packaging_share   = SUM(component.actual_cost or component.target_cost
                         for component in components
                         if component.variant_id IS NULL OR component.variant_id == primary.id)
margin_per_unit    = primary_variant.target_msrp - unit_cost - packaging_share
total_margin       = margin_per_unit * forecast_volume - overhead
```

## Edge cases v1.2 must handle

1. **No primary variant set** — show "set a primary variant first" prompt (current placeholder already does this).
2. **MSRP or factory_cost missing** — render dashes; don't compute partial garbage.
3. **Multi-currency** — punt for now; assume USD everywhere.
4. **Wholesale vs MSRP** — wholesale revenue is typically 0.45-0.55 × MSRP. v1.2 should let user toggle "model on MSRP" vs "model on wholesale".
5. **Per-variant components** — components flagged for a non-primary variant must NOT pollute the primary variant's margin.
6. **Negative margin** — surface as a red warning, never hidden.

## Why not just compute it now (v1.1)

- `forecast_volume` requires a UI + schema decision (per-month? per-quarter? per-year?).
- `overhead` is org-level data we haven't modeled.
- Multi-currency support is a real question for the user base.
- A "Profit Model" widget that says "$23.40/unit" without overhead or volume is technically true but misleading. Better to ship a real model in v1.2 than a misleading number now.

## v1.2 implementation sketch

- New columns OR new tables (decide in v1.2 plan-mode session):
  - `projects.forecast_volume_units` (Integer, nullable) — quick path
  - `projects.overhead_per_unit` (Float, nullable) — quick path
  - OR: `project_forecasts` table with date range + volume — proper path
- New crud helper `calculate_profit_model(db, project_id) -> dict` returning all components of the formula for display + verification.
- Profit Model section template gets a real number panel + a "what-if" slider for volume.
- Export to CSV (per variant + per packaging item).
- Optionally an AI tool `forecast_volume_from_market_size(...)` that proposes a volume based on category, with confirmation.

## Out of scope forever (or at least beyond v1.2)

- Full cap-table / fundraising integration.
- Multi-currency conversion (manual entry is fine for the team's scale).
- Tax / duty / freight modeling (lives in landed-cost, not retail margin).
