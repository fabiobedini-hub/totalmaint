"""TotalMant Admin: the separate console for the server's administrator."""
import pytest
from fastapi.testclient import TestClient

from conftest import Api

HOME = ("192.168.1.20", 50000)


@pytest.fixture
def admin(client):
    """The console, opened from the home network and logged in."""
    from app.admin_main import _fails, app as admin_app
    _fails.clear()
    with TestClient(admin_app, client=HOME) as c:
        assert c.post("/api/login", json={"password": "admin-test-password"}).status_code == 200
        yield c


def register(client, email, family):
    r = client.post("/api/auth/signup", json={"name": email.split("@")[0], "email": email,
                                               "password": "secret123", "group_name": family})
    assert r.status_code == 200, r.text
    return Api(client, r.json()["token"])


def test_only_home_network_and_tailscale(client):
    from app.admin_main import app as admin_app, allowed_address
    assert allowed_address("192.168.1.20") and allowed_address("10.0.0.5") and allowed_address("100.101.102.103")
    assert allowed_address("127.0.0.1") and allowed_address("172.18.0.1") and allowed_address("fd7a:115c:a1e0::1")
    assert not allowed_address("8.8.8.8") and not allowed_address("2a01:4f8::1") and not allowed_address("testclient")
    with TestClient(admin_app, client=("81.166.10.10", 4000)) as outside:
        assert outside.get("/").status_code == 403
        assert outside.post("/api/login", json={"password": "admin-test-password"}).status_code == 403


def test_login_password_and_lockout(client):
    from app.admin_main import _fails, app as admin_app
    _fails.clear()
    with TestClient(admin_app, client=HOME) as c:
        assert c.get("/api/dashboard").status_code == 401
        assert c.get("/api/status").json()["configured"] is True
        for _ in range(5):
            assert c.post("/api/login", json={"password": "wrong"}).status_code == 401
        assert c.post("/api/login", json={"password": "admin-test-password"}).status_code == 429  # locked
    _fails.clear()


def test_family_account_cannot_use_console(api, client):
    from app.admin_main import app as admin_app
    with TestClient(admin_app, client=HOME) as c:
        r = c.get("/api/users", headers={"Authorization": api.h["Authorization"]})
        assert r.status_code == 401  # the app's own log-in means nothing here


def test_dashboard_and_events(api, client, admin):
    register(client, "ola@test.no", "Familien Nordmann")
    client.post("/api/auth/login", json={"email": "ola@test.no", "password": "secret123"})
    d = admin.get("/api/dashboard").json()
    assert d["totals"]["families"] == 2 and d["totals"]["users"] == 2
    assert d["today"]["families"]["now"] == 2 and d["today"]["logins"]["now"] >= 1
    kinds = [e["kind"] for e in d["recent"]]
    assert "signup" in kinds and "setup" in kinds


def test_families_show_counts_not_content(api, client, admin):
    ola = register(client, "ola@test.no", "Familien Nordmann")
    boat = ola.asset("Boat", "boat")
    ola.task(boat["id"], "Antifouling")
    fams = {f["name"]: f for f in admin.get("/api/families").json()}
    nord = fams["Familien Nordmann"]
    assert nord["things"] == 1 and nord["tasks"] == 1 and nord["owner"]["email"] == "ola@test.no"
    detail = admin.get(f"/api/families/{nord['id']}").json()
    assert detail["counts"]["things_by_kind"] == {"boat": 1}
    assert "Antifouling" not in str(detail) and "Boat" not in str(detail)


def test_reset_link_block_and_delete_user(api, client, admin):
    ola = register(client, "ola@test.no", "Familien Nordmann")
    uid = ola.get("/api/me")["id"]
    link = admin.post(f"/api/users/{uid}/reset-link").json()["link"]
    assert client.post(f"/api/auth/reset/{link.rsplit('/', 1)[1]}", json={"password": "olanew1"}).status_code == 200
    # block: open session ends, log-in refused
    ola = Api(client, client.post("/api/auth/login", json={"email": "ola@test.no", "password": "olanew1"}).json()["token"])
    admin.post(f"/api/users/{uid}/block", json={"blocked": True})
    ola.get("/api/me", expect=403)
    assert client.post("/api/auth/login", json={"email": "ola@test.no", "password": "olanew1"}).status_code == 403
    admin.post(f"/api/users/{uid}/block", json={"blocked": False})
    assert client.post("/api/auth/login", json={"email": "ola@test.no", "password": "olanew1"}).status_code == 200
    # delete: their lonely family goes too
    r = admin.delete(f"/api/users/{uid}").json()
    assert r["families_deleted"] == ["Familien Nordmann"]
    assert [f["name"] for f in admin.get("/api/families").json()] == ["Family"]


def test_only_owner_with_members_must_hand_over(api, client, admin):
    ola = register(client, "ola@test.no", "Familien Nordmann")
    inv = ola.post("/api/invitations", {"email": "kari@test.no"})
    client.post(f"/api/invite/{inv['link'].rsplit('/', 1)[1]}/accept", json={"name": "Kari", "password": "secret123"})
    assert admin.delete(f"/api/users/{ola.get('/api/me')['id']}").status_code == 400


def test_delete_family(api, client, admin):
    ola = register(client, "ola@test.no", "Familien Nordmann")
    ola.asset("Boat", "boat")
    ola.post("/api/vendors", {"company": "Båtverft"})
    gid = ola.get("/api/me")["group"]["id"]
    r = admin.delete(f"/api/families/{gid}").json()
    assert r["accounts_deleted"] == ["ola@test.no"]
    assert client.post("/api/auth/login", json={"email": "ola@test.no", "password": "secret123"}).status_code == 401
    api.get("/api/me")  # the other family is untouched


def test_signup_settings_from_console(api, client, admin):
    body = {"name": "X", "email": "x@test.no", "password": "secret123", "group_name": "X"}
    admin.put("/api/settings/signup", json={"mode": "closed"})
    assert client.get("/api/auth/status").json()["signup_enabled"] is False
    assert client.post("/api/auth/signup", json=body).status_code == 403
    code = admin.get("/api/settings/new-code").json()["code"]
    admin.put("/api/settings/signup", json={"mode": "code", "code": code})
    assert client.get("/api/auth/status").json()["signup_needs_code"] is True
    assert client.post("/api/auth/signup", json=body).status_code == 403
    assert client.post("/api/auth/signup", json={**body, "code": code}).status_code == 200
    admin.put("/api/settings/signup", json={"mode": "env"})
    assert admin.get("/api/settings").json()["signup_from"] == ".env"


def test_backup_now_and_download(api, admin):
    r = admin.post("/api/backups").json()
    assert r["ok"] and r["name"].startswith("db-")
    files = admin.get("/api/backups").json()["files"]
    assert files[0]["name"] == r["name"]
    assert admin.get(f"/api/backups/{r['name']}").status_code == 200
    assert admin.get("/api/backups/..%2Fsecret.key").status_code in (400, 404)


def test_system_and_mail_pages(api, admin):
    s = admin.get("/api/system").json()
    assert s["database"] == "SQLite" and any(t["name"] == "users" and t["rows"] == 1 for t in s["tables"])
    assert admin.get("/api/mail").json()["configured"] is False
    assert admin.post("/api/mail/test", json={"to": "a@b.no"}).json()["ok"] is False
    assert admin.get("/api/events").json()["events"]


def test_messages_follow_the_language(client):
    from app.admin_main import _fails, app as admin_app
    _fails.clear()
    with TestClient(admin_app, client=HOME) as c:
        for lang, word in [("en", "Wrong password"), ("no", "Feil passord"), ("it", "Password sbagliata")]:
            r = c.post("/api/login", json={"password": "nope"}, headers={"X-Lang": lang})
            assert r.json()["detail"] == word
    _fails.clear()
    with TestClient(admin_app, client=("81.166.10.10", 4000)) as outside:
        assert "rete di casa" in outside.get("/", headers={"Accept-Language": "it-IT,it;q=0.9"}).json()["detail"]


def test_events_carry_key_and_values_for_translation(api, client, admin):
    register(client, "ola@test.no", "Familien Nordmann")
    ev = next(e for e in admin.get("/api/events?kind=signup").json()["events"])
    assert ev["msg"] == "signup" and ev["params"] == {"name": "ola", "email": "ola@test.no", "family": "Familien Nordmann"}
    assert ev["text"] == "ola <ola@test.no> registered Familien Nordmann"  # English stays for older viewers and search
