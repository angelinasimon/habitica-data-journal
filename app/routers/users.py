# app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
from uuid import UUID
from app.db import get_db, UserORM
from app.models.schemas import UserCreate, User  # Pydantic input/output

router = APIRouter()

# POST /users: insert a user, 201; if email exists, 409
@router.post("", response_model=User, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db)):
  u = UserORM(name=body.name, email=body.email, timezone=body.timezone)
  db.add(u)
  try:
    db.commit()
  except IntegrityError:
    db.rollback()
    raise HTTPException(status_code=409, detail="email already exists")
  db.refresh(u)  # load DB-generated fields (timestamps)
  return User(
    id=UUID(u.id),
    name=u.name,
    email=u.email,
    timezone=u.timezone,
    created_at=u.created_at or datetime.now(timezone.utc),
    updated_at=u.updated_at or datetime.now(timezone.utc),
  )

# GET /users/{id}: fetch; 200 or 404
@router.get("/{user_id}", response_model=User)
def get_user(user_id: str, db: Session = Depends(get_db)):
  u = db.get(UserORM, user_id)
  if not u:
    raise HTTPException(status_code=404, detail="user not found")
  return User(
    id=UUID(u.id),
    name=u.name,
    email=u.email,
    timezone=u.timezone,
    created_at=u.created_at,
    updated_at=u.updated_at,
  )

# PUT /users/{id}: update fields; handle duplicate emails (409)
@router.put("/{user_id}", response_model=User)
def update_user(user_id: str, body: UserCreate, db: Session = Depends(get_db)):
  u = db.get(UserORM, user_id)
  if not u:
    raise HTTPException(status_code=404, detail="user not found")
  u.name = body.name
  u.email = body.email
  u.timezone = body.timezone
  try:
    db.commit()
  except IntegrityError:
    db.rollback()
    raise HTTPException(status_code=409, detail="email already exists")
  db.refresh(u)
  return User(
    id=UUID(u.id),
    name=u.name,
    email=u.email,
    timezone=u.timezone,
    created_at=u.created_at,
    updated_at=u.updated_at,
  )

# DELETE /users/{id}: delete the record if found (204 either way is fine for idempotency)
@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: str, db: Session = Depends(get_db)):
  u = db.get(UserORM, user_id)
  if u:
    db.delete(u)
    db.commit()
  return  # 204 No Content

