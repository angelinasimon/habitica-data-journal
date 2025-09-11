from uuid import UUID
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.models import schemas
from app.db import get_db
from app import crud
from app.auth import get_current_user   # make sure this import exists


router = APIRouter(prefix="/contexts", tags=["contexts"])

@router.post("", response_model=schemas.ContextRead, status_code=status.HTTP_201_CREATED)
def create_context(
    payload: schemas.ContextCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return crud.context.create_context(db, user_id=current_user.id, payload=payload)

# Replace the old users/{user_id} route with a "me" lister that matches tests
@router.get("", response_model=List[schemas.ContextRead])
def list_my_contexts(
    active_only: bool = Query(False, description="Only contexts whose window includes 'now'"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    return crud.context.list_user_contexts(db, user_id=current_user.id, active_only=active_only)
    return crud.context.list_contexts(db, user_id=user_id, active_only=active_only)