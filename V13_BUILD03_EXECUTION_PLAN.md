# v1.3 Build 03 Execution Plan - Overview Product Concept

## Purpose

Turn the first product-thinking area in Overview from a field-like `Product Thesis` block plus a separate `Inspired By` section into a readable `Product Concept` section that explains what the knife is, why it exists, and what inspired it.

This is a UI/information-architecture build only. No schema, AI parsing, brittle thesis extraction, or rendering preview work.

## User Problem

PMs need the top of Overview to read like product strategy, not a database form. After checking Project Pulse, they should immediately understand the product concept and its inspiration without jumping between separated sections.

## Exact UI Scope

Touch:

- `app/templates/project_detail.html`
- `app/static/css/styles.css`
- `app/i18n/en.json`
- `app/i18n/zh.json`
- `V13_BUILD03_OVERVIEW_PRODUCT_CONCEPT_PLAN.md`
- `CHANGELOG.md`
- `CURRENT_TASK.md`
- new `test_v13_build03.py`

Do not touch:

- routes
- services
- models
- migrations
- AI tools/prompts
- rendering/prototype-photo history sections

## Template Plan

In `project_detail.html`:

- Replace the visible Thesis section title with `Product Concept`.
- Preserve the anchor behavior needed by existing links:
  - keep `id="thesis"` or add a compatibility anchor so old `#thesis` links still land correctly.
  - add a clearer `id="product-concept"` only if it does not break existing tests/links.
- Keep existing inline thesis edit form unchanged:
  - same route: `/projects/{id}/thesis/inline-edit`
  - same textarea name: `project_thesis`
  - same JS toggles unless a rename is purely cosmetic.
- Keep business-plan re-extract behavior unchanged:
  - same form route: `/projects/{id}/thesis/extract-upload`
  - same file input and allowed file types.
- Move/re-render Inspired By references inside or directly beneath Product Concept:
  - use compact concept-reference chips/rows for linked ideas.
  - preserve `Link Idea`, `Create & Link Idea`, unlink, and all modal form behavior.
  - keep `id="inspired-by"` as a compatibility anchor around the references or as an internal anchor.
- Remove the old standalone visual weight of Inspired By as a separate peer section, unless keeping a very small internal subheader is clearer.
- Keep Project Journal where it is for now; do not fold Journal into Product Concept.

## Source Of Truth

| Visible item | Source of truth | Notes |
|---|---|---|
| Product Concept prose | `Project.project_thesis` | Display unchanged content; no parsing into subfields. |
| Missing concept empty state | `health.critical_missing` / thesis length rule from existing health | Do not create a second thesis-completeness rule. |
| Business plan re-extract state | `business_plan_file` and existing query params | Preserve current behavior. |
| Inspired By references | `linked_ideas` from `crud.get_ideas_for_project()` | Existing idea linkage remains source of truth. |
| Available ideas for modal | `available_ideas` from route context | Existing modal select stays. |

## Permissions

- `can_edit` continues to gate:
  - inline thesis edit
  - business-plan re-extract
  - Link Idea
  - Create & Link Idea
  - unlink idea
- Viewer can see public concept prose and linked ideas, but cannot mutate.
- No sensitive factory/engineer/cost fields are added to Product Concept.

## i18n Labels

Likely new or changed keys:

- `section.product_concept`
- `concept.thesis_label` or `concept.thesis_guide`
- `concept.references`
- `concept.no_references`
- `concept.add_reference`

Keep existing keys where they still make sense:

- `btn.extract_from_business_plan`
- `btn.reextract`
- `btn.link_idea`
- `btn.create_link_idea`
- `project.thesis_missing`
- `project.thesis_guide`

Exact EN/ZH parity is required.

## Styling Plan

- Add a `product-concept-section` / `concept-*` style block near existing Product Thesis CSS.
- Make thesis text readable as prose, not a small form field:
  - moderate max height can remain if long thesis dominates the page, but avoid making the core concept feel buried.
  - no nested cards inside cards.
- Render linked ideas as compact chips/rows with serial, type, name, and optional note.
- Preserve mobile layout without horizontal overflow.

## Tests

Add `test_v13_build03.py`.

Required assertions:

- Product Concept appears after Project Pulse.
- Product Concept appears before files/renderings and Timeline.
- `#thesis` compatibility still works or the test proves the old link target is still present.
- Existing thesis inline edit still opens and saves through `/thesis/inline-edit`.
- Business-plan re-extract form still appears for admin/PM and stays hidden for viewer.
- Linked ideas render as concept references.
- Create & Link Idea modal still opens and can create/link a fake idea.
- Viewer sees concept references but no edit/link/create/unlink controls.
- i18n parity remains exact.
- `python3 test_build_v121.py` still passes.
- Re-run `test_v13_build01.py` and `test_v13_build02.py` because this build touches the same Overview area.

## Deferrals

- No standalone positioning schema.
- No target-customer field.
- No AI summarization of thesis into bullets or subfields.
- No parsing thesis for positioning/customer/risk sections.
- No rendering preview in Product Concept; Build 04 owns Renderings.
- No Designer Portal placeholder.
- No Product Journal merge.

## Rollback / Safety

- Since no schema or route changes are planned, rollback is template/CSS/i18n/test only.
- Preserve old anchors and form routes to avoid breaking existing deep links and tests.
- If modal behavior becomes fragile, keep the existing modal markup location and only change the visible presentation around it.
