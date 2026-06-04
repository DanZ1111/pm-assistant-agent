# v1.3 Build 05 Execution Plan - Variant Command Cards

## Status

Plan-only execution gate. Locks resolved per Claude review on 2026-06-04.
Builds 03 + 04 are committed at `bc80506`. Implementation may begin
against this revised plan.

## User Problem

PMs compare knife variants as product options, not as database rows. A
variant needs to show what the SKU is, what differs, what packaging /
accessories belong to it, and what the commercial picture looks like,
all in one scannable card.

## Product Decision

Variants become expandable command cards inside the existing `#variants`
section. This build does not replace the existing Packaging & Accessories
management section; instead, each variant card summarizes relevant
components so PMs can compare variants without jumping down to the
component table.

The existing Packaging & Accessories section remains the place to
add/edit/delete components in Build 05. Moving component editing fully
inside variant cards is deferred.

## Scope Decision — Layout-Only (Option A)

The user's Overview redesign wireframe in `project_overview_redesign_plan.md`
shows structured spec fields (Blade.Steel, Blade.Length, Handle.Material,
Handle.Texture, Mechanism.Lock, Mechanism.Opening, Dimensions, Sales format,
Packaging cost as a separate field). The current `project_variants` model
only has three free-text summary columns (`material_summary`,
`size_color_summary`, `packaging_summary`) plus pricing fields.

**Decision: ship the wireframe's LAYOUT now (Option A); defer the
structured-spec SCHEMA to a future Build 05B.**

Why:
- Adds zero schema risk to v1.3.
- Gives PMs the immediate visual experience of the wireframe.
- Build 05B can fill structured fields into the same layout without
  touching the layout code.

Specifically in Build 05:
- Use the wireframe's two-column expand grid: `Specs | Packaging & Accessories`
  above `Pricing & Cost | Profit`.
- "Specs" tile contains the three existing free-text summaries grouped
  under `Material`, `Size & Color`, and `Packaging` sub-labels — narrative
  not field-list.
- The wireframe's `Sales format` row in the collapsed summary is omitted
  in Build 05 because no `sales_format` field exists. Build 05B adds it.
- `Packaging cost` stays inside the existing `packaging_summary` free
  text (e.g. "Color box · $0.90"). Build 05B promotes it to its own field.

## Feature Design Review

1. **Real workflow problem:** PMs need to compare product options,
   packaging, cost, MSRP, and status quickly before choosing what to
   develop or launch.
2. **Repeated or edge-case:** Repeated; variant review happens during
   design, quoting, packaging, and launch decisions.
3. **Structured data:** Existing `project_variants` and
   `project_variant_components` already contain the required Build 05
   data. Structured spec schema is deferred to Build 05B.
4. **Could live in notes first:** Detailed specs stay in free-text
   summaries for now; no blade/handle/mechanism schema yet.
5. **Intake burden:** No new intake burden; existing add/edit forms
   remain.
6. **AI role:** No AI behavior change; AI may already propose
   variant/component changes through existing confirmed flows.
7. **Display payoff:** PM can compare variants as command cards instead
   of scanning scattered fields.
8. **Migration impact:** None.
9. **Minimal schema:** No schema change; no image attachment model.
10. **Minimal UI change:** Rework only the Variants display and preserve
    forms/routes.
11. **Deferred:** Detailed spec schema, sales_format field, variant
    thumbnails from media, real profit model, inline component editing in
    cards, drag/drop ordering, variant comparison matrix.

## UI Scope

Touch:
- `app/templates/components/variants_section.html`
- `app/routes/projects.py` (route-side `components_by_variant` grouping)
- `app/static/css/styles.css`
- `app/static/js/main.js` (small `#variant-N` anchor bootstrap)
- `app/i18n/en.json`
- `app/i18n/zh.json`
- `test_v13_build05.py`
- `CURRENT_TASK.md`
- `CHANGELOG.md`
- `V13_BUILD05_VARIANT_COMMAND_CARDS_PLAN.md`

Do not touch:
- `app/models.py`
- migrations
- AI tools
- variant/component CRUD behavior
- quotation/profit backend
- existing Packaging & Accessories section markup or routes

## LOCKED DECISIONS (resolved from Claude review)

### Lock 1 — `components_by_variant` route-side grouping

`app/routes/projects.py:project_detail` computes a derived dict from the
already-loaded `components` list:

```python
components_by_variant = {None: [], **{v.id: [] for v in variants}}
for c in components:
    components_by_variant.setdefault(c.variant_id, []).append(c)
```

Template iterates `components_by_variant[v.id]` + `components_by_variant[None]`.
No new DB query; template loops are O(C/V) per card instead of O(V × C).

### Lock 2 — Collapsed component count format

Format: `"{shared_count} shared + {variant_count} for this variant"` where:
- `shared_count = len(components_by_variant[None])` (project-wide)
- `variant_count = len(components_by_variant[v.id])`

When `variant_count == 0`: just `"{shared_count} shared"`.
When `shared_count == 0` and `variant_count == 0`: omit the line.

### Lock 3 — `#variant-N` anchor bootstrap

Add to `main.js`:

```js
(function () {
  var hash = window.location.hash;
  if (!hash.startsWith('#variant-')) return;
  document.querySelectorAll('details.variant-command-card[open]').forEach(function (d) {
    d.open = false;
  });
  var target = document.querySelector(hash);
  if (target && target.tagName === 'DETAILS') {
    target.open = true;
    target.scrollIntoView({ behavior: 'auto', block: 'start' });
  }
})();
```

URL `/projects/123#variant-7` opens variant-7 (overriding the
first-primary default) and scrolls to it.

### Lock 4 — `<details>` marker suppression + custom chevron

Add to `styles.css`:

```css
details.variant-command-card > summary {
  list-style: none;
  cursor: pointer;
}
details.variant-command-card > summary::-webkit-details-marker {
  display: none;
}
details.variant-command-card > summary::before {
  content: "\F285"; /* bi-chevron-right */
  font-family: "bootstrap-icons";
  display: inline-block;
  transition: transform 0.15s ease;
  margin-right: 0.5rem;
}
details.variant-command-card[open] > summary::before {
  transform: rotate(90deg);
}
```

Replaces the OS-default triangle with a Bootstrap Icons chevron that
rotates 90° when the card opens. Consistent across browsers.

## Wireframe-Derived Layout

Collapsed summary row (matches wireframe §4 Variants block):

```
[chevron] Variant Name                              [Primary badge]
[thumb-icon] SKU: FK-001-S · Status badge
Target cost: $4.20 · Target MSRP: $14.99       3 shared + 2 for this variant
```

For viewers (no `can_view_costs`): the cost row is omitted entirely. The
component-count line still shows.

Expanded body (2×2 grid, matches wireframe expanded variant block):

```
┌─── Specs ──────────────────┬─── Packaging & Accessories ───┐
│ Material                   │ Project-wide components       │
│   {material_summary}       │   • {component name + type}   │
│ Size & Color               │ Variant-specific components   │
│   {size_color_summary}     │   • {component name + type}   │
│ Packaging                  │ {empty state if none}         │
│   {packaging_summary}      │                                │
├─── Pricing & Cost ─────────┼─── Profit ─────────────────────┤
│ Target factory cost: $X.XX │ Naive margin: $Y.YY            │
│ Actual factory cost: pend  │ (Full profit model coming     │
│ Target MSRP: $Z.ZZ         │  in v1.4 — see Profit Model   │
│                            │  section below)                │
│                            │ {viewer: section absent}       │
├────────────────────────────┴────────────────────────────────┤
│ Notes & Actions                                              │
│ {notes free text}                                            │
│ [Set Primary] [Edit] [Delete (admin)]                       │
└─────────────────────────────────────────────────────────────┘
```

Grid collapses to single-column at narrow widths (`@media (max-width:
768px)`).

## Profit Placeholder Content (resolved)

For `can_view_costs` (admin / PM):
- If both `target_factory_cost` and `target_msrp` exist: render naive
  margin = `target_msrp - target_factory_cost` formatted as USD.
- If only one exists: show the existing one + "(other not set)".
- If neither exists: "Not enough data for a margin preview yet."
- Always followed by: "Full profit model coming in v1.4 — see Profit
  Model section below ↓"

For viewer: the entire Profit cell renders as empty / absent. The
two-column row becomes a single `Pricing & Cost` cell spanning both
columns (or the row is hidden if `target_factory_cost` and
`target_msrp` are also missing).

## Component Summary Rules

Component source of truth:
- `project_variant_components` (preloaded into `components` list by the
  existing route).

Per-card summary includes:
- Project-wide components (`variant_id is NULL`) — appear in every card.
- Variant-specific components (`variant_id == v.id`) — appear only in
  the matching card.

Cost visibility:
- Component target/actual costs appear only when `can_view_costs`.
- Viewer can see component names/types/notes but not costs.

Component editing:
- Existing Packaging & Accessories section remains below Variants.
- The card includes a `[Manage components ↓]` link to `#packaging`.
- Verify `#packaging` anchor exists on `app/templates/components/packaging_section.html`;
  add if missing (one-line `id="packaging"` on the section wrapper).
- Build 05 must NOT create new component-edit routes.

## Source Of Truth

| Visible field | Source of truth | Rule |
|---|---|---|
| Variant order | `crud.get_variants_for_project()` | Primary first, then id ascending, unchanged. |
| Primary marker | `ProjectVariant.is_primary` | Existing service-layer truth. |
| Variant status | `ProjectVariant.status` | Existing `variant_status.*` keys. |
| SKU | `ProjectVariant.sku` | Fallback to `common.no_sku`. |
| Material summary | `ProjectVariant.material_summary` | Display only. |
| Size/color summary | `ProjectVariant.size_color_summary` | Display only. |
| Packaging summary | `ProjectVariant.packaging_summary` | Display only. |
| Notes | `ProjectVariant.notes` | Display only. |
| Pricing/cost | `ProjectVariant.target_factory_cost`, `actual_factory_cost`, `target_msrp` | Visible only when `can_view_costs`; format as existing dollar values. |
| Naive margin | Computed `target_msrp - target_factory_cost` | `can_view_costs` only; both values must be set. |
| Component summary | `components_by_variant` derived dict (Lock 1) | Include project-wide plus matching variant-specific components. |
| Component count summary | `len(components_by_variant[None])` + `len(components_by_variant[v.id])` (Lock 2) | "X shared + Y for this variant" format. |

## Route / Service / Schema Impact

Routes:
- No new routes.
- Preserve:
  - `POST /projects/{project_id}/variants`
  - `POST /projects/{project_id}/variants/{variant_id}/edit`
  - `POST /projects/{project_id}/variants/{variant_id}/set-primary`
  - `POST /projects/{project_id}/variants/{variant_id}/delete`
  - component routes in `app/routes/variants.py`
- Modify only `project_detail` to compute `components_by_variant` (Lock 1).

Services:
- No service behavior changes.
- Existing CRUD helpers already write change-log rows and enforce one
  primary variant.

Schema:
- No schema change.
- No migration.
- No `variant_image_id`, no spec table, no ordering column, no
  `sales_format` column (deferred to Build 05B).

AI:
- No AI behavior change.
- No new AI tool registry entry because Build 05 creates no new
  structured behavior. Existing variant/component AI tools remain the
  write path.

## Permissions

- Everyone who can view the project can see variant names, SKU, status,
  summaries, component names/types, and notes.
- `can_view_costs` controls all variant/component cost/MSRP/naive-margin
  numbers AND the entire Profit cell.
- `can_edit` controls Add Variant, Edit, Set Primary, and `[Manage
  components]` link.
- Admin-only delete remains admin-only.
- Viewer cards must not contain cost text, cost form controls, edit
  buttons, set-primary buttons, delete forms, naive-margin computation,
  or component cost columns.

## i18n Keys

Add these exact keys in EN/ZH with parity:

| Key | EN | ZH |
|---|---|---|
| `variant.command_cards` | Variant command cards | 变体指挥卡 |
| `variant.thumbnail_placeholder` | Variant preview | 变体预览 |
| `variant.specs` | Specs | 规格 |
| `variant.pricing_cost` | Pricing & Cost | 价格与成本 |
| `variant.profit` | Profit | 利润 |
| `variant.components_summary` | Packaging & Accessories | 包装与配件 |
| `variant.project_wide_components` | Project-wide components | 项目级组件 |
| `variant.variant_components` | Variant-specific components | 变体专属组件 |
| `variant.no_components` | No linked components yet. | 暂无关联组件。 |
| `variant.no_specs` | No specs summarized yet. | 暂无规格摘要。 |
| `variant.open_details` | Open details | 展开详情 |
| `variant.manage_components` | Manage components | 管理组件 |
| `variant.naive_margin` | Naive margin | 估算毛利 |
| `variant.margin_other_missing` | (other value not set) | （另一项未填） |
| `variant.margin_no_data` | Not enough data for a margin preview yet. | 暂无足够数据估算毛利。 |
| `variant.profit_future_note` | Full profit model coming in v1.4 — see Profit Model section below. | 完整的利润模型将在 v1.4 推出，详见下方利润模型区。 |
| `variant.not_tracked` | Not tracked | 暂未记录 |
| `variant.count_summary_full` | {shared} shared + {variant} for this variant | 共享 {shared} 个 + 本变体 {variant} 个 |
| `variant.count_summary_shared_only` | {shared} shared | 共享 {shared} 个 |

Reuse:
- `variant.material`
- `variant.size_color`
- `variant.packaging`
- `variant.target_cost`
- `variant.actual_cost`
- `form.target_msrp`
- `profit.costs_hidden`
- `common.no_sku`
- `component_type.*`

EN/ZH parity is required.

## Styling Plan

- New `.variant-command-card` block (the `<details>` element).
- Custom chevron via `::before` (Lock 4).
- Collapsed summary uses flex layout: chevron + name + Primary badge on
  top row; thumbnail-placeholder + SKU + Status badge on second row;
  cost row + component-count on third row (hidden for viewer where
  applicable).
- Expanded body uses CSS grid: `grid-template-columns: 1fr 1fr; gap: 1rem`.
  Collapses to `grid-template-columns: 1fr` at `max-width: 768px`.
- Notes & Actions row spans both columns regardless of viewport.
- Thumbnail placeholder is a Bootstrap Icons icon (`bi-box-seam` or
  `bi-image`) in a neutral 56×56px box.
- No fixed heights on the spec / packaging cells — let content set
  height.

## Tests

Create `test_v13_build05.py`.

Required automated checks:
- i18n parity remains exact.
- Variants render as `.variant-command-card` expandable cards.
- First primary variant is open by default; if no primary exists, first
  variant is open.
- Collapsed summary shows variant name, SKU, status, primary marker,
  component-count line, and pricing row (for `can_view_costs`).
- Expanded body shows Specs, Packaging & Accessories, Pricing & Cost,
  Profit cell, Notes & Actions.
- Project-wide components appear in every variant card.
- Variant-specific components appear only in the matching variant card.
- Component count format: assert `"X shared + Y for this variant"`
  rendered when both > 0; `"X shared"` when variant count is 0.
- Naive margin renders when both target_factory_cost AND target_msrp
  are set; renders "(other value not set)" when only one is set;
  renders "Not enough data..." when neither is set. PM/admin only.
- PM/admin see variant and component costs + Profit cell;
  viewer does not see costs, naive margin, or Profit cell.
- Anchor bootstrap: GET `/projects/{id}#variant-N` returns HTML where
  `<details id="variant-N" open>` is present and no other card has
  `open`. (Static test — JS bootstrap behavior verified by integration.)
- Add Variant still works.
- Edit Variant still works.
- Set Primary still works and keeps only one primary.
- Admin delete still works; non-admin does not see delete.
- Existing Packaging & Accessories section still renders and component
  management still works.
- `#packaging` anchor exists on the components section.
- No schema migration required: verify no new tables/columns.

Real Playwright assertions (not just screenshots):
- Mobile (375px viewport): `.variant-command-card` has no horizontal
  overflow (`boundingBox.width <= viewport.width`).
- After clicking the collapsed summary, the expanded grid is visible
  and its inner rows do not overflow horizontally.

Browser screenshots (for visual review, not as test gates):
- Desktop variants collapsed view.
- Desktop variants expanded view (Variant B from wireframe).
- Mobile variants collapsed + expanded.

Regression:
- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build05.py`
- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build04.py`
- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build03.py`
- `python3 test_build_v121.py`

## Explicit Deferrals

- No detailed blade/handle/mechanism dimension schema (→ Build 05B).
- No `sales_format` field (→ Build 05B).
- No `packaging_cost` as separate field (→ Build 05B).
- No variant-specific image attachment or thumbnail selection (→ later).
- No real profit model implementation (→ v1.4).
- No component editing directly inside each variant card.
- No drag/drop ordering.
- No variant comparison matrix.
- No AI changes.

## Rollback / Safety

Rollback is template/CSS/JS/i18n/test plus the small route grouping:
- Restore the old `variants_section.html`.
- Restore `project_detail` route to its pre-Build-05 state (remove
  `components_by_variant`).
- Remove Build 05 CSS, JS bootstrap, and i18n keys.
- Remove `test_v13_build05.py`.

Existing variant/component rows, routes, service functions, and change
log behavior remain untouched.

## Acceptance Criteria

- PM can compare variant options without scanning separate rows and
  tables.
- Commercial context is visually tied to the variant when the viewer
  has permission.
- Component context is visible in the variant card while component
  management stays in the existing section.
- Layout matches the wireframe's collapsed + expanded structure (2×2
  grid).
- Naive margin shows for PM/admin only; viewer sees no profit context.
- Anchor link `#variant-N` opens that specific card.
- Mobile view has no horizontal overflow.
- No schema, route, service, or AI mutation behavior changes.
