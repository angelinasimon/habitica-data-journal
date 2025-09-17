# app/services/reminders.py
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, or_

from app.db import UserORM, HabitORM, EventORM, ContextORM
from app.models.schemas import ReminderDue

# If you store status as Enum on the ORM, import that Enum;
# otherwise we'll compare strings safely inside _is_active.
try:
    from app.models.schemas import HabitStatus  # your Enum lives in schemas
except Exception:
    HabitStatus = None


def _local_day_bounds(as_of_utc: datetime, tz: ZoneInfo):
    local = as_of_utc.astimezone(tz)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = local.replace(hour=23, minute=59, second=59, microsecond=999_999)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _is_active(status_value) -> bool:
    """Allow either Enum or plain string for habit.status."""
    if HabitStatus and isinstance(status_value, HabitStatus):
        return status_value == HabitStatus.active
    return str(status_value).lower() == "active"


def _has_active_context(db, user_id, day_start_utc: datetime, day_end_utc: datetime) -> bool:
    """Return True if any context overlaps [day_start_utc, day_end_utc]."""
    user_id_str = str(user_id)  # <<< IMPORTANT for SQLite TEXT PKs
    q = (
        select(ContextORM.id)
        .where(
            ContextORM.user_id == user_id_str,
            ContextORM.start_utc <= day_end_utc,
            # allow open-ended contexts: end_utc IS NULL OR end_utc >= day_start
            or_(ContextORM.end_utc == None, ContextORM.end_utc >= day_start_utc),
        )
        .limit(1)
    )
    return db.execute(q).first() is not None


def get_due_habits(db, user: UserORM, as_of_utc: datetime):
    """
    Return a list of ReminderDue for THIS user:
      - only ACTIVE habits
      - that have NO events in the user's local day window
      - and are NOT suppressed by an active context window
    """
    tz = ZoneInfo(user.timezone or "UTC")
    day_start_utc, day_end_utc = _local_day_bounds(as_of_utc, tz)

    # If any context is active for this user today, mute all reminders.
    if _has_active_context(db, user.id, day_start_utc, day_end_utc):
        return []

    # Fetch this user's habits (owner scoped)
    user_id_str = str(user.id)
    habits = db.execute(
        select(HabitORM.id, HabitORM.name, HabitORM.status).where(HabitORM.user_id == user_id_str)
    ).all()

    due: list[ReminderDue] = []
    for hid, hname, status in habits:
        if not _is_active(status):
            continue

        # Any event today for this habit?
        has_event = (
            db.execute(
                select(EventORM.id)
                .where(
                    EventORM.habit_id == hid,
                    EventORM.occurred_at_utc >= day_start_utc,
                    EventORM.occurred_at_utc <= day_end_utc,
                )
                .limit(1)
            ).first()
            is not None
        )
        if not has_event:
            due.append(ReminderDue(habit_id=hid, habit_name=hname))

    return due


def run_reminder_cycle(db, as_of_utc: datetime) -> int:
    """
    One full pass: for each user, compute due habits and log them.
    Returns the total number of due items found.
    """
    import logging
    logger = logging.getLogger("scheduler")

    total = 0
    users = db.execute(select(UserORM)).scalars().all()

    for user in users:
        for item in get_due_habits(db, user, as_of_utc):
            logger.info("[Reminder] User %s: %s due today", user.id, item.habit_name)
            total += 1

    return total
