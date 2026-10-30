import hashlib
import mimetypes
import secrets
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from . import events
from .auth import create_token, current_user, hash_password, new_ical_token, verify_password
from .config import (INVITE_DAYS, MAX_UPLOAD_MB, PUBLIC_URL, RESET_HOURS, SIGNUP_CODE, SIGNUP_ENABLED, SMTP_HOST,
                     UPLOAD_DIR)
from .db import get_db
from .recurrence import add_interval, next_counter_after_completion, next_due_after_completion
from .services import (asset_total_cost, calendar_events, completion_out, part_out, task_out,
                       task_status, warranty_out)
from .permissions import (ALL, PERMISSIONS, Ctx, clean, group_asset_ids, group_ctx, memberships_of, new_group,
                          require)
from .reminders import send_invitation, send_password_reset
from .templates_data import find_template, list_templates

router = APIRouter(prefix="/api")


def _get_or_404(db: Session, model, obj_id: int):
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(404, f"{model.__name__} {obj_id} not found")
    return obj


def _asset(db: Session, ctx: Ctx, asset_id: int) -> m.Asset:
    """An asset of the active group; other groups' things simply don't exist (404)."""
    a = db.get(m.Asset, asset_id)
    if a is None or a.group_id != ctx.group.id:
        raise HTTPException(404, f"Asset {asset_id} not found")
    return a


def _owner_asset(db: Session, obj):
    if isinstance(obj, m.Asset):
        return obj
    if isinstance(obj, m.Completion):
        return obj.task.asset
    return db.get(m.Asset, obj.asset_id)


def _mine(db: Session, ctx: Ctx, model, obj_id: int):
    """Get a row of the active group (through its asset, or directly for vendors) or 404."""
    obj = db.get(model, obj_id)
    if obj is not None:
        gid = obj.group_id if isinstance(obj, m.Vendor) else getattr(_owner_asset(db, obj), "group_id", None)
        if gid == ctx.group.id:
            return obj
    raise HTTPException(404, f"{model.__name__} {obj_id} not found")


def _delete_files(db: Session, entity_type: str, entity_id: int) -> None:
    for att in db.scalars(select(m.Attachment).where(
            m.Attachment.entity_type == entity_type, m.Attachment.entity_id == entity_id)):
        (UPLOAD_DIR / att.stored_name).unlink(missing_ok=True)
        db.delete(att)


def _record_reading(db: Session, asset: m.Asset, value: float, on: date, user_id: Optional[int]) -> None:
    """Log a km / engine-hour reading; the newest reading becomes the asset's current value."""
    db.add(m.CounterReading(asset_id=asset.id, reading_on=on, value=value, recorded_by_id=user_id))
    if asset.counter_on is None or on >= asset.counter_on:
        asset.counter_value = value
        asset.counter_on = on


def _check_vendor(db: Session, ctx: Ctx, vendor_id: Optional[int]) -> None:
    if vendor_id is None:
        return
    v = db.get(m.Vendor, vendor_id)
    if v is None or v.group_id != ctx.group.id:
        raise HTTPException(400, "Vendor not found")


def _check_refs(db: Session, ctx: Ctx, body: s.TaskIn) -> None:
    _check_vendor(db, ctx, body.vendor_id)
    if body.assigned_to_id is not None and db.scalar(select(m.Membership.id).where(
            m.Membership.group_id == ctx.group.id, m.Membership.user_id == body.assigned_to_id)) is None:
        raise HTTPException(400, "User not found")


def _check_component(db: Session, asset_id: int, component_id: Optional[int]) -> None:
    if component_id is None:
        return
    comp = db.get(m.Component, component_id)
    if comp is None or comp.asset_id != asset_id:
        raise HTTPException(400, "Component does not belong to this asset")


# =============================== auth & users ===============================
def _token_out(db: Session, user: m.User) -> s.TokenOut:
    return s.TokenOut(token=create_token(user), user=s.UserOut.model_validate(user))


def signup_settings(db: Session) -> tuple[str, str]:
    """(mode, code): mode is "open", "code" or "closed". TotalMant Admin can change it (settings table);
    otherwise SIGNUP / SIGNUP_CODE from .env count."""
    rows = {r.key: r.value for r in db.scalars(select(m.Setting).where(m.Setting.key.in_(["signup_mode", "signup_code"])))}
    if "signup_mode" in rows:
        mode = rows["signup_mode"]
        return mode, rows.get("signup_code", "") if mode == "code" else ""
    if not SIGNUP_ENABLED:
        return "closed", ""
    return ("code", SIGNUP_CODE) if SIGNUP_CODE else ("open", "")


@router.get("/auth/status")
def auth_status(db: Session = Depends(get_db)):
    has_users = db.scalar(select(func.count(m.User.id))) > 0
    mode, code = signup_settings(db)
    return {"needs_setup": not has_users, "signup_enabled": mode != "closed", "signup_needs_code": bool(code)}


def _check_signup_code(db: Session, code: str) -> None:
    mode, wanted = signup_settings(db)
    if mode == "closed":
        raise HTTPException(403, "Registering new families is switched off; ask for an invitation")
    if wanted and not secrets.compare_digest((code or "").strip(), wanted):
        raise HTTPException(403, "Wrong sign-up code")


@router.post("/auth/setup", response_model=s.TokenOut)
def first_setup(body: s.SetupIn, db: Session = Depends(get_db)):
    """Creates the first (admin) user and their group. Only works while the database has no users."""
    if db.scalar(select(func.count(m.User.id))) > 0:
        raise HTTPException(400, "Setup already done")
    user = m.User(name=body.name, email=body.email.lower().strip(), lang=body.lang,
                  password_hash=hash_password(body.password), is_admin=True,
                  ical_token=new_ical_token())
    db.add(user)
    db.flush()
    g = new_group(db, body.group_name or ("Familien" if body.lang == "no" else "Family"), user)
    events.log(db, "setup", f"{user.name} <{user.email}> set up the server with {g.name}", user, g.id)
    db.commit()
    return _token_out(db, user)


@router.post("/auth/signup", response_model=s.TokenOut)
def signup(body: s.SignupIn, db: Session = Depends(get_db)):
    """Register a new family: a new account and a new group with that name, the person as owner."""
    _check_signup_code(db, body.code)
    email = body.email.lower().strip()
    if db.scalar(select(m.User).where(m.User.email == email)):
        raise HTTPException(400, "This e-mail already has an account: log in and add the new family under Settings")
    user = m.User(name=body.name, email=email, lang=body.lang, password_hash=hash_password(body.password),
                  ical_token=new_ical_token())
    db.add(user)
    db.flush()
    g = new_group(db, body.group_name, user)
    events.log(db, "signup", f"{user.name} <{user.email}> registered {g.name}", user, g.id)
    db.commit()
    return _token_out(db, user)


@router.post("/auth/login", response_model=s.TokenOut)
def login(body: s.LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(m.User).where(m.User.email == body.email.lower().strip()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong e-mail or password")
    if user.blocked:
        events.log(db, "login_blocked", user.email, user)
        db.commit()
        raise HTTPException(403, "This account is blocked; contact the administrator")
    events.log(db, "login", user.email, user, user.current_group_id)
    db.commit()
    return _token_out(db, user)


@router.get("/me")
def me(ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    user = ctx.user
    out = s.UserOut.model_validate(user).model_dump()
    out["ical_url"] = f"{PUBLIC_URL}/ical/{user.ical_token}.ics"
    out["group"] = {"id": ctx.group.id, "name": ctx.group.name}
    out["role"] = {"id": ctx.membership.role.id, "key": ctx.membership.role.key, "name": ctx.membership.role.name}
    out["permissions"] = ALL if ctx.is_owner else sorted(ctx.perms, key=ALL.index)
    out["is_owner"] = ctx.is_owner
    out["groups"] = [{"id": x.group_id, "name": x.group.name, "role": x.role.name}
                     for x in memberships_of(db, user.id)]
    return out


@router.patch("/me", response_model=s.UserOut)
def update_me(body: s.UserUpdate, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name is not None:
        user.name = body.name
    if body.lang is not None:
        user.lang = body.lang
    if body.email_reminders is not None:
        user.email_reminders = body.email_reminders
    if body.password:
        user.password_hash = hash_password(body.password)
    db.add(user)
    db.commit()
    return user


@router.post("/me/group")
def switch_group(body: s.SwitchGroupIn, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    """Choose which of your groups the app shows."""
    if not any(x.group_id == body.group_id for x in memberships_of(db, user.id)):
        raise HTTPException(404, "You are not a member of that group")
    user.current_group_id = body.group_id
    db.commit()
    return {"ok": True}


@router.post("/me/ical-reset")
def reset_ical(user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    user.ical_token = new_ical_token()
    db.add(user)
    db.commit()
    return {"ical_url": f"{PUBLIC_URL}/ical/{user.ical_token}.ics"}


# =============================== forgotten password ===============================
def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_reset(db: Session, user: m.User, by: Optional[m.User] = None) -> str:
    """Creates a one-time link; earlier unused links of the same user stop working."""
    now = datetime.utcnow()
    for old in db.scalars(select(m.PasswordReset).where(m.PasswordReset.user_id == user.id,
                                                        m.PasswordReset.used_at.is_(None))):
        old.used_at = now
    token = secrets.token_urlsafe(32)
    db.add(m.PasswordReset(user_id=user.id, token_hash=_hash(token), created_by_id=by.id if by else None,
                           expires_at=now + timedelta(hours=RESET_HOURS)))
    db.commit()
    return f"{PUBLIC_URL}/#/reset/{token}"


def _open_reset(db: Session, token: str) -> m.PasswordReset:
    r = db.scalar(select(m.PasswordReset).where(m.PasswordReset.token_hash == _hash(token)))
    if r is None or r.used_at is not None:
        raise HTTPException(404, "This link is no longer valid; ask for a new one")
    if r.expires_at < datetime.utcnow():
        raise HTTPException(410, "This link has expired; ask for a new one")
    return r


@router.post("/auth/forgot")
def forgot_password(body: s.ForgotIn, db: Session = Depends(get_db)):
    """E-mails a reset link. The answer is the same whether the address exists or not,
    so the page can't be used to find out who has an account."""
    user = db.scalar(select(m.User).where(m.User.email == body.email.lower().strip()))
    if user is not None and SMTP_HOST and not user.blocked:
        recent = db.scalar(select(func.count(m.PasswordReset.id)).where(
            m.PasswordReset.user_id == user.id,
            m.PasswordReset.created_at >= datetime.utcnow() - timedelta(hours=1))) or 0
        if recent < 3:  # don't let anyone flood a mailbox
            sent, err = send_password_reset(user, _new_reset(db, user), RESET_HOURS, body.lang)
            events.log(db, "mail_sent" if sent else "mail_failed",
                       f"Password link to {user.email}" + (f": {err}" if err else ""), user)
            db.commit()
    return {"ok": True, "mail_enabled": bool(SMTP_HOST)}


@router.get("/auth/reset/{token}")
def reset_info(token: str, db: Session = Depends(get_db)):
    r = _open_reset(db, token)
    return {"email": r.user.email, "name": r.user.name}


@router.post("/auth/reset/{token}", response_model=s.TokenOut)
def reset_password(token: str, body: s.ResetIn, db: Session = Depends(get_db)):
    """Sets the new password, logs out every other device, and logs this one in."""
    r = _open_reset(db, token)
    user = r.user
    if user.blocked:
        raise HTTPException(403, "This account is blocked; contact the administrator")
    user.password_hash = hash_password(body.password)
    user.session_version = (user.session_version or 0) + 1
    r.used_at = datetime.utcnow()
    events.log(db, "reset_done", user.email, user)
    db.commit()
    return _token_out(db, user)


@router.post("/users/{user_id}/reset-link")
def admin_reset_link(user_id: int, ctx: Ctx = Depends(require("members.manage")), db: Session = Depends(get_db)):
    """For a member who forgot their password when the server can't send e-mail: a link to hand over."""
    mem = _membership(db, ctx, user_id)
    if mem.role.key == "owner" and not ctx.is_owner:
        raise HTTPException(403, "Only the owner can do this for the owner")
    if len(memberships_of(db, user_id)) > 1 and user_id != ctx.user.id:
        raise HTTPException(403, "This person is also in another group; they use \"Forgot password\" themselves")
    link = _new_reset(db, mem.user, ctx.user)
    events.log(db, "reset_requested", f"{ctx.user.email} made a password link for {mem.user.email}", ctx.user, ctx.group.id)
    db.commit()
    return {"link": link, "hours": RESET_HOURS}


# =============================== group, members ===============================
def _member_out(mem: m.Membership) -> s.MemberOut:
    u = mem.user
    return s.MemberOut(id=u.id, name=u.name, email=u.email, lang=u.lang, is_admin=u.is_admin,
                       email_reminders=u.email_reminders, role_id=mem.role_id, role_name=mem.role.name,
                       role_key=mem.role.key)


def _membership(db: Session, ctx: Ctx, user_id: int) -> m.Membership:
    mem = db.scalar(select(m.Membership).where(m.Membership.group_id == ctx.group.id,
                                               m.Membership.user_id == user_id))
    if mem is None:
        raise HTTPException(404, "Not a member of this group")
    return mem


def _role(db: Session, ctx: Ctx, role_id: Optional[int], default_key: str = "creator") -> m.Role:
    if role_id is None:
        role = db.scalar(select(m.Role).where(m.Role.group_id == ctx.group.id, m.Role.key == default_key))
    else:
        role = db.get(m.Role, role_id)
    if role is None or role.group_id != ctx.group.id:
        raise HTTPException(400, "Role not found")
    if role.key == "owner" and not ctx.is_owner:
        raise HTTPException(403, "Only the owner can make someone owner")
    return role


def _legacy_role_id(db: Session, ctx: Ctx, body) -> Optional[int]:
    """Older app versions send is_admin instead of a role."""
    if getattr(body, "role_id", None) is not None or getattr(body, "is_admin", None) is None:
        return getattr(body, "role_id", None)
    key = "admin" if body.is_admin else "creator"
    return db.scalar(select(m.Role.id).where(m.Role.group_id == ctx.group.id, m.Role.key == key))


def _owner_count(db: Session, group_id: int) -> int:
    return db.scalar(select(func.count(m.Membership.id)).join(m.Role)
                     .where(m.Membership.group_id == group_id, m.Role.key == "owner")) or 0


@router.post("/groups", response_model=s.GroupOut)
def create_group(body: s.NewGroupIn, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    """Someone who already has an account starts another family (a cabin with friends, a boat club ...).
    They become its owner and the app switches to it."""
    _check_signup_code(db, body.code)
    g = new_group(db, body.name.strip(), user)
    events.log(db, "family_created", f"{user.email} created {g.name}", user, g.id)
    db.commit()
    return s.GroupOut(id=g.id, name=g.name)


@router.get("/group", response_model=s.GroupOut)
def get_group(ctx: Ctx = Depends(group_ctx)):
    return s.GroupOut(id=ctx.group.id, name=ctx.group.name)


@router.patch("/group", response_model=s.GroupOut)
def rename_group(body: s.GroupIn, ctx: Ctx = Depends(require("members.manage")), db: Session = Depends(get_db)):
    ctx.group.name = body.name
    db.commit()
    return s.GroupOut(id=ctx.group.id, name=ctx.group.name)


@router.get("/users", response_model=list[s.MemberOut])
def list_users(ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    """The members of the active group (used for 'responsible person' and the members page)."""
    mems = db.scalars(select(m.Membership).where(m.Membership.group_id == ctx.group.id)).all()
    return sorted([_member_out(x) for x in mems], key=lambda x: x.name.lower())


@router.post("/users", response_model=s.MemberOut)
def create_user(body: s.UserCreate, ctx: Ctx = Depends(require("members.manage")), db: Session = Depends(get_db)):
    """Make an account straight away with a password you hand over (the invitation is the other way)."""
    email = body.email.lower().strip()
    if db.scalar(select(m.User).where(m.User.email == email)):
        raise HTTPException(400, "E-mail already in use; send an invitation instead")
    role = _role(db, ctx, _legacy_role_id(db, ctx, body))
    user = m.User(name=body.name, email=email, lang=body.lang, password_hash=hash_password(body.password),
                  ical_token=new_ical_token(), current_group_id=ctx.group.id)
    db.add(user)
    db.flush()
    mem = m.Membership(user_id=user.id, group_id=ctx.group.id, role_id=role.id)
    db.add(mem)
    events.log(db, "member_added", f"{ctx.user.email} added {user.email} to {ctx.group.name} as {role.name}",
               ctx.user, ctx.group.id)
    db.commit()
    db.refresh(mem)
    return _member_out(mem)


@router.patch("/users/{user_id}", response_model=s.MemberOut)
def update_user(user_id: int, body: s.UserUpdate, ctx: Ctx = Depends(require("members.manage")),
                db: Session = Depends(get_db)):
    mem = _membership(db, ctx, user_id)
    user = mem.user
    if mem.role.key == "owner" and not ctx.is_owner:
        raise HTTPException(403, "Only the owner can change the owner")
    role_id = _legacy_role_id(db, ctx, body)
    if role_id is not None and role_id != mem.role_id:
        role = _role(db, ctx, role_id)
        if mem.role.key == "owner" and _owner_count(db, ctx.group.id) <= 1:
            raise HTTPException(400, "The group needs an owner: make someone else owner first")
        if user.id == ctx.user.id and not ctx.is_owner and not ("members.manage" in role.perm_set):
            raise HTTPException(400, "You cannot remove your own admin rights")
        mem.role_id = role.id
    for field in ("name", "lang", "email_reminders"):
        value = getattr(body, field)
        if value is not None:
            setattr(user, field, value)
    if body.password:
        # an account in several groups belongs to more than this group: only its own owner changes the password
        if len(memberships_of(db, user.id)) > 1 and user.id != ctx.user.id:
            raise HTTPException(403, "This person is also in another group; they change their password themselves")
        user.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(mem)
    return _member_out(mem)


@router.delete("/users/{user_id}")
def delete_user(user_id: int, ctx: Ctx = Depends(require("members.manage")), db: Session = Depends(get_db)):
    """Removes the person from this group. The account itself goes too when it is in no other group."""
    if user_id == ctx.user.id:
        raise HTTPException(400, "You cannot delete yourself")
    mem = _membership(db, ctx, user_id)
    if mem.role.key == "owner":
        raise HTTPException(403, "The owner cannot be removed")
    user = mem.user
    for t in db.scalars(select(m.Task).where(m.Task.assigned_to_id == user.id,
                                             m.Task.asset_id.in_(group_asset_ids(db, ctx.group.id)))):
        t.assigned_to_id = None
    db.delete(mem)
    db.flush()
    events.log(db, "member_removed", f"{ctx.user.email} removed {user.email} from {ctx.group.name}", ctx.user, ctx.group.id)
    if not memberships_of(db, user.id):
        db.delete(user)
    elif user.current_group_id == ctx.group.id:
        user.current_group_id = None
    db.commit()
    return {"ok": True}


@router.post("/group/transfer-owner")
def transfer_owner(body: s.TransferIn, ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    """Owner only: another member becomes owner, you become admin."""
    if not ctx.is_owner:
        raise HTTPException(403, "Only the owner can hand over the group")
    target = _membership(db, ctx, body.user_id)
    roles = {r.key: r for r in ctx.group.roles}
    target.role_id = roles["owner"].id
    ctx.membership.role_id = roles["admin"].id
    db.commit()
    return {"ok": True}


# =============================== roles ===============================
def _role_out(db: Session, r: m.Role) -> s.RoleOut:
    n = db.scalar(select(func.count(m.Membership.id)).where(m.Membership.role_id == r.id)) or 0
    perms = ALL if r.key == "owner" else sorted(r.perm_set, key=ALL.index)
    return s.RoleOut(id=r.id, key=r.key, name=r.name, permissions=perms, members=n,
                     locked=r.key == "owner", builtin=r.key is not None)


@router.get("/permissions")
def permission_catalog(user: m.User = Depends(current_user)):
    i = 1 if user.lang == "no" else 0
    return [{"key": k, "label": v[i]} for k, v in PERMISSIONS.items()]


@router.get("/roles", response_model=list[s.RoleOut])
def list_roles(ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    return [_role_out(db, r) for r in ctx.group.roles]


@router.post("/roles", response_model=s.RoleOut)
def create_role(body: s.RoleIn, ctx: Ctx = Depends(require("roles.manage")), db: Session = Depends(get_db)):
    r = m.Role(group_id=ctx.group.id, key=None, name=body.name, permissions=clean(body.permissions))
    db.add(r)
    db.commit()
    db.refresh(r)
    return _role_out(db, r)


@router.put("/roles/{role_id}", response_model=s.RoleOut)
def update_role(role_id: int, body: s.RoleIn, ctx: Ctx = Depends(require("roles.manage")),
                db: Session = Depends(get_db)):
    r = _get_or_404(db, m.Role, role_id)
    if r.group_id != ctx.group.id:
        raise HTTPException(404, "Role not found")
    if r.key == "owner":
        raise HTTPException(400, "The owner role is locked")
    new = clean(body.permissions)
    # you may not take away your own power to fix roles (the owner can always fix things)
    if r.id == ctx.membership.role_id and not ctx.is_owner and "roles.manage" not in new.split(","):
        raise HTTPException(400, "You cannot remove 'Edit roles' from your own role")
    r.name = body.name
    r.permissions = new
    db.commit()
    return _role_out(db, r)


@router.delete("/roles/{role_id}")
def delete_role(role_id: int, ctx: Ctx = Depends(require("roles.manage")), db: Session = Depends(get_db)):
    """Own roles only. Members who had it become Viewers."""
    r = _get_or_404(db, m.Role, role_id)
    if r.group_id != ctx.group.id:
        raise HTTPException(404, "Role not found")
    if r.key is not None:
        raise HTTPException(400, "Built-in roles cannot be deleted")
    viewer = db.scalar(select(m.Role).where(m.Role.group_id == ctx.group.id, m.Role.key == "viewer"))
    for mem in db.scalars(select(m.Membership).where(m.Membership.role_id == r.id)):
        mem.role_id = viewer.id
    db.flush()
    db.delete(r)
    db.commit()
    return {"ok": True}


# =============================== invitations ===============================
def _invite_link(inv: m.Invitation) -> str:
    return f"{PUBLIC_URL}/#/invite/{inv.token}"


def _invite_out(inv: m.Invitation) -> s.InvitationOut:
    return s.InvitationOut(id=inv.id, email=inv.email, role_id=inv.role_id, role_name=inv.role.name,
                           expires_at=inv.expires_at, created_at=inv.created_at, link=_invite_link(inv),
                           invited_by_name=inv.invited_by.name if inv.invited_by else None)


def _open_invite(db: Session, token: str) -> m.Invitation:
    inv = db.scalar(select(m.Invitation).where(m.Invitation.token == token))
    if inv is None or inv.accepted_at is not None:
        raise HTTPException(404, "This invitation is no longer valid")
    if inv.expires_at < datetime.utcnow():
        raise HTTPException(410, "This invitation has expired; ask for a new one")
    return inv


@router.get("/invitations", response_model=list[s.InvitationOut])
def list_invitations(ctx: Ctx = Depends(require("members.manage")), db: Session = Depends(get_db)):
    q = select(m.Invitation).where(m.Invitation.group_id == ctx.group.id, m.Invitation.accepted_at.is_(None),
                                   m.Invitation.expires_at >= datetime.utcnow()).order_by(m.Invitation.created_at.desc())
    return [_invite_out(i) for i in db.scalars(q)]


@router.post("/invitations", response_model=s.InvitationOut)
def create_invitation(body: s.InvitationIn, ctx: Ctx = Depends(require("members.manage")),
                      db: Session = Depends(get_db)):
    """Creates a one-time link and e-mails it when SMTP is set up. The link is always returned, to copy by hand."""
    email = body.email.lower().strip()
    existing = db.scalar(select(m.User).where(m.User.email == email))
    if existing and any(x.group_id == ctx.group.id for x in memberships_of(db, existing.id)):
        raise HTTPException(400, "Already a member of this group")
    role = _role(db, ctx, body.role_id)
    inv = m.Invitation(group_id=ctx.group.id, email=email, role_id=role.id, token=secrets.token_urlsafe(32),
                       invited_by_id=ctx.user.id, expires_at=datetime.utcnow() + timedelta(days=INVITE_DAYS))
    db.add(inv)
    db.commit()
    db.refresh(inv)
    out = _invite_out(inv)
    out.mailed, out.mail_error = send_invitation(inv, body.lang or ctx.user.lang)
    events.log(db, "invite_sent", f"{ctx.user.email} invited {email} to {ctx.group.name} as {role.name}"
               + ("" if out.mailed else " (link copied, no e-mail)"), ctx.user, ctx.group.id)
    if out.mailed:
        events.log(db, "mail_sent", f"Invitation to {email}", ctx.user, ctx.group.id)
    elif SMTP_HOST:
        events.log(db, "mail_failed", f"Invitation to {email}: {out.mail_error}", ctx.user, ctx.group.id)
    db.commit()
    return out


@router.delete("/invitations/{invitation_id}")
def cancel_invitation(invitation_id: int, ctx: Ctx = Depends(require("members.manage")),
                      db: Session = Depends(get_db)):
    inv = _get_or_404(db, m.Invitation, invitation_id)
    if inv.group_id != ctx.group.id:
        raise HTTPException(404, "Invitation not found")
    db.delete(inv)
    db.commit()
    return {"ok": True}


@router.get("/invite/{token}")
def invitation_info(token: str, db: Session = Depends(get_db)):
    """Public: what the invitation page shows before someone accepts."""
    inv = _open_invite(db, token)
    has_account = db.scalar(select(m.User.id).where(m.User.email == inv.email)) is not None
    return {"group_name": inv.group.name, "email": inv.email, "role_name": inv.role.name,
            "invited_by": inv.invited_by.name if inv.invited_by else None, "has_account": has_account}


@router.post("/invite/{token}/accept", response_model=s.TokenOut)
def accept_invitation(token: str, body: s.AcceptIn, db: Session = Depends(get_db)):
    """New person: name + password make the account. Existing account: their password proves it is them."""
    inv = _open_invite(db, token)
    user = db.scalar(select(m.User).where(m.User.email == inv.email))
    if user is None:
        if not body.name:
            raise HTTPException(400, "Name is required")
        user = m.User(name=body.name, email=inv.email, lang=body.lang, password_hash=hash_password(body.password),
                      ical_token=new_ical_token())
        db.add(user)
        db.flush()
    elif not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong password")
    elif user.blocked:
        raise HTTPException(403, "This account is blocked; contact the administrator")
    if not any(x.group_id == inv.group_id for x in memberships_of(db, user.id)):
        db.add(m.Membership(user_id=user.id, group_id=inv.group_id, role_id=inv.role_id))
    user.current_group_id = inv.group_id
    inv.accepted_at = datetime.utcnow()
    events.log(db, "invite_accepted", f"{user.email} joined {inv.group.name} as {inv.role.name}", user, inv.group_id)
    db.commit()
    return _token_out(db, user)


# =============================== assets ===============================
@router.get("/assets", response_model=list[s.AssetSummary])
def list_assets(ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    out = []
    for a in db.scalars(select(m.Asset).where(m.Asset.group_id == ctx.group.id).order_by(m.Asset.name)):
        statuses = [task_status(t) for t in a.tasks]
        out.append(s.AssetSummary(
            **s.AssetOut.model_validate(a).model_dump(),
            task_count=sum(1 for t in a.tasks if t.active),
            overdue_count=statuses.count("overdue"),
            due_soon_count=statuses.count("due_soon"),
            total_cost=asset_total_cost(db, a.id),
        ))
    return out


@router.post("/assets", response_model=s.AssetOut)
def create_asset(body: s.AssetIn, ctx: Ctx = Depends(require("assets.create")), db: Session = Depends(get_db)):
    user = ctx.user
    data = body.model_dump()
    value = data.pop("counter_value")
    asset = m.Asset(group_id=ctx.group.id, **data)
    db.add(asset)
    db.flush()
    if value is not None and asset.counter_unit != "none":
        _record_reading(db, asset, value, date.today(), user.id)
    db.commit()
    return asset


@router.get("/assets/{asset_id}", response_model=s.AssetDetail)
def get_asset(asset_id: int, ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    a = _asset(db, ctx, asset_id)
    tasks = sorted(a.tasks, key=lambda t: (not t.active, t.next_due or date.max, t.title))
    attachments = db.scalars(select(m.Attachment).where(
        m.Attachment.entity_type == "asset", m.Attachment.entity_id == a.id)).all()
    return s.AssetDetail(
        **s.AssetOut.model_validate(a).model_dump(),
        components=[s.ComponentOut.model_validate(c) for c in sorted(a.components, key=lambda c: c.name)],
        tasks=[task_out(t) for t in tasks],
        parts=[part_out(p) for p in sorted(a.parts, key=lambda p: p.name)],
        warranties=[warranty_out(w) for w in sorted(a.warranties, key=lambda w: w.end_date or date.max)],
        attachments=[s.AttachmentOut.model_validate(x) for x in attachments],
        total_cost=asset_total_cost(db, a.id),
        readings=[s.CounterReadingOut.model_validate(r) for r in db.scalars(
            select(m.CounterReading).where(m.CounterReading.asset_id == a.id)
            .order_by(m.CounterReading.reading_on.desc(), m.CounterReading.id.desc()).limit(10))],
    )


@router.put("/assets/{asset_id}", response_model=s.AssetOut)
def update_asset(asset_id: int, body: s.AssetIn, ctx: Ctx = Depends(require("assets.edit")),
                 db: Session = Depends(get_db)):
    user = ctx.user
    a = _asset(db, ctx, asset_id)
    data = body.model_dump()
    value = data.pop("counter_value")
    for k, v in data.items():
        setattr(a, k, v)
    if value is not None and a.counter_unit != "none" and value != a.counter_value:
        _record_reading(db, a, value, date.today(), user.id)
    db.commit()
    return a


@router.post("/assets/{asset_id}/counter", response_model=s.AssetOut)
def add_counter_reading(asset_id: int, body: s.CounterIn, ctx: Ctx = Depends(require("counters.record")),
                        db: Session = Depends(get_db)):
    user = ctx.user
    a = _asset(db, ctx, asset_id)
    if a.counter_unit == "none":
        raise HTTPException(400, "This thing has no km / hour counter")
    _record_reading(db, a, body.value, body.reading_on, user.id)
    db.commit()
    return a


@router.delete("/counter-readings/{reading_id}")
def delete_counter_reading(reading_id: int, ctx: Ctx = Depends(require("counters.record")),
                           db: Session = Depends(get_db)):
    r = _mine(db, ctx, m.CounterReading, reading_id)
    a = db.get(m.Asset, r.asset_id)
    db.delete(r)
    db.flush()
    last = db.scalars(select(m.CounterReading).where(m.CounterReading.asset_id == a.id)
                      .order_by(m.CounterReading.reading_on.desc(), m.CounterReading.id.desc()).limit(1)).first()
    a.counter_value = last.value if last else None
    a.counter_on = last.reading_on if last else None
    db.commit()
    return {"ok": True}


@router.delete("/assets/{asset_id}")
def delete_asset(asset_id: int, ctx: Ctx = Depends(require("assets.delete")), db: Session = Depends(get_db)):
    _purge_asset(db, _asset(db, ctx, asset_id))
    db.commit()
    return {"ok": True}


def _purge_asset(db: Session, a: m.Asset) -> None:
    """Delete an asset with everything that belongs to it, files on disk included (no commit)."""
    _delete_files(db, "asset", a.id)
    for c in a.components:
        _delete_files(db, "component", c.id)
    for t in a.tasks:
        _delete_files(db, "task", t.id)
        for c in t.completions:
            _delete_files(db, "completion", c.id)
    for p in a.parts:
        _delete_files(db, "part", p.id)
    for w in a.warranties:
        _delete_files(db, "warranty", w.id)
    for pu in db.scalars(select(m.Purchase).where(m.Purchase.asset_id == a.id)):
        _delete_files(db, "purchase", pu.id)
    db.delete(a)


# =============================== components ===============================
@router.post("/assets/{asset_id}/components", response_model=s.ComponentOut)
def create_component(asset_id: int, body: s.ComponentIn, ctx: Ctx = Depends(require("components.create")),
                     db: Session = Depends(get_db)):
    _asset(db, ctx, asset_id)
    c = m.Component(asset_id=asset_id, **body.model_dump())
    db.add(c)
    db.commit()
    return c


@router.put("/components/{component_id}", response_model=s.ComponentOut)
def update_component(component_id: int, body: s.ComponentIn, ctx: Ctx = Depends(require("components.edit")),
                     db: Session = Depends(get_db)):
    c = _mine(db, ctx, m.Component, component_id)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    db.commit()
    return c


@router.delete("/components/{component_id}")
def delete_component(component_id: int, ctx: Ctx = Depends(require("components.delete")),
                     db: Session = Depends(get_db)):
    c = _mine(db, ctx, m.Component, component_id)
    _delete_files(db, "component", component_id)
    db.delete(c)
    db.commit()
    return {"ok": True}


# =============================== tasks ===============================
@router.get("/tasks", response_model=list[s.TaskOut])
def list_tasks(
    status: Optional[str] = Query(None, description="overdue | due_soon | ok | none | inactive | open"),
    asset_id: Optional[int] = None,
    mine: bool = False,
    ctx: Ctx = Depends(group_ctx),
    db: Session = Depends(get_db),
):
    user = ctx.user
    q = select(m.Task).where(m.Task.asset_id.in_(group_asset_ids(db, ctx.group.id)))
    if asset_id:
        q = q.where(m.Task.asset_id == asset_id)
    if mine:
        q = q.where((m.Task.assigned_to_id == user.id) | (m.Task.assigned_to_id.is_(None)))
    tasks = [task_out(t) for t in db.scalars(q)]
    if status == "open":
        tasks = [t for t in tasks if t.status in ("overdue", "due_soon")]
    elif status:
        tasks = [t for t in tasks if t.status == status]
    tasks.sort(key=lambda t: (t.status == "inactive", t.next_due or date.max, t.title))
    return tasks


@router.post("/assets/{asset_id}/tasks", response_model=s.TaskOut)
def create_task(asset_id: int, body: s.TaskIn, ctx: Ctx = Depends(require("tasks.create")),
                db: Session = Depends(get_db)):
    user = ctx.user
    _asset(db, ctx, asset_id)
    _check_component(db, asset_id, body.component_id)
    _check_refs(db, ctx, body)
    t = m.Task(asset_id=asset_id, created_by_id=user.id, **body.model_dump())
    if t.next_due is None and t.interval_unit != "none":
        t.next_due = date.today()
    asset = db.get(m.Asset, asset_id)
    if t.counter_interval and t.counter_next_due is None and asset.counter_value is not None:
        t.counter_next_due = asset.counter_value + t.counter_interval
    db.add(t)
    db.commit()
    db.refresh(t)
    return task_out(t)


@router.get("/tasks/{task_id}", response_model=s.TaskDetail)
def get_task(task_id: int, ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    return task_out(_mine(db, ctx, m.Task, task_id), detail=True)


@router.put("/tasks/{task_id}", response_model=s.TaskOut)
def update_task(task_id: int, body: s.TaskIn, ctx: Ctx = Depends(require("tasks.edit")),
                db: Session = Depends(get_db)):
    t = _mine(db, ctx, m.Task, task_id)
    _check_component(db, t.asset_id, body.component_id)
    _check_refs(db, ctx, body)
    if body.vendor_id != t.vendor_id:  # another vendor: the old request no longer counts
        t.vendor_status, t.vendor_requested_on, t.vendor_booked_for = None, None, None
    for k, v in body.model_dump().items():
        setattr(t, k, v)
    if t.counter_interval and t.counter_next_due is None and t.asset.counter_value is not None:
        t.counter_next_due = t.asset.counter_value + t.counter_interval
    t.last_reminded_on = None
    db.commit()
    db.refresh(t)
    return task_out(t)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, ctx: Ctx = Depends(require("tasks.delete")), db: Session = Depends(get_db)):
    t = _mine(db, ctx, m.Task, task_id)
    _delete_files(db, "task", t.id)
    for c in t.completions:
        _delete_files(db, "completion", c.id)
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/complete", response_model=s.TaskDetail)
def complete_task(task_id: int, body: s.CompletionIn, ctx: Ctx = Depends(require("tasks.complete")),
                  db: Session = Depends(get_db)):
    """Log that the task was done; recurring tasks get a new due date, one-off tasks are closed."""
    user = ctx.user
    t = _mine(db, ctx, m.Task, task_id)
    _check_vendor(db, ctx, body.vendor_id)
    asset = t.asset
    has_counter = asset.counter_unit != "none"
    reading = body.counter_value if has_counter else None
    if reading is not None and (asset.counter_value is None or reading != asset.counter_value):
        _record_reading(db, asset, reading, body.done_on, user.id)
    if reading is None and has_counter:
        reading = asset.counter_value  # nobody typed it: use the latest known value
    db.add(m.Completion(task_id=t.id, done_on=body.done_on, cost=body.cost, notes=body.notes, done_by_id=user.id,
                        counter_value=reading, vendor_id=body.vendor_id))
    nxt = next_due_after_completion(body.done_on, t.interval_value, t.interval_unit)
    by_counter = has_counter and bool(t.counter_interval)
    if by_counter:
        t.counter_next_due = next_counter_after_completion(reading, t.counter_interval, t.counter_next_due)
    if nxt is None and not by_counter:  # one-off job: closed
        t.active = False
    t.next_due = nxt
    t.vendor_status, t.vendor_requested_on, t.vendor_booked_for = None, None, None
    t.last_reminded_on = None
    db.commit()
    db.refresh(t)
    return task_out(t, detail=True)


@router.patch("/tasks/{task_id}/vendor-status", response_model=s.TaskOut)
def set_vendor_status(task_id: int, body: s.VendorStatusIn, ctx: Ctx = Depends(require("tasks.edit")),
                      db: Session = Depends(get_db)):
    """requested (the request was sent), confirmed (vendor agreed a date), none (start over)."""
    t = _mine(db, ctx, m.Task, task_id)
    if body.status != "none" and t.vendor_id is None:
        raise HTTPException(400, "The task has no vendor")
    if body.status == "none":
        t.vendor_status, t.vendor_requested_on, t.vendor_booked_for = None, None, None
    elif body.status == "requested":
        t.vendor_status = "requested"
        t.vendor_requested_on = body.on or date.today()
        t.vendor_booked_for = None
    else:
        if body.on is None:
            raise HTTPException(400, "A confirmed job needs a date")
        t.vendor_status = "confirmed"
        t.vendor_booked_for = body.on
        t.vendor_requested_on = t.vendor_requested_on or date.today()
    db.commit()
    db.refresh(t)
    return task_out(t)


@router.delete("/completions/{completion_id}")
def delete_completion(completion_id: int, ctx: Ctx = Depends(require("history.delete")),
                      db: Session = Depends(get_db)):
    c = _mine(db, ctx, m.Completion, completion_id)
    _delete_files(db, "completion", completion_id)
    db.delete(c)
    db.commit()
    return {"ok": True}


# =============================== vendors ===============================
def _vendor_out(db: Session, v: m.Vendor) -> s.VendorOut:
    n = db.scalar(select(func.count(m.Task.id)).where(m.Task.vendor_id == v.id, m.Task.active.is_(True))) or 0
    return s.VendorOut.model_validate(v).model_copy(update={"open_tasks": n})


@router.get("/vendors", response_model=list[s.VendorOut])
def list_vendors(ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    vendors = db.scalars(select(m.Vendor).where(m.Vendor.group_id == ctx.group.id).order_by(m.Vendor.company)).all()
    return [_vendor_out(db, v) for v in vendors]


@router.post("/vendors", response_model=s.VendorOut)
def create_vendor(body: s.VendorIn, ctx: Ctx = Depends(require("vendors.manage")), db: Session = Depends(get_db)):
    v = m.Vendor(group_id=ctx.group.id, **body.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return _vendor_out(db, v)


@router.get("/vendors/{vendor_id}", response_model=s.VendorOut)
def get_vendor(vendor_id: int, ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    return _vendor_out(db, _mine(db, ctx, m.Vendor, vendor_id))


@router.get("/vendors/{vendor_id}/history", response_model=s.VendorHistory)
def vendor_history(vendor_id: int, ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    """Open tasks given to the vendor, jobs they did, and what they have cost."""
    v = _mine(db, ctx, m.Vendor, vendor_id)
    tasks = db.scalars(select(m.Task).where(m.Task.vendor_id == v.id, m.Task.active.is_(True))).all()
    comps = db.scalars(select(m.Completion).where(m.Completion.vendor_id == v.id)
                       .order_by(m.Completion.done_on.desc(), m.Completion.id.desc())).all()
    year_start = date(date.today().year, 1, 1)
    return s.VendorHistory(
        vendor=_vendor_out(db, v),
        open_tasks=sorted([task_out(t) for t in tasks], key=lambda t: (t.next_due or date.max, t.title)),
        jobs=[s.VendorJob(completion_id=c.id, task_id=c.task_id, task_title=c.task.title, asset_id=c.task.asset_id,
                          asset_name=c.task.asset.name, done_on=c.done_on, cost=c.cost, notes=c.notes) for c in comps],
        total_spent=round(sum(c.cost or 0 for c in comps), 2),
        spent_this_year=round(sum(c.cost or 0 for c in comps if c.done_on >= year_start), 2),
    )


@router.put("/vendors/{vendor_id}", response_model=s.VendorOut)
def update_vendor(vendor_id: int, body: s.VendorIn, ctx: Ctx = Depends(require("vendors.manage")),
                  db: Session = Depends(get_db)):
    v = _mine(db, ctx, m.Vendor, vendor_id)
    for k, val in body.model_dump().items():
        setattr(v, k, val)
    for p in db.scalars(select(m.SparePart).where(m.SparePart.vendor_id == v.id)):
        p.supplier = v.company  # keep the stored name in step with the vendor list
    db.commit()
    db.refresh(v)
    return _vendor_out(db, v)


@router.delete("/vendors/{vendor_id}")
def delete_vendor(vendor_id: int, ctx: Ctx = Depends(require("vendors.manage")), db: Session = Depends(get_db)):
    v = _mine(db, ctx, m.Vendor, vendor_id)
    # the column was added later on existing databases, so don't rely on ON DELETE SET NULL
    for t in db.scalars(select(m.Task).where(m.Task.vendor_id == v.id)):
        t.vendor_id, t.vendor_status, t.vendor_requested_on, t.vendor_booked_for = None, None, None, None
    for c in db.scalars(select(m.Completion).where(m.Completion.vendor_id == v.id)):
        c.vendor_id = None
    for p in db.scalars(select(m.SparePart).where(m.SparePart.vendor_id == v.id)):
        p.vendor_id = None  # the part keeps the name as plain text
    db.delete(v)
    db.commit()
    return {"ok": True}


# =============================== spare parts / shopping ===============================
def _part_vendor(db: Session, ctx: Ctx, body: s.PartIn) -> None:
    """The supplier is a vendor from the shared list; keep its name in `supplier` as well."""
    if body.vendor_id is None:
        body.supplier = None
        return
    v = db.get(m.Vendor, body.vendor_id)
    if v is None or v.group_id != ctx.group.id:
        raise HTTPException(400, "Vendor not found")
    body.supplier = v.company


@router.post("/assets/{asset_id}/parts", response_model=s.PartOut)
def create_part(asset_id: int, body: s.PartIn, ctx: Ctx = Depends(require("parts.manage")),
                db: Session = Depends(get_db)):
    _asset(db, ctx, asset_id)
    _check_component(db, asset_id, body.component_id)
    _part_vendor(db, ctx, body)
    p = m.SparePart(asset_id=asset_id, **body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return part_out(p)


@router.put("/parts/{part_id}", response_model=s.PartOut)
def update_part(part_id: int, body: s.PartIn, ctx: Ctx = Depends(require("parts.manage")),
                db: Session = Depends(get_db)):
    p = _mine(db, ctx, m.SparePart, part_id)
    _check_component(db, p.asset_id, body.component_id)
    _part_vendor(db, ctx, body)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return part_out(p)


@router.delete("/parts/{part_id}")
def delete_part(part_id: int, ctx: Ctx = Depends(require("parts.manage")), db: Session = Depends(get_db)):
    p = _mine(db, ctx, m.SparePart, part_id)
    _delete_files(db, "part", part_id)
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.get("/shopping-list", response_model=list[s.PartOut])
def shopping_list(ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    """Parts flagged for purchase, plus anything below its minimum stock."""
    parts = db.scalars(select(m.SparePart).where(m.SparePart.asset_id.in_(group_asset_ids(db, ctx.group.id)))).all()
    out = [part_out(p) for p in parts if p.on_shopping_list or (p.min_qty > 0 and p.qty_in_stock < p.min_qty)]
    out.sort(key=lambda p: (p.supplier or "~", p.name))
    return out


@router.post("/parts/{part_id}/bought", response_model=s.PartOut)
def mark_bought(part_id: int, body: Optional[s.PurchaseIn] = None, ctx: Ctx = Depends(require("parts.manage")),
                db: Session = Depends(get_db)):
    """Register a purchase: adds the quantity to stock, takes it off the shopping list and records the cost."""
    user = ctx.user
    p = _mine(db, ctx, m.SparePart, part_id)
    if body is None:
        qty = p.qty_to_buy if p.on_shopping_list else max(p.min_qty - p.qty_in_stock, 1)
        body = s.PurchaseIn(qty=max(qty, 1), unit_price=p.unit_price)
    if body.unit_price is not None:
        p.unit_price = body.unit_price  # remember the latest price
    purchase = m.Purchase(
        asset_id=p.asset_id, part_id=p.id, part_name=p.name, bought_on=body.bought_on, qty=body.qty,
        unit_price=body.unit_price,
        total=round(body.qty * body.unit_price, 2) if body.unit_price is not None else None,
        bought_by_id=user.id,
    )
    db.add(purchase)
    p.qty_in_stock += body.qty
    p.on_shopping_list = False
    db.commit()
    db.refresh(p)
    out = part_out(p)
    out.last_purchase_id = purchase.id  # lets the app attach the receipt right away
    return out


@router.get("/purchases", response_model=list[s.PurchaseOut])
def list_purchases(asset_id: Optional[int] = None, part_id: Optional[int] = None,
                   ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    q = (select(m.Purchase).where(m.Purchase.asset_id.in_(group_asset_ids(db, ctx.group.id)))
         .order_by(m.Purchase.bought_on.desc(), m.Purchase.id.desc()))
    if asset_id:
        q = q.where(m.Purchase.asset_id == asset_id)
    if part_id:
        q = q.where(m.Purchase.part_id == part_id)
    return db.scalars(q).all()


@router.delete("/purchases/{purchase_id}")
def delete_purchase(purchase_id: int, ctx: Ctx = Depends(require("history.delete")),
                    db: Session = Depends(get_db)):
    """Undo a purchase: removes the cost and takes the quantity back out of stock."""
    pu = _mine(db, ctx, m.Purchase, purchase_id)
    if pu.part_id:
        part = db.get(m.SparePart, pu.part_id)
        if part:
            part.qty_in_stock = max(part.qty_in_stock - pu.qty, 0)
    _delete_files(db, "purchase", pu.id)
    db.delete(pu)
    db.commit()
    return {"ok": True}


# =============================== warranties ===============================
@router.get("/warranties", response_model=list[s.WarrantyOut])
def list_warranties(ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    ws = db.scalars(select(m.Warranty).where(m.Warranty.asset_id.in_(group_asset_ids(db, ctx.group.id)))).all()
    return sorted([warranty_out(w) for w in ws], key=lambda w: w.end_date or date.max)


@router.post("/assets/{asset_id}/warranties", response_model=s.WarrantyOut)
def create_warranty(asset_id: int, body: s.WarrantyIn, ctx: Ctx = Depends(require("warranties.manage")),
                    db: Session = Depends(get_db)):
    _asset(db, ctx, asset_id)
    _check_component(db, asset_id, body.component_id)
    w = m.Warranty(asset_id=asset_id, **body.model_dump())
    db.add(w)
    db.commit()
    db.refresh(w)
    return warranty_out(w)


@router.put("/warranties/{warranty_id}", response_model=s.WarrantyOut)
def update_warranty(warranty_id: int, body: s.WarrantyIn, ctx: Ctx = Depends(require("warranties.manage")),
                    db: Session = Depends(get_db)):
    w = _mine(db, ctx, m.Warranty, warranty_id)
    _check_component(db, w.asset_id, body.component_id)
    for k, v in body.model_dump().items():
        setattr(w, k, v)
    db.commit()
    db.refresh(w)
    return warranty_out(w)


@router.delete("/warranties/{warranty_id}")
def delete_warranty(warranty_id: int, ctx: Ctx = Depends(require("warranties.manage")),
                    db: Session = Depends(get_db)):
    w = _mine(db, ctx, m.Warranty, warranty_id)
    _delete_files(db, "warranty", warranty_id)
    db.delete(w)
    db.commit()
    return {"ok": True}


# =============================== attachments ===============================
ENTITY_MODELS = {
    "asset": m.Asset, "component": m.Component, "task": m.Task,
    "completion": m.Completion, "part": m.SparePart, "warranty": m.Warranty, "purchase": m.Purchase,
}


def _entity(db: Session, ctx: Ctx, entity_type: str, entity_id: int):
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        raise HTTPException(400, "Unknown entity type")
    return _mine(db, ctx, model, entity_id)


@router.get("/attachments", response_model=list[s.AttachmentOut])
def list_attachments(entity_type: str, entity_id: int, ctx: Ctx = Depends(group_ctx),
                     db: Session = Depends(get_db)):
    _entity(db, ctx, entity_type, entity_id)
    return db.scalars(select(m.Attachment).where(
        m.Attachment.entity_type == entity_type, m.Attachment.entity_id == entity_id
    ).order_by(m.Attachment.uploaded_at.desc())).all()


@router.post("/attachments", response_model=s.AttachmentOut)
async def upload_attachment(
    entity_type: str = Form(...),
    entity_id: int = Form(...),
    file: UploadFile = File(...),
    ctx: Ctx = Depends(require("attachments.add")),
    db: Session = Depends(get_db),
):
    user = ctx.user
    _entity(db, ctx, entity_type, entity_id)
    data = await file.read()
    if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File larger than {MAX_UPLOAD_MB} MB")
    original = Path(file.filename or "file").name
    stored = f"{uuid.uuid4().hex}{Path(original).suffix.lower()[:10]}"
    (UPLOAD_DIR / stored).write_bytes(data)
    att = m.Attachment(
        entity_type=entity_type, entity_id=entity_id, filename=original, stored_name=stored,
        content_type=file.content_type or mimetypes.guess_type(original)[0] or "application/octet-stream",
        size=len(data), uploaded_by_id=user.id,
    )
    db.add(att)
    db.commit()
    return att


@router.get("/attachments/{attachment_id}/file")
def download_attachment(attachment_id: int, ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    att = _get_or_404(db, m.Attachment, attachment_id)
    _entity(db, ctx, att.entity_type, att.entity_id)
    path = UPLOAD_DIR / att.stored_name
    if not path.exists():
        raise HTTPException(404, "File missing on disk")
    return FileResponse(path, media_type=att.content_type, filename=att.filename)


@router.delete("/attachments/{attachment_id}")
def delete_attachment(attachment_id: int, ctx: Ctx = Depends(require("attachments.delete")),
                      db: Session = Depends(get_db)):
    att = _get_or_404(db, m.Attachment, attachment_id)
    _entity(db, ctx, att.entity_type, att.entity_id)
    (UPLOAD_DIR / att.stored_name).unlink(missing_ok=True)
    db.delete(att)
    db.commit()
    return {"ok": True}


# =============================== templates ===============================
@router.get("/templates")
def get_templates(kind: str, user: m.User = Depends(current_user)):
    return list_templates(kind, user.lang)


@router.post("/assets/{asset_id}/apply-template")
def apply_template(asset_id: int, key: str = Query(...), start: Optional[date] = None,
                   ctx: Ctx = Depends(require("templates.apply")), db: Session = Depends(get_db)):
    """Create the template's components and tasks on the asset. Existing items with the same name are reused."""
    user = ctx.user
    asset = _asset(db, ctx, asset_id)
    tpl = find_template(key)
    if tpl is None:
        raise HTTPException(404, "Template not found")
    lang = user.lang if user.lang in ("en", "no") else "en"
    start = start or date.today()

    existing_components = {c.name.lower(): c for c in asset.components}
    comp_by_key: dict[str, m.Component] = {}
    for ckey, names in tpl["components"].items():
        name = names[lang]
        comp = existing_components.get(name.lower())
        if comp is None:
            comp = m.Component(asset_id=asset.id, name=name)
            db.add(comp)
            db.flush()
        comp_by_key[ckey] = comp

    existing_tasks = {t.title.lower() for t in asset.tasks}
    created = 0
    for title_en, title_no, value, unit, ckey, *season in tpl["tasks"]:
        title = title_no if lang == "no" else title_en
        due = start
        if season:  # seasonal job: next occurrence of that day of the year
            month, day = map(int, season[0].split("-"))
            due = date(start.year, month, day)
            if due < start - timedelta(days=30):  # just passed (within a month) = still to do now
                due = date(start.year + 1, month, day)
        if title.lower() in existing_tasks:
            continue
        db.add(m.Task(
            asset_id=asset.id, title=title, interval_value=value, interval_unit=unit,
            component_id=comp_by_key[ckey].id if ckey else None,
            next_due=due, remind_days_before=14 if season else 7 if unit in ("months", "years") else 1,
            created_by_id=user.id,
        ))
        created += 1
    db.commit()
    return {"tasks_created": created, "components": len(comp_by_key)}


# =============================== dashboard & calendar ===============================
@router.get("/dashboard")
def dashboard(mine: bool = False, asset_id: Optional[int] = None,
              ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    """Overview. asset_id limits everything (tasks, costs, recent work, warranties, parts) to one thing."""
    user = ctx.user
    mine_ids = group_asset_ids(db, ctx.group.id)
    today = date.today()
    q = select(m.Task).where(m.Task.active.is_(True), m.Task.asset_id.in_(mine_ids))
    if asset_id:
        q = q.where(m.Task.asset_id == asset_id)
    if mine:
        q = q.where((m.Task.assigned_to_id == user.id) | (m.Task.assigned_to_id.is_(None)))
    tasks = [task_out(t) for t in db.scalars(q)]
    overdue = sorted([t for t in tasks if t.status == "overdue"], key=lambda t: t.next_due or date.min)
    due_soon = sorted([t for t in tasks if t.status == "due_soon"], key=lambda t: t.next_due or date.min)
    upcoming = sorted(
        [t for t in tasks if t.status == "ok" and t.next_due and t.next_due <= today + timedelta(days=60)],
        key=lambda t: t.next_due,
    )

    year_start = date(today.year, 1, 1)
    cq = select(m.Completion).join(m.Task).where(m.Task.asset_id.in_(mine_ids))
    if asset_id:
        cq = cq.where(m.Task.asset_id == asset_id)
    comps = db.scalars(cq.where(m.Completion.done_on >= year_start)).all()
    pq_cost = select(m.Purchase).where(m.Purchase.asset_id.in_(mine_ids))
    if asset_id:
        pq_cost = pq_cost.where(m.Purchase.asset_id == asset_id)
    buys = db.scalars(pq_cost.where(m.Purchase.bought_on >= year_start)).all()
    cost_by_asset: dict[str, float] = {}
    for c in comps:
        cost_by_asset[c.task.asset.name] = cost_by_asset.get(c.task.asset.name, 0) + (c.cost or 0)
    for b in buys:
        cost_by_asset[b.asset.name] = cost_by_asset.get(b.asset.name, 0) + (b.total or 0)
    recent_work = db.scalars(cq.order_by(m.Completion.done_on.desc(), m.Completion.id.desc()).limit(8)).all()
    recent_buys = db.scalars(pq_cost.order_by(m.Purchase.bought_on.desc(), m.Purchase.id.desc()).limit(8)).all()
    recent = [
        {**completion_out(c).model_dump(), "kind": "work", "task_title": c.task.title,
         "asset_name": c.task.asset.name, "asset_id": c.task.asset_id, "date": c.done_on}
        for c in recent_work
    ] + [
        {"kind": "purchase", "id": b.id, "task_title": f"{b.part_name} × {b.qty}", "asset_name": b.asset.name,
         "asset_id": b.asset_id, "done_on": b.bought_on, "date": b.bought_on, "cost": b.total,
         "done_by_name": b.bought_by.name if b.bought_by else None, "task_id": None}
        for b in recent_buys
    ]
    recent = sorted(recent, key=lambda r: (r["date"], r["id"]), reverse=True)[:8]

    wq = select(m.Warranty).where(m.Warranty.end_date >= today, m.Warranty.end_date <= today + timedelta(days=90),
                                  m.Warranty.asset_id.in_(mine_ids))
    pq = select(m.SparePart).where(m.SparePart.asset_id.in_(mine_ids))
    if asset_id:
        wq = wq.where(m.Warranty.asset_id == asset_id)
        pq = pq.where(m.SparePart.asset_id == asset_id)
    warranties = [warranty_out(w) for w in db.scalars(wq)]
    parts = db.scalars(pq).all()
    shopping = sum(1 for p in parts if p.on_shopping_list or (p.min_qty > 0 and p.qty_in_stock < p.min_qty))

    return {
        "overdue": overdue,
        "due_soon": due_soon,
        "upcoming": upcoming,
        "cost_this_year": round(sum(c.cost or 0 for c in comps) + sum(b.total or 0 for b in buys), 2),
        "done_this_year": len(comps),
        "cost_by_asset": [{"asset": k, "cost": round(v, 2)} for k, v in sorted(cost_by_asset.items(), key=lambda kv: -kv[1])],
        "recent": recent,
        "warranties_expiring": warranties,
        "shopping_count": shopping,
        "asset_count": db.scalar(select(func.count(m.Asset.id)).where(m.Asset.group_id == ctx.group.id)),
    }


@router.get("/calendar")
def calendar(start: date, end: date, mine: bool = False, asset_id: Optional[int] = None,
             ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    if (end - start).days > 400:
        raise HTTPException(400, "Range too large")
    return calendar_events(db, start, end, ctx.user.id if mine else None, asset_id, [ctx.group.id])


@router.get("/costs")
def costs(year: Optional[int] = None, asset_id: Optional[int] = None,
          ctx: Ctx = Depends(group_ctx), db: Session = Depends(get_db)):
    """All spending (work done + parts bought), newest first. For export / overview."""
    mine_ids = group_asset_ids(db, ctx.group.id)
    cq = select(m.Completion).join(m.Task).where(m.Task.asset_id.in_(mine_ids))
    pq = select(m.Purchase).where(m.Purchase.asset_id.in_(mine_ids))
    if year:
        cq = cq.where(m.Completion.done_on >= date(year, 1, 1), m.Completion.done_on <= date(year, 12, 31))
        pq = pq.where(m.Purchase.bought_on >= date(year, 1, 1), m.Purchase.bought_on <= date(year, 12, 31))
    if asset_id:
        cq = cq.where(m.Task.asset_id == asset_id)
        pq = pq.where(m.Purchase.asset_id == asset_id)
    rows = [
        {"kind": "work", "date": c.done_on, "title": c.task.title, "asset_name": c.task.asset.name, "cost": c.cost}
        for c in db.scalars(cq)
    ] + [
        {"kind": "purchase", "date": b.bought_on, "title": f"{b.part_name} × {b.qty}", "asset_name": b.asset.name, "cost": b.total}
        for b in db.scalars(pq)
    ]
    return sorted(rows, key=lambda r: r["date"], reverse=True)


@router.get("/interval-preview")
def interval_preview(start: date, value: int, unit: str, _: m.User = Depends(current_user)):
    """Small helper for the form: show the next three due dates."""
    out, d = [], start
    for _ in range(3):
        if d is None:
            break
        out.append(d)
        d = add_interval(d, value, unit)
    return out
