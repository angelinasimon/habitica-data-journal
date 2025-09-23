# app/routers/analytics.py
from __future__ import annotations
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from app.auth import get_current_user
from app.services.analytics import weekly_completion, habit_heatmap, slip_detector

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _user_id_from(current_user: Any) -> str:
    """Extract a user id from model/namespace/dict without assuming type."""
    if hasattr(current_user, "id"):
        return getattr(current_user, "id")
    if isinstance(current_user, dict) and "id" in current_user:
        return current_user["id"]
    raise ValueError("current_user has no 'id' field")


@router.get("/weekly")
def get_weekly(
    start: Optional[date] = Query(None, description="YYYY-MM-DD (local to user)"),
    end: Optional[date] = Query(None, description="YYYY-MM-DD (local to user)"),
    current_user: Any = Depends(get_current_user),
):
    """Return weekly completion % for the current user."""
    user_id = _user_id_from(current_user)
    return weekly_completion(user_id, start, end)


@router.get("/heatmap")
def get_heatmap(
    start: Optional[date] = Query(None, description="YYYY-MM-DD start"),
    end: Optional[date] = Query(None, description="YYYY-MM-DD end"),
    current_user: Any = Depends(get_current_user),
):
    """Return heatmap counts for completions grouped by day-of-week × time-bucket."""
    user_id = _user_id_from(current_user)
    return habit_heatmap(user_id, start, end)


@router.get("/slips")
def get_slips(
    threshold: float = Query(0.15, ge=0.0, le=1.0),
    w7: int = Query(7, ge=1),
    w30: int = Query(30, ge=7),
    current_user: Any = Depends(get_current_user),
):
    """Return habits that are slipping compared to 30-day baseline."""
    user_id = _user_id_from(current_user)
    return slip_detector(user_id, window_7_days=w7, window_30_days=w30, slip_threshold=threshold)

# Alias to satisfy tests that call /analytics/slipping
@router.get("/slipping")
def get_slipping(
    threshold: float = Query(0.15, ge=0.0, le=1.0),
    w7: int = Query(7, ge=1),
    w30: int = Query(30, ge=7),
    current_user: Any = Depends(get_current_user),
):
    user_id = _user_id_from(current_user)
    return slip_detector(user_id, window_7_days=w7, window_30_days=w30, slip_threshold=threshold)
