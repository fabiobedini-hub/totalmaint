"""TotalMant Admin – the console for whoever runs the server (not for the families).

A separate web app on its own port (NAS: 8081). It shares the database and the code with
TotalMaint, but:
  * it only answers to home-network / Tailscale addresses (ADMIN_ALLOW_NETS),
  * it has its own log-in: the ADMIN_PASSWORD from .env, not a family account,
  * it sees every family and account, but only counts of what is inside a family.

Run locally:   python -m uvicorn app.admin_main:app --port 8001   (from the backend folder)
"""
import gzip
import ipaddress
import os
import platform
import secrets
import shutil
import sqlite3
import subprocess
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import events
from . import models as m
from .api import _new_reset, _purge_asset, signup_settings
from .config import (ADMIN_ALLOW_NETS, ADMIN_DIR, ADMIN_PASSWORD, ADMIN_SESSION_HOURS, ADMINER_URL, APP_VERSION,
                     BACKUP_DIR, DATABASE_URL, INVITE_DAYS, PUBLIC_URL, RESET_HOURS, SECRET_KEY, SMTP_FROM,
                     SMTP_HOST, SMTP_PORT, SMTP_USER, UPLOAD_DIR)
from .db import get_db
from .permissions import memberships_of
from .reminders import send_mail

COOKIE = "tm_admin"
STARTED = datetime.now(timezone.utc)

app = FastAPI(title="TotalMant Admin", version=APP_VERSION, docs_url=None, redoc_url=None, openapi_url=None)
router = APIRouter(prefix="/api")


# ---------------------------------------------------------------- who may knock at the door
def _networks():
    if ADMIN_ALLOW_NETS.strip() == "*":
        return None
    return [ipaddress.ip_network(n.strip(), strict=False) for n in ADMIN_ALLOW_NETS.split(",") if n.strip()]


_NETS = _networks()


def allowed_address(host: Optional[str]) -> bool:
    if _NETS is None:
        return True
    try:
        ip = ipaddress.ip_address((host or "").split("%")[0])
    except ValueError:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return any(ip in n for n in _NETS)


@app.middleware("http")
async def home_network_only(request: Request, call_next):
    host = request.client.host if request.client else None
    if not allowed_address(host):
        return JSONResponse({"detail": "TotalMant Admin only answers on the home network or Tailscale"}, 403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# ---------------------------------------------------------------- log-in (one password, from .env)
_fails: dict[str, list[float]] = {}  # address -> times of recent wrong passwords
MAX_FAILS, LOCK_MINUTES = 5, 15


def _password_fingerprint() -> str:
    """Part of the session: changing ADMIN_PASSWORD logs every open console out."""
    import hashlib
    return hashlib.sha256(f"tm-admin:{ADMIN_PASSWORD}".encode()).hexdigest()[:16]


def _session_token() -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"aud": "tm-admin", "pw": _password_fingerprint(), "iat": int(now.timestamp()),
                       "exp": now + timedelta(hours=ADMIN_SESSION_HOURS)}, SECRET_KEY, algorithm="HS256")


def admin_session(request: Request) -> bool:
    token = request.cookies.get(COOKIE)
    if not token or not ADMIN_PASSWORD:
        raise HTTPException(401, "Log in")
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"], audience="tm-admin")
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired, log in again")
    if data.get("pw") != _password_fingerprint():
        raise HTTPException(401, "The admin password has changed, log in again")
    return True


class LoginIn(BaseModel):
    password: str


@router.get("/status")
def status():
    return {"configured": len(ADMIN_PASSWORD) >= 10, "version": APP_VERSION}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    if len(ADMIN_PASSWORD) < 10:
        raise HTTPException(503, "Set ADMIN_PASSWORD (at least 10 characters) in .env and restart")
    who = request.client.host if request.client else "?"
    now = time.time()
    recent = [t for t in _fails.get(who, []) if now - t < LOCK_MINUTES * 60]
    if len(recent) >= MAX_FAILS:
        raise HTTPException(429, f"Too many wrong passwords: wait {LOCK_MINUTES} minutes")
    if not secrets.compare_digest(body.password.encode(), ADMIN_PASSWORD.encode()):
        recent.append(now)
        _fails[who] = recent
        events.log(db, "admin_login", f"Wrong admin password from {who}")
        db.commit()
        raise HTTPException(401, "Wrong password")
    _fails.pop(who, None)
    events.log(db, "admin_login", f"Admin console log-in from {who}")
    db.commit()
    response.set_cookie(COOKIE, _session_token(), httponly=True, samesite="strict",
                        secure=request.url.scheme == "https", max_age=ADMIN_SESSION_HOURS * 3600)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}


# ---------------------------------------------------------------- helpers
def _day_start(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


def _count(db: Session, q) -> int:
    return db.scalar(q) or 0


def _count_events(db: Session, kinds, start: datetime, end: datetime) -> int:
    kinds = [kinds] if isinstance(kinds, str) else kinds
    return _count(db, select(func.count(m.Event.id)).where(m.Event.kind.in_(kinds), m.Event.at >= start, m.Event.at < end))


def _created(db: Session, model, start: datetime, end: datetime) -> int:
    return _count(db, select(func.count(model.id)).where(model.created_at >= start, model.created_at < end))


def _done(db: Session, start: date, end: date) -> int:
    return _count(db, select(func.count(m.Completion.id)).where(m.Completion.done_on >= start, m.Completion.done_on < end))


def _event_out(e: m.Event, names: dict) -> dict:
    return {"id": e.id, "at": e.at.isoformat() + "Z", "kind": e.kind, "label": events.KINDS.get(e.kind, e.kind),
            "text": e.text, "user_id": e.user_id, "group_id": e.group_id, "group_name": names.get(e.group_id)}


def _group_names(db: Session) -> dict:
    return dict(db.execute(select(m.Group.id, m.Group.name)).all())


def _uploads_size() -> tuple[int, int]:
    n = size = 0
    if UPLOAD_DIR.exists():
        for f in UPLOAD_DIR.iterdir():
            if f.is_file():
                n += 1
                size += f.stat().st_size
    return n, size


def _backups() -> list[dict]:
    if not BACKUP_DIR.exists():
        return []
    files = [f for f in BACKUP_DIR.iterdir() if f.is_file() and f.name.startswith("db-")]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return [{"name": f.name, "size": f.stat().st_size,
             "at": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat()} for f in files]


def _last_login(db: Session) -> dict:
    rows = db.execute(select(m.Event.user_id, func.max(m.Event.at)).where(m.Event.kind == "login")
                      .group_by(m.Event.user_id)).all()
    return {uid: at.isoformat() + "Z" for uid, at in rows if uid}


# ---------------------------------------------------------------- dashboard
@router.get("/dashboard")
def dashboard(_: bool = Depends(admin_session), db: Session = Depends(get_db)):
    today = date.today()
    t0, y0 = _day_start(today), _day_start(today - timedelta(days=1))
    t1 = t0 + timedelta(days=1)
    month0 = _day_start(today.replace(day=1))
    # the same stretch of last month: 1st .. same day (shorter months: their last day)
    prev_end_day = today.replace(day=1) - timedelta(days=1)
    prev0 = _day_start(prev_end_day.replace(day=1))
    prev1 = _day_start(prev_end_day.replace(day=min(today.day, prev_end_day.day))) + timedelta(days=1)

    def pair(fn):
        return {"now": fn(t0, t1), "before": fn(y0, t0)}

    def month(fn):
        return {"now": fn(month0, t1), "before": fn(prev0, prev1)}

    active_families = lambda a, b: len({  # noqa: E731 – families with a log-in or finished work in [a, b)
        *[g for (g,) in db.execute(select(m.Event.group_id).where(m.Event.kind == "login", m.Event.at >= a,
                                                                  m.Event.at < b, m.Event.group_id.is_not(None)))],
        *[g for (g,) in db.execute(select(m.Asset.group_id).join(m.Task, m.Task.asset_id == m.Asset.id)
                                   .join(m.Completion, m.Completion.task_id == m.Task.id)
                                   .where(m.Completion.done_on >= a.date(), m.Completion.done_on < b.date()))],
    })
    files, size = _uploads_size()
    names = _group_names(db)
    recent = db.scalars(select(m.Event).where(m.Event.kind.not_in(["login", "admin_login"]))
                        .order_by(m.Event.at.desc(), m.Event.id.desc()).limit(12))
    last_reminder = db.scalars(select(m.Event).where(m.Event.kind == "reminders").order_by(m.Event.at.desc()).limit(1)).first()
    backups = _backups()
    mode, _code = signup_settings(db)
    return {
        "today": {
            "families": pair(lambda a, b: _created(db, m.Group, a, b)),
            "users": pair(lambda a, b: _created(db, m.User, a, b)),
            "logins": pair(lambda a, b: _count_events(db, "login", a, b)),
            "tasks_done": pair(lambda a, b: _done(db, a.date(), b.date())),
            "mails": pair(lambda a, b: _count_events(db, "mail_sent", a, b)),
            "mail_errors": pair(lambda a, b: _count_events(db, "mail_failed", a, b)),
        },
        "month": {
            "active_families": month(active_families),
            "new_families": month(lambda a, b: _created(db, m.Group, a, b)),
            "new_users": month(lambda a, b: _created(db, m.User, a, b)),
            "tasks_done": month(lambda a, b: _done(db, a.date(), b.date())),
        },
        "totals": {
            "families": _count(db, select(func.count(m.Group.id))),
            "users": _count(db, select(func.count(m.User.id))),
            "blocked": _count(db, select(func.count(m.User.id)).where(m.User.blocked.is_(True))),
            "things": _count(db, select(func.count(m.Asset.id))),
            "tasks": _count(db, select(func.count(m.Task.id)).where(m.Task.active.is_(True))),
            "open_invites": _count(db, select(func.count(m.Invitation.id)).where(
                m.Invitation.accepted_at.is_(None), m.Invitation.expires_at >= datetime.utcnow())),
            "files": files, "files_size": size,
        },
        "recent": [_event_out(e, names) for e in recent],
        "server": {
            "version": APP_VERSION, "signup": mode, "mail": bool(SMTP_HOST),
            "last_backup": backups[0]["at"] if backups else None,
            "last_reminders": (last_reminder.at.isoformat() + "Z") if last_reminder else None,
        },
    }


# ---------------------------------------------------------------- families
def _family_rows(db: Session) -> list[dict]:
    assets = dict(db.execute(select(m.Asset.group_id, func.count(m.Asset.id)).group_by(m.Asset.group_id)).all())
    tasks = dict(db.execute(select(m.Asset.group_id, func.count(m.Task.id)).join(m.Task, m.Task.asset_id == m.Asset.id)
                            .where(m.Task.active.is_(True)).group_by(m.Asset.group_id)).all())
    last = dict(db.execute(select(m.Event.group_id, func.max(m.Event.at)).where(m.Event.group_id.is_not(None))
                           .group_by(m.Event.group_id)).all())
    out = []
    for g in db.scalars(select(m.Group).order_by(m.Group.created_at.desc(), m.Group.id.desc())):
        owner = next((x.user for x in g.memberships if x.role.key == "owner"), None)
        out.append({"id": g.id, "name": g.name, "created_at": g.created_at.isoformat() + "Z",
                    "members": len(g.memberships), "things": assets.get(g.id, 0), "tasks": tasks.get(g.id, 0),
                    "owner": {"id": owner.id, "name": owner.name, "email": owner.email} if owner else None,
                    "last_activity": (last[g.id].isoformat() + "Z") if g.id in last else None})
    return out


@router.get("/families")
def families(_: bool = Depends(admin_session), db: Session = Depends(get_db)):
    return _family_rows(db)


@router.get("/families/{group_id}")
def family(group_id: int, _: bool = Depends(admin_session), db: Session = Depends(get_db)):
    g = db.get(m.Group, group_id)
    if g is None:
        raise HTTPException(404, "Family not found")
    ids = select(m.Asset.id).where(m.Asset.group_id == g.id)
    logins = _last_login(db)
    kinds = dict(db.execute(select(m.Asset.kind, func.count(m.Asset.id)).where(m.Asset.group_id == g.id)
                            .group_by(m.Asset.kind)).all())
    task_ids = select(m.Task.id).where(m.Task.asset_id.in_(ids))
    files = db.execute(select(func.count(m.Attachment.id), func.coalesce(func.sum(m.Attachment.size), 0)).where(
        ((m.Attachment.entity_type == "asset") & m.Attachment.entity_id.in_(ids))
        | ((m.Attachment.entity_type == "task") & m.Attachment.entity_id.in_(task_ids)))).one()
    names = _group_names(db)
    return {
        "id": g.id, "name": g.name, "created_at": g.created_at.isoformat() + "Z",
        "members": [{"id": x.user_id, "name": x.user.name, "email": x.user.email, "role": x.role.name,
                     "role_key": x.role.key, "blocked": x.user.blocked, "last_login": logins.get(x.user_id),
                     "other_families": len(memberships_of(db, x.user_id)) - 1}
                    for x in sorted(g.memberships, key=lambda x: (x.role.key != "owner", x.user.name.lower()))],
        "roles": [{"name": r.name, "key": r.key, "permissions": len(r.perm_set) if r.key != "owner" else None}
                  for r in g.roles],
        "counts": {
            "things": sum(kinds.values()), "things_by_kind": kinds,
            "tasks": _count(db, select(func.count(m.Task.id)).where(m.Task.asset_id.in_(ids), m.Task.active.is_(True))),
            "done": _count(db, select(func.count(m.Completion.id)).where(m.Completion.task_id.in_(task_ids))),
            "vendors": _count(db, select(func.count(m.Vendor.id)).where(m.Vendor.group_id == g.id)),
            "files": files[0], "files_size": int(files[1] or 0),
        },
        "invites": [{"id": i.id, "email": i.email, "role": i.role.name, "expires_at": i.expires_at.isoformat() + "Z"}
                    for i in db.scalars(select(m.Invitation).where(
                        m.Invitation.group_id == g.id, m.Invitation.accepted_at.is_(None),
                        m.Invitation.expires_at >= datetime.utcnow()))],
        "events": [_event_out(e, names) for e in db.scalars(
            select(m.Event).where(m.Event.group_id == g.id).order_by(m.Event.at.desc(), m.Event.id.desc()).limit(25))],
    }


def purge_group(db: Session, g: m.Group) -> None:
    """Delete a family and everything in it, files on disk included (no commit)."""
    for a in db.scalars(select(m.Asset).where(m.Asset.group_id == g.id)):
        _purge_asset(db, a)
    db.flush()
    for v in db.scalars(select(m.Vendor).where(m.Vendor.group_id == g.id)):
        db.delete(v)
    for inv in db.scalars(select(m.Invitation).where(m.Invitation.group_id == g.id)):
        db.delete(inv)
    for u in db.scalars(select(m.User).where(m.User.current_group_id == g.id)):
        u.current_group_id = None
    for e in db.scalars(select(m.Event).where(m.Event.group_id == g.id)):
        e.group_id = None
    db.flush()
    db.delete(g)  # its roles and memberships go with it (cascade)
    db.flush()


@router.delete("/families/{group_id}")
def delete_family(group_id: int, _: bool = Depends(admin_session), db: Session = Depends(get_db)):
    """Deletes the family with all its things, history and files. Members who are in no other
    family lose their account too (they could no longer use the app)."""
    g = db.get(m.Group, group_id)
    if g is None:
        raise HTTPException(404, "Family not found")
    name, members = g.name, [x.user for x in g.memberships]
    purge_group(db, g)
    db.flush()
    gone = []
    for u in members:
        if not memberships_of(db, u.id):
            gone.append(u.email)
            db.delete(u)
        elif u.current_group_id == group_id:
            u.current_group_id = None
    events.log(db, "admin", f"Deleted family {name}" + (f" and account(s) {', '.join(gone)}" if gone else ""))
    db.commit()
    return {"ok": True, "accounts_deleted": gone}


# ---------------------------------------------------------------- users
@router.get("/users")
def users(_: bool = Depends(admin_session), db: Session = Depends(get_db)):
    logins = _last_login(db)
    return [{"id": u.id, "name": u.name, "email": u.email, "lang": u.lang, "created_at": u.created_at.isoformat() + "Z",
             "blocked": u.blocked, "is_admin": u.is_admin, "last_login": logins.get(u.id),
             "families": [{"id": x.group_id, "name": x.group.name, "role": x.role.name, "role_key": x.role.key}
                          for x in memberships_of(db, u.id)]}
            for u in db.scalars(select(m.User).order_by(m.User.created_at.desc(), m.User.id.desc()))]


def _user(db: Session, user_id: int) -> m.User:
    u = db.get(m.User, user_id)
    if u is None:
        raise HTTPException(404, "Account not found")
    return u


@router.post("/users/{user_id}/reset-link")
def reset_link(user_id: int, _: bool = Depends(admin_session), db: Session = Depends(get_db)):
    """A one-time link to choose a new password, to hand over yourself (SMS, Messenger ...)."""
    u = _user(db, user_id)
    link = _new_reset(db, u)
    events.log(db, "reset_requested", f"Admin console made a password link for {u.email}", u)
    db.commit()
    return {"link": link, "hours": RESET_HOURS}


class BlockIn(BaseModel):
    blocked: bool


@router.post("/users/{user_id}/block")
def block(user_id: int, body: BlockIn, _: bool = Depends(admin_session), db: Session = Depends(get_db)):
    """Blocked: can't log in, open sessions stop working, gets no reminders."""
    u = _user(db, user_id)
    u.blocked = body.blocked
    if body.blocked:
        u.session_version = (u.session_version or 0) + 1  # end the sessions that are open now
    events.log(db, "admin", f"{'Blocked' if body.blocked else 'Unblocked'} {u.email}", u)
    db.commit()
    return {"ok": True, "blocked": u.blocked}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, _: bool = Depends(admin_session), db: Session = Depends(get_db)):
    """Families where they were the only member go with the account. If they are the only owner of
    a family that has other members, someone else must become owner first (or delete the family)."""
    u = _user(db, user_id)
    alone, owned = [], []
    for mem in memberships_of(db, u.id):
        others = [x for x in mem.group.memberships if x.user_id != u.id]
        if not others:
            alone.append(mem.group)
        elif mem.role.key == "owner" and not any(x.role.key == "owner" for x in others):
            owned.append(mem.group.name)
    if owned:
        raise HTTPException(400, f"{u.name} is the only owner of {', '.join(owned)}, which has other members: "
                                 "they hand it over in the app first (Settings → Make owner), or delete the family")
    names = [g.name for g in alone]
    for g in alone:
        purge_group(db, g)
    for t in db.scalars(select(m.Task).where(m.Task.assigned_to_id == u.id)):
        t.assigned_to_id = None
    for mem in memberships_of(db, u.id):
        db.delete(mem)
    db.flush()
    email = u.email
    db.delete(u)
    events.log(db, "admin", f"Deleted account {email}" + (f" and family {', '.join(names)}" if names else ""))
    db.commit()
    return {"ok": True, "families_deleted": names}


# ---------------------------------------------------------------- invitations
@router.get("/invitations")
def invitations(_: bool = Depends(admin_session), db: Session = Depends(get_db)):
    now = datetime.utcnow()
    rows = db.scalars(select(m.Invitation).order_by(m.Invitation.created_at.desc()).limit(200))
    out = []
    for i in rows:
        st = "accepted" if i.accepted_at else "expired" if i.expires_at < now else "open"
        out.append({"id": i.id, "email": i.email, "family": i.group.name, "group_id": i.group_id, "role": i.role.name,
                    "invited_by": i.invited_by.name if i.invited_by else None, "status": st,
                    "created_at": i.created_at.isoformat() + "Z", "expires_at": i.expires_at.isoformat() + "Z",
                    "accepted_at": (i.accepted_at.isoformat() + "Z") if i.accepted_at else None})
    signups = db.scalars(select(m.Event).where(m.Event.kind.in_(["signup", "family_created", "setup"]))
                         .order_by(m.Event.at.desc()).limit(50))
    return {"invitations": out, "signups": [_event_out(e, _group_names(db)) for e in signups]}


@router.delete("/invitations/{invitation_id}")
def cancel_invitation(invitation_id: int, _: bool = Depends(admin_session), db: Session = Depends(get_db)):
    inv = db.get(m.Invitation, invitation_id)
    if inv is None:
        raise HTTPException(404, "Invitation not found")
    events.log(db, "admin", f"Cancelled the invitation for {inv.email} to {inv.group.name}", group_id=inv.group_id)
    db.delete(inv)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- e-mail
@router.get("/mail")
def mail(_: bool = Depends(admin_session), db: Session = Depends(get_db)):
    names = _group_names(db)
    log = db.scalars(select(m.Event).where(m.Event.kind.in_(["mail_sent", "mail_failed", "reminders"]))
                     .order_by(m.Event.at.desc(), m.Event.id.desc()).limit(100))
    return {"configured": bool(SMTP_HOST), "host": SMTP_HOST, "port": SMTP_PORT, "user": SMTP_USER,
            "sender": SMTP_FROM or SMTP_USER, "log": [_event_out(e, names) for e in log]}


class TestMailIn(BaseModel):
    to: str = Field(min_length=3, max_length=200)


@router.post("/mail/test")
def mail_test(body: TestMailIn, _: bool = Depends(admin_session), db: Session = Depends(get_db)):
    from email.message import EmailMessage
    if not SMTP_HOST:
        return {"ok": False, "error": "SMTP_HOST is not set in .env, so e-mail is switched off"}
    msg = EmailMessage()
    msg["Subject"] = "TotalMant Admin: test"
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = body.to
    msg.set_content("E-mail from TotalMaint works.\n")
    try:
        send_mail(msg)
        events.log(db, "mail_sent", f"Test e-mail to {body.to}")
        ok, err = True, None
    except Exception as exc:  # show the SMTP error as it is
        err = f"{type(exc).__name__}: {exc}"
        events.log(db, "mail_failed", f"Test e-mail to {body.to}: {err}")
        ok = False
    db.commit()
    return {"ok": ok, "error": err}


# ---------------------------------------------------------------- settings
def _set(db: Session, key: str, value: str) -> None:
    row = db.get(m.Setting, key)
    if row is None:
        db.add(m.Setting(key=key, value=value))
    else:
        row.value = value


@router.get("/settings")
def settings(_: bool = Depends(admin_session), db: Session = Depends(get_db)):
    mode, code = signup_settings(db)
    from_db = db.get(m.Setting, "signup_mode") is not None
    return {"signup_mode": mode, "signup_code": code, "signup_from": "admin" if from_db else ".env",
            "public_url": PUBLIC_URL, "invite_days": INVITE_DAYS, "reset_hours": RESET_HOURS,
            "session_hours": ADMIN_SESSION_HOURS, "allow_nets": ADMIN_ALLOW_NETS}


class SignupIn(BaseModel):
    mode: str = Field(pattern="^(open|code|closed|env)$")  # env = forget the console's choice, use .env again
    code: str = ""


@router.put("/settings/signup")
def set_signup(body: SignupIn, _: bool = Depends(admin_session), db: Session = Depends(get_db)):
    if body.mode == "env":
        for k in ("signup_mode", "signup_code"):
            row = db.get(m.Setting, k)
            if row:
                db.delete(row)
    else:
        code = body.code.strip()
        if body.mode == "code" and len(code) < 4:
            raise HTTPException(400, "The code needs at least 4 characters")
        _set(db, "signup_mode", body.mode)
        _set(db, "signup_code", code if body.mode == "code" else "")
    db.flush()
    mode, code = signup_settings(db)
    events.log(db, "admin", f"Registration of new families: {mode}" + (" (with code)" if code else ""))
    db.commit()
    return {"signup_mode": mode, "signup_code": code}


@router.get("/settings/new-code")
def new_code(_: bool = Depends(admin_session)):
    """A random code that is easy to read out (no 0/O, 1/l)."""
    alphabet = "abcdefghjkmnpqrstuvwxyz23456789"
    return {"code": "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(2))}


# ---------------------------------------------------------------- backups
def _sqlite_path() -> Optional[Path]:
    if DATABASE_URL.startswith("sqlite:///"):
        return Path(DATABASE_URL.removeprefix("sqlite:///"))
    return None


@router.get("/backups")
def backups(_: bool = Depends(admin_session)):
    free = shutil.disk_usage(BACKUP_DIR if BACKUP_DIR.exists() else BACKUP_DIR.parent)
    return {"dir": str(BACKUP_DIR), "files": _backups(), "disk_free": free.free, "disk_total": free.total,
            "kind": "sqlite" if _sqlite_path() else "postgresql"}


@router.post("/backups")
def backup_now(_: bool = Depends(admin_session), db: Session = Depends(get_db)):
    """Same format as nas/backup.sh (db-YYYY-MM-DD_HHMM.sql.gz) so both lists stay one list; keeps the newest 30."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    src = _sqlite_path()
    try:
        if src is not None:
            target = BACKUP_DIR / f"db-{stamp}.sqlite"
            with sqlite3.connect(src) as a, sqlite3.connect(target) as b:
                a.backup(b)
        else:
            target = BACKUP_DIR / f"db-{stamp}.sql.gz"
            url = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
            proc = subprocess.run(["pg_dump", "--no-owner", url], capture_output=True, timeout=600)
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.decode(errors="replace").strip()[-400:] or "pg_dump failed")
            with gzip.open(target, "wb") as f:
                f.write(proc.stdout)
    except FileNotFoundError:
        raise HTTPException(500, "pg_dump is not installed in this container (rebuild it with the new Dockerfile)")
    except Exception as exc:
        events.log(db, "backup", f"Backup FAILED: {exc}")
        db.commit()
        raise HTTPException(500, f"Backup failed: {exc}")
    old = sorted((f for f in BACKUP_DIR.iterdir() if f.name.startswith("db-")), key=lambda f: f.stat().st_mtime)
    for f in old[:-30]:
        f.unlink(missing_ok=True)
    events.log(db, "backup", f"Backup {target.name} ({target.stat().st_size // 1024} kB)")
    db.commit()
    return {"ok": True, "name": target.name, "size": target.stat().st_size}


@router.get("/backups/{name}")
def download_backup(name: str, _: bool = Depends(admin_session)):
    if "/" in name or "\\" in name or not name.startswith("db-"):
        raise HTTPException(400, "Bad file name")
    f = BACKUP_DIR / name
    if not f.is_file():
        raise HTTPException(404, "Backup not found")
    return FileResponse(f, filename=name, media_type="application/octet-stream")


# ---------------------------------------------------------------- database & system
TABLES = [("users", m.User), ("groups", m.Group), ("memberships", m.Membership), ("roles", m.Role),
          ("invitations", m.Invitation), ("assets", m.Asset), ("components", m.Component), ("tasks", m.Task),
          ("completions", m.Completion), ("spare_parts", m.SparePart), ("purchases", m.Purchase),
          ("warranties", m.Warranty), ("vendors", m.Vendor), ("attachments", m.Attachment),
          ("counter_readings", m.CounterReading), ("password_resets", m.PasswordReset), ("events", m.Event)]


@router.get("/system")
def system(_: bool = Depends(admin_session), db: Session = Depends(get_db)):
    files, size = _uploads_size()
    kind = "SQLite" if _sqlite_path() else "PostgreSQL"
    db_size = None
    if _sqlite_path() and _sqlite_path().exists():
        db_size = _sqlite_path().stat().st_size
    elif kind == "PostgreSQL":
        try:
            db_size = db.scalar(select(func.pg_database_size(func.current_database())))
        except Exception:
            db_size = None
    return {
        "version": APP_VERSION, "python": platform.python_version(), "platform": platform.platform(),
        "database": kind, "database_where": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else str(_sqlite_path()),
        "database_size": db_size, "uploads": files, "uploads_size": size,
        "started_at": STARTED.isoformat(), "timezone": os.getenv("TZ", time.tzname[0]),
        "tables": [{"name": n, "rows": _count(db, select(func.count()).select_from(model))} for n, model in TABLES],
        "adminer_url": ADMINER_URL,
    }


@router.get("/events")
def event_log(kind: Optional[str] = None, before: Optional[int] = None, _: bool = Depends(admin_session),
              db: Session = Depends(get_db)):
    q = select(m.Event).order_by(m.Event.id.desc()).limit(100)
    if kind:
        q = q.where(m.Event.kind == kind)
    if before:
        q = q.where(m.Event.id < before)
    names = _group_names(db)
    return {"kinds": events.KINDS, "events": [_event_out(e, names) for e in db.scalars(q)]}


app.include_router(router)


@app.get("/health")
def health():
    return {"ok": True}


app.mount("/", StaticFiles(directory=ADMIN_DIR, html=True), name="admin")
