# v1.3 Build 05B Execution Plan - Structured Variant Specs

## Status

Plan-only execution gate. Locks the deferred scope from `V13_BUILD05_EXECUTION_PLAN.md`
("Option A — Layout-Only"). Build 05B fills the wireframe's structured-spec slots
without redesigning the Variant Command Card layout.

Predecessor: Build 05 shipped at `4d8c847`.

## User Problem

Build 05 shipped variant command cards with wireframe layout but limited spec
detail (only `material_summary`, `size_color_summary`, `packaging_summary` —
three free-text fields). The `project_overview_redesign_plan.md` §5.5
wireframe groups specs into four reader-friendly categories (Blade, Handle,
Mechanism, Dimensions) plus a distinct Sales Format identifier and a separate
Packaging Cost number. PMs need that vocabulary so each section reads as
product-spec narrative rather than a generic blob.

## Product Decision

Add six new variant columns, surfaced in the existing Build 05 card layout:

| New column | Type | Purpose |
|---|---|---|
| `sales_format` | String (nullable) | Single / Combo Pack / Colorway / Packaging Variant / Other |
| `packaging_cost` | Float (nullable) | Per-variant packaging cost (separate from factory cost) |
| `blade_summary` | Text (nullable) | "Steel: VG-10; Length: 3.5"; Finish: stonewash; Edge: drop point" |
| `handle_summary` | Text (nullable) | "Material: G-10; Color: black; Texture: football leather" |
| `mechanism_summary` | Text (nullable) | "Lock: liner; Opening: flipper; Clip: deep carry" |
| `dimensions_summary` | Text (nullable) | "Overall: 7.5"; Closed: 4.1"; Weight: 95g" |

This is Option A from the Build 05 plan ("light"). Option B (one column per
leaf wireframe field — 17 columns) was rejected because most columns would be
empty in real usage; per-section narrative text preserves units / mixed
languages / qualifiers that flat columns can't. A future Build 05C/D can
promote any per-section field to structured columns once usage data shows
which fields are reliably filled in.

The existing `material_summary`, `size_color_summary`, `packaging_summary`
columns are NOT removed. Edit form retains them as "Legacy notes" inputs
behind a collapsible details element so existing data isn't lost; display
prefers new fields. Build 05C may sunset the legacy columns once we confirm
no live project depends on them.

## Feature Design Review

1. **Real workflow problem:** PMs need spec-section vocabulary on every
   variant card so they can compare blades / handles / mechanisms quickly
   without parsing one large summary blob.
2. **Repeated or edge-case:** Repeated — spec review happens during design,
   quoting, packaging, and launch decisions.
3. **Structured data:** Six new nullable columns. Existing free-text columns
   stay; usage data will tell us whether to promote any of them in Build 05C+.
4. **Could live in notes first:** Existing `material_summary` etc are exactly
   that "notes first" path. After Build 05 the user explicitly asked for the
   wireframe's structured grouping, so Build 05B graduates each section to its
   own column.
5. **Intake burden:** Edit form gains 6 inputs. Add form gains 6 inputs.
   Each input is optional; placeholders suggest format. No new required field.
6. **AI role:** `create_variant` + `update_variant` AI tool schemas extended
   to accept the 6 new fields. Confirmation-card flow unchanged. AI can write
   them through the existing Build 27 proposal pipeline.
7. **Display payoff:** Spec section of the expanded card reads as four
   grouped narratives instead of one generic textarea.
8. **Migration impact:** Migration 005 adds 6 nullable columns. Idempotent
   via `add_column_if_missing`. Rollback path: drop the columns (or just leave
   them — they're nullable and harmless if unused).
9. **Minimal schema:** 6 columns is the minimum that maps to the wireframe's
   four spec sections + sales_format + packaging_cost. Less and we lose the
   wireframe's grouping; more and we fight YAGNI.
10. **Minimal UI change:** Build 05's 2×2 grid is preserved. The Specs cell
    splits into four labeled sub-sections (one per new column). Pricing &
    Cost cell adds a Packaging Cost row. Collapsed summary adds a Sales
    Format line beside the SKU row.
11. **Deferred:** Flat structured columns per leaf wireframe field
    (blade_steel, blade_length, …) — Build 05C if needed. Variant image
    attachments. Profit Model real calculation. Sales-format filters on the
    project list. Legacy column sunset (Build 05C).

## UI Scope

Touch:
- `app/models.py` — add 6 columns on `ProjectVariant`
- `app/migrations.py` — migration `005_v1_3_add_variant_structured_specs`
- `app/templates/components/variants_section.html` — split Specs cell + add
  Sales Format to collapsed summary + add Packaging Cost row to Pricing cell
- `app/routes/projects.py` — no change (route still passes the variant; new
  fields are model attributes)
- `app/routes/variants.py` — accept 6 new fields in `add` and `edit` form
  parsing; pass through to crud
- `app/crud.py` — `create_variant` + `update_variant` accept 6 new fields
- `app/ai/tools.py` + `app/ai/prompts.py` — extend `create_variant` and
  `update_variant` tool schemas with 6 new optional fields
- `app/static/css/styles.css` — minor: sub-section styling inside Specs cell
- `app/i18n/en.json` + `zh.json` — add 12 new keys (6 labels + 6 placeholders)
- `test_v13_build05b.py` — new
- `CURRENT_TASK.md`, `CHANGELOG.md`

Do not touch:
- `app/static/js/main.js` (variant anchor bootstrap is unchanged)
- existing variant CRUD routes shape (just extend the form parsing)
- Build 05 layout markers (`.variant-command-card`, `.variant-command-grid`)

## Schema — Migration 005

```python
(
    "005_v1_3_add_variant_structured_specs",
    lambda eng: _add_variant_structured_specs(eng),
),
```

```python
def _add_variant_structured_specs(engine):
    """Build 05B — six new optional columns on project_variants for the
    wireframe's structured spec grouping. All nullable, all defaultless.
    No data migration; existing rows keep NULL and naturally show the
    section's empty state until edited."""
    add_column_if_missing(engine, "project_variants", "sales_format", "VARCHAR")
    add_column_if_missing(engine, "project_variants", "packaging_cost", "REAL")
    add_column_if_missing(engine, "project_variants", "blade_summary", "TEXT")
    add_column_if_missing(engine, "project_variants", "handle_summary", "TEXT")
    add_column_if_missing(engine, "project_variants", "mechanism_summary", "TEXT")
    add_column_if_missing(engine, "project_variants", "dimensions_summary", "TEXT")
```

REAL for `packaging_cost` matches `target_factory_cost` / `actual_factory_cost` type.

## Sales Format Enum

Stored as String for forward flexibility (custom values still allowed) but
the add/edit form's dropdown offers a canonical list:

| Value | EN label | ZH label |
|---|---|---|
| `single` | Single product | 单件 |
| `combo` | Combo pack | 套装 |
| `colorway` | Colorway variant | 配色款 |
| `packaging_variant` | Packaging variant | 包装款 |
| `retail` | Retail edition | 零售版 |
| `amazon` | Amazon edition | 亚马逊版 |
| `other` | Other | 其他 |

Display logic: `t('sales_format.' ~ v.sales_format)` if set, fallback to the
raw string if a custom value was AI-supplied.

## UI Changes inside variants_section.html

### Collapsed summary — add Sales Format chip

The existing meta row (SKU + Status badge) gains a Sales Format chip after
the status badge:

```jinja
<span class="badge variant-status-badge status-{{ v.status }}">{{ t('variant_status.' ~ v.status) }}</span>
{% if v.sales_format %}
<span class="variant-command-sales-format">
  <i class="bi bi-tag me-1"></i>{{ t('sales_format.' ~ v.sales_format, default=v.sales_format) }}
</span>
{% endif %}
```

### Expanded Specs cell — split into four sub-sections

```jinja
<div class="variant-command-cell variant-command-cell-specs">
  <h3 class="variant-command-cell-title">{{ t('variant.specs') }}</h3>
  <div class="variant-command-spec-group">
    <h4>{{ t('spec.blade') }}</h4>
    <p>{{ v.blade_summary or t('variant.no_section_specs') }}</p>
  </div>
  <div class="variant-command-spec-group">
    <h4>{{ t('spec.handle') }}</h4>
    <p>{{ v.handle_summary or t('variant.no_section_specs') }}</p>
  </div>
  <div class="variant-command-spec-group">
    <h4>{{ t('spec.mechanism') }}</h4>
    <p>{{ v.mechanism_summary or t('variant.no_section_specs') }}</p>
  </div>
  <div class="variant-command-spec-group">
    <h4>{{ t('spec.dimensions') }}</h4>
    <p>{{ v.dimensions_summary or t('variant.no_section_specs') }}</p>
  </div>
  {% if v.material_summary or v.size_color_summary or v.packaging_summary %}
  <details class="variant-command-legacy-notes">
    <summary>{{ t('variant.legacy_notes') }}</summary>
    {% if v.material_summary %}<p><strong>{{ t('variant.material') }}:</strong> {{ v.material_summary }}</p>{% endif %}
    {% if v.size_color_summary %}<p><strong>{{ t('variant.size_color') }}:</strong> {{ v.size_color_summary }}</p>{% endif %}
    {% if v.packaging_summary %}<p><strong>{{ t('variant.packaging') }}:</strong> {{ v.packaging_summary }}</p>{% endif %}
  </details>
  {% endif %}
</div>
```

If all four new fields AND all three legacy fields are empty, the cell shows
`variant.no_specs` (existing string).

### Expanded Pricing cell — add Packaging Cost row

```jinja
<div class="variant-command-cell variant-command-cell-pricing">
  ...existing 3 rows (target_cost, actual_cost, target_msrp)...
  <div>
    <dt>{{ t('variant.packaging_cost') }}</dt>
    <dd>{% if v.packaging_cost %}${{ "%.2f"|format(v.packaging_cost) }}{% else %}<span class="variant-command-muted">{{ t('variant.not_tracked') }}</span>{% endif %}</dd>
  </div>
</div>
```

### Naive margin calculation update

The Profit cell's naive margin remains `target_msrp - target_factory_cost`
in Build 05B. **Packaging cost is NOT subtracted** because it's a separate
operational cost; the existing `target_factory_cost` already represents the
total factory-side cost in most projects' usage. A future Build 05C / v1.4
real profit model can layer packaging cost in properly.

This is a conscious choice to keep Build 05B layout-aligned and not silently
change the margin number. The Pricing cell now SHOWS packaging_cost so PMs
have the data; the Profit cell stays focused on factory-cost-vs-MSRP.

## Add / Edit Forms

The existing add and edit forms in `variants_section.html` already use a
12-col Bootstrap grid. Add 6 inputs in a new "Specs & format" sub-row:

```jinja
<div class="col-md-4">
  <label class="form-label small fw-bold">{{ t('variant.sales_format') }}</label>
  <select name="sales_format" class="form-select form-select-sm">
    <option value="">{{ t('variant.sales_format_unset') }}</option>
    {% for f in ['single','combo','colorway','packaging_variant','retail','amazon','other'] %}
    <option value="{{ f }}" {% if v.sales_format == f %}selected{% endif %}>{{ t('sales_format.' ~ f) }}</option>
    {% endfor %}
  </select>
</div>
<div class="col-md-4">
  <label class="form-label small fw-bold">{{ t('variant.packaging_cost') }}</label>
  <input type="text" name="packaging_cost" class="form-control form-control-sm" value="{{ v.packaging_cost or '' }}" placeholder="0.00">
</div>
<!-- 4 textareas, one per spec section, with format placeholder -->
<div class="col-md-6">
  <label class="form-label small fw-bold">{{ t('spec.blade') }}</label>
  <textarea name="blade_summary" class="form-control form-control-sm" rows="2"
            placeholder="Steel: VG-10; Length: 3.5&quot;; Finish: stonewash">{{ v.blade_summary or '' }}</textarea>
</div>
<!-- ... handle, mechanism, dimensions ... -->
```

The legacy `material_summary` / `size_color_summary` / `packaging_summary`
inputs stay in the form, but move into a "Legacy notes" `<details>` block at
the bottom of the form so PMs see they exist without being distracted by them.

## Route Changes — variants.py

`POST /projects/{project_id}/variants` (add):

```python
@router.post("/projects/{project_id}/variants")
def variant_add(
    request: Request,
    project_id: int,
    variant_name: str = Form(...),
    sku: str = Form(""),
    status: str = Form("evaluating"),
    is_primary: int = Form(0),
    target_factory_cost: str = Form(""),
    actual_factory_cost: str = Form(""),
    target_msrp: str = Form(""),
    material_summary: str = Form(""),
    size_color_summary: str = Form(""),
    packaging_summary: str = Form(""),
    notes: str = Form(""),
    # Build 05B additions:
    sales_format: str = Form(""),
    packaging_cost: str = Form(""),
    blade_summary: str = Form(""),
    handle_summary: str = Form(""),
    mechanism_summary: str = Form(""),
    dimensions_summary: str = Form(""),
    db: Session = Depends(get_db),
):
    ...
```

Same shape for `/edit`. Parse `packaging_cost` as float via existing
`_parse_float` helper. Pass all 6 new fields through to `crud.create_variant`
/ `crud.update_variant`.

## CRUD Changes — crud.py

`create_variant` and `update_variant` accept the 6 new fields as optional
kwargs. Existing change-log write logic continues to record changes; add the
6 new field names to the `VARIANT_DISPLAY_NAMES` dict so they get a human
label in the change log.

## AI Tool Registry Updates

In `app/ai/tools.py`, the `create_variant` and `update_variant` tool schemas
get the 6 new optional fields with JSON-schema string/number types:

```python
"sales_format": {
    "type": "string",
    "enum": ["single", "combo", "colorway", "packaging_variant", "retail", "amazon", "other"],
    "description": "Sales-format identifier...",
},
"packaging_cost": {"type": "number", "description": "Packaging cost per unit, USD."},
"blade_summary": {"type": "string", "description": "Blade specs narrative..."},
"handle_summary": {"type": "string", "description": "Handle specs narrative..."},
"mechanism_summary": {"type": "string", "description": "Mechanism specs..."},
"dimensions_summary": {"type": "string", "description": "Dimensions narrative..."},
```

Confirmation-card flow is unchanged. AI can propose these fields; user
confirms via the existing Build 27 pipeline before any write.

Update `AI_TOOLS_REGISTRY.md` row for `create_variant` / `update_variant`
to note the Build 05B field additions.

## i18n Keys

Add these in EN + ZH (parity-locked):

| Key | EN | ZH |
|---|---|---|
| `spec.blade` | Blade | 刀身 |
| `spec.handle` | Handle | 手柄 |
| `spec.mechanism` | Mechanism | 机构 |
| `spec.dimensions` | Dimensions | 尺寸 |
| `variant.sales_format` | Sales format | 销售形态 |
| `variant.sales_format_unset` | — Not set — | — 未设置 — |
| `variant.packaging_cost` | Packaging cost | 包装成本 |
| `variant.no_section_specs` | Not specified | 暂未填写 |
| `variant.legacy_notes` | Legacy notes (from earlier builds) | 旧版备注（早期版本） |
| `sales_format.single` | Single product | 单件 |
| `sales_format.combo` | Combo pack | 套装 |
| `sales_format.colorway` | Colorway variant | 配色款 |
| `sales_format.packaging_variant` | Packaging variant | 包装款 |
| `sales_format.retail` | Retail edition | 零售版 |
| `sales_format.amazon` | Amazon edition | 亚马逊版 |
| `sales_format.other` | Other | 其他 |

16 keys × 2 langs = 32 new translations. Parity must hold at 620/620.

## Source Of Truth

| Visible field | Source | Notes |
|---|---|---|
| Sales format chip (collapsed) | `ProjectVariant.sales_format` | NULL → chip absent |
| Sales format select (form) | enum list above | "Not set" maps to empty string → NULL |
| Blade / Handle / Mechanism / Dimensions text | new `*_summary` columns | NULL → "Not specified" empty state |
| Packaging cost (Pricing cell) | new `packaging_cost` column | NULL → "Not tracked" |
| Legacy notes details | existing 3 columns | only renders if at least one is non-empty |
| Naive margin | unchanged: `target_msrp - target_factory_cost` | packaging_cost NOT subtracted |

## Permissions

Unchanged from Build 05. `can_view_costs` gates packaging_cost (it's a cost
number). `can_edit` gates the form inputs. Viewer sees the four spec sections
+ Sales Format chip but not packaging_cost.

## Tests — test_v13_build05b.py

Required assertions:

- Migration 005 applied: `project_variants` table has 6 new columns.
- Adding a variant via the form with all 6 new fields → DB row has those
  values.
- Editing a variant to set the 6 new fields → DB row updates + change-log
  rows created for each modified field.
- GET project detail with a variant that has `sales_format=combo` → chip
  renders with the localized "Combo pack" label.
- GET project detail with a variant that has all 4 spec summaries → expanded
  Specs cell shows 4 sub-sections each with their text.
- GET project detail with a variant that has only legacy `material_summary` →
  legacy notes `<details>` block renders; new sections show "Not specified".
- Packaging cost row appears in Pricing cell for `can_view_costs`; absent
  for viewer.
- Naive margin computation unchanged (still msrp - cost; ignores packaging).
- AI tool registry: `create_variant` schema includes the 6 new field names
  with correct types.
- i18n parity at 620/620.
- All Build 05 assertions (cards, grid, anchor, chevron, count format) still
  pass.

Regression:
- `python3 test_v13_build05b.py`
- `env BASE_URL=http://localhost:8000 python3 test_v13_build05.py`
- `python3 test_v13_build04.py`, `test_v13_build03.py`, `test_v13_build02.py`,
  `test_v13_build01.py`, `test_build_v121.py`, `test_build30.py`,
  `test_build30b.py`, `test_build30c.py`, `test_ai_e2e.py`.

No JSDOM tests touched (no JS change).

## Explicit Deferrals

- Flat structured columns per leaf wireframe field (`blade_steel`,
  `blade_length`, `handle_color`, etc.) → Build 05C if usage data justifies.
- Variant image attachments → out of scope.
- Real profit model that subtracts packaging cost → v1.4.
- Sales-format filters on `/projects` list → out of scope.
- Backfilling new fields from existing `material_summary` text → not safe to
  auto-parse; PMs migrate manually as they edit.
- Sunsetting legacy columns → Build 05C after we confirm no live dependence.

## Rollback / Safety

Build 05B is additive — no existing column is removed.

Rollback path if needed:
- Revert this commit's app/* + template/* changes (Build 05 layout survives).
- The 6 new columns can remain in the DB indefinitely as harmless NULLs.
- Migration 005 doesn't need to be reverted; it's idempotent and the columns
  are nullable.

## Acceptance Criteria

- Migration 005 applies cleanly on the dev SQLite DB and would on Railway
  PostgreSQL.
- Adding a variant via the form with all 6 new fields persists them to the
  DB and renders them in the card.
- The four wireframe spec sections (Blade / Handle / Mechanism / Dimensions)
  each render as a labeled sub-block within the Specs cell.
- Sales Format chip appears in the collapsed summary when set.
- Packaging Cost row appears in the Pricing & Cost cell for `can_view_costs`.
- Legacy `material_summary` / `size_color_summary` / `packaging_summary`
  data remains visible behind a Legacy notes details element if present.
- AI can propose all 6 new fields via the existing confirmation-card flow.
- i18n parity holds at 620/620.
- All Build 05 layout invariants still pass.
