# tests/test_analytics.py
import os
from types import SimpleNamespace
from uuid import uuid4
from datetime import datetime, timezone
import pytest

from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="function")
def client(db_session):
    os.environ["DISABLE_SCHEDULER"] = "1"
    with TestClient(app) as c:
        yield c

def _iso(dtstr):
    # dtstr like "2025-09-01T10:00:00Z"
    return dtstr

def test_weekly_completion_two_weeks(client):
    # 1) Create user
    r = client.post("/users", json={
        "email": f"weekly+{uuid4().hex[:8]}@example.com",
        "name": "Weekly User",
        "timezone": "America/Phoenix",
    })
    assert r.status_code in (200, 201), r.text
    user = r.json()
    user_id = user["id"]

    # 2) Override auth to return this user for analytics routes
    from app.auth import get_current_user
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=user_id)

    try:
        # 3) Create a daily habit
        r = client.post("/habits/", json={
            "user_id": user_id,
            "name": "Hydrate"
            # Include other required fields if your API needs them (e.g., frequency/status)
        })
        assert r.status_code in (200, 201), r.text
        habit = r.json()
        habit_id = habit["id"]

        # 4) Log events: 5 days in week starting 2025-09-01, 6 days in week starting 2025-09-08
        week1_days = ["2025-09-01","2025-09-02","2025-09-03","2025-09-04","2025-09-05"]      # 5/7
        week2_days = ["2025-09-08","2025-09-09","2025-09-10","2025-09-11","2025-09-12","2025-09-13"]  # 6/7

        for d in week1_days + week2_days:
            r = client.post("/events/", json={
                "habit_id": habit_id,
                "occurred_at": f"{d}T10:00:00Z"  # one event per day
            })
            assert r.status_code in (200, 201), r.text

        # 5) Call analytics with explicit window (Mon 9/01 through Sun 9/14)
        r = client.get("/analytics/weekly", params={
            "start": "2025-09-01",
            "end":   "2025-09-14",
        })
        assert r.status_code == 200, r.text
        data = r.json()

        # 6) Assert structure & values
        assert isinstance(data, list) and len(data) >= 2
        assert data[0]["week_start"] == "2025-09-01"
        assert data[1]["week_start"] == "2025-09-08"

        # Allow tiny float error
        assert abs(data[0]["completion_pct"] - (5/7)) < 1e-6
        assert abs(data[1]["completion_pct"] - (6/7)) < 1e-6
    finally:
        app.dependency_overrides.clear()
