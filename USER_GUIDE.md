# PM Product Tracker — User Guide

This is a structured product project tracker for knife and product development. It manages projects from concept through mass production, with timeline tracking, delay warnings, file uploads, and AI-assisted intake.

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

---

## The Projects List

The projects list is your home screen. It shows all projects and highlights those that need attention.

### Needs Attention section

At the top of the page, you'll see:
- **Delayed projects** — projects with overdue phases (shown in red with days late)
- **Projects missing critical info** — projects with empty critical fields (shown in orange)
- **Phases due this week** — phases whose planned end date falls in the next 7 days

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

Each project detail page has four sections:

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

### 2. Timeline

Shows all phases in order with planned/actual dates, status, and owner.

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

### 3. Files & Renderings

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

### 4. Change Log

A history of every change made to the project, newest first. Includes:
- Field edits (shows old → new value)
- Phase updates
- File uploads and deletions
- Archive events
- AI intake events (shown with `ai` attribution)

---

## AI Intake

The AI Intake page lets you create a new project from unstructured information.

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
