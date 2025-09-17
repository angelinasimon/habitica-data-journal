import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

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
    One scheduler per process.
    If REMINDER_CRON is set, use it. Otherwise fall back to REMINDER_INTERVAL_MINUTES.
    """
    from app.core.settings import settings

    job_defaults = {
        "coalesce": True,   # collapse missed runs into one
        "max_instances": 1  # no overlapping jobs
    }

    tz = ZoneInfo(settings.TIMEZONE)
    sched = BackgroundScheduler(timezone=tz, job_defaults=job_defaults)

    if settings.REMINDER_CRON:  # prefer CRON when provided
        trigger = CronTrigger.from_crontab(settings.REMINDER_CRON, timezone=tz)
        sched.add_job(
            _reminder_job,
            trigger=trigger,
            id="reminders:cron",
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info("Scheduler configured with CRON=%s TZ=%s", settings.REMINDER_CRON, settings.TIMEZONE)
    else:
        minutes = int(settings.REMINDER_INTERVAL_MINUTES)
        sched.add_job(
            _reminder_job,
            trigger=IntervalTrigger(minutes=minutes),
            id="reminders:interval",
            replace_existing=True,
            misfire_grace_time=60,
        )
        logger.info("Scheduler configured with interval=%s min TZ=%s", minutes, settings.TIMEZONE)

    return sched

def start_scheduler(app) -> None:
    """
    Start once per worker. Safe in dev. Respects TESTING/DISABLE_SCHEDULER.
    """
    from app.core.settings import settings

    if settings.DISABLE_SCHEDULER or settings.TESTING:
        logger.info("Scheduler disabled (DISABLE_SCHEDULER=%s, TESTING=%s)", settings.DISABLE_SCHEDULER, settings.TESTING)
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
