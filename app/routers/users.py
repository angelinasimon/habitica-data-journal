# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.schemas import UserCreate, User  # Pydantic models
from app import crud

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
