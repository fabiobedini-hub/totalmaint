"""Groups, roles, invitations: who sees what, and who may change what."""
from datetime import datetime, timedelta

import pytest

from conftest import Api


def login(client, email, password="secret123"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return Api(client, r.json()["token"])


def roles(api):
    return {r["key"] or r["name"]: r for r in api.get("/api/roles")}


def member(api, client, email, role_key):
    api.post("/api/users", {"name": email.split("@")[0], "email": email, "password": "secret123",
                            "role_id": roles(api)[role_key]["id"]})
    return login(client, email)


# ---------- the first user ----------
def test_setup_makes_owner_of_a_family_group(api):
    me = api.get("/api/me")
    assert me["group"]["name"] == "Family"
    assert me["role"]["key"] == "owner" and me["is_owner"] is True
    assert "assets.create" in me["permissions"] and "roles.manage" in me["permissions"]
    assert [r["key"] for r in api.get("/api/roles")] == ["owner", "admin", "creator", "viewer"]


# ---------- built-in roles ----------
def test_viewer_sees_everything_but_changes_nothing(api, client):
    a = api.asset()
    t = api.task(a["id"], "Filter")
    v = member(api, client, "viewer@test.no", "viewer")
    assert [x["name"] for x in v.get("/api/assets")] == ["House"]
    assert v.get(f"/api/tasks/{t['id']}")["title"] == "Filter"
    assert v.get("/api/me")["permissions"] == []
    v.post("/api/assets", {"name": "Car", "kind": "car"}, expect=403)
    v.post(f"/api/assets/{a['id']}/tasks", {"title": "X"}, expect=403)
    v.post(f"/api/tasks/{t['id']}/complete", {}, expect=403)
    v.delete(f"/api/tasks/{t['id']}", expect=403)


def test_creator_works_inside_things_but_cannot_create_them(api, client):
    a = api.asset()
    c = member(api, client, "creator@test.no", "creator")
    c.post("/api/assets", {"name": "Boat", "kind": "boat"}, expect=403)
    c.put(f"/api/assets/{a['id']}", {"name": "Renamed", "kind": "home"}, expect=403)
    comp = c.post(f"/api/assets/{a['id']}/components", {"name": "Heat pump"})
    t = c.task(a["id"], "Clean filter", component_id=comp["id"])
    c.put(f"/api/tasks/{t['id']}", {"title": "Clean filters", "interval_value": 1, "interval_unit": "years"})
    c.post(f"/api/tasks/{t['id']}/complete", {"cost": 100})
    c.delete(f"/api/tasks/{t['id']}", expect=403)        # no deleting by default
    c.delete(f"/api/components/{comp['id']}", expect=403)
    c.post(f"/api/assets/{a['id']}/apply-template?key=house_basic", expect=403)
    c.get("/api/invitations", expect=403)


def test_admin_edits_a_role_and_it_applies_at_once(api, client):
    a = api.asset()
    c = member(api, client, "creator@test.no", "creator")
    t = c.task(a["id"], "Paint")
    c.delete(f"/api/tasks/{t['id']}", expect=403)
    creator = roles(api)["creator"]
    api.put(f"/api/roles/{creator['id']}", {"name": "Creator", "permissions": creator["permissions"] + ["tasks.delete"]})
    c.delete(f"/api/tasks/{t['id']}")
    # and taking create away again
    api.put(f"/api/roles/{creator['id']}", {"name": "Creator", "permissions": []})
    c.post(f"/api/assets/{a['id']}/tasks", {"title": "X"}, expect=403)


def test_custom_role(api, client):
    a = api.asset("Car", "car", counter_unit="km")
    mech = api.post("/api/roles", {"name": "Mechanic", "permissions": ["tasks.complete", "counters.record", "nonsense"]})
    assert mech["permissions"] == ["tasks.complete", "counters.record"] and mech["builtin"] is False
    t = api.task(a["id"], "Oil change")
    api.post("/api/users", {"name": "Mek", "email": "mek@test.no", "password": "secret123", "role_id": mech["id"]})
    mek = login(client, "mek@test.no")
    mek.post(f"/api/tasks/{t['id']}/complete", {"counter_value": 12000})
    mek.post(f"/api/assets/{a['id']}/counter", {"value": 12500})
    mek.post(f"/api/assets/{a['id']}/tasks", {"title": "X"}, expect=403)
    # deleting the role turns its members into viewers
    api.delete(f"/api/roles/{mech['id']}")
    assert mek.get("/api/me")["role"]["key"] == "viewer"


def test_owner_role_is_locked_and_builtins_stay(api):
    r = roles(api)
    api.put(f"/api/roles/{r['owner']['id']}", {"name": "Boss", "permissions": []}, expect=400)
    api.delete(f"/api/roles/{r['viewer']['id']}", expect=400)


def test_admin_cannot_saw_off_their_own_branch(api, client):
    adm = member(api, client, "adm@test.no", "admin")
    admin_role = roles(api)["admin"]
    adm.put(f"/api/roles/{admin_role['id']}", {"name": "Admin", "permissions": ["tasks.edit"]}, expect=400)
    me = adm.get("/api/me")
    adm.patch(f"/api/users/{me['id']}", {"role_id": roles(api)["viewer"]["id"]}, expect=400)
    # and an admin cannot touch the owner
    owner = api.get("/api/me")
    adm.patch(f"/api/users/{owner['id']}", {"role_id": roles(api)["viewer"]["id"]}, expect=403)
    adm.delete(f"/api/users/{owner['id']}", expect=403)
    adm.post("/api/users", {"name": "X", "email": "x@test.no", "password": "secret123",
                            "role_id": roles(api)["owner"]["id"]}, expect=403)


def test_transfer_ownership(api, client):
    adm = member(api, client, "adm@test.no", "admin")
    target = adm.get("/api/me")["id"]
    adm.post("/api/group/transfer-owner", {"user_id": target}, expect=403)
    api.post("/api/group/transfer-owner", {"user_id": target})
    assert adm.get("/api/me")["is_owner"] is True
    assert api.get("/api/me")["role"]["key"] == "admin"


# ---------- separate groups ----------
def signup(client, monkeypatch, email, group):
    from app import api as api_module
    monkeypatch.setattr(api_module, "SIGNUP_CODE", "letmein")
    r = client.post("/api/auth/signup", json={"name": "Other", "email": email, "password": "secret123",
                                               "group_name": group, "code": "letmein"})
    assert r.status_code == 200, r.text
    return Api(client, r.json()["token"])


def test_register_new_family_is_open_by_default(api, client):
    body = {"name": "Ola", "email": "ola@test.no", "password": "secret123", "group_name": "Familien Nordmann"}
    assert client.get("/api/auth/status").json()["signup_enabled"] is True
    r = client.post("/api/auth/signup", json=body)
    assert r.status_code == 200, r.text
    me = Api(client, r.json()["token"]).get("/api/me")
    assert me["group"]["name"] == "Familien Nordmann" and me["is_owner"] is True
    # the same e-mail can't register twice
    r = client.post("/api/auth/signup", json={**body, "group_name": "Another"})
    assert r.status_code == 400 and "log in" in r.json()["detail"]


def test_signup_code_and_closed(api, client, monkeypatch):
    from app import api as api_module
    body = {"name": "X", "email": "x@test.no", "password": "secret123", "group_name": "X"}
    monkeypatch.setattr(api_module, "SIGNUP_CODE", "letmein")
    assert client.post("/api/auth/signup", json=body).status_code == 403
    assert client.post("/api/auth/signup", json={**body, "code": "wrong"}).status_code == 403
    assert client.post("/api/auth/signup", json={**body, "code": "letmein"}).status_code == 200
    monkeypatch.setattr(api_module, "SIGNUP_ENABLED", False)
    assert client.post("/api/auth/signup", json={**body, "email": "y@test.no", "code": "letmein"}).status_code == 403


def test_setup_with_family_name(client):
    r = client.post("/api/auth/setup", json={"name": "Fabio", "email": "f@test.no", "password": "secret123",
                                              "group_name": "Familien Bedini"})
    assert Api(client, r.json()["token"]).get("/api/me")["group"]["name"] == "Familien Bedini"


def test_logged_in_user_starts_another_family(api, client, monkeypatch):
    api.asset("House")
    g = api.post("/api/groups", {"name": "Hytta"})
    me = api.get("/api/me")
    assert me["group"]["id"] == g["id"] and me["is_owner"] is True
    assert sorted(x["name"] for x in me["groups"]) == ["Family", "Hytta"]
    assert api.get("/api/assets") == []  # the new family starts empty
    from app import api as api_module
    monkeypatch.setattr(api_module, "SIGNUP_ENABLED", False)
    api.post("/api/groups", {"name": "Båtforening"}, expect=403)


def test_groups_cannot_see_each_other(api, client, monkeypatch):
    house = api.asset()
    task = api.task(house["id"], "Secret")
    vendor = api.post("/api/vendors", {"company": "Our plumber"})
    other = signup(client, monkeypatch, "club@test.no", "Boat club")
    assert other.get("/api/me")["group"]["name"] == "Boat club"
    assert other.get("/api/assets") == [] and other.get("/api/vendors") == []
    assert other.get("/api/dashboard")["asset_count"] == 0
    assert [u["email"] for u in other.get("/api/users")] == ["club@test.no"]
    other.get(f"/api/assets/{house['id']}", expect=404)
    other.get(f"/api/tasks/{task['id']}", expect=404)
    other.put(f"/api/tasks/{task['id']}", {"title": "Hacked"}, expect=404)
    other.post(f"/api/tasks/{task['id']}/complete", {}, expect=404)
    other.get(f"/api/vendors/{vendor['id']}", expect=404)
    # can't hang their own things on our vendor or our people
    boat = other.asset("Boat", "boat")
    other.post(f"/api/assets/{boat['id']}/tasks", {"title": "X", "vendor_id": vendor["id"]}, expect=400)
    me = api.get("/api/me")
    other.post(f"/api/assets/{boat['id']}/tasks", {"title": "X", "assigned_to_id": me["id"]}, expect=400)
    # calendar of the first group doesn't show the boat club's things
    other.task(boat["id"], "Antifouling")
    titles = {e["title"] for e in api.get("/api/calendar", params={"start": "2000-01-01", "end": "2000-12-31"})}
    assert "Antifouling" not in titles
    assert all(t["title"] != "Antifouling" for t in api.get("/api/tasks"))


# ---------- invitations ----------
def test_invite_new_person(api, client):
    viewer = roles(api)["viewer"]
    inv = api.post("/api/invitations", {"email": "Guest@Test.no", "role_id": viewer["id"]})
    assert inv["email"] == "guest@test.no" and inv["mailed"] is False and "/#/invite/" in inv["link"]
    token = inv["link"].rsplit("/", 1)[1]
    info = client.get(f"/api/invite/{token}").json()
    assert info == {"group_name": "Family", "email": "guest@test.no", "role_name": "Viewer",
                    "invited_by": "Fabio", "has_account": False}
    r = client.post(f"/api/invite/{token}/accept", json={"name": "Guest", "password": "secret123"})
    assert r.status_code == 200, r.text
    guest = Api(client, r.json()["token"])
    assert guest.get("/api/me")["role"]["key"] == "viewer"
    # one-time
    assert client.get(f"/api/invite/{token}").status_code == 404
    assert client.post(f"/api/invite/{token}/accept", json={"name": "G", "password": "secret123"}).status_code == 404
    assert api.get("/api/invitations") == []


def test_invite_existing_account_into_second_group(api, client, monkeypatch):
    other = signup(client, monkeypatch, "club@test.no", "Boat club")
    inv = other.post("/api/invitations", {"email": "admin@test.no"})  # default role: creator
    token = inv["link"].rsplit("/", 1)[1]
    assert client.get(f"/api/invite/{token}").json()["has_account"] is True
    assert client.post(f"/api/invite/{token}/accept", json={"password": "wrong12"}).status_code == 401
    r = client.post(f"/api/invite/{token}/accept", json={"password": "secret123"})
    me = Api(client, r.json()["token"]).get("/api/me")
    assert me["group"]["name"] == "Boat club" and me["role"]["key"] == "creator"
    assert sorted(g["name"] for g in me["groups"]) == ["Boat club", "Family"]
    # switching back
    family = next(g for g in me["groups"] if g["name"] == "Family")
    api.post("/api/me/group", {"group_id": family["id"]})
    assert api.get("/api/me")["group"]["name"] == "Family"
    # the header picks a group for one request too
    club = next(g for g in me["groups"] if g["name"] == "Boat club")
    assert api.get("/api/me", headers={"X-Group-Id": str(club["id"])})["group"]["name"] == "Boat club"
    # removing them from the club keeps the account
    uid = me["id"]
    other.delete(f"/api/users/{uid}")
    assert api.get("/api/me")["group"]["name"] == "Family"


def test_expired_and_cancelled_invites(api, client):
    from app import models as m
    from app.db import SessionLocal
    inv = api.post("/api/invitations", {"email": "late@test.no"})
    token = inv["link"].rsplit("/", 1)[1]
    with SessionLocal() as db:
        row = db.get(m.Invitation, inv["id"])
        row.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
    assert client.get(f"/api/invite/{token}").status_code == 410
    inv2 = api.post("/api/invitations", {"email": "never@test.no"})
    api.delete(f"/api/invitations/{inv2['id']}")
    assert client.get(f"/api/invite/{inv2['link'].rsplit('/', 1)[1]}").status_code == 404


def test_cannot_invite_a_member_twice(api):
    api.post("/api/invitations", {"email": "admin@test.no"}, expect=400)


# ---------- the upgrade of an existing database ----------
def test_existing_data_becomes_the_family_group(client):
    """Simulates the NAS: users, things and vendors from before groups existed."""
    from app import models as m
    from app.auth import hash_password, new_ical_token
    from app.db import SessionLocal
    from app.permissions import migrate_to_groups
    with SessionLocal() as db:
        fabio = m.User(name="Fabio", email="fabio@test.no", password_hash=hash_password("secret123"),
                       is_admin=True, lang="no", ical_token=new_ical_token())
        wife = m.User(name="Wife", email="wife@test.no", password_hash=hash_password("secret123"),
                      ical_token=new_ical_token())
        helper = m.User(name="Helper", email="help@test.no", password_hash=hash_password("secret123"),
                        is_admin=True, ical_token=new_ical_token())
        db.add_all([fabio, wife, helper, m.Asset(name="Hus"), m.Vendor(company="Rørlegger")])
        db.commit()
        assert "Familien" in migrate_to_groups(db)
        assert migrate_to_groups(db) is None  # second start: nothing to do
    f = login(client, "fabio@test.no")
    me = f.get("/api/me")
    assert me["group"]["name"] == "Familien" and me["is_owner"] is True
    assert [x["name"] for x in f.get("/api/assets")] == ["Hus"]
    assert [v["company"] for v in f.get("/api/vendors")] == ["Rørlegger"]
    by_mail = {u["email"]: u["role_key"] for u in f.get("/api/users")}
    assert by_mail == {"fabio@test.no": "owner", "wife@test.no": "creator", "help@test.no": "admin"}
    # Norwegian user: role names in Norwegian
    assert [r["name"] for r in f.get("/api/roles")] == ["Eier", "Administrator", "Bidragsyter", "Leser"]


@pytest.mark.parametrize("path", ["/api/assets", "/api/me", "/api/roles"])
def test_user_without_group_is_refused(client, path):
    from app import models as m
    from app.auth import hash_password, new_ical_token
    from app.db import SessionLocal
    with SessionLocal() as db:
        db.add(m.User(name="Lost", email="lost@test.no", password_hash=hash_password("secret123"),
                      ical_token=new_ical_token()))
        db.commit()
    assert login(client, "lost@test.no").c.get(path, headers=login(client, "lost@test.no").h).status_code == 403


def test_italian_user_gets_italian_roles_and_messages(client):
    r = client.post("/api/auth/setup", json={"name": "Fabio", "email": "it@test.no", "password": "secret123", "lang": "it"})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    roles = {x["key"]: x["name"] for x in client.get("/api/roles", headers=h).json()}
    assert roles == {"owner": "Proprietario", "admin": "Amministratore", "creator": "Collaboratore", "viewer": "Lettore"}
    labels = {x["key"]: x["label"] for x in client.get("/api/permissions", headers=h).json()}
    assert labels["tasks.create"] == "Creare attività"
    assert client.get("/api/me", headers=h).json()["lang"] == "it"
