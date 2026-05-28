"""Community events feed endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.deps import CurrentUser, get_current_user
from app.services.events import get_events


router = APIRouter()


@router.get("")
def list_events(
    refresh: bool = Query(False, description="Bypass the 6h cache"),
    _: CurrentUser = Depends(get_current_user),  # auth-gate: only logged-in users
):
    """Return upcoming + recent community events from PSC and similar sources."""
    return get_events(force_refresh=refresh)
