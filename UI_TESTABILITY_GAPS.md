# UI Testability Gaps

Per [QA_BUILD11_EXECUTION_PLAN.md](QA_BUILD11_EXECUTION_PLAN.md) User
lock 8: the QA system never adds fragile `text=...` or class-name
grep assertions when a stable `data-*` attribute is missing. Instead,
it documents the gap here and proposes a minimal `app/*` patch the
user reviews and approves separately.

Each entry below:
1. **What the QA system needs to check**
2. **What's missing in the template**
3. **Proposed patch** (3 lines or fewer)
4. **Risk if shipped without the patch** — what kind of regression
   would slip through without the assertion

## Status

- **Found during QA-11 selector audit (2026-06-13)**
- 3 gaps. None block QA-11 from shipping; the journey uses only
  testable selectors and skips the assertions that need patches.
- All 3 are additive `data-*` attributes — no template logic changes.

---

## Gap 1: Project Pulse "Attention Needed" card has no granular state attribute

### What QA wants to check

After PM creates an active blocker, the Project Pulse card on the
Overview should switch from "no_urgent / inspiration / thesis_needed
/ missing_field" to "blocker_action_title". This is the load-bearing
PM-comprehension check: *can the PM tell at a glance that there's an
active blocker without reading paragraph text?*

### What's missing

In [app/templates/project_detail.html:167](app/templates/project_detail.html#L167), the
`.pulse-action-card` has 5 conditional rendering states but only
exposes them via:
- `.pulse-action-danger` class (covers BOTH `blocker` AND `delay`)
- `.pulse-action-warning` class (covers `needs_info`)
- (no extra class) covers `no_urgent`, `thesis`, `inspiration`

We can't distinguish `blocker` from `delay` without parsing the
visible title text. Title text is i18n'd, so any text-match is
fragile across locales.

### Proposed patch

In `app/templates/project_detail.html` around line 167, add a
`data-pulse-action-type` attribute that exposes the resolved state:

```jinja
<div class="pulse-card pulse-action-card{% ... existing classes ... %}"
     data-pulse-action-type="{%
       if command_center_state and command_center_state.newest_active_blocker %}blocker{%
       elif delay %}delay{%
       elif 'project_thesis' in health.critical_missing %}thesis{%
       elif health.needs_info %}missing_field{%
       elif not linked_ideas and current_phase and current_phase.phase_order <= 3 %}inspiration{%
       else %}no_urgent{%
     endif %}">
```

(Mirrors the existing if/elif/else cascade; ~6 lines.)

### Risk without the patch

A regression where, after a PM opens a real blocker, the Pulse card
silently stays in `no_urgent` state because the Jinja condition
evaluation order changed — invisible until a PM hits a real bug and
asks "why didn't the system tell me there's a blocker?"

The current `variant_pricing_isolation` contract and the
`ai_proposes_blocker` contract would still pass — neither checks the
Pulse card.

---

## Gap 2: Variant card has no `data-variant-target-cost` / `data-variant-msrp`

### What QA wants to check

After a color-only variant is added with a different cost, the
variant card on the project page should show the variant's
target_factory_cost. Cross-section consistency check: the variant
section should show variant cost X, and the project-metadata section
should show project cost Y, and X ≠ Y (proves the isolation contract
holds end-to-end, including the rendered HTML, not just the DB row).

### What's missing

In [app/templates/components/variants_section.html:160-172](app/templates/components/variants_section.html#L160-L172), the variant
cost is rendered as:

```jinja
<strong>${{ "%.2f"|format(v.target_factory_cost) }}</strong>
```

Inside `.variant-command-cost-line` — but the value is in a text
node, not exposed as a data attribute. To read it from Playwright,
we'd need either:
- Parse the text content (fragile — currency formatting could change)
- Use `:nth-of-type` selector position (fragile — reorder breaks it)

### Proposed patch

On the `<details>` element at line 132 (where `id="variant-{{ v.id }}"`
already exists), add data attributes mirroring the displayed values:

```jinja
<details class="variant-command-card{% ... existing ... %}"
         id="variant-{{ v.id }}"
         data-variant-id="{{ v.id }}"
         data-variant-name="{{ v.variant_name }}"
         data-variant-target-cost="{{ v.target_factory_cost or '' }}"
         data-variant-msrp="{{ v.target_msrp or '' }}"
         {% if v.id == default_open_id %}open{% endif %}>
```

(4 new attributes; no logic changes.)

### Risk without the patch

After a color-only variant is created with a different cost, a future
refactor of `variants_section.html` could accidentally render the
PROJECT-level cost on the variant card (cross-wiring bug). The
existing `variant_pricing_isolation` contract checks the DB row, not
the rendered HTML — so the bug would ship and a PM would see "Variant:
Black, target cost $14.50" matching the PROJECT cost instead of the
variant's own $18.00.

---

## Gap 3: Project metadata items have no `data-field` attribute

### What QA wants to check

Project-level target_factory_cost and target_msrp render in the
`#project-metadata` grid. Two scenarios need them:

1. **Cross-section consistency** (paired with Gap 2): assert
   `data-project-target-cost` differs from `data-variant-target-cost`.
2. **Viewer privacy via structural absence**: assert that for a
   viewer, the `data-field="target_factory_cost"` element does not
   exist in the DOM (currently wrapped in `{% if can_sensitive %}`).

### What's missing

[app/templates/project_detail.html:1497-1516](app/templates/project_detail.html#L1497-L1516)
renders project metadata as ordered `.project-metadata-item` divs.
There's no `data-field` attribute, so finding a specific row requires:
- Position (`:nth-child(1)`) — fragile (fields are conditional)
- Label text matching — fragile (i18n)

### Proposed patch

Add `data-field` to each `.project-metadata-item`:

```jinja
{% if can_sensitive %}
<div class="project-metadata-item" data-field="target_factory_cost">
  <span>{{ t('form.target_factory_cost') }}</span>
  <strong data-field-value>{% if project.target_factory_cost_display %}{{ project.target_factory_cost_display }}{% else %}—{% endif %}</strong>
</div>
{% endif %}
<div class="project-metadata-item" data-field="target_msrp">
  <span>{{ t('form.target_msrp') }}</span>
  <strong data-field-value>{% if project.target_msrp_display %}{{ project.target_msrp_display }}{% else %}—{% endif %}</strong>
</div>
... etc.
```

(One `data-field` attribute per item; one `data-field-value` on the
strong; ~8 lines of additive attributes across the section.)

### Risk without the patch

A regression where viewer privacy on `target_factory_cost` breaks
(the `{% if can_sensitive %}` wrap is removed during a refactor) would
not be caught — the existing `viewer_permission_boundaries` contract
checks the `can_view_costs` permission helper, not the rendered HTML.
A PM who logs in as viewer for a screenshare would see costs they
shouldn't, and the QA system would still show green.

---

## What QA-11 ships despite these gaps

The football_knife_asd_lifecycle journey uses only the **testable**
assertions:

- ✓ Timeline Command Center current phase, next action, health band
- ✓ Active blocker count in the phase strip (`data-blocker="active"`)
- ✓ Timeline History rows by event type (`data-event-type="..."`) +
  text content of `.timeline-history-title` / `.timeline-history-body`
- ✓ Viewer privacy on variant costs via `.variant-command-cost-line`
  count (structurally hidden by `{% if can_view_costs %}`)
- ✓ Cross-page consistency: `/projects` index `.stage-pill` text ==
  `/projects/{id}` `.pulse-stage` text (this IS testable today)

And skips:
- ✗ Pulse "Attention Needed" granular state check (needs Gap 1 patch)
- ✗ Cross-section cost consistency Variant vs Project (needs Gaps
  2+3 patches)
- ✗ Viewer privacy on project target_factory_cost via structural
  absence (needs Gap 3 patch)

When the user approves the 3 patches, QA-11b can land those 3
additional assertions in `pm_views.py` and extend the journey.
Until then, the journey is a baseline that catches at least the
testable subset — the user lock 9 success criterion ("catches at
least one class of bug per-build test.py would miss") is satisfied
by the testable subset alone.
