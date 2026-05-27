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
from app.routers import auth, calls, dashboard, upload

app = FastAPI(
    title="SurveySparrow SE Coach API",
    version="0.1.0",
    description="Backend for the SE Demo Assessment portal.",
)


@app.on_event("startup")
def _startup():
    # Auto-create tables on boot (idempotent). For real migrations, swap to Alembic.
    init_db()


_origins = os.getenv("CORS_ORIGINS",
                     "http://localhost:3000,https://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(calls.router, prefix="/calls", tags=["calls"])
app.include_router(upload.router, prefix="/calls", tags=["upload"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])


@app.get("/", tags=["health"])
def root():
    return {"service": "se-coach-api", "status": "ok"}


@app.get("/health", tags=["health"])
def health():
    return {"status": "healthy"}
