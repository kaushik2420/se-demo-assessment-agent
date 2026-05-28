# Deployment runbook — SE Coach Portal

**Target:** Live for kaushik + the SE team in ~30 minutes.
**Stack:** Backend on Render ($7/mo) · Postgres on Render (free or $7/mo) · Frontend on Vercel (free) · Anthropic API for scoring.
**Cost:** ~$14/mo + Anthropic API usage (~$0.05 per call analyzed).
**Not used (yet):** AWS, Granola Business API, SES email — defer to month-2 handoff.

---

## What you'll need before you start

- A GitHub account (you almost certainly have this).
- A Render account: <https://dashboard.render.com/register> (free signup).
- A Vercel account: <https://vercel.com/signup> (free signup).
- An Anthropic API key: <https://console.anthropic.com> → API Keys → create. Note the key once (`sk-ant-...`) — you can't see it again.

---

## Step 1 — Push the repo to GitHub (5 min)

If you haven't already:

```bash
cd /Users/kaushik/Documents/Claude/Projects/Demo\ quality\ assessment\ agent/se-demo-assessment-agent
git init
git add .
git commit -m "Initial commit: SE coach portal"

# Create a GitHub repo (private) at https://github.com/new
# Name it: se-demo-assessment-agent

git remote add origin git@github.com:<your-github-user>/se-demo-assessment-agent.git
git branch -M main
git push -u origin main
```

---

## Step 2 — Deploy backend + Postgres on Render (10 min)

1. Render dashboard → **New +** → **Blueprint**
2. Connect your GitHub account, select `se-demo-assessment-agent`
3. Render reads `render.yaml` and lists 2 resources: `se-coach-api` (web service) and `se-coach-db` (Postgres)
4. Click **Apply** — Render provisions the Postgres (~2 min) and starts building the backend image (~5 min)
5. While that builds, click into `se-coach-api` → **Environment** and add these secrets:

   | Key                  | Value                                                                  |
   | -------------------- | ---------------------------------------------------------------------- |
   | `ANTHROPIC_API_KEY`  | The `sk-ant-...` key from Anthropic                                    |
   | `JWT_SECRET`         | Run locally: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |

   (`DATABASE_URL` is auto-injected; `CLAUDE_MODEL` and `CORS_ORIGINS` come from `render.yaml`.)

6. Wait for build to finish ("Live" badge appears). Note the URL — it'll be like `https://se-coach-api.onrender.com`.
7. Verify: `curl https://se-coach-api.onrender.com/health` → `{"status":"healthy"}`

---

## Step 3 — Deploy frontend on Vercel (5 min)

1. Vercel dashboard → **Add New…** → **Project**
2. Import the same GitHub repo
3. **Configure project:**
   - Root Directory: `web/frontend`
   - Framework: Next.js (auto-detected)
   - Environment Variables (add one):
     - `NEXT_PUBLIC_API_BASE` = your Render URL (e.g. `https://se-coach-api.onrender.com`)
4. Click **Deploy** — ~2 min build, then "Visit" → live URL like `https://se-demo-assessment-agent.vercel.app`.
5. Note the Vercel URL.

---

## Step 4 — Wire CORS back to the frontend (2 min)

Render dashboard → `se-coach-api` → **Environment**:
- Update `CORS_ORIGINS` to include your Vercel URL:
  `https://se-demo-assessment-agent.vercel.app,http://localhost:3000`
- Save → Render auto-redeploys (~1 min).

---

## Step 5 — Create the first users (5 min)

You need to create at least one admin/manager (you) and a few SE accounts.

Render dashboard → `se-coach-api` → **Shell** tab → opens a web terminal in the container. Then:

```bash
# Create the entire team (you + 9 SEs) in one shot. All names, emails, roles baked into app/admin.py.
python -m app.admin seed-team

# Verify
python -m app.admin list-users
```

`seed-team` prints a one-time password for each user — copy each row from the terminal output and DM that password to that person via Slack DM (NOT a channel) or 1Password. **Your own password is in that table too** (top row) — write it down before closing the shell. The script is idempotent: re-running it skips anyone who already exists, so it's safe to run again later (just edit `TEAM_SEED` in `web/backend/app/admin.py` to add new joiners and re-run).

**Current team baked into `seed-team`:**

| Email                                       | Name              | Role     | Title                                |
| ------------------------------------------- | ----------------- | -------- | ------------------------------------ |
| kaushik.natarajan@surveysparrow.com         | Kaushik Natarajan | admin    | Director of Solutions and Consulting |
| parul.gajaraj@surveysparrow.com             | Parul Gajaraj     | se       | Lead Solution Engineer               |
| melodina.carnelian@surveysparrow.com        | Melodina Carnelian| se       | Senior Solution Engineer             |
| yamuna.easwari@surveysparrow.com            | Yamuna E          | se       | Senior Solution Engineer             |
| sushmitha.nb@surveysparrow.com              | Sushmitha NB      | manager  | Associate Manager                    |
| ishrath.ahamed@surveysparrow.com            | Ishrath Ahamed    | se       | Lead Solution Engineer               |
| karthik.kumarendhiran@surveysparrow.com     | Karthik K         | se       | Senior Solution Engineer             |
| subiksha.m@surveysparrow.com                | Subiksha M        | se       | Solution Engineer                    |
| sujith.balakrishnan@surveysparrow.com       | Sujith B          | se       | Principal Solution Engineer          |
| hala@surveysparrow.com                      | Hala Haseeb       | se       | Lead Solution Engineer               |

---

## Step 6 — Smoke test end-to-end (3 min)

1. Open your Vercel URL → log in as Ishrath (or any SE).
2. Click **+ Upload transcript**.
3. Pick **Demo call**, type a prospect name, paste a real Granola transcript.
4. Click **Analyze →**. Within 30-60s you should land on `/call/<id>` with the full scorecard.
5. Log out → log in as yourself (manager) → check `/manager` and `/executive` show the data.

If anything fails, see Troubleshooting at the bottom.

---

## Step 7 — Tell your team (5 min)

Share the Vercel URL and the SE onboarding doc (`SE_ONBOARDING.md`) in your Slack #se-team channel. DM each SE their initial password individually.

---

## Optional: custom domain

Either platform takes 5 min to set up a custom domain (e.g. `se-coach.surveysparrow.com`):
- Render: dashboard → service → Settings → Custom Domains → add the CNAME they provide to your DNS
- Vercel: same flow under project Settings → Domains

Then update `CORS_ORIGINS` and `NEXT_PUBLIC_API_BASE` accordingly.

---

## Local development (run before pushing changes)

```bash
# Spin up DB + backend + frontend in one command
docker compose up --build
# → http://localhost:3000

# After first boot, create a local user in another terminal:
docker compose exec api python -m app.admin create-user dev@local "Dev User" manager devpass

# Login at http://localhost:3000/login with dev@local / devpass
```

---

## Cost projection

| Service        | Plan                | Cost                           |
| -------------- | ------------------- | ------------------------------ |
| Render backend | Starter             | $7 / month                     |
| Render Postgres | Free (90 days) → Starter | $0 → $7 / month                |
| Vercel         | Hobby (free)        | $0                             |
| Anthropic API  | pay-per-use         | ~$0.05 per call analyzed       |
| **Total**      |                     | **$7-14/mo + ~$5 per 100 calls** |

At ~50 calls/month across the team, that's roughly **$20/month all in**.

---

## Troubleshooting

| Symptom                                  | Likely cause                                                         | Fix                                                                  |
| ---------------------------------------- | -------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Login fails with "Invalid email or password" | User doesn't exist, or wrong password                                | Re-run `create-user` in Render Shell                                 |
| Frontend shows "Failed to load" everywhere | CORS not configured                                                  | Check `CORS_ORIGINS` env var includes your exact Vercel URL          |
| Upload fails with 500                    | Anthropic key invalid                                                | Check `ANTHROPIC_API_KEY` in Render env; tail backend logs           |
| All scores look identical and generic    | `ANTHROPIC_API_KEY` not set → LLM client falls back to mock          | Set the key in Render env vars → redeploy                            |
| Backend boots but `/health` 404s         | Container failed to start                                            | Render → service → Logs tab → look for stack trace                   |
| "Database error" on first request        | Tables not yet created                                               | The startup hook auto-runs `init_db()`; check logs — might be a connection-string issue (Render uses `postgres://` prefix; we auto-convert) |

For anything else: Render and Vercel both have responsive support chat.

---

## When you're ready to hand off to SurveySparrow engineering (~month 2)

The same code targets AWS without modification. The architecture v2 doc has the full AWS deployment plan (`infra/main.tf` Terraform skeleton, ECS Fargate, RDS Postgres, SES). The handoff is:

1. Export Postgres from Render: `pg_dump $RENDER_DATABASE_URL > backup.sql`
2. Restore to RDS Postgres (Terraform spins it up)
3. Deploy the same Docker image to ECS Fargate (the Dockerfile is portable)
4. Point CloudFront + S3 at the same Next.js build
5. Swap `CORS_ORIGINS` and DNS

I'll write a dedicated `HANDOFF.md` closer to that date.
