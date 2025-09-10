# tests/test_habits_api.py
import uuid
import contextlib
from fastapi import Depends

from app.main import app
from app.db import get_db, UserORM
from app.auth import get_current_user as auth_get_current_user  # dependency to override

def _install_user_override(client, db_session, name="H User", email=None, timezone="America/Phoenix"):
    """Create a user in the test DB and override get_current_user to return it."""
    email = email or f"h+{uuid.uuid4().hex}@example.com"
    u = UserORM(name=name, email=email, timezone=timezone)
    db_session.add(u); db_session.commit(); db_session.refresh(u)

    def override():
        return u
    app.dependency_overrides[auth_get_current_user] = override
    return u

def _remove_user_override():
    with contextlib.suppress(KeyError):
        del app.dependency_overrides[auth_get_current_user]


def test_create_habit_and_get(client, db_session):
    user = _install_user_override(client, db_session)

    r = client.post("/habits/", json={"name": "Drink Water", "difficulty": "easy"})
    assert r.status_code == 201, r.text
    h = r.json()
    assert isinstance(h["id"], int)
    assert h["name"] == "Drink Water"
    assert h["difficulty"] == "easy"

    r2 = client.get(f"/habits/{h['id']}")
    assert r2.status_code == 200
    assert r2.json()["name"] == "Drink Water"

    _remove_user_override()


def test_list_my_habits(client, db_session):
    user = _install_user_override(client, db_session)

    client.post("/habits/", json={"name": "Read", "difficulty": "medium"})
    client.post("/habits/", json={"name": "Stretch", "difficulty": "easy"})

    r = client.get("/habits/users/me")
    assert r.status_code == 200
    names = {x["name"] for x in r.json()}
    assert {"Read", "Stretch"} <= names

    _remove_user_override()


def test_duplicate_habit_name_409_case_insensitive(client, db_session):
    user = _install_user_override(client, db_session)

    assert client.post("/habits/", json={"name": "Run"}).status_code == 201
    r = client.post("/habits/", json={"name": "run"})
    assert r.status_code == 409
    assert "name" in r.json()["detail"].lower() or "already" in r.json()["detail"].lower()

    _remove_user_override()


def test_patch_habit_rename_and_status(client, db_session):
    user = _install_user_override(client, db_session)

    h = client.post("/habits/", json={"name": "Journal"}).json()
    # rename
    r1 = client.patch(f"/habits/{h['id']}", json={"name": "Journal Daily"})
    assert r1.status_code == 200
    assert r1.json()["name"] == "Journal Daily"
    # change difficulty + status
    r2 = client.patch(f"/habits/{h['id']}", json={"difficulty": "hard", "status": "paused"})
    assert r2.status_code == 200
    body = r2.json()
    assert body["difficulty"] == "hard"
    assert body["status"] == "paused"

    _remove_user_override()


def test_delete_habit_then_404(client, db_session):
    user = _install_user_override(client, db_session)

    h = client.post("/habits/", json={"name": "DeleteMe"}).json()
    r = client.delete(f"/habits/{h['id']}")
    assert r.status_code == 204
    r2 = client.get(f"/habits/{h['id']}")
    assert r2.status_code == 404

    _remove_user_override()


def test_get_streak_no_events(client, db_session):
    user = _install_user_override(client, db_session)

    h = client.post("/habits/", json={"name": "Streakless"}).json()
    r = client.get(f"/habits/{h['id']}/streak")
    # If your streak endpoint returns {current,max,last_completed}
    assert r.status_code == 200
    data = r.json()
    assert data["current"] == 0
    assert data["max"] == 0
    assert data["last_completed"] is None

    _remove_user_override()

def test_pause_and_resume_habit(client, db_session):
    user = _install_user_override(client, db_session)

    # Create habit (starts active)
    h = client.post("/habits/", json={"name": "PauseTest"}).json()
    assert h["status"] == "active"

    # Pause
    r1 = client.post(f"/habits/{h['id']}/pause")
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["status"] == "paused"

    # Resume
    r2 = client.post(f"/habits/{h['id']}/resume")
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["status"] == "active"

    _remove_user_override()


def test_pause_nonexistent_habit_404(client, db_session):
    _install_user_override(client, db_session)
    r = client.post("/habits/999999/pause")
    assert r.status_code == 404
    _remove_user_override()
