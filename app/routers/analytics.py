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
from app.models.schemas import FeatureRowOut                 # NEW
from app.db import get_db                                      # NEW  (adjust path if yours differs)

router = APIRouter(prefix="/analytics", tags=["analytics"])


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
    response_model=List[FeatureRowOut],
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
    """
    Returns per-day feature rows for each habit between `start` and `end` (inclusive).
    If `user_id` is omitted, the current authenticated user's id is used.

    **Example response (single row):**
    ```json
    [
      {
        "habit_id": 42,
        "habit_name": "Study",
        "day": "2025-09-29",
        "dow": "Mon",
        "last_7d_completion_rate": 0.57,
        "last_30d_completion_rate": 0.73,
        "current_streak": 4,
        "median_completion_bucket": "evening",
        "context": {"travel": false, "exam": true, "illness": false},
        "slip": true
      }
    ]
    ```
    """
    if start > end:
        raise HTTPException(status_code=400, detail="`start` must be <= `end`")

    effective_user_id = user_id or _user_id_from(current_user)

    rows = build_daily_features(
        db=db,
        start=start,
        end=end,
        user_id=effective_user_id,
    )

    # Normalize dataclass -> dict for the response model
    normalized = [asdict(r) if is_dataclass(r) else r for r in rows]
    return normalized


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

@router.get(
    "/features",
    summary="Per-day habit feature rows",
)
def get_features(
    start: date = Query(..., description="Inclusive start date (YYYY-MM-DD, local to user)"),
    end: date = Query(..., description="Inclusive end date (YYYY-MM-DD, local to user)"),
    user_id: Optional[str] = Query(
        None,
        description="Optional user UUID; defaults to current user if omitted."
    ),
    db: Session = Depends(get_db),
    current_user: Any = Depends(get_current_user),
):
    """
    Returns one row per (habit, day) between `start` and `end` (inclusive).
    If `user_id` is omitted, the authenticated user's id is used.

    **Example response (single row):**
    ```json
    [
      {
        "user_id": "c7c2e3d0-1234-4b8a-b111-222233334444",
        "habit_id": 42,
        "day": "2025-09-29",
        "last_7d_completion_rate": 0.57,
        "last_30d_completion_rate": 0.73,
        "current_streak": 4,
        "dow": "Mon",
        "median_completion_bucket": "evening",
        "difficulty": "medium",
        "active": true,
        "context": {"travel": false, "exam": true, "illness": false},
        "slip": true
      }
    ]
    ```
    """
    if start > end:
        raise HTTPException(status_code=400, detail="`start` must be <= `end`")

    effective_user_id = user_id or _user_id_from(current_user)

    rows = build_daily_features(
        db=db,
        user_id=effective_user_id,
        start=start,
        end=end,
    )

    # dataclass -> dict and rename fields for API friendliness
    out: List[dict] = []
    for r in rows:
        d = asdict(r) if is_dataclass(r) else dict(r)
        out.append({
            "user_id": d["user_id"],
            "habit_id": d["habit_id"],
            "day": d["day"].isoformat() if hasattr(d["day"], "isoformat") else d["day"],
            "last_7d_completion_rate": d["last_7d_rate"],
            "last_30d_completion_rate": d["last_30d_rate"],
            "current_streak": d["current_streak"],
            "dow": DOW3[d["dow"]] if isinstance(d["dow"], int) and 0 <= d["dow"] <= 6 else d["dow"],
            "median_completion_bucket": d["hour_bucket"],   # could be None
            "difficulty": d["difficulty"],                  # "easy"/"medium"/"hard" or None
            "active": d["active"],
            "context": {
                "travel": d["is_travel"],
                "exam": d["is_exam"],
                "illness": d["is_illness"],
            },
            "slip": d["slip_7d_flag"],
        })

    return out