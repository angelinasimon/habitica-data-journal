from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.models import schemas
from app.db import get_db
from app import crud  # you’ll implement functions noted below

router = APIRouter(prefix="/habits", tags=["habits"])

@router.post("", response_model=schemas.HabitRead, status_code=status.HTTP_201_CREATED)
def create_habit(payload: schemas.HabitCreate, db: Session = Depends(get_db)):
    habit = crud.habits.create(db, payload)  # expects HabitCreate
    return habit

@router.get("/{habit_id}", response_model=schemas.HabitRead)
def get_habit(habit_id: UUID, db: Session = Depends(get_db)):
    habit = crud.habits.get(db, habit_id)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    return habit

# List a user’s habits (lives here for convenience, even though path starts with /users)
@router.get("/users/{user_id}", response_model=List[schemas.HabitRead])
def list_user_habits(
    user_id: UUID,
    db: Session = Depends(get_db),
    only_active: bool = Query(False, description="If true, return only active habits"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items = crud.habits.list_by_user(db, user_id, only_active=only_active, limit=limit, offset=offset)
    return items

@router.put("/{habit_id}")
def update_habit(habit_id: str):
    return {"ok": True, "route": "PUT /habits/{id}", "habit_id": habit_id}

@router.delete("/{habit_id}", status_code=204)
def delete_habit(habit_id: str):
    return

@router.patch("/{habit_id}", response_model=schemas.HabitRead)
def update_habit(habit_id: UUID, patch: schemas.HabitPatch, db: Session = Depends(get_db)):
    update_data = patch.model_dump(exclude_unset=True, exclude_none=True)
    if not update_data:
        # nothing to do – you can return 200 with current state, or 400; 200 is friendlier
        habit = crud.habits.get(db, habit_id)
        if not habit:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found")
        return habit

    habit = crud.habits.update(db, habit_id, update_data)
    if not habit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found")
    return habit

@router.patch("/{habit_id}/resume", response_model=schemas.HabitRead)
def resume_habit(habit_id: UUID, db: Session = Depends(get_db)):
    habit = crud.habits.set_status(db, habit_id, schemas.HabitStatus.active)
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    return habit