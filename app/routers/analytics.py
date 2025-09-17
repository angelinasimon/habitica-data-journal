# app/routers/analytics.py
from fastapi import APIRouter, Depends, Query
from typing import Any, Optional
from datetime import date
from app.auth import get_current_user
from app.services.analytics import weekly_completion, habit_heatmap, slip_detector

router = APIRouter(prefix="/analytics", tags=["analytics"])

def _user_id_from(current_user: Any) -> str:
    """Extract a user id from model/namespace/dict without assuming type."""
    # Attribute style: Pydantic model / SimpleNamespace / ORM with .id
    if hasattr(current_user, "id"):
        return getattr(current_user, "id")
    # Mapping style: dict with "id"
    if isinstance(current_user, dict) and "id" in current_user:
        return current_user["id"]
    # If your auth uses a different field name, extend here:
    raise ValueError("current_user has no 'id' field")

@router.get("/weekly")
def get_weekly(
    start: Optional[date] = Query(None, description="YYYY-MM-DD, local to user"),
    end: Optional[date] = Query(None, description="YYYY-MM-DD, local to user"),
    current_user: Any = Depends(get_current_user),
):
    user_id = _user_id_from(current_user)
    return weekly_completion(user_id, start, end)

@router.get("/heatmap")
def get_heatmap(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    current_user: Any = Depends(get_current_user),
):
    user_id = _user_id_from(current_user)
    return habit_heatmap(user_id, start, end)

@router.get("/slips")
def get_slips(current_user: Any = Depends(get_current_user)):
    user_id = _user_id_from(current_user)
    return slip_detector(user_id)