from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from app.models import schemas
from app.db import EventORM, HabitORM
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

def _canon(s: str) -> str:
    return s.strip().lower()

def _conflict(detail: str):
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

def create(db: Session, payload: schemas.EventCreate) -> Optional[EventORM]:
    # ensure habit exists
    if not db.get(HabitORM, payload.habit_id):
        return None
    event = EventORM(
        habit_id=payload.habit_id,
        occurred_at=payload.occurred_at,  # already normalized by schema validator
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event

def list_for_habit(
    db: Session,
    habit_id: UUID,
    *,
    start: Optional[datetime],
    end: Optional[datetime],
    limit: int,
    offset: int,
) -> List[EventORM]:
    stmt = select(EventORM).where(EventORM.habit_id == habit_id)
    if start is not None:
        stmt = stmt.where(EventORM.occurred_at >= start)
    if end is not None:
        stmt = stmt.where(EventORM.occurred_at < end)
    stmt = stmt.order_by(EventORM.occurred_at.desc()).offset(offset).limit(limit)
    return db.execute(stmt).scalars().all()

def log_event(
    db: Session, *, habit_id: int, occurred_at_utc: datetime, note: str | None = None
) -> EventORM:
    ev = EventORM(habit_id=habit_id, occurred_at_utc=occurred_at_utc, note=note)
    try:
        db.add(ev); db.commit(); db.refresh(ev)
    except IntegrityError:
        db.rollback(); _conflict("Event already exists at that timestamp for this habit.")
    return ev

def list_events(
    db: Session, *, habit_id: int, start: datetime | None = None, end: datetime | None = None,
    limit: int = 1000
) -> list[EventORM]:
    q = db.query(EventORM).filter(EventORM.habit_id == habit_id)
    if start: q = q.filter(EventORM.occurred_at_utc >= start)
    if end:   q = q.filter(EventORM.occurred_at_utc < end)
    return q.order_by(EventORM.occurred_at_utc.asc()).limit(limit).all()

def delete_event(db: Session, ev: EventORM) -> None:
    db.delete(ev); db.commit()