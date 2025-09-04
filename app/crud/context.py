from typing import List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, and_
from app.models import schemas
from app.db import ContextORM

def create(db: Session, payload: schemas.ContextCreate, *, user_id: UUID) -> ContextORM:
    ctx = ContextORM(
        user_id=user_id,
        kind=payload.kind,
        start=payload.start,
        end=payload.end,
        metadata=payload.metadata,
    )
    db.add(ctx)
    db.commit()
    db.refresh(ctx)
    return ctx

def list_for_user(db: Session, user_id: UUID, *, active_only: bool, now: datetime, limit: int, offset: int) -> List[ContextORM]:
    stmt = select(ContextORM).where(ContextORM.user_id == user_id)
    if active_only:
        # active if start <= now and (end is null or end > now)
        stmt = stmt.where(and_(ContextORM.start <= now, or_(ContextORM.end.is_(None), ContextORM.end > now)))
    return db.execute(stmt.offset(offset).limit(limit)).scalars().all()
