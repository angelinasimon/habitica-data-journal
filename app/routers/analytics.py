# app/routers/analytics.py
from __future__ import annotations
from dataclasses import asdict, is_dataclass  # NEW
from datetime import date
from typing import Any, Optional, List        # MOD

from fastapi import APIRouter, Depends, Query, HTTPException  # MOD
from sqlalchemy.orm import Session                              # NEW

from app.auth import get_current_user
from app.services.analytics import weekly_completion, habit_heatmap, slip_detector
from app.services.features import build_daily_features                # NEW
from app.models.schemas import FeaturePublic           # NEW
from app.db import get_db, HabitORM                                     # NEW  (adjust path if yours differs)

router = APIRouter(prefix="/analytics", tags=["analytics"])
DOW3 = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

def _user_id_from(current_user: Any) -> str:
    """Extract a user id from model/namespace/dict without assuming type."""
    if hasattr(current_user, "id"):
        return getattr(current_user, "id")
    if isinstance(current_user, dict) and "id" in current_user:
        return current_user["id"]
    raise ValueError("current_user has no 'id' field")


# ---------------- NEW: /analytics/features ----------------

@router.get(
    "/features",
    response_model=List[FeaturePublic],
    summary="Per-day habit feature rows",
)
def get_features(
    start: date = Query(..., description="Inclusive start date (YYYY-MM-DD, local to user)"),
    end: date = Query(..., description="Inclusive end date (YYYY-MM-DD, local to user)"),
    user_id: Optional[str] = Query(
        None,
        description="Optional user UUID string to filter results; defaults to current user."
    ),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    if start > end:
        raise HTTPException(status_code=400, detail="`start` must be <= `end`")

    effective_user_id = user_id or _user_id_from(current_user)

    # Build internal rows (dataclasses)
    rows = build_daily_features(
        db=db,
        user_id=effective_user_id,
        start=start,
        end=end,
    )

    if not rows:
        return []

    # Fetch habit names once
    habit_ids = {r.habit_id for r in rows}
    name_rows = (
        db.query(HabitORM.id, HabitORM.name)
        .filter(HabitORM.id.in_(habit_ids))
        .all()
    )
    habit_name_by_id = {hid: hname for hid, hname in name_rows}

    # Map internal → public
    out: List[FeaturePublic] = []
    for r in rows:
        out.append({
            "habit_id": r.habit_id,
            "habit_name": habit_name_by_id.get(r.habit_id, ""),
            "day": r.day,  # Pydantic will serialize to "YYYY-MM-DD"
            "dow": DOW3[r.dow],  # 0..6 -> "Mon".."Sun"
            "last_7d_completion_rate": r.last_7d_rate,
            "last_30d_completion_rate": r.last_30d_rate,
            "current_streak": r.current_streak,
            "median_completion_bucket": r.hour_bucket,
            "context": {
                "travel": r.is_travel,
                "exam": r.is_exam,
                "illness": r.is_illness,
            },
            "slip": r.slip_7d_flag,
        })

    return out

# ---------------- Existing endpoints (unchanged) -----------

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

