# app/services/reminders.py
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select

# Adjust these imports to your project:
# - If your ORM models live in app.db, import from there
# - Or if you have app.models.orm, import from there
from app.db import UserORM, HabitORM, EventORM, ContextORM  # <-- adjust if needed

logger = logging.getLogger("reminders")

def _local_day_bounds(as_of_utc: datetime, tz: ZoneInfo):
    """Return the start/end of that user's local day, expressed back in UTC."""
    local = as_of_utc.astimezone(tz)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local   = local.replace(hour=23, minute=59, second=59, microsecond=999_999)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

def _has_active_context(db, user_id, day_start_utc: datetime, day_end_utc: datetime) -> bool:
    """
    Minimal policy: any context overlapping the local day suppresses reminders.
    Later you can refine (e.g., only suppress certain habit kinds).
    """
    q = (
        select(ContextORM.id)
        .where(
            ContextORM.user_id == user_id,
            ContextORM.start_utc <= day_end_utc,
            ContextORM.end_utc   >= day_start_utc,
        )
        .limit(1)
    )
    return db.execute(q).first() is not None

def get_due_habits(db, as_of_utc: datetime):
    """
    Returns a list of (user_id, habit_id, habit_name) that are due today
    per each user's local day, have no event today, and are not paused/hidden.
    """
    due = []

    # Fetch all users with their timezones (you can paginate if large)
    users = db.execute(select(UserORM.id, UserORM.timezone)).all()

    for user_id, tzname in users:
        tz = ZoneInfo(tzname or "UTC")
        day_start_utc, day_end_utc = _local_day_bounds(as_of_utc, tz)

        # Decide if any active context suppresses reminders today
        suppress_all = _has_active_context(db, user_id, day_start_utc, day_end_utc)

        # Active, non-paused habits
        habits = db.execute(
            select(HabitORM.id, HabitORM.name, HabitORM.status)
            .where(HabitORM.user_id == user_id)
        ).all()

        for hid, hname, status in habits:
            if status != "active":
                continue
            if suppress_all:
                continue

            # Any event for this habit in the user's local day?
            event_exists = db.execute(
                select(EventORM.id)
                .where(
                    EventORM.habit_id == hid,
                    EventORM.occurred_at_utc >= day_start_utc,
                    EventORM.occurred_at_utc <= day_end_utc,
                )
                .limit(1)
            ).first() is not None

            if not event_exists:
                due.append((user_id, hid, hname))
    return due

def run_reminder_cycle(db, as_of_utc: datetime) -> int:
    """
    One full pass: compute dues and log them (hook for future email/push).
    Returns how many due items were found (for metrics/tests).
    """
    items = get_due_habits(db, as_of_utc)
    for user_id, habit_id, name in items:
        logger.info("[Reminder] User %s: %s due today", user_id, name)
        # TODO: enqueue push/email/OS notifications here
    return len(items)
