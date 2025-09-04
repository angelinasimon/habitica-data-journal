from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.models import schemas
from app.db import get_db
from app import crud

router = APIRouter(prefix="/contexts", tags=["contexts"])

@router.post("", response_model=schemas.ContextRead, status_code=status.HTTP_201_CREATED)
def create_context(payload: schemas.ContextCreate, db: Session = Depends(get_db)):
    ctx = crud.contexts.create(db, payload)
    return ctx

# List contexts for a user with optional active_only filter (mounted here; path begins /users)
@router.get("/users/{user_id}", response_model=List[schemas.ContextRead])
def list_user_contexts(
    user_id: UUID,
    db: Session = Depends(get_db),
    active_only: bool = Query(False, description="Only contexts whose window includes 'now'"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items = crud.contexts.list_for_user(db, user_id, active_only=active_only, limit=limit, offset=offset)
    return items
