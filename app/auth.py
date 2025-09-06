# app/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db import get_db, UserORM

router = APIRouter(prefix="/auth", tags=["auth"])  # ← this is what main.py imports

def get_current_user(db: Session = Depends(get_db)) -> UserORM:
    user = db.query(UserORM).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No users in DB")
    return user

@router.get("/me")
def read_me(current_user: UserORM = Depends(get_current_user)):
    return {"id": str(current_user.id), "email": getattr(current_user, "email", None)}
