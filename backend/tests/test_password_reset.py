"""Forgot password: e-mailed one-time link, admin link when there is no e-mail, old log-ins end."""
from datetime import datetime, timedelta

import pytest

from conftest import Api


@pytest.fixture
def mails(monkeypatch):
    """Pretend SMTP is set up and catch the e-mails instead of sending them."""
    from app import api as api_module
    from app import reminders
    sent = []
    monkeypatch.setattr(api_module, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(reminders, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(reminders, "send_mail", lambda msg: sent.append(msg))
    return sent


def link_in(msg):
    return next(line for line in msg.get_content().splitlines() if "/#/reset/" in line).strip()


def token_of(link):
    return link.rsplit("/", 1)[1]


def test_forgot_password_by_email(api, client, mails):
    r = client.post("/api/auth/forgot", json={"email": " ADMIN@test.no"})
    assert r.json() == {"ok": True, "mail_enabled": True}
    assert len(mails) == 1 and mails[0]["To"] == "admin@test.no"
    token = token_of(link_in(mails[0]))
    assert client.get(f"/api/auth/reset/{token}").json() == {"email": "admin@test.no", "name": "Fabio"}
    r = client.post(f"/api/auth/reset/{token}", json={"password": "newpass1"})
    assert r.status_code == 200 and r.json()["user"]["email"] == "admin@test.no"
    # new password works, old one doesn't, the link is used up
    assert client.post("/api/auth/login", json={"email": "admin@test.no", "password": "newpass1"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "admin@test.no", "password": "secret123"}).status_code == 401
    assert client.post(f"/api/auth/reset/{token}", json={"password": "again123"}).status_code == 404


def test_unknown_address_gets_the_same_answer(api, client, mails):
    r = client.post("/api/auth/forgot", json={"email": "nobody@test.no"})
    assert r.json() == {"ok": True, "mail_enabled": True} and mails == []


def test_without_smtp_nothing_is_sent(api, client):
    assert client.post("/api/auth/forgot", json={"email": "admin@test.no"}).json() == {"ok": True, "mail_enabled": False}


def test_reset_logs_out_other_devices(api, client, mails):
    old = api  # logged in before the reset
    old.get("/api/me")
    client.post("/api/auth/forgot", json={"email": "admin@test.no"})
    r = client.post(f"/api/auth/reset/{token_of(link_in(mails[0]))}", json={"password": "newpass1"})
    old.get("/api/me", expect=401)
    Api(client, r.json()["token"]).get("/api/me")  # the device that reset stays logged in


def test_newest_link_wins_and_mails_are_limited(api, client, mails):
    for _ in range(5):
        client.post("/api/auth/forgot", json={"email": "admin@test.no"})
    assert len(mails) == 3  # at most three per hour
    first, last = token_of(link_in(mails[0])), token_of(link_in(mails[-1]))
    assert client.get(f"/api/auth/reset/{first}").status_code == 404
    assert client.get(f"/api/auth/reset/{last}").status_code == 200


def test_expired_link(api, client, mails):
    from app import models as m
    from app.db import SessionLocal
    client.post("/api/auth/forgot", json={"email": "admin@test.no"})
    with SessionLocal() as db:
        for r in db.query(m.PasswordReset):
            r.expires_at = datetime.utcnow() - timedelta(minutes=1)
        db.commit()
    assert client.get(f"/api/auth/reset/{token_of(link_in(mails[0]))}").status_code == 410


def test_admin_link_for_a_member(api, client):
    api.post("/api/users", {"name": "Kid", "email": "kid@test.no", "password": "secret123"})
    kid = next(u for u in api.get("/api/users") if u["email"] == "kid@test.no")
    out = api.post(f"/api/users/{kid['id']}/reset-link")
    assert "/#/reset/" in out["link"] and out["hours"] == 2
    r = client.post(f"/api/auth/reset/{token_of(out['link'])}", json={"password": "kidnew1"})
    assert r.status_code == 200
    assert client.post("/api/auth/login", json={"email": "kid@test.no", "password": "kidnew1"}).status_code == 200
    # a creator can't make links, and nobody can for people outside the group
    kid_api = Api(client, r.json()["token"])
    me = api.get("/api/me")
    kid_api.post(f"/api/users/{me['id']}/reset-link", expect=403)
    api.post("/api/users/9999/reset-link", expect=404)
