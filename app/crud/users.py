from typing import Optional, Dict, Any, List
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db import UserORM
from app.models import schemas


class DuplicateEmailError(Exception):
    """Raised when a unique-email conflict occurs."""
    pass


def create(db: Session, payload: schemas.UserCreate) -> UserORM:
    user = UserORM(name=payload.name, email=payload.email, timezone=payload.timezone)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Assuming `email` has a UNIQUE constraint in your DB model/migration
        raise DuplicateEmailError("email already exists")
    db.refresh(user)
    return user


def get(db: Session, user_id: UUID) -> Optional[UserORM]:
    return db.get(UserORM, user_id)


def get_by_email(db: Session, email: str) -> Optional[UserORM]:
    stmt = select(UserORM).where(UserORM.email == email)
    
    return db.execute(stmt).scalars().first()


def replace(db: Session, user_id: UUID, data: Dict[str, Any]) -> Optional[UserORM]:
    """
    Full update (PUT semantics): all mutable fields must be present in `data`.
    """
    user = db.get(UserORM, user_id)
    if not user:
        return None

    user.name = data["name"]
    user.email = data["email"]
    user.timezone = data.get("timezone")

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateEmailError("email already exists")
    db.refresh(user)
    return user


def patch(db: Session, user_id: UUID, data: Dict[str, Any]) -> Optional[UserORM]:
    """
    Partial update (PATCH semantics): only fields in `data` are modified.
    """
    user = db.get(UserORM, user_id)
    if not user:
        return None

    for k, v in data.items():
        setattr(user, k, v)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DuplicateEmailError("email already exists")
    db.refresh(user)
    return user


def delete(db: Session, user_id: UUID) -> bool:
    user = db.get(UserORM, user_id)
    if not user:
        return False
    db.delete(user)
    db.commit()
    return True


def list_users(db: Session, *, limit: int = 50, offset: int = 0) -> List[UserORM]:
    stmt = select(UserORM).offset(offset).limit(limit)
    return db.execute(stmt).scalars().all()
