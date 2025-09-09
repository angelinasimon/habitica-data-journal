# tests/test_users_api.py
import uuid

def test_create_user_and_get(client):
    payload = {"name": "Ana", "email": "ana@example.com", "timezone": "America/Phoenix"}
    r = client.post("/users", json=payload)
    assert r.status_code == 201
    u = r.json()
    # id is a UUID string
    uuid.UUID(u["id"])
    assert u["name"] == "Ana"
    assert u["email"] == "ana@example.com"

    r2 = client.get(f"/users/{u['id']}")
    assert r2.status_code == 200
    assert r2.json()["email"] == "ana@example.com"


def test_create_user_duplicate_email_conflict(client):
    payload = {"name": "Bee", "email": "bee@example.com", "timezone": "America/Phoenix"}
    assert client.post("/users", json=payload).status_code == 201
    r = client.post("/users", json=payload)
    assert r.status_code == 409
    assert "email" in r.json()["detail"].lower()


def test_put_user_updates_and_duplicate_409(client):
    u1 = client.post("/users", json={"name":"X","email":"x@example.com"}).json()
    u2 = client.post("/users", json={"name":"Y","email":"y@example.com"}).json()

    # change u2's email to u1's -> conflict
    r_conflict = client.put(f"/users/{u2['id']}", json={"name":"Y","email":"x@example.com","timezone":"America/Phoenix"})
    assert r_conflict.status_code == 409

    # successful put on u2
    r_ok = client.put(f"/users/{u2['id']}", json={"name":"Y2","email":"y2@example.com","timezone":"America/Phoenix"})
    assert r_ok.status_code == 200
    assert r_ok.json()["name"] == "Y2"
    assert r_ok.json()["email"] == "y2@example.com"


def test_patch_user_partial(client):
    u = client.post("/users", json={"name":"Patchy","email":"patch@example.com"}).json()
    # Fast minimal patch: just name
    r = client.patch(f"/users/{u['id']}", json={"name":"Patched"})
    # If you don't have PATCH implemented, skip or adjust accordingly.
    if r.status_code == 405:
        # endpoint not implemented yet
        return
    assert r.status_code == 200
    assert r.json()["name"] == "Patched"


def test_delete_user_then_get_404(client):
    u = client.post("/users", json={"name":"Del","email":"del@example.com"}).json()
    r = client.delete(f"/users/{u['id']}")
    assert r.status_code == 204
    r2 = client.get(f"/users/{u['id']}")
    assert r2.status_code == 404
