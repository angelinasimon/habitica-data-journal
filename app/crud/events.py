from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from app.models import schemas
from app.db import EventORM, HabitORM

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
