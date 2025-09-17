# tests/test_reminder_job_logic.py
from datetime import datetime, timezone
from app.db import SessionLocal
from app.services import reminders

def test_run_reminder_cycle_smoke():
    with SessionLocal() as db:
        count = reminders.run_reminder_cycle(db, datetime.now(timezone.utc))
        assert isinstance(count, int)