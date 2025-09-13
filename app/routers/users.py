# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db import get_db, UserORM, HabitORM, EventORM, ContextORM
from sqlalchemy import select, and_, exists, literal, not_
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from app.models.schemas import UserCreate, User, ReminderDue  # Pydantic models
from app import crud
from app.services.reminders import get_due_habits  
from typing import List
from uuid import UUID
router = APIRouter(prefix="/users", tags=["users"])

@router.post("", response_model=User, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    u = crud.users.create(db, name=body.name, email=body.email, timezone=body.timezone)
    return u  # response_model handles serialization

@router.get("/{user_id}", response_model=User)
def get_user(user_id: str, db: Session = Depends(get_db)):
    u = crud.users.get(db, user_id)
    if not u:
        raise HTTPException(status_code=404, detail="user not found")
    return u

def _is_active(status_val) -> bool:
    # Works for enum or plain string storage
    try:
        return str(getattr(status_val, "value", status_val)).lower() == "active"
    except Exception:
        return str(status_val).lower() == "active"

@router.get("/{user_id}/reminders",
            response_model=List[ReminderDue],
            status_code=status.HTTP_200_OK)
def list_user_reminders(
    user_id: UUID,
    as_of: datetime | None = Query(None, description="Optional ISO timestamp; defaults to now (UTC)"),
    db: Session = Depends(get_db),
):
    # SQLite stores PK as TEXT → cast UUID to str for lookups
    user_pk = str(user_id)
    user = db.get(UserORM, user_pk)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Compute the user's local "today" window; compare in UTC (your DB stores UTC)
    now_utc = as_of.astimezone(timezone.utc) if as_of else datetime.now(timezone.utc)
    tz = ZoneInfo(user.timezone or "UTC")
    local = now_utc.astimezone(tz)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local   = local.replace(hour=23, minute=59, second=59, microsecond=999_999)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc   = end_local.astimezone(timezone.utc)

    # Pull this user's habits
    habits = db.execute(
        select(HabitORM.id, HabitORM.name, HabitORM.status)
        .where(HabitORM.user_id == user_pk)
    ).all()

    result: List[ReminderDue] = []

    for hid, hname, status_val in habits:
        if not _is_active(status_val):
            continue

        # Any event for THIS habit in today's local window? (use the correct column)
        has_event = db.execute(
            select(literal(1))
            .where(
                and_(
                    EventORM.habit_id == hid,
                    getattr(EventORM, "occurred_at_utc") >= start_utc,
                    getattr(EventORM, "occurred_at_utc") <= end_utc,
                )
            )
            .limit(1)
        ).first() is not None
        if has_event:
            continue

        # Any context overlapping today for THIS user? (correct columns: start_utc/end_utc)
        has_context_overlap = db.execute(
            select(literal(1))
            .where(
                and_(
                    ContextORM.user_id == user_pk,
                    ContextORM.start_utc <= end_utc,
                    # end_utc can be NULL (open-ended); treat NULL as open-ended
                    (ContextORM.end_utc == None) | (ContextORM.end_utc >= start_utc),
                )
            )
            .limit(1)
        ).first() is not None
        if has_context_overlap:
            continue

        result.append(ReminderDue(habit_id=hid, habit_name=hname))

    return result
@router.put("/{user_id}", response_model=User)
def replace_user(user_id: str, body: UserCreate, db: Session = Depends(get_db)):
    u = crud.users.replace(db, user_id, {"name": body.name, "email": body.email, "timezone": body.timezone})
    if not u:
        raise HTTPException(status_code=404, detail="user not found")
    return u

@router.patch("/{user_id}", response_model=User)
def patch_user(user_id: str, body: dict, db: Session = Depends(get_db)):
    u = crud.users.patch(db, user_id, body)
    if not u:
        raise HTTPException(status_code=404, detail="user not found")
    return u

@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: str, db: Session = Depends(get_db)):
    ok = crud.users.delete(db, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="user not found")
    return
