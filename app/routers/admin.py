from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.reminders import run_reminder_cycle

router = APIRouter(prefix="/admin", tags=["admin"])

@router.post("/reminders/run-once")
def run_reminders_once(db: Session = Depends(get_db)):
    count = run_reminder_cycle(db, datetime.now(timezone.utc))
    return {"checked": count}
