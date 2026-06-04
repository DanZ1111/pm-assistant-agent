# v1.3 Build 03 - Overview Product Concept

## Summary

Rework the concept area so it reads like product strategy, not a database field. Product Concept includes Product Thesis, positioning where present, and Inspired By references.

Renderings are not part of this build and remain a separate section in Build 04.

## Implementation Changes

- Rename/reframe the thesis area as `Product Concept`.
- Keep the full thesis readable as paragraph prose.
- Preserve inline edit and business-plan re-extract behavior.
- Surface Inspired By as lightweight chips/rows within or directly below Product Concept.
- Keep existing Create & Link Idea and Link Idea flows.
- Do not create new positioning fields.
- If target customer or positioning exists only inside thesis text, do not attempt brittle parsing in this build.
- No schema changes.

## Explicit Deferrals

- No standalone positioning schema.
- No AI summarization of thesis into subfields.
- No rendering previews in this section.

## Tests

- Add `test_v13_build03.py`.
- Verify Product Concept renders after Project Pulse.
- Verify thesis inline edit still works.
- Verify business-plan re-extract form still appears for allowed users.
- Verify linked ideas render as concept references.
- Verify Create & Link Idea modal still works.
- Run `python3 test_build_v121.py`.

## Acceptance Criteria

- Product Concept explains what the product is and why it exists.
- Inspired By feels connected to the concept but does not bury thesis.

## Implementation Notes

- Implemented Product Concept as the primary Overview concept section with `id="product-concept"`.
- Added hidden `#thesis` compatibility anchor inside Product Concept so older deep links and redirects still land in the right area.
- Preserved existing thesis inline edit route/form/textarea and business-plan re-extract form.
- Moved Inspired By references into Product Concept as internal concept-reference chips/rows.
- Preserved Link Idea, Create & Link Idea, unlink, and all existing modal routes.
- Updated Build 02 Pulse missing-concept wording from Product Thesis to Product Concept.
- Added exact EN/ZH keys from the Build 03 execution plan.
- No schema, route, service, AI prompt/tool, rendering, or Product Journal changes.

## Verification

- `env BASE_URL=http://localhost:8001 python3 test_v13_build03.py` — 20/20 passed.
- `env BASE_URL=http://localhost:8001 python3 test_v13_build01.py` — 16/16 passed.
- `env BASE_URL=http://localhost:8001 python3 test_v13_build02.py` — 11/11 passed.
- `python3 test_build_v121.py` — 19/19 passed.
