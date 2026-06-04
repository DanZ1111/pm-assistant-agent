# v1.3 Build 04 Execution Plan - Overview Renderings Section

## Status

Implemented and verified after review approval.

Build 03 Product Concept and Build 04 Renderings are both implemented but not committed at the time this file was updated.

## User Problem

PMs need to recognize the product visually near the top of Overview without digging into the full Files & Renderings gallery. Product Concept explains the idea; Renderings should immediately show what the product currently looks like.

## Product Decision

Renderings is its own section after Product Concept. It is not part of Product Concept and it is not a replacement for the existing Files & Renderings or Rendering History sections.

This build is a display build. It reuses existing project files and media history. It does not create a designer upload backend, visual-selection workflow, or new media model.

## UI Scope

Touch:
- `app/templates/project_detail.html`
- `app/static/css/styles.css`
- `app/i18n/en.json`
- `app/i18n/zh.json`
- `test_v13_build04.py`
- `CURRENT_TASK.md`
- `CHANGELOG.md`
- `V13_BUILD04_OVERVIEW_RENDERINGS_PLAN.md`

Expected UI order in Overview:
1. Project Pulse
2. Product Concept
3. Renderings
4. Variants / Packaging / Quotations / Profit placeholder
5. Files & Renderings
6. Rendering History
7. Prototype Photos
8. Metadata / Change Log

New section:
- Primary anchor: `id="renderings-overview"`
- Visible title: Renderings / 渲染图
- Location: immediately after Product Concept and before Variants.
- Content when visual exists:
  - One latest visual preview.
  - Filename.
  - Category label.
  - Uploaded date.
  - Source note/comment when present.
  - Link to full-size image or file.
  - Link to Rendering History.
  - Link to Prototype Photos if the chosen visual is a prototype photo or if prototype photos exist.
  - Disabled Designer Portal placeholder.
- Preview sizing:
  - Inline images must fit the section and never render at native 4K dimensions.
  - Target CSS: `.renderings-overview-preview img { max-width: 100%; max-height: 360px; width: 100%; object-fit: contain; }` with mobile-safe container constraints.
- Document fallback:
  - If the latest available rendering/prototype item is not an image, render the same card frame with a file-type icon, filename, file size when present, category, uploaded date, source note when present, and an `Open file` link.
  - Do not render a broken or empty `<img>` for non-image files.
- Content when no visual exists:
  - Empty state explaining that no rendering/prototype photo has been uploaded.
  - If `can_edit`, link to existing Files upload section.
  - Disabled Designer Portal placeholder.

## Source Of Truth

Visible field mapping:

| Visible field | Source of truth | Rule |
|---|---|---|
| Latest visual preview | Existing `ProjectFile` rows already loaded as `renderings` and `prototype_photos` | Prefer newest image in `renderings` by `ProjectFile.uploaded_at desc`; else newest image in `prototype_photos` by `uploaded_at desc`; else newest non-image rendering/prototype file by `uploaded_at desc` as a document fallback; else empty state. |
| Filename | `ProjectFile.original_filename` fallback `ProjectFile.filename` | Display only. |
| Category | `ProjectFile.file_category` | Render through existing `file_category.*` i18n keys. |
| Uploaded date | `ProjectFile.uploaded_at` | Display as existing short timestamp style. |
| Source note | `ProjectFile.source_note` | Display only; editing remains in Rendering History / Prototype Photos. |
| Full-size link | `/uploads/{{ f.filename }}` | Existing static upload path; no new download route. |
| History links | Existing anchors `#renderings`, `#prototype-photos`, `#files` | Use current sections. |
| Designer Portal placeholder | Static UI label | Disabled/non-clickable; must say future/not active. |

Important semantic lock: "latest" means newest by `ProjectFile.uploaded_at` only. Comment edits, AI summaries, downloads, or other engagement signals do not change latest-visual ordering in Build 04.

No Timeline backend-honesty mapping is required because this is not a Timeline build.

## Route / Service / Schema Impact

Routes:
- No new route.
- Existing `project_detail` route may add one derived context object such as `latest_overview_visual` from already-loaded `renderings` and `prototype_photos`.

Services:
- No new service required.
- Do not add a new query unless the existing `renderings` / `prototype_photos` lists are insufficient.

Schema:
- No schema change.
- No migration.
- No new `ProjectFile` category.
- No pinning/selection column.

AI:
- No AI behavior change.
- AI should not choose, pin, upload, or summarize visuals in this build.

## Permissions

- All users who can view the project may see the latest visual preview and file metadata already visible in the project detail page.
- Upload CTA appears only for `can_edit`.
- Delete, comment edit, upload form, and admin-only file controls remain in existing Files / History sections.
- The overview card must not expose sensitive costs, factory, or engineer data.
- Designer Portal placeholder is disabled for every role.

## i18n Keys

Add these exact keys in EN/ZH with parity:

| Key | EN | ZH |
|---|---|---|
| `section.renderings_overview` | Renderings | 渲染图 |
| `renderings.latest_visual` | Latest visual | 最新视觉稿 |
| `renderings.open_history` | Open rendering history | 查看渲染图历史 |
| `renderings.open_prototype_photos` | Open prototype photos | 查看样品照片 |
| `renderings.open_file` | Open file | 打开文件 |
| `renderings.no_visual_title` | No rendering or prototype photo yet | 暂无渲染图或样品照片 |
| `renderings.no_visual_copy` | Upload a rendering or prototype photo in Files to show the newest visual here automatically. | 在文件区上传渲染图或样品照片后，这里会自动显示最新视觉资料。 |
| `renderings.designer_portal` | Designer Portal | 设计师入口 |
| `renderings.designer_portal_future` | Future workspace for design handoff. Not active yet. | 未来用于设计交接的工作区，当前尚未启用。 |

Reuse existing keys where possible:
- `files.open_full_size`
- `files.upload_in_files`
- `file_category.rendering`
- `file_category.prototype_photo`
- `table.updated` or existing timestamp labels if they fit

## Tests

Create `test_v13_build04.py`.

Required automated checks:
- i18n parity remains exact.
- Renderings section appears after Product Concept and before Variants.
- `#renderings-overview` is the standalone section anchor.
- Existing `#renderings`, `#prototype-photos`, and `#files` anchors still exist.
- With no rendering/prototype photo, empty state appears and editable users see the upload link.
- With an uploaded rendering image, the section shows that image, filename, category, upload date, and link to Rendering History.
- With 2 rendering images and 3 prototype photos, the preview uses the newest rendering image by `uploaded_at`, and the `Open prototype photos` link is still present.
- If no rendering image exists but a prototype photo exists, the section uses the prototype photo.
- If only a non-image rendering/prototype file exists, the section shows a document fallback with file-type icon, filename, size when present, category, uploaded date, and `Open file` link instead of a broken image.
- Designer Portal renders as disabled/future placeholder and does not navigate.
- Viewer role can see the preview but cannot see upload/delete/comment-edit controls in the overview card.
- Existing Files upload still works for `file_category=rendering`.
- Existing Rendering History still shows the uploaded file.
- At 375px viewport width, the Renderings overview section must not create horizontal page overflow; image width must be contained within the viewport.

Regression:
- `env BASE_URL=http://localhost:8001 python3 test_v13_build04.py`
- `env BASE_URL=http://localhost:8001 python3 test_v13_build03.py`
- `python3 test_build_v121.py`

Browser screenshots:
- Desktop Overview with latest rendering.
- Desktop Overview empty state.
- Mobile Overview with latest rendering.

## Explicit Deferrals

- No Designer Portal backend.
- No designer account workflow.
- No image pinning or manual "mark as hero visual".
- No visual diffing.
- No AI-generated visual summary.
- No rendering approval states.
- No new file category.
- No lightbox integration in the overview preview. Clicking/opening uses `/uploads/{{ f.filename }}` in a new tab, even though the deeper Files gallery has its own lightbox.

## Rollback / Safety

Rollback is low-risk because the build is display-only:
- Remove the `renderings-overview` section.
- Remove any derived route context variable.
- Remove Build 04 CSS and i18n keys.
- Remove `test_v13_build04.py`.

Existing files, rendering history, prototype photos, uploads, and database rows remain untouched.

## Acceptance Criteria

- PM can identify the latest product visual in the first screen of Overview.
- Renderings remains a separate section after Product Concept.
- Full media history remains available deeper in Overview.
- No schema, route, service, or AI mutation behavior changes.

## Implementation Results

- Added a display-only `latest_overview_visual` context value in `app/routes/projects.py`.
- Added `#renderings-overview` after Product Concept in `app/templates/project_detail.html`.
- Added section-safe preview, document fallback, metadata, history links, mobile layout, and disabled Designer Portal placeholder.
- Added exact EN/ZH i18n keys.
- Added `test_v13_build04.py`.

## Verification Results

- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build04.py` — 20/20 passed.
- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build03.py` — 20/20 passed.
- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build02.py` — 11/11 passed.
- `env BASE_URL=http://127.0.0.1:8001 python3 test_v13_build01.py` — 16/16 passed.
- `python3 test_build_v121.py` — 19/19 passed.
- `git diff --check` — clean.
