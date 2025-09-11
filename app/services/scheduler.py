# app/services/scheduler.py
import os
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("scheduler")

def _reminder_job():
    """Entry point APScheduler calls. Opens its own DB session."""
    from app.db import SessionLocal  # import here to avoid circulars
    from app.services import reminders

    db = SessionLocal()
    try:
        now_utc = datetime.now(timezone.utc)
        count = reminders.run_reminder_cycle(db, now_utc)
        logger.info("Reminder cycle finished; %s due items.", count)
    except Exception:
        logger.exception("Reminder cycle failed")
    finally:
        db.close()

def _create_scheduler() -> BackgroundScheduler:
    """
    One scheduler per process. We run in UTC and convert to each user's local
    day when computing what's due.
    """
    job_defaults = {
        "coalesce": True,      # if we missed a run (server slept), run once
        "max_instances": 1     # no overlapping reminder jobs
    }
    sched = BackgroundScheduler(timezone="UTC", job_defaults=job_defaults)

    # Dev default: run every 15 minutes; prod: set REMINDER_INTERVAL_MINUTES=60
    minutes = int(os.getenv("REMINDER_INTERVAL_MINUTES", "15"))
    sched.add_job(
        _reminder_job,
        trigger=IntervalTrigger(minutes=minutes),
        id="reminders:interval",
        replace_existing=True,
        misfire_grace_time=60,
    )
    return sched

def start_scheduler(app) -> None:
    """
    Start once per worker. Safe in dev if you set DISABLE_SCHEDULER=1 for pytest.
    """
    if os.getenv("DISABLE_SCHEDULER", "0") == "1":
        logger.info("Scheduler disabled by env (DISABLE_SCHEDULER=1)")
        return
    if getattr(app.state, "scheduler", None):
        logger.info("Scheduler already present on app.state; skipping")
        return

    sched = _create_scheduler()
    sched.start()
    app.state.scheduler = sched
    logger.info("Scheduler started")

def shutdown_scheduler(app) -> None:
    sched = getattr(app.state, "scheduler", None)
    if sched:
        try:
            sched.shutdown(wait=False)
        finally:
            app.state.scheduler = None
        logger.info("Scheduler stopped")