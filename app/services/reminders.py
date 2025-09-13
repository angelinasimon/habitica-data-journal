from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from app.db import UserORM, HabitORM, EventORM, ContextORM
# If you have an Enum for status, import it:
try:
    from app.db import HabitStatus  # adjust if it lives elsewhere
except Exception:
    HabitStatus = None

def _local_day_bounds(as_of_utc: datetime, tz: ZoneInfo):
    local = as_of_utc.astimezone(tz)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local   = local.replace(hour=23, minute=59, second=59, microsecond=999_999)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

def _has_active_context(db, user_id, day_start_utc: datetime, day_end_utc: datetime) -> bool:
    # ✅ compare using the raw user_id value (let SQLAlchemy handle types)
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

def _is_active(status_value) -> bool:
    # ✅ handle both Enum and string storage
    if HabitStatus and isinstance(status_value, HabitStatus):
        return status_value == HabitStatus.active
    # strings like "active", "ACTIVE", etc.
    return str(status_value).lower() == "active"

def get_due_habits(db, user: UserORM, as_of_utc: datetime):
    tz = ZoneInfo(user.timezone or "UTC")
    day_start_utc, day_end_utc = _local_day_bounds(as_of_utc, tz)

    if _has_active_context(db, user.id, day_start_utc, day_end_utc):
        return []

    # ✅ no string casts; let SA bind the correct type for user.id
    habits = db.execute(
    select(HabitORM.id, HabitORM.name, HabitORM.status)
    .where(HabitORM.user_id == str(user.id))
    ).all()

    suppressed = db.execute(
        select(ContextORM.id)
        .where(
            ContextORM.user_id == str(user.id),
            ContextORM.start_utc <= day_end_utc,
            ContextORM.end_utc >= day_start_utc,
        )
        .limit(1)
    ).first() is not None

    due = []
    for hid, hname, status in habits:
        if not _is_active(status):
            continue

        has_event = db.execute(
            select(EventORM.id)
            .where(
                EventORM.habit_id == hid,
                # ✅ use the same timestamp column your Event writer uses:
                EventORM.occurred_at_utc >= day_start_utc,
                EventORM.occurred_at_utc <= day_end_utc,
            )
            .limit(1)
        ).first() is not None

        if not has_event:
            due.append((hid, hname))
    return due

def run_reminder_cycle(db, as_of_utc: datetime) -> int:
    """
    One full pass: for each user, compute due habits and log them.
    Returns the total number of due items found.
    """
    # If not already declared at top of file:
    # import logging
    # logger = logging.getLogger("scheduler")

    total = 0

    # Fetch all users once (lets SQLAlchemy bind the correct PK type)
    users = db.execute(select(UserORM)).scalars().all()

    for user in users:
        # Your helper returns a list of (habit_id, habit_name) for THIS user
        due = get_due_habits(db, user, as_of_utc)
        for habit_id, habit_name in due:
            logger.info("[Reminder] User %s: %s due today", user.id, habit_name)
            total += 1

    return total
