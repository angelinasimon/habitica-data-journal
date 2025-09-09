from typing import Optional, Dict, Any, List
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.db import HabitORM
from app.models.schemas import Difficulty, HabitStatus, HabitCreate, HabitPatch

def _canon(s: str) -> str:
    return s.strip().lower()

def _conflict(detail: str):
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

def _to_enum(val, enum_cls):
    if val is None or isinstance(val, enum_cls):
        return val
    return enum_cls(val)

# ---- aligned names to match router ----

def create(db: Session, payload: HabitCreate, *, user_id: str) -> HabitORM:
    # payload has: name, difficulty?, status?
    name = payload.name
    difficulty = _to_enum(getattr(payload, "difficulty", Difficulty.medium), Difficulty)
    status     = _to_enum(getattr(payload, "status", HabitStatus.active), HabitStatus)

    habit = HabitORM(
        user_id=user_id,
        name=name,
        name_canonical=_canon(name),
        difficulty=difficulty or Difficulty.medium,
        status=status or HabitStatus.active,
    )
    try:
        db.add(habit); db.commit(); db.refresh(habit)
    except IntegrityError:
        db.rollback(); _conflict("You already have a habit with that name.")
    return habit

def get(db: Session, *, habit_id: int, user_id: str) -> HabitORM | None:
    # enforce ownership
    return db.query(HabitORM).filter(
        HabitORM.id == habit_id,
        HabitORM.user_id == user_id
    ).one_or_none()

def get_by_name(db: Session, *, user_id: str, name: str) -> HabitORM | None:
    return (
        db.query(HabitORM)
        .filter(HabitORM.user_id == user_id, HabitORM.name_canonical == _canon(name))
        .one_or_none()
    )

def list_by_user(
    db: Session, *, user_id: str, only_active: bool | None = None, limit: int = 100, offset: int = 0
) -> list[HabitORM]:
    q = db.query(HabitORM).filter(HabitORM.user_id == user_id)
    if only_active:
        q = q.filter(HabitORM.status == HabitStatus.active)
    return q.order_by(HabitORM.created_at.desc()).offset(offset).limit(limit).all()

def update(
    db: Session, *, habit_id: int, user_id: str, data: dict
) -> HabitORM | None:
    habit = get(db, habit_id=habit_id, user_id=user_id)
    if not habit:
        return None

    # handle rename → recanonicalize
    if "name" in data:
        habit.name = data["name"]
        habit.name_canonical = _canon(data["name"])

    # enums (allow strings)
    if "difficulty" in data and data["difficulty"] is not None:
        habit.difficulty = _to_enum(data["difficulty"], Difficulty)
    if "status" in data and data["status"] is not None:
        habit.status = _to_enum(data["status"], HabitStatus)

    try:
        db.commit(); db.refresh(habit)
    except IntegrityError:
        db.rollback(); _conflict("You already have a habit with that name.")
    return habit

def delete(db: Session, *, habit_id: int, user_id: str) -> bool:
    habit = get(db, habit_id=habit_id, user_id=user_id)
    if not habit:
        return False
    db.delete(habit)
    db.commit()
    return True
