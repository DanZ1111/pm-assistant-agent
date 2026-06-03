# v1.3 Build 05 - Variant Command Cards

## Summary

Redesign Variants as expandable command cards. Variants are where PMs compare sales formats, specs, packaging, accessories, pricing, cost, and profit context.

This build reuses existing variant/component fields. Defer detailed product-spec schema.

## Implementation Changes

- Replace current flat variant cards with expandable variant command cards.
- Collapsed card shows:
  - thumbnail placeholder or latest related image placeholder
  - variant name
  - SKU
  - status
  - primary marker
  - target cost / target MSRP for allowed users
  - short material/spec/packaging summary when present
- Expanded card shows:
  - material summary
  - size/color summary
  - packaging summary
  - accessories/components summary
  - pricing & cost
  - profit model placeholder
  - notes/actions
- Keep existing add/edit/set-primary/delete routes and permissions.
- Existing project-level cost/MSRP may remain fallback context, but the intended commercial home is variant cards.
- No schema changes.

## Explicit Deferrals

- No detailed blade/handle/mechanism dimension schema.
- No variant image attachment model.
- No real profit model calculation beyond existing placeholder behavior.
- No drag/drop variant ordering.

## Tests

- Add `test_v13_build05.py`.
- Verify variants render as expandable cards.
- Verify PM/admin see allowed cost fields and viewer does not.
- Verify add/edit/set-primary still work.
- Verify component summaries appear in expanded variant context when present.
- Verify no schema migration is required.
- Run `python3 test_build_v121.py`.

## Acceptance Criteria

- PM can compare variant options without scanning long database rows.
- Commercial context is visually tied to the variant it belongs to.
