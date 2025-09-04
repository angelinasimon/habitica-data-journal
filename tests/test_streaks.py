# tests/test_streaks.py  (or in your existing test file)
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

def test_streaks_current_and_max(client, db_session, user_factory, habit_factory, event_factory):
    tz = ZoneInfo("America/Phoenix")
    now = datetime.now(timezone.utc)

    user = user_factory(timezone="America/Phoenix")
    habit = habit_factory(user_id=user.id)

    # today + yesterday (duplicate yesterday)
    today_local = now.astimezone(tz).replace(hour=8, minute=0, second=0, microsecond=0)
    yday_local  = (today_local - timedelta(days=1)).replace(hour=20)

    event_factory(habit_id=habit.id, occurred_at=today_local.astimezone(timezone.utc))
    event_factory(habit_id=habit.id, occurred_at=yday_local.astimezone(timezone.utc))
    event_factory(habit_id=habit.id, occurred_at=(yday_local.replace(hour=9)).astimezone(timezone.utc))

    r = client.get(f"/habits/{habit.id}/streak")
    body = r.json()
    assert r.status_code == 200
    assert body["current"] == 2
    assert body["max"] >= 2
    assert body["last_completed"] is not None
