"""Accounts, login and who may do what."""


def test_first_setup_then_closed(client):
    assert client.get("/api/auth/status").json() == {"needs_setup": True, "signup_enabled": False}
    r = client.post("/api/auth/setup", json={"name": "A", "email": "A@Test.no", "password": "secret123"})
    assert r.status_code == 200 and r.json()["user"]["is_admin"] is True
    assert client.get("/api/auth/status").json()["needs_setup"] is False
    again = client.post("/api/auth/setup", json={"name": "B", "email": "b@test.no", "password": "secret123"})
    assert again.status_code == 400


def test_login(api, client):
    assert client.post("/api/auth/login", json={"email": "ADMIN@test.no ", "password": "secret123"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "admin@test.no", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "nobody@test.no", "password": "secret123"}).status_code == 401


def test_api_needs_login(client):
    assert client.get("/api/assets").status_code == 401
    assert client.get("/api/assets", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_only_admin_manages_users(api, client):
    api.post("/api/users", {"name": "Kid", "email": "kid@test.no", "password": "secret123"})
    token = client.post("/api/auth/login", json={"email": "kid@test.no", "password": "secret123"}).json()["token"]
    kid = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/users", json={"name": "X", "email": "x@test.no", "password": "secret123"}, headers=kid)
    assert r.status_code == 403
    assert client.get("/api/assets", headers=kid).status_code == 200  # but can use the app


def test_admin_cannot_lock_themselves_out(api):
    me = api.get("/api/me")
    api.delete(f"/api/users/{me['id']}", expect=400)
    api.patch(f"/api/users/{me['id']}", {"is_admin": False}, expect=400)


def test_duplicate_email_refused(api):
    api.post("/api/users", {"name": "Kid", "email": "kid@test.no", "password": "secret123"})
    api.post("/api/users", {"name": "Kid 2", "email": "KID@test.no", "password": "secret123"}, expect=400)
