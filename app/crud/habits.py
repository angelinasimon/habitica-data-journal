from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db import HabitORM
from app.models import schemas

def create(db: Session, payload: schemas.HabitCreate, *, user_id: UUID) -> HabitORM:
    habit = HabitORM(
        user_id=user_id,
        name=payload.name,
        difficulty=payload.difficulty,  # if Enum, SQLA column can be String/Enum
        timezone=payload.timezone,
        start_date=payload.start_date,
        status="active",
    )
    db.add(habit)
    db.commit()
    db.refresh(habit)
    return habit

def get(db: Session, habit_id: UUID) -> Optional[HabitORM]:
    return db.get(HabitORM, habit_id)

def list_by_user(db: Session, user_id: UUID, *, only_active: bool, limit: int, offset: int) -> List[HabitORM]:
    stmt = select(HabitORM).where(HabitORM.user_id == user_id)
    if only_active:
        stmt = stmt.where(HabitORM.status == "active")
    return db.execute(stmt.offset(offset).limit(limit)).scalars().all()

def update(db: Session, habit_id: UUID, data: Dict[str, Any]) -> Optional[HabitORM]:
    habit = db.get(HabitORM, habit_id)
    if not habit:
        return None
    for k, v in data.items():
        setattr(habit, k, v)
    db.commit()
    db.refresh(habit)
    return habit

def set_status(db: Session, habit_id: UUID, status: schemas.HabitStatus) -> Optional[HabitORM]:
    habit = db.get(HabitORM, habit_id)
    if not habit:
        return None
    habit.status = status
    db.commit()
    db.refresh(habit)
    return habit
