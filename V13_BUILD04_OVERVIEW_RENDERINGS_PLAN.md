# v1.3 Build 04 - Overview Renderings Section

## Summary

Add a standalone Renderings section after Product Concept. The PM should be able to recognize the product visually without digging through the full file list.

This build reuses existing files/rendering history. No new rendering backend.

## Implementation Changes

- Add `Renderings` section after Product Concept.
- Show latest rendering or prototype/sample image when available.
- Include basic file metadata:
  - filename
  - uploaded date
  - source note if present
  - category
- Add link/anchor to existing Rendering History.
- Add Designer Portal placeholder clearly labeled as future.
- If no rendering exists, show a useful empty state and link to Files upload.
- Keep full Files & Renderings and Rendering History sections deeper in Overview.
- No schema changes.

## Explicit Deferrals

- No designer upload portal backend.
- No image selection/pinning workflow.
- No AI visual comparison.
- No new file categories.

## Tests

- Add `test_v13_build04.py`.
- Verify latest rendering appears in standalone Renderings section.
- Verify empty state appears when no rendering exists.
- Verify link to Rendering History works.
- Verify Designer Portal is clearly a placeholder.
- Verify file upload still works in existing Files section.
- Run `python3 test_build_v121.py`.

## Acceptance Criteria

- PM can visually identify the project early in Overview.
- Rendering history remains available without dominating the top of the page.

## Implementation Notes

- Implemented as a display-only section using existing `project_files` rows.
- Latest visual is chosen by `ProjectFile.uploaded_at` only: newest rendering image first, newest prototype image second, newest non-image rendering/prototype fallback third.
- Inline images are constrained with section-safe max dimensions so large uploads cannot dominate the page.
- Non-image rendering/prototype files render as a document fallback card with file metadata.
- Designer Portal remains a disabled placeholder.

## Verification

- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build04.py` — 20/20 passed.
- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build03.py` — 20/20 passed.
- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build02.py` — 11/11 passed.
- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build01.py` — 16/16 passed.
- `python3 test_build_v121.py` — 19/19 passed.
