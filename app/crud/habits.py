# app/crud/habits.py
from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db import HabitORM
from app.models import schemas
from datetime import date
from app.models.schemas import Difficulty, HabitStatus, HabitCreate

from datetime import date


def create(db, payload: HabitCreate, *, user_id: str) -> HabitORM:
    habit = HabitORM(
        user_id=user_id,
        name=payload.name,
        difficulty=payload.difficulty or Difficulty.medium,
        timezone=payload.timezone,
        start_date=payload.start_date or date.today(),
        status=HabitStatus.active,
    )
    db.add(habit); db.commit(); db.refresh(habit)
    return habit

def get(db: Session, *, habit_id: UUID, user_id: UUID) -> Optional[HabitORM]:
    stmt = select(HabitORM).where(HabitORM.id == habit_id, HabitORM.user_id == user_id)
    return db.execute(stmt).scalars().first()

def list_by_user(db: Session, *, user_id: UUID, only_active: bool, limit: int, offset: int) -> List[HabitORM]:
    stmt = select(HabitORM).where(HabitORM.user_id == user_id)
    if only_active:
        stmt = stmt.where(HabitORM.status == "active")
    return db.execute(stmt.offset(offset).limit(limit)).scalars().all()

def update(db: Session, *, habit_id: UUID, user_id: UUID, data: Dict[str, Any]) -> Optional[HabitORM]:
    habit = get(db, habit_id=habit_id, user_id=user_id)
    if not habit:
        return None
    for k, v in data.items():
        setattr(habit, k, v)
    db.commit()
    db.refresh(habit)
    return habit

def delete(db: Session, *, habit_id: UUID, user_id: UUID) -> bool:
    habit = get(db, habit_id=habit_id, user_id=user_id)
    if not habit:
        return False
    db.delete(habit)   # assumes proper FK/relationship cascade if events exist
    db.commit()
    return True

def set_status(db: Session, *, habit_id: UUID, user_id: UUID, status: schemas.HabitStatus) -> Optional[HabitORM]:
    habit = get(db, habit_id=habit_id, user_id=user_id)
    if not habit:
        return None
    habit.status = status
    db.commit()
    db.refresh(habit)
    return habit
