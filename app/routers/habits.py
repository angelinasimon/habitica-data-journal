from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.models import schemas
from app.db import get_db
from app import crud
from app.services.streaks import compute_streaks, NotFound

router = APIRouter(prefix="/habits", tags=["habits"])

@router.post("/", response_model=schemas.HabitRead, status_code=status.HTTP_201_CREATED)
def create_habit(
    payload: schemas.HabitCreate,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    return crud.habits.create(db, payload, user_id=current_user.id)

@router.get("/{habit_id}", response_model=schemas.HabitRead)
def get_habit(
    habit_id: int,  # <-- int, not UUID
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    habit = crud.habits.get(db, habit_id=habit_id, user_id=current_user.id)
    if not habit:
        raise HTTPException(404, "Habit not found")
    return habit

@router.get("/users/me", response_model=List[schemas.HabitRead])
def list_my_habits(
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user),
    only_active: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return crud.habits.list_by_user(
        db, user_id=current_user.id, only_active=only_active, limit=limit, offset=offset
    )

@router.get("/{habit_id}/streak", response_model=schemas.Streak)
def get_habit_streak(
    habit_id: int,  # <-- int
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user),
    as_of: datetime | None = Query(None),
):
    if as_of and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    try:
        return compute_streaks(db, habit_id, user_id=current_user.id, as_of=as_of)
    except NotFound:
        raise HTTPException(404, "Habit not found")

@router.patch("/{habit_id}", response_model=schemas.HabitRead)
def patch_habit(
    habit_id: int,  # <-- int
    patch: schemas.HabitPatch,
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    data = patch.model_dump(exclude_unset=True, exclude_none=True)
    habit = crud.habits.update(db, habit_id=habit_id, user_id=current_user.id, data=data)
    if not habit:
        raise HTTPException(404, "Habit not found")
    return habit

@router.delete("/{habit_id}", status_code=204)
def delete_habit(
    habit_id: int,  # <-- int
    db: Session = Depends(get_db),
    current_user: schemas.User = Depends(get_current_user)
):
    ok = crud.habits.delete(db, habit_id=habit_id, user_id=current_user.id)
    if not ok:
        raise HTTPException(404, "Habit not found")
    return
@router.post("/{habit_id}/pause", response_model=schemas.HabitRead)
def pause_habit(habit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    h = crud.habits.get(db, habit_id=habit_id, user_id=current_user.id)
    if not h: raise HTTPException(404, "Habit not found")
    return crud.habits.update(db, habit_id=habit_id, user_id=current_user.id, data={"status": "paused"})

@router.post("/{habit_id}/resume", response_model=schemas.HabitRead)
def resume_habit(habit_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    h = crud.habits.get(db, habit_id=habit_id, user_id=current_user.id)
    if not h: raise HTTPException(404, "Habit not found")
    return crud.habits.update(db, habit_id=habit_id, user_id=current_user.id, data={"status": "active"})
