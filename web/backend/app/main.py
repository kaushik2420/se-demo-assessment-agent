"""
FastAPI entry point for the SE Coach portal.

Run locally:
    cd web/backend
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000

API surface:
    POST /auth/login                -> { access_token }
    GET  /me                        -> current SE profile
    GET  /calls                     -> list calls for current user (or all if manager)
    GET  /calls/{id}                -> call detail with scores + insights
    POST /calls/upload              -> upload transcript (paste or file) → enqueue analysis
    GET  /dashboard/se              -> SE dashboard payload (scores, trend, coaching action)
    GET  /dashboard/manager         -> team leaderboard + aggregates
    GET  /dashboard/ceo             -> CEO executive summary payload
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import auth, calls, dashboard, events, slack, team, tracker, upload

app = FastAPI(
    title="SurveySparrow SE Coach API",
    version="0.1.0",
    description="Backend for the SE Demo Assessment portal.",
)


@app.on_event("startup")
def _startup():
    # Auto-create tables on boot (idempotent). For real migrations, swap to Alembic.
    init_db()
    # Schedule Granola auto-sync every 30 minutes (skips silently if no API key)
    if os.getenv("GRANOLA_API_KEY"):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from app.services.granola_sync import run_sync
            scheduler = BackgroundScheduler(timezone="UTC")
            scheduler.add_job(run_sync, "interval", minutes=30,
                              id="granola_sync", max_instances=1,
                              coalesce=True, misfire_grace_time=600)
            scheduler.start()
            print("[scheduler] Granola auto-sync every 30 min — enabled")
        except Exception as e:
            print(f"[scheduler] failed to start Granola auto-sync: {e}")
    else:
        print("[scheduler] GRANOLA_API_KEY not set — auto-sync disabled")

    # Slack tracker staleness reminder — runs daily at 09:00 UTC
    if os.getenv("SLACK_BOT_TOKEN"):
        try:
            from apscheduler.schedulers.background import BackgroundScheduler as _BS
            from apscheduler.triggers.cron import CronTrigger
            from app.services.slack_tracker import check_staleness_and_remind
            s2 = _BS(timezone="UTC")
            s2.add_job(check_staleness_and_remind, CronTrigger(hour=9, minute=0),
                       id="tracker_staleness", max_instances=1, coalesce=True)
            s2.start()
            print("[scheduler] Tracker staleness reminders daily at 09:00 UTC — enabled")
        except Exception as e:
            print(f"[scheduler] failed to start staleness reminders: {e}")


_origins = [o.strip() for o in os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,https://localhost:3000"
).split(",") if o.strip()]

# Also allow any *.vercel.app (preview deploys) and any
# *.surveysparrow.{com,internal} if/when you add a custom domain.
_origin_regex = r"^https://([a-z0-9-]+\.)*(vercel\.app|surveysparrow\.com|surveysparrow\.internal)$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(calls.router, prefix="/calls", tags=["calls"])
app.include_router(upload.router, prefix="/calls", tags=["upload"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
app.include_router(events.router, prefix="/events", tags=["events"])
app.include_router(team.router, prefix="/team", tags=["team"])
app.include_router(tracker.router, prefix="/tracker", tags=["tracker"])
app.include_router(slack.router, prefix="/slack", tags=["slack"])


@app.get("/", tags=["health"])
def root():
    return {"service": "se-coach-api", "status": "ok"}


@app.get("/health", tags=["health"])
def health():
    return {"status": "healthy"}
