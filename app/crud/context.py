from typing import List
from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, or_, and_
from app.models import schemas
from app.db import ContextORM
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.schemas import ContextKind

def _canon(s: str) -> str:
    return s.strip().lower()

def _conflict(detail: str):
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

def create_context(
    db: Session, *,
    user_id: str,
    kind: ContextKind = ContextKind.custom,
    start_utc: datetime,
    end_utc: datetime | None,
    data: dict | None = None,
) -> ContextORM:
    ctx = ContextORM(
        user_id=user_id,
        kind=kind,
        start_utc=start_utc,
        end_utc=end_utc,
        data=data or {},
    )
    db.add(ctx); db.commit(); db.refresh(ctx); return ctx

def list_contexts(
    db: Session, *, user_id: str, active_only: bool = False
) -> list[ContextORM]:
    q = db.query(ContextORM).filter(ContextORM.user_id == user_id)
    if active_only:
        q = q.filter((ContextORM.end_utc.is_(None)) | (ContextORM.end_utc > utcnow()))
    return q.order_by(ContextORM.start_utc.desc()).all()

def end_context(db: Session, ctx: ContextORM, end_utc: datetime) -> ContextORM:
    ctx.end_utc = end_utc
    db.commit(); db.refresh(ctx); return ctx

