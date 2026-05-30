# DEPLOYMENT.md — Multi-department Deployment Runbook

> This document is the canonical "how to spin up a new department instance" runbook. Build 25 chose **separate-deployment-per-department** as the multi-tenancy strategy: same git repo, same image, different database + env vars. Total isolation, zero code change.

The PM dept's existing instance keeps running unchanged. A second instance for Beauty (or any new department) is provisioned per the steps below.

---

## Architecture in one paragraph

Every department instance is an identical FastAPI process running this repo. Each has its own PostgreSQL database (`DATABASE_URL` env var), its own bootstrap admin (`INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD`), and optionally its own OpenAI key (`OPENAI_API_KEY`). The app doesn't know about departments — isolation is purely at the deployment boundary. To add a department, provision one more service. To remove a department, delete its service + DB plugin.

---

## Provisioning a new department on Railway

Steps below are for **Railway**. If you ever switch hosts, the same env-var contract applies — only the service-creation steps change.

### 1. Create a new Railway service from this repo

1. Open the Railway dashboard for the project.
2. Click **New** → **GitHub Repo** → pick `pm-assistant-agent` → **Deploy**.
3. Railway auto-detects `nixpacks` from `railway.toml` and uses `python3 run.py` as the start command. No buildpack tweaks needed.
4. Name the service something obvious — e.g. `pm-tracker-beauty`. The existing service should already be `pm-tracker-pm` (rename if it isn't, so the two are easy to tell apart).

### 2. Attach a fresh PostgreSQL plugin

1. Inside the new service, click **New** → **Database** → **Add PostgreSQL**.
2. Railway auto-provisions a fresh PG instance and sets `DATABASE_URL` on the service.
3. The first boot will:
   - Run `Base.metadata.create_all(bind=engine)` → creates every table from scratch.
   - Run `migrations.run_pending(engine)` → applies any column-level migrations (Builds 13+).
   - Both are idempotent and safe on a fresh DB.

### 3. Set per-instance env vars

In the new service's **Variables** tab, set:

| Variable | Value | Purpose |
|---|---|---|
| `INITIAL_ADMIN_USERNAME` | `beauty_admin` (or whoever) | One-time bootstrap of the first admin user. Used by `app/main.py:_bootstrap_admin_from_env()` on first boot. |
| `INITIAL_ADMIN_PASSWORD` | `<a strong random password>` | Same. **Save this securely; you log in with it once and create real users from there.** |
| `OPENAI_API_KEY` | `<Beauty's own key>` | So OpenAI usage is billed/tracked per dept. Can share PM's key if preferred. |
| `SECRET_KEY` | `<a fresh random 32+ char string>` | Session-cookie signing. Must be unique per instance so a session cookie from PM can't be replayed against Beauty. Generate with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `DISABLE_RELOAD` | `1` | Production mode — `app/run.py` skips uvicorn auto-reload. |
| `RAILWAY_ENVIRONMENT` | (auto-set by Railway) | Causes `app/run.py` to also disable reload. |

`DATABASE_URL` is set automatically by the PostgreSQL plugin — don't set it manually.

> **After first successful login** with the bootstrap admin: log out, edit the service's Variables tab, and **delete `INITIAL_ADMIN_USERNAME` and `INITIAL_ADMIN_PASSWORD`**. Per `app/main.py:_bootstrap_admin_from_env()`, the bootstrap is idempotent and won't re-create the admin, but leaving plaintext credentials in env vars is bad hygiene.

### 4. Custom domain (optional but recommended)

1. In Railway, **Settings** → **Networking** → **Generate Domain** for the new service. You'll get something like `pm-tracker-beauty-production.up.railway.app`.
2. If you have a base domain (e.g. `tracker.yourcompany.com`):
   - Add a CNAME for `beauty.tracker.yourcompany.com` → `pm-tracker-beauty-production.up.railway.app`
   - Add a CNAME for `pm.tracker.yourcompany.com` → the existing PM service's Railway domain
   - In each Railway service's **Settings** → **Networking** → **Custom Domain**, add the matching subdomain
3. URL scheme convention: **subdomain per department**: `pm.tracker.example.com`, `beauty.tracker.example.com`. Don't use path-based routing — it would require app code changes and break the zero-code-change property of this build.

### 5. Verify the new instance

Right after first deploy, in this order:

1. **Health check:** `curl https://beauty.tracker.example.com/healthz` → `{"status": "ok"}`.
2. **Version string:** `curl -s https://beauty.tracker.example.com/auth/login | grep -o "1.1.0-build25"` → exactly one match.
3. **First admin login:** open the URL in a browser. Sign in with `INITIAL_ADMIN_USERNAME` + `INITIAL_ADMIN_PASSWORD`. Should land on `/projects` with an empty project list.
4. **Isolation check:** in two separate browser windows (one signed into PM, one signed into Beauty), create one project in each with the same name (e.g. "Test isolation"). Reload both lists — each sees only its own. Visit the other's `/projects/1` URL — you should land on YOUR `/projects/1` (different content, confirming the DBs are separate).
5. **Bootstrap cleanup:** in Railway, delete `INITIAL_ADMIN_USERNAME` and `INITIAL_ADMIN_PASSWORD` from the Beauty service's Variables.

If all 5 pass, the new department is live.

---

## Adding a 3rd / 4th / Nth department

Same steps as above. Each new service is fully independent — no global config to update, no other instance to touch.

If you ever reach 4+ departments, revisit the architecture: row-level multi-tenancy (one DB with `organization_id` on every row) becomes more attractive than provisioning N separate services. That's a v1.2-scoped conversation — see the `Build 25 — Beauty Department isolated deployment` section in `MASTERPLAN.md` and the architectural review in `~/.claude/plans/can-you-still-find-nested-cook.md`.

---

## Operating multiple instances

| Concern | How it's handled |
|---|---|
| **Migrations** | Auto-run on each instance's startup via `migrations.run_pending(engine)`. New schema changes ship via `git push` and run independently on each instance on next deploy. |
| **Backups** | Per-instance. Railway PostgreSQL plugins have their own backup snapshots. Set the same backup cadence on every instance. |
| **Code changes** | One `git push` to `main` → both instances auto-redeploy with the same image. They always run identical code. |
| **User accounts** | Separate per instance. No SSO. If a person needs access to both PM and Beauty, they get two separate accounts. (Build a unified SSO layer in v1.2+ if this becomes a regular ask.) |
| **OpenAI spend** | Per-instance. Each `OPENAI_API_KEY` shows independent usage in the OpenAI dashboard. Shared key works too if you'd rather have one bill. |
| **File uploads** | Per-instance. Each instance's `app/uploads/` is local to its container. **Important for Railway**: container storage is ephemeral. If you need persistent file uploads, attach a Railway Volume to each instance's `app/uploads/` path. The existing PM instance has this configured (or needs to be — verify). |

---

## Rolling back / deleting a department instance

To remove a department (rare):

1. Railway dashboard → the department's service → **Settings** → **Delete service**.
2. Railway dashboard → the department's PostgreSQL plugin → **Delete plugin**.
3. Remove the custom domain CNAME from DNS.

No effect on any other instance. The deletion is total — no leftover state in PM's DB.

---

## What this build does NOT do (deferred to v1.2 if needed)

- **Cross-department views.** An admin can't see "all projects across all departments" because there is no global view; each instance only knows its own DB. Would require Option 1 (row-level multi-tenancy).
- **Shared Good Ideas board.** Same reason.
- **Org-wide AI search.** Same reason.
- **SSO across departments.** Each instance has its own user table.
- **Per-department branding.** Same image, same templates. Logos / colors are not per-instance.
- **Auto-provisioning script.** This runbook is manual. A `provision_department.sh` script could automate steps 1-3 via Railway CLI; not built in v1.1.
