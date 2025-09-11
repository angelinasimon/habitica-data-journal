# tests/test_contexts_api.py
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import Depends
from app.main import app
from app.db import UserORM
from app.auth import get_current_user as auth_get_current_user
from app.routers.context import get_current_user as auth_get_current_user

def _install_user_override(client, db_session, name="C User", email=None, timezone_str="America/Phoenix"):
    email = email or f"c+{uuid.uuid4().hex}@example.com"
    u = UserORM(name=name, email=email, timezone=timezone_str)
    db_session.add(u); db_session.commit(); db_session.refresh(u)

    def override():
        return u
    app.dependency_overrides[auth_get_current_user] = override
    return u

def _remove_user_override():
    try:
        del app.dependency_overrides[auth_get_current_user]
    except KeyError:
        pass


def test_create_and_list_contexts_me(client, db_session):
    user = _install_user_override(client, db_session)

    start = datetime(2025, 1, 5, 12, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=3)

    # create
    r = client.post("/contexts", json={
        "kind": "travel",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "data": {"city": "NYC"} 
    })
    assert r.status_code == 201, r.text
    ctx = r.json()
    assert ctx["kind"] == "travel"
    assert ctx["data"]["city"] == "NYC"

    # list mine (now just GET /contexts)
    r2 = client.get("/contexts")
    assert r2.status_code == 200
    items = r2.json()
    assert any(c["id"] == ctx["id"] for c in items)

    _remove_user_override()

def test_active_only_filter(client, db_session):
    user = _install_user_override(client, db_session)
    now = datetime(2025, 1, 10, 12, 0, tzinfo=timezone.utc)

    # active: start yesterday, no end
    a = client.post("/contexts", json={
        "kind": "exam",
        "start": (now - timedelta(days=1)).isoformat(),
        "end": None,
    })
    # inactive: ended
    b = client.post("/contexts", json={
        "kind": "travel",
        "start": (now - timedelta(days=5)).isoformat(),
        "end": (now - timedelta(days=2)).isoformat(),
    })
    assert a.status_code == 201 and b.status_code == 201

    # list active_only (again just GET /contexts)
    r = client.get("/contexts", params={"active_only": True})
    assert r.status_code == 200
    kinds = {c["kind"] for c in r.json()}
    assert "exam" in kinds
    assert "travel" not in kinds

    _remove_user_override()