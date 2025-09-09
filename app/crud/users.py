# app/crud/users.py
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.db import UserORM

def _conflict(detail: str):
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

def create(db: Session, *, name: str, email: str, timezone: str | None) -> UserORM:
    user = UserORM(name=name, email=email, timezone=timezone)
    try:
        db.add(user); db.commit(); db.refresh(user)
    except IntegrityError:
        db.rollback(); _conflict("Email already exists.")
    return user

def get(db: Session, user_id: str) -> UserORM | None:  # str (uuid string)
    return db.get(UserORM, user_id)

def get_by_email(db: Session, email: str) -> Optional[UserORM]:
    stmt = select(UserORM).where(UserORM.email == email)
    return db.execute(stmt).scalars().first()

def replace(db: Session, user_id: str, data: Dict[str, Any]) -> Optional[UserORM]:
    user = db.get(UserORM, user_id)
    if not user:
        return None
    user.name = data["name"]
    user.email = data["email"]
    user.timezone = data.get("timezone")
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); _conflict("Email already exists.")
    db.refresh(user)
    return user

def patch(db: Session, user_id: str, data: Dict[str, Any]) -> Optional[UserORM]:
    user = db.get(UserORM, user_id)
    if not user:
        return None
    for k, v in data.items():
        setattr(user, k, v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); _conflict("Email already exists.")
    db.refresh(user)
    return user

def delete(db: Session, user_id: str) -> bool:
    user = db.get(UserORM, user_id)
    if not user:
        return False
    db.delete(user)
    db.commit()
    return True

def list_users(db: Session, *, limit: int = 50, offset: int = 0) -> List[UserORM]:
    stmt = select(UserORM).offset(offset).limit(limit)
    return db.execute(stmt).scalars().all()
