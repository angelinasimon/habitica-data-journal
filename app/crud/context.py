# app/crud/context.py
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from fastapi import HTTPException, status

from app.db import ContextORM
from app.models.schemas import ContextCreate, ContextKind

def _bad_request(detail: str):
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)

def _conflict(detail: str):
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def get(db: Session, ctx_id: int, *, user_id: str) -> Optional[ContextORM]:
    return db.query(ContextORM).filter(ContextORM.id == ctx_id, ContextORM.user_id == user_id).one_or_none()

def create_context(db: Session, *, user_id: str, payload: ContextCreate, block_overlaps_per_kind: bool = False) -> ContextORM:
    # Pydantic validator already ensures tz-awareness; store UTC
    start_utc = payload.start.astimezone(timezone.utc)
    end_utc = payload.end.astimezone(timezone.utc) if payload.end else None

    # Extra guard to produce nice 400s instead of DB 500s
    if end_utc is not None and not (end_utc > start_utc):
        _bad_request("end must be after start")

    # OPTIONAL POLICY: prevent overlaps for the same kind
    if block_overlaps_per_kind:
        # overlap if existing.start < new.end AND (existing.end IS NULL OR existing.end > new.start)
        overlap_q = (
            db.query(ContextORM)
            .filter(
                ContextORM.user_id == user_id,
                ContextORM.kind == payload.kind,
                ContextORM.start_utc < (end_utc or datetime.max.replace(tzinfo=timezone.utc)),
                or_(ContextORM.end_utc.is_(None), ContextORM.end_utc > start_utc),
            )
        )
        if overlap_q.first():
            _conflict(f"Overlapping '{payload.kind}' context already exists")

    ctx = ContextORM(
        user_id=user_id,
        kind=payload.kind,            # ContextKind is a str Enum → stored as text in your model
        start_utc=start_utc,
        end_utc=end_utc,
        data=payload.data or {},
    )
    db.add(ctx); db.commit(); db.refresh(ctx)
    return ctx
    

def list_user_contexts(db: Session, *, user_id: str, active_only: bool = False) -> List[ContextORM]:
    q = db.query(ContextORM).filter(ContextORM.user_id == user_id)
    if active_only:
        q = q.filter(or_(ContextORM.end_utc.is_(None), ContextORM.end_utc > _now_utc()))
    return q.order_by(ContextORM.start_utc.desc()).all()

def end(db: Session, *, ctx_id: int, user_id: str, end_utc: Optional[datetime] = None) -> Optional[ContextORM]:
    ctx = get(db, ctx_id, user_id=user_id)
    if not ctx:
        return None
    end_val = (end_utc or _now_utc()).astimezone(timezone.utc)
    if end_val <= ctx.start_utc:
        _bad_request("end must be after start")
    ctx.end_utc = end_val
    db.commit(); db.refresh(ctx)
    return ctx

