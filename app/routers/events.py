from uuid import UUID
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.models import schemas
from app.db import get_db, HabitORM
from app.auth import get_current_user
from app import crud

router = APIRouter(prefix="/events", tags=["events"])



@router.post("", response_model=schemas.EventRead, status_code=201)
def log_event(payload: schemas.EventCreate,
              db: Session = Depends(get_db),
              current_user=Depends(get_current_user)):
    habit = db.get(HabitORM, payload.habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    return crud.events.create(
        db,
        habit_id=payload.habit_id,
        occurred_at=payload.occurred_at,
        user_tz=habit.user.timezone or "UTC",
    )

# List events for a habit in a date range (mounted here but path starts with /habits)
@router.get("/habits/{habit_id}", response_model=List[schemas.EventRead])
def list_habit_events(
    habit_id: int,
    db: Session = Depends(get_db),
    start: Optional[datetime] = Query(None, description="Start (inclusive). If naive, treated as UTC."),
    end: Optional[datetime] = Query(None, description="End (exclusive). If naive, treated as UTC."),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    # Normalize naive datetimes to UTC for storage consistency
    def norm(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    items = crud.events.list_for_habit(db, habit_id, start=norm(start), end=norm(end), limit=limit, offset=offset)
    return items
