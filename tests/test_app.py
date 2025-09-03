from fastapi.testclient import TestClient
from uuid import uuid4
from app.main import app

client = TestClient(app)

def test_ping():
    r = client.get("/ping")
    assert r.status_code == 200
    assert r.json()["message"] == "pong"

def test_create_user():
    unique = str(uuid4())
    payload = {
        "name": "A",
        "email": f"a+{unique}@example.com",
        "timezone": "America/Phoenix"
    }
    r = client.post("/users", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert "id" in body and len(body["id"]) > 10
    assert body["email"].startswith("a+") and body["email"].endswith("@example.com")
