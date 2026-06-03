# PM Product Tracker — User Guide

> **中文 UI is available** as of v1.1.0-build23 — click `中文` in the navbar to switch. Your preference is saved.

This is a structured product project tracker for knife and product development. It manages projects from concept through mass production, with timeline tracking, delay warnings, file uploads, and AI-assisted intake.

---

## v1.2.1 速览

v1.2.1 是一个工作流打磨 + 新部门入驻解锁版。重点更新：

- **Excel 批量导入**：直接上传 `.xlsx` / `.xlsm` / `.xls` / `.csv`，AI 提取每个项目（保留来源表名 + 行号 + 价格表达），逐行可编辑（Create / Skip / Update Existing），一键提交。原来手动一条条录入的工作量直接归零。
- **PM 草稿删除**：PM 现在可以直接删除自己创建、且**所有阶段都还没启动**的项目。一旦某个阶段被推进过，项目就脱离 draft 状态，需要 Admin 或 Archive。
- **创建防重复**：之前出现过的"页面卡了点了 6 次 Submit → 6 条重复项目"问题彻底修复。后端 idempotency token 保证一次点击只生成一条；空白 PM 字段会自动填创建者的 username，所以 PM 创建的项目能在 My Projects 看到。
- **价格字段更聪明**：Target Factory Cost / Target MSRP 现在支持 `under 120 RMB`、`$70-100`、`约 120 RMB 出厂` 这样的真实表达。
- **AI 工作区 Chinese IME 修复**：用中文输入法打英文片段（比如 `LC200N`）时，中间确认候选词的 Enter 不会再被误判为 "发送消息"。
- **项目详情布局重做**：去掉了左侧低价值的侧边栏，PM/工程师/工厂/阶段/上市日期压缩到标题下面的紧凑条；Commercial Snapshot 单独成段。

完整列表见 `CHANGELOG.md` 中的 `## v1.2.1`。

---

## What's new in v1.2.1

A workflow-polish + new-department onboarding-unlock release. Seven patches that landed on the v1.2.0 line.

### Onboarding + intake

- **Excel batch intake** — `/projects/new?tab=ai` accepts `.xlsx`, `.xlsm`, `.xls`, and `.csv` portfolios. AI extracts a `projects` array (preserving source sheet + row hint and pricing fidelity like `$32-38`). Per-row review table lets you edit any field and choose Create / Skip / Update Existing per row. One click commits all confirmed rows atomically through a single idempotency token.
- **PM-facing price strings** — Target Factory Cost / Target MSRP now preserve real-world planning expressions like `under 120 RMB` or `$70-100`. Simple USD values still mirror into the legacy numeric column for future profit math.

### Project workflow safety

- **Project creation safety** — server-side idempotency tokens make the New Project form safe against double-clicks during slow submits. Blank `product_manager` defaults to the creator's username so PM-created projects land in their My Projects, not orphaned on admin. Display-name typed into the PM field is normalized to the canonical username when exactly one user matches.
- **PM draft delete** — PMs can now delete their own projects when no phase has started. Once any phase advances, the project leaves draft state and PM must use Archive instead. Admin retains unrestricted delete; viewer can delete nothing.

### Day-to-day ergonomics

- **Chinese IME** — both assistant composers (bottom dock + side panel) now share a four-layer IME defense including a one-shot post-`compositionend` suppression window. Chinese-keyboard typing of English fragments like `LC200N` no longer fires premature submits.
- **Project detail layout** — removed the low-value left sidebar; promoted PM / Engineer / Factory / Stage / Launch into a compact header facts grid under the project title; added a full-width Commercial Snapshot section near the top.

### Ops

- **Railway build fix** — `nixpacks.toml` pins Python-only so deploys no longer try to npm-install the JSDOM dev dependency.

---

## v1.2 中文速览

v1.2 把 AI 从底部聊天框升级成专业的 **AI 工作区**：桌面上以可调宽度的右侧分屏出现，移动端则是全屏面板；折叠时只保留一个紧凑的输入栏。

主要变化：
- **AI 工作区**：右侧面板和左侧项目数据并排呈现；输入框在面板内部，标题栏始终高于项目内容，关闭后仍可从历史里恢复。模式控件改成 Ask / Capture 分段按钮和 This Project / Global 分段按钮，更专业也更直观。
- **确认卡（Confirmation Cards）**：每一次需要写入的操作（创建日记、灵感、变体、包装件、文件备注、敏感字段、阶段计划调整、Finish Phase 等）都会先在对话中显示一张可编辑的确认卡。点 Confirm 才真的写入，点 Cancel 直接丢弃，绝不会静默落库。
- **附件（Attachments）**：可以在输入区粘贴 PDF / DOCX / 图片直接讨论。原始字节保存在公开 `/uploads` 之外的临时位置，只有在你确认 “保存到项目文件” 之后才会进入 `project_files`，并写入 `changed_by="ai"` 的审计日志。
- **项目上下文自动注入**：在项目页里打开 AI 工作区时，AI 会自动知道你在哪个项目，无需重复说明。Viewer 仍是只读，不会看到 PM 私有字段。
- **重复灵感识别 + 一键 Create & Link**：说 “这个项目是从一次广交会上看到的陶瓷茶杯启发的”，AI 会查重，建议链接已有 Idea 或新建并立即 link 到 Inspired By。

视频/截图详见上方 “Professional Assistant Workspace” 段落。

---

## What's new in v1.2

v1.2 turns the AI assistant from a bottom chat into a professional, project-aware workspace where every write is reviewed before it lands.

### Professional Assistant Workspace

Opens beside the tracker as a resizable split panel on desktop and a full-screen pane on mobile. The collapsed state is a compact dock; expanded state moves the composer into the panel itself, so the bottom dock no longer overlaps the conversation. Header controls (history, archive, close) always sit above tracker content. Mode and scope are now segmented controls — Ask / Capture and This Project / Global — instead of raw dropdowns. Conversation scope is immutable after the first message: changing project/global context starts a new thread after confirmation.

### Confirmation Cards

Every assistant write (journal entries, Ideas, variants, packaging/accessory components, file comments, allowlisted project fields, phase-plan adjustments, Finish Phase, attachment saves) shows up as an editable card in the conversation with Confirm and Cancel buttons. You can edit the proposed values before confirming. Server-side revalidation on confirm re-checks auth, role, project access, allowlists, and proposal state. Double-confirmed and cancelled proposals are refused.

### Assistant Attachments

Attach PDF, DOCX, PNG, JPG/JPEG, WEBP, or GIF files from the dock or panel composer (10 MB cap). PDF and DOCX text is extracted locally for the conversation; pending images are passed to the assistant as image content. Bytes stay in an ignored, non-public location until you confirm a `Save to project files` proposal — at that point they move into `project_files` through the normal audited service, recording `changed_by="ai"` and `source_type="ai_chat"`. Cancelled or stale (24h+) pending inputs are cleaned up automatically.

### Global Search

In Global scope (no specific project context), the assistant has read-only access to `search_projects` and `get_project_context`. You can ask "find projects with launch date in June" or "what's the status of the Beauty Cup project" and get role-filtered results — viewers still don't see PM-only fields. Global scope never writes; if you want to save something, switch the conversation to a specific project first.

### Idea Auto-Capture

When you say something like "we were inspired by a Japanese ceramic mug at the Canton tradeshow" while a project is active, the assistant proposes creating that Idea and linking it to the project's Inspired By section in one confirmation card. You can edit the proposed name, type, and source before confirming. The "Inspired By" section updates immediately on confirmation.

### Duplicate Idea Detection

Before proposing a new Idea, the assistant searches existing Ideas for likely duplicates. If one is found, the confirmation card offers **Link existing** (use the existing Idea) and **Create new** (make a separate one), so you don't accumulate near-duplicates like "ceramic mug" and "ceramic tea mug."

### Sensitive fields stay gated

Factory, engineer, target cost, MSRP, launch date, and Thesis can only be changed through a confirmation card. Derived fields (`current_stage`, `delayed`, `needs_info`) and operational fields (`status`) remain non-writable through chat — per the project's non-negotiable rules.

---

## v1.1 中文速览

v1.1 把系统从“项目资料表”推进成“产品开发工作台”：PM 可以记录项目日志、上传商业计划并提取 Product Thesis、管理多 SKU / 包装 / 报价资料、追踪计划日期和实际进度、保存渲染图与样品照片历史，并用底部 AI Chat 辅助记录信息。

中文界面已经上线：点击导航栏里的 **中文** 即可切换，登录用户的偏好会保存到账号，未登录用户会保存到浏览器 cookie。项目名称、品牌、工厂、SKU、MSRP、Thesis、AI、PM 等业务数据和常用行业术语不会被翻译。

常用入口：
- **New Project**：手动创建，或使用 **AI 辅助创建项目** 从笔记/文件提取字段。
- **Project detail**：查看 Thesis、项目日志、灵感来源、Timeline 2.0、文件、渲染图历史、样品照片、Variants、Packaging、Quotation、Profit Model 占位信息。
- **AI 助手工作区**：底部紧凑输入栏可展开为右侧工作区；在项目页内，AI 会自动带入当前项目上下文。PM / Admin 可以让 AI 提议创建并关联灵感，确认后才会写入。
- **My Projects**：PM / Admin 的日常项目列表。

---

## Getting Started

### How to create a project

1. Click **New Project** in the top navigation
2. Enter a **Project Name** — this is the only required field
3. Fill in as many fields as you can: brand, PM, engineer, factory, target cost, MSRP, launch date, and Product Thesis
4. Select prototype rounds: **Single** (8 phases) or **Double** (10 phases)
5. Click **Create Project**

The project will be created immediately. If critical fields are missing, a **Needs Info** warning will appear on the card.

**Tip:** Use **AI Intake** if you have product notes, a brief, or a spec sheet — the AI can extract the fields for you.

### Chinese UI (Build 23)

Use the **EN / 中文** switcher in the navbar to change the visible UI language.

- Logged-in users: the choice is saved to your account.
- Logged-out visitors: the choice is saved in the browser cookie.
- Project data stays exactly as entered. Product terms such as Thesis, SKU, MSRP, AI, and PM intentionally stay in English because they are clearer for mixed-language product work.

---

## The Projects List

The projects list is your home screen. It shows all projects and highlights those that need attention.

### Needs Attention section

At the top of the page, you'll see:
- **Delayed projects** — projects with overdue phases (shown in red with days late)
- **Phases due this week** — phases whose planned end date falls in the next 7 days

(As of Build 19, "Needs Info" no longer appears in this banner — it still shows on each card and as a filter tab below.)

### Filter tabs

| Tab | Shows |
|---|---|
| All | Every project |
| Active | Projects with status = Active |
| Delayed | Projects with at least one overdue phase |
| Needs Info | Projects missing critical fields |
| Completed | Completed projects |
| Archived | Archived projects |

### Card view vs Table view

- **Card view** (default): Shows name, brand, SKU, stage, PM, factory cost, MSRP, planned launch
- **Table view**: Better for comparing cost, factory, PM, and dates side by side

The toggle button is in the top right of the projects list. Your preference is saved in your browser.

### My Projects (Build 19)

PMs and admins get a separate **My Projects** tab in the navbar (hidden from viewers).

- **PM view**: only projects where you're listed as the Product Manager.
- **Admin view**: all projects in the system, same wide table layout.

This is the focused view — use it day-to-day. Use the full Projects list when you need to compare across the org.

### Last-opened project memory (Build 19)

Clicking the **Projects** link in the navbar now sends you back to the project detail page you last viewed, not the full list. Double-click the same link to clear that memory and go to the full list. Pure browser-side; nothing is stored on the server.

---

## Field Levels Explained

| Level | Meaning |
|---|---|
| **Required** | Cannot create a project without it (only Project Name) |
| **Critical** | Missing = Needs Info warning. Should be filled before the project can be managed properly |
| **Recommended** | Helpful but not blocking |

### Critical fields

- Brand
- Product Manager
- Engineer
- Factory
- Target Factory Cost
- Target MSRP
- Planned Launch Date
- Product Thesis (must be ≥ 80 characters)

### What does "Needs Info" mean?

**Needs Info** means the project is missing one or more critical fields. The badge shows how many fields are missing. It does not block the project from existing — it's a reminder that the project is not fully managed yet.

Example: A project exists but has no factory assigned yet. It will show "3 missing fields" until factory, cost, and MSRP are filled in.

### What does "Delayed" mean?

**Delayed** means at least one phase has a planned end date in the past and is not marked Done or Skipped. It is calculated automatically — you cannot manually set a project as "Delayed."

The delay badge shows the number of days the worst overdue phase is late.

---

## Project Detail Page

Each project detail page is the working record for one product.

### 1. Product Thesis

The first and most prominent section. This is the strategic reason the product exists.

A good Product Thesis answers:
- Why does this product exist?
- Who is it for?
- What problem does it solve?
- What makes it different from existing options?
- Why does it belong to this brand?
- What is the target price logic?
- What are the main risks or unknowns?

**Minimum length:** 80 characters. Shorter = treated as incomplete.

### Business Plan Upload + Thesis Extraction (Build 15)

You can upload a business plan or product brief and ask AI to draft the Product Thesis.

- Supported inputs: PDF, DOCX, DOC, and images. DOC requires LibreOffice on the server.
- AI proposes a thesis and any detected inspirations. It does not write directly.
- You review, edit, link/create/skip suggested Good Ideas, then confirm.
- Refreshing the preview does not re-run AI; the saved extraction result is reused.
- PM/admin can later edit the Product Thesis inline on the project detail page.

### Project Journal (Build 14)

The Project Journal is an internal project memory section for PMs and admins. Use it for factory feedback, design rationale, meeting notes, risk notes, sample test results, and decisions that should not disappear into chat history.

- PM/admin can add entries.
- Viewers cannot see journal content.
- Raw entry text is preserved.
- AI can summarize journal entries on demand.
- Bottom AI Chat can create journal entries in Intake mode.

### Inspired By

Projects can link to ideas from the **Good Ideas** board. Use this section to record which material, structure, feature, aesthetic, manufacturing idea, or reference inspired the project.

As of Build 26, PMs and admins can click **Create & Link Idea** to capture a new inspiration without leaving the project page. You can also describe the inspiration in the assistant's **Capture** mode: the assistant proposes the Idea, checks for likely duplicates, and waits for confirmation before creating or linking anything.

### Timeline 2.0 (Build 17)

Shows all phases in order with planned/actual dates, status, and owner.

Timeline 2.0 separates **Plan** from **Reality**:

- **Planned Start / Planned End** are the schedule targets.
- **Actual Start / Actual End** record what really happened.
- Changing a planned date requires a reason. The change history is saved and shown under the phase.
- A `*` marker appears next to planned dates that have been adjusted.
- **Finish Phase** marks the active phase done, sets today's actual end date, and advances the next phase to in progress.

**Phase statuses:**
- `not_started` — work hasn't begun
- `in_progress` — currently being worked on
- `done` — completed
- `delayed` — overdue and not done
- `skipped` — intentionally bypassed

**Default phase templates:**

_Single prototype (8 phases):_
Design → Engineering Review → Prototype 1 → Prototype Review → Pre-production Sample → Mass Production → Launch Prep → Launch

_Double prototype (10 phases):_
Design → Engineering Review → Prototype 1 → Prototype 1 Review → Prototype 2 → Prototype 2 Review → Pre-production Sample → Mass Production → Launch Prep → Launch

To edit a phase, click the **Edit** button. To add a phase, click **Add Phase** at the bottom of the timeline.

### Files & Renderings

Upload any file associated with the project. Files are organized by category:

| Category | Use case |
|---|---|
| Rendering | Product renders, 3D views, design visuals |
| Reference | Competitor products, inspiration images |
| Quotation | Factory quotation sheets |
| Factory Feedback | Sample feedback, quality reports |
| Thesis | Brand brief, product thesis documents |
| Packaging | Packaging designs, dielines |
| Other | Anything else |

**Images** appear in the gallery grid. Click any thumbnail to open the full-resolution lightbox. Use ← → arrow keys or the prev/next buttons to navigate. Press **Escape** to close.

**Non-image files** (PDF, Word, Excel) appear in the document list with a download link.

**Upload:** Drag and drop a file onto the upload zone, or click the zone to browse. Select a category, then click **Upload File**.

### Rendering History (Build 18)

Every file you upload with category **Rendering** also appears here, newest first. Each entry shows the thumbnail, filename, when it was uploaded, and a short comment.

- Click a thumbnail to open the rendering at full size.
- Click **Add comment / Edit comment** (PM + admin) to write a short note about the rendering — "what changed in this version", "why we picked this finish", "what the factory pushed back on". Comments are saved instantly and recorded in the Change Log.
- The most recent rendering also appears as a small thumbnail in the top-right of the project's card on the Projects list page — so you can scan the grid and remember which project looks like what.

### Prototype Photos (Build 18)

Same idea as Rendering History but for physical prototype photos. Upload a file with category **Prototype Photo** and it appears here. Use the comment field to capture context — "first sample, plastic too brittle", "v2 with new hinge", "color match approved by client".

### Variants, Packaging, Quotation, and Profit Model (Build 16)

v1.1 adds lightweight commercial structure to the project detail page.

**Variants** are product SKUs: different sizes, colors, materials, bundles, or price tiers. One variant can be marked **Primary** so the project has a clear main SKU.

**Packaging & Accessories** records what ships with the product: boxes, sheaths, inserts, screws, spare parts, included accessories, or variant-specific extras. Components can apply to the whole project or only one variant.

**Quotation Files** surfaces uploaded files in the **Quotation** category. Viewers can see that quotation files exist but cannot download sensitive quote content.

**Profit Model placeholder** shows the future model inputs and a simple preview where data exists. The full profit model is intentionally deferred, but the intended formulas are:

```text
Margin per unit = MSRP - factory cost - packaging/accessory unit costs
Total profit = margin per unit × forecast volume - overhead
```

### Change Log

A history of every change made to the project, newest first. Includes:
- Field edits (shows old → new value)
- Phase updates
- File uploads and deletions
- Archive events
- AI intake events (shown with `ai` attribution)

---

## AI Assistant Workspace (Build 27)

A compact assistant dock sits at the bottom of every authenticated page. Submit a message and the assistant opens beside the tracker on desktop or as a full-screen pane on mobile. The expanded workspace has its own composer, so the dock disappears while you work. Close the pane to return to the full tracker; conversation history remains available.

- **Capture / Ask** — Capture can propose structured tracker updates. Ask is read-only Q&A.
- **This Project / Global** — On project detail pages, This Project automatically supplies the active project's role-filtered context. Global can search and inspect role-filtered project summaries. Switching scope during a conversation starts a new thread after confirmation.
- **Resizable workspace** — drag the assistant's left edge on desktop. Your preferred width is remembered in your browser.
- **Editable review cards** — journal entries, inspirations, variants, packaging/accessory components, file comments, allowlisted project fields, phase-plan changes, and Finish Phase actions wait for review and confirmation. If a likely Idea duplicate exists, choose **Link existing** or **Create new anyway**.
- **PDF, DOCX, and image discussion** — use the paperclip in either composer to attach a document or reference image. The assistant can discuss the pending input before you decide whether it belongs in project files.
- **Confirmed attachment filing** — in This Project scope, review the proposed file category and note, then confirm **Save Pending Attachment**. In Global scope, discuss first and name a target project before saving.

Pending attachment bytes are not public project files. Remove a chip or cancel its save proposal to discard it; unconfirmed pending inputs also expire after 24 hours. Use the history dropdown to reopen past conversations or archive threads you no longer need. Delete actions remain manual.

Viewer questions about sensitive topics (factory, costs, journal content, business plans, variant costs, packaging costs, quotations) are blocked before any AI call.

---

## AI-Assisted Create Project (Build 22)

The Create Project page (`/projects/new`) has two tabs:

- **Manual Form** — fill in fields by hand (the default).
- **AI-Assisted** — paste notes or upload a PDF/image. AI extracts the fields, you review and confirm before anything is saved.

The old standalone "AI Intake" navbar link is gone. The link still works as a redirect — `/ai/intake` sends you to `/projects/new?tab=ai`.

For quick chat-driven capture (no full project creation), use the bottom chat bar instead — it can propose journal entries for review and confirmation inside existing projects.

---

## AI Intake (legacy)

The AI Intake flow is now embedded in the AI-Assisted tab on Create Project. The instructions below describe the same flow.

### Option A — Paste text

1. Go to **AI Intake** in the navbar
2. Paste any raw notes, emails, WhatsApp messages, or meeting notes
3. Click **Extract Fields**
4. Review the proposed fields — edit anything the AI got wrong
5. Fill in any missing fields manually
6. Click **Confirm & Create Project**

Nothing is saved until you click Confirm.

### Option B — Upload a file

1. Go to **AI Intake** in the navbar
2. Under "Upload a File", choose a PDF (spec sheet, quotation, email export) or an image of the product
3. Select a file category
4. Click **Analyze File**
5. Review the proposed fields and AI summary
6. Edit and confirm

Supported file types: **PDF**, **PNG**, **JPG**, **WEBP**, **GIF**

The uploaded file will be automatically attached to the project when you confirm.

### What fields can AI extract?

- Project Name
- Brand
- SKU
- Product Type
- Product Manager
- Engineer
- Factory
- Target Factory Cost (USD)
- Target MSRP (USD)
- Planned Launch Date
- Product Thesis

AI only fills in fields it's confident about. It never invents information not present in the input.

---

## Good Ideas 💡

The **Good Ideas** tab is a collaborative brainstorming board for raw inspirations that aren't products yet. Materials, structures, features, aesthetics, manufacturing techniques — log them here so the team can later combine ideas across categories into new products.

### Layout
Six columns by idea type:
- **Material** — new metal alloys, woods, plastics, fabrics
- **Structure** — mechanisms, fold patterns, locks, joints
- **Feature** — functional capabilities (magnetic close, auto-lock, vibration alert)
- **Aesthetic** — visual/design language (carbon look, two-tone, gradient)
- **Manufacturing** — production technique, finishing method
- **Other** — anything that doesn't fit above

Each idea card shows its serial number (`IDEA-001`), name, source-tinted badge, contributor, and project usage count.

### Adding an idea
Click **+ New Idea** on the board. Fill in:
- **Name** — short label
- **Description** — longer detail (why is this cool? how might we use it?)
- **Type** — pick a column
- **Source** — factory / tradeshow / internet / customer / team / competitor / other
- **Source Detail** — specific factory name, URL, tradeshow, etc.
- **Contributor** — defaults to your name; change if logging for someone else

### Permissions
- **Everyone** (admin, PM, viewer) can **view and create** ideas
- **PMs and admins** can **edit** any idea
- **Only admins** can **delete**

### Linking ideas to projects
On any project detail page, scroll to the **Inspired By** section. Click **Link Idea** to pick from open ideas, optionally with a note describing how the idea is being used in this project.

When you link an idea to a project, its status becomes `in_use`. When all projects unlink it, it goes back to `open` and is available for new combinations.

### AI dual-mode intake
Paste any text into AI Intake — the AI now detects whether you're logging an idea or a project:
- *"We're working on a new Damascus Chef Knife for Rblack, MSRP $129.99"* → **project**
- *"Found a cool tri-fold mechanism on Amazon, we could use it later"* → **idea**

If the AI gets it wrong, the confirmation page has a toggle link to switch modes.

---

## Calendar

The **Calendar** tab (visible to everyone who can log in) shows a month-by-month view of your project launches.

### Layout
- **Left column:** list of months in the selected year, each with a count of planned and actually-launched projects
- **Right column:** the selected month's roster, split into two sections — Planned and Actually Launched

### Year navigation
Use the `◀ 2026 ▶` arrows at the top right. The **Today** button jumps back to the current year and month.

### What counts as "Planned"
A project shows up in a month's **Planned** list if its `planned_launch_date` falls in that month and the project is not archived.

### What counts as "Actually Launched"
A project shows up in a month's **Actually Launched** list if its **Launch phase** is marked **Done** and has an `actual_end_date` set, and that date falls in the month.

To record an actual launch:
1. Open the project detail page
2. In the Timeline section, find the **Launch** phase
3. Click **Edit** → set Status to **Done** → set **Actual End Date** to the day it shipped → Save

### Variance display
For each actually-launched project, the calendar shows the variance versus its planned date:
- "5 days late" (in red) — shipped after the planned date
- "3 days early" (in green) — shipped before the planned date
- "on time" (in green) — exact match

This makes it easy to see at a glance which projects slipped and by how much.

---

## Admin — Database Inspector

Available at `/admin/database`. Read-only view showing:

1. **Table Overview** — row counts for all tables
2. **Field Usage** — % of projects with each field filled in
3. **Project Health Summary** — which active projects are missing each critical field
4. **Recent Changes** — last 50 change log entries across all projects

---

## Common Questions

**Q: Can I create a project without filling in all the fields?**
Yes. Only Project Name is required. All other fields can be added later. Missing critical fields will show a Needs Info warning.

**Q: Can I edit a project after creating it?**
Yes. Click the **Edit** button in the project detail sidebar.

**Q: How do I archive a project?**
On the project detail page, click **Archive** in the sidebar. Archived projects still exist and can be viewed, but they won't appear in Active or Delayed filters.

**Q: Why does my project show as Delayed even though I updated the dates?**
Delay is calculated automatically from phases. If any phase has a planned end date in the past and is not marked Done or Skipped, the project will show as Delayed. Mark the phase as Done or update its planned end date to resolve it.

**Q: What is the difference between Planned Launch Date and Estimated Launch Date?**
- **Planned Launch Date** — the original target you entered
- **Estimated Launch Date** — automatically calculated based on current delays. If no phases are delayed, these match.

**Q: How do I record a note or update without changing a field?**
Currently, notes are recorded automatically when fields change. In a future version, you'll be able to add manual event notes directly to the change log.

---

## Deploying to Railway

This section is for the person who runs the deploy. End users just visit the URL and log in.

### Prerequisites
- The repo pushed to GitHub (any visibility)
- A Railway account (free tier works for testing)
- Your OpenAI API key

### Steps

1. **Create the Railway project**
   - Railway → New Project → Deploy from GitHub repo → select this repo
   - Railway auto-detects FastAPI via `railway.toml` and `requirements.txt`

2. **Attach a PostgreSQL database**
   - In your service → New → Database → PostgreSQL
   - Railway auto-injects `DATABASE_URL` into your service

3. **Set environment variables** (Service → Variables tab)

   | Key | Value | Notes |
   |---|---|---|
   | `OPENAI_API_KEY` | `sk-...` | Your OpenAI key |
   | `INITIAL_ADMIN_USERNAME` | e.g. `admin` | One-time bootstrap |
   | `INITIAL_ADMIN_PASSWORD` | a strong password | One-time bootstrap |

   `DATABASE_URL` is auto-set by the PostgreSQL plugin — don't touch it.

4. **Add a persistent volume for uploads** (CRITICAL)
   - Service → Settings → Volumes → New Volume
   - **Mount path:** `/app/app/uploads`
   - **Size:** 1 GB (can be increased later)
   - Without this volume, every redeploy wipes your uploaded files.

5. **Deploy**
   - Railway deploys automatically on push to your tracked branch
   - First startup will: create all tables, create your admin from the env vars, print `[bootstrap] Admin 'youradmin' created from env vars` in the logs

6. **First login**
   - Visit the Railway-generated URL (e.g. `pm-tracker.up.railway.app`)
   - Log in with `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD`
   - Click **Users** in the navbar → generate PINs for your team

7. **Remove the bootstrap secrets** (IMPORTANT)
   - Once logged in successfully, go back to Railway Variables tab
   - **Delete `INITIAL_ADMIN_USERNAME` and `INITIAL_ADMIN_PASSWORD`**
   - The bootstrap is idempotent and won't run again, but leaving credentials in env vars is poor hygiene

### Updating after deploy
- Push to GitHub → Railway auto-redeploys
- Volume keeps your uploads; PostgreSQL keeps your projects, users, change log
- The admin bootstrap will skip on every subsequent startup (admin already exists)

### Troubleshooting
- **Health check fails:** verify `/healthz` returns 200 (the route is in `app/main.py`)
- **DB connection error:** confirm `DATABASE_URL` is present and the PostgreSQL plugin is healthy
- **Files disappear after redeploy:** you forgot the volume — go back to step 4
- **Can't log in after deploy:** check service logs for the `[bootstrap]` line; if it didn't run, your env vars weren't set in time
- **Need to reset admin password:** see "Emergency admin reset" below

### Emergency admin reset

If you're locked out of the admin account (forgot the password, env-var bootstrap was misconfigured, etc.) and you can't reach the Railway shell:

1. In Railway → service → Variables → add:
   - **Key:** `EMERGENCY_RESET_TOKEN`
   - **Value:** a long random string (44+ chars). Generate one locally:
     ```
     python3 -c "import secrets; print(secrets.token_urlsafe(32))"
     ```
2. Wait ~30 seconds for the service to redeploy automatically
3. Visit `https://your-app.up.railway.app/auth/emergency-reset` in your browser
4. Paste the token + pick a new username and password (entered twice)
5. Submit → you'll be redirected to the login page → log in with the new credentials
6. **Delete the `EMERGENCY_RESET_TOKEN` env var from Railway immediately.** Leaving it set is a permanent backdoor to your admin account.

Without `EMERGENCY_RESET_TOKEN` set, the `/auth/emergency-reset` route returns 404 — it doesn't exist as far as the outside world can tell.
