import mimetypes
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .auth import (admin_user, create_token, current_user, hash_password, new_ical_token,
                   verify_password)
from .config import MAX_UPLOAD_MB, PUBLIC_URL, UPLOAD_DIR
from .db import get_db
from .recurrence import add_interval, next_counter_after_completion, next_due_after_completion
from .services import (asset_total_cost, calendar_events, completion_out, part_out, task_out,
                       task_status, warranty_out)
from .templates_data import find_template, list_templates

router = APIRouter(prefix="/api")


def _get_or_404(db: Session, model, obj_id: int):
    obj = db.get(model, obj_id)
    if obj is None:
        raise HTTPException(404, f"{model.__name__} {obj_id} not found")
    return obj


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


def _check_refs(db: Session, body: s.TaskIn) -> None:
    if body.vendor_id is not None and db.get(m.Vendor, body.vendor_id) is None:
        raise HTTPException(400, "Vendor not found")
    if body.assigned_to_id is not None and db.get(m.User, body.assigned_to_id) is None:
        raise HTTPException(400, "User not found")


def _check_component(db: Session, asset_id: int, component_id: Optional[int]) -> None:
    if component_id is None:
        return
    comp = db.get(m.Component, component_id)
    if comp is None or comp.asset_id != asset_id:
        raise HTTPException(400, "Component does not belong to this asset")


# =============================== auth & users ===============================
@router.get("/auth/status")
def auth_status(db: Session = Depends(get_db)):
    has_users = db.scalar(select(func.count(m.User.id))) > 0
    return {"needs_setup": not has_users}


@router.post("/auth/setup", response_model=s.TokenOut)
def first_setup(body: s.SetupIn, db: Session = Depends(get_db)):
    """Creates the first (admin) user. Only works while the database has no users."""
    if db.scalar(select(func.count(m.User.id))) > 0:
        raise HTTPException(400, "Setup already done")
    user = m.User(name=body.name, email=body.email.lower().strip(), lang=body.lang,
                  password_hash=hash_password(body.password), is_admin=True,
                  ical_token=new_ical_token())
    db.add(user)
    db.commit()
    return s.TokenOut(token=create_token(user), user=s.UserOut.model_validate(user))


@router.post("/auth/login", response_model=s.TokenOut)
def login(body: s.LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(m.User).where(m.User.email == body.email.lower().strip()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong e-mail or password")
    return s.TokenOut(token=create_token(user), user=s.UserOut.model_validate(user))


@router.get("/me")
def me(user: m.User = Depends(current_user)):
    out = s.UserOut.model_validate(user).model_dump()
    out["ical_url"] = f"{PUBLIC_URL}/ical/{user.ical_token}.ics"
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


@router.post("/me/ical-reset")
def reset_ical(user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    user.ical_token = new_ical_token()
    db.add(user)
    db.commit()
    return {"ical_url": f"{PUBLIC_URL}/ical/{user.ical_token}.ics"}


@router.get("/users", response_model=list[s.UserOut])
def list_users(_: m.User = Depends(current_user), db: Session = Depends(get_db)):
    return db.scalars(select(m.User).order_by(m.User.name)).all()


@router.post("/users", response_model=s.UserOut)
def create_user(body: s.UserCreate, _: m.User = Depends(admin_user), db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    if db.scalar(select(m.User).where(m.User.email == email)):
        raise HTTPException(400, "E-mail already in use")
    user = m.User(name=body.name, email=email, lang=body.lang, is_admin=body.is_admin,
                  password_hash=hash_password(body.password), ical_token=new_ical_token())
    db.add(user)
    db.commit()
    return user


@router.patch("/users/{user_id}", response_model=s.UserOut)
def update_user(user_id: int, body: s.UserUpdate, admin: m.User = Depends(admin_user),
                db: Session = Depends(get_db)):
    user = _get_or_404(db, m.User, user_id)
    for field in ("name", "lang", "email_reminders", "is_admin"):
        value = getattr(body, field)
        if value is not None:
            setattr(user, field, value)
    if body.password:
        user.password_hash = hash_password(body.password)
    if user.id == admin.id and body.is_admin is False:
        raise HTTPException(400, "You cannot remove your own admin rights")
    db.commit()
    return user


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: m.User = Depends(admin_user), db: Session = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(400, "You cannot delete yourself")
    db.delete(_get_or_404(db, m.User, user_id))
    db.commit()
    return {"ok": True}


# =============================== assets ===============================
@router.get("/assets", response_model=list[s.AssetSummary])
def list_assets(_: m.User = Depends(current_user), db: Session = Depends(get_db)):
    out = []
    for a in db.scalars(select(m.Asset).order_by(m.Asset.name)):
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
def create_asset(body: s.AssetIn, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    data = body.model_dump()
    value = data.pop("counter_value")
    asset = m.Asset(**data)
    db.add(asset)
    db.flush()
    if value is not None and asset.counter_unit != "none":
        _record_reading(db, asset, value, date.today(), user.id)
    db.commit()
    return asset


@router.get("/assets/{asset_id}", response_model=s.AssetDetail)
def get_asset(asset_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    a = _get_or_404(db, m.Asset, asset_id)
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
def update_asset(asset_id: int, body: s.AssetIn, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    a = _get_or_404(db, m.Asset, asset_id)
    data = body.model_dump()
    value = data.pop("counter_value")
    for k, v in data.items():
        setattr(a, k, v)
    if value is not None and a.counter_unit != "none" and value != a.counter_value:
        _record_reading(db, a, value, date.today(), user.id)
    db.commit()
    return a


@router.post("/assets/{asset_id}/counter", response_model=s.AssetOut)
def add_counter_reading(asset_id: int, body: s.CounterIn, user: m.User = Depends(current_user),
                        db: Session = Depends(get_db)):
    a = _get_or_404(db, m.Asset, asset_id)
    if a.counter_unit == "none":
        raise HTTPException(400, "This thing has no km / hour counter")
    _record_reading(db, a, body.value, body.reading_on, user.id)
    db.commit()
    return a


@router.delete("/counter-readings/{reading_id}")
def delete_counter_reading(reading_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    r = _get_or_404(db, m.CounterReading, reading_id)
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
def delete_asset(asset_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    a = _get_or_404(db, m.Asset, asset_id)
    # remove the files of the asset and of everything that belongs to it
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
    db.commit()
    return {"ok": True}


# =============================== components ===============================
@router.post("/assets/{asset_id}/components", response_model=s.ComponentOut)
def create_component(asset_id: int, body: s.ComponentIn, _: m.User = Depends(current_user),
                     db: Session = Depends(get_db)):
    _get_or_404(db, m.Asset, asset_id)
    c = m.Component(asset_id=asset_id, **body.model_dump())
    db.add(c)
    db.commit()
    return c


@router.put("/components/{component_id}", response_model=s.ComponentOut)
def update_component(component_id: int, body: s.ComponentIn, _: m.User = Depends(current_user),
                     db: Session = Depends(get_db)):
    c = _get_or_404(db, m.Component, component_id)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    db.commit()
    return c


@router.delete("/components/{component_id}")
def delete_component(component_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    _delete_files(db, "component", component_id)
    db.delete(_get_or_404(db, m.Component, component_id))
    db.commit()
    return {"ok": True}


# =============================== tasks ===============================
@router.get("/tasks", response_model=list[s.TaskOut])
def list_tasks(
    status: Optional[str] = Query(None, description="overdue | due_soon | ok | none | inactive | open"),
    asset_id: Optional[int] = None,
    mine: bool = False,
    user: m.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = select(m.Task)
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
def create_task(asset_id: int, body: s.TaskIn, user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    _get_or_404(db, m.Asset, asset_id)
    _check_component(db, asset_id, body.component_id)
    _check_refs(db, body)
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
def get_task(task_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    return task_out(_get_or_404(db, m.Task, task_id), detail=True)


@router.put("/tasks/{task_id}", response_model=s.TaskOut)
def update_task(task_id: int, body: s.TaskIn, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    t = _get_or_404(db, m.Task, task_id)
    _check_component(db, t.asset_id, body.component_id)
    _check_refs(db, body)
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
def delete_task(task_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    t = _get_or_404(db, m.Task, task_id)
    _delete_files(db, "task", t.id)
    for c in t.completions:
        _delete_files(db, "completion", c.id)
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.post("/tasks/{task_id}/complete", response_model=s.TaskDetail)
def complete_task(task_id: int, body: s.CompletionIn, user: m.User = Depends(current_user),
                  db: Session = Depends(get_db)):
    """Log that the task was done; recurring tasks get a new due date, one-off tasks are closed."""
    t = _get_or_404(db, m.Task, task_id)
    if body.vendor_id is not None and db.get(m.Vendor, body.vendor_id) is None:
        raise HTTPException(400, "Vendor not found")
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
def set_vendor_status(task_id: int, body: s.VendorStatusIn, _: m.User = Depends(current_user),
                      db: Session = Depends(get_db)):
    """requested (the request was sent), confirmed (vendor agreed a date), none (start over)."""
    t = _get_or_404(db, m.Task, task_id)
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
def delete_completion(completion_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    _delete_files(db, "completion", completion_id)
    db.delete(_get_or_404(db, m.Completion, completion_id))
    db.commit()
    return {"ok": True}


# =============================== vendors ===============================
def _vendor_out(db: Session, v: m.Vendor) -> s.VendorOut:
    n = db.scalar(select(func.count(m.Task.id)).where(m.Task.vendor_id == v.id, m.Task.active.is_(True))) or 0
    return s.VendorOut.model_validate(v).model_copy(update={"open_tasks": n})


@router.get("/vendors", response_model=list[s.VendorOut])
def list_vendors(_: m.User = Depends(current_user), db: Session = Depends(get_db)):
    vendors = db.scalars(select(m.Vendor).order_by(m.Vendor.company)).all()
    return [_vendor_out(db, v) for v in vendors]


@router.post("/vendors", response_model=s.VendorOut)
def create_vendor(body: s.VendorIn, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    v = m.Vendor(**body.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return _vendor_out(db, v)


@router.get("/vendors/{vendor_id}", response_model=s.VendorOut)
def get_vendor(vendor_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    return _vendor_out(db, _get_or_404(db, m.Vendor, vendor_id))


@router.get("/vendors/{vendor_id}/history", response_model=s.VendorHistory)
def vendor_history(vendor_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    """Open tasks given to the vendor, jobs they did, and what they have cost."""
    v = _get_or_404(db, m.Vendor, vendor_id)
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
def update_vendor(vendor_id: int, body: s.VendorIn, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    v = _get_or_404(db, m.Vendor, vendor_id)
    for k, val in body.model_dump().items():
        setattr(v, k, val)
    for p in db.scalars(select(m.SparePart).where(m.SparePart.vendor_id == v.id)):
        p.supplier = v.company  # keep the stored name in step with the vendor list
    db.commit()
    db.refresh(v)
    return _vendor_out(db, v)


@router.delete("/vendors/{vendor_id}")
def delete_vendor(vendor_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    v = _get_or_404(db, m.Vendor, vendor_id)
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
def _part_vendor(db: Session, body: s.PartIn) -> None:
    """The supplier is a vendor from the shared list; keep its name in `supplier` as well."""
    if body.vendor_id is None:
        body.supplier = None
        return
    v = db.get(m.Vendor, body.vendor_id)
    if v is None:
        raise HTTPException(400, "Vendor not found")
    body.supplier = v.company


@router.post("/assets/{asset_id}/parts", response_model=s.PartOut)
def create_part(asset_id: int, body: s.PartIn, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    _get_or_404(db, m.Asset, asset_id)
    _check_component(db, asset_id, body.component_id)
    _part_vendor(db, body)
    p = m.SparePart(asset_id=asset_id, **body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return part_out(p)


@router.put("/parts/{part_id}", response_model=s.PartOut)
def update_part(part_id: int, body: s.PartIn, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    p = _get_or_404(db, m.SparePart, part_id)
    _check_component(db, p.asset_id, body.component_id)
    _part_vendor(db, body)
    for k, v in body.model_dump().items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return part_out(p)


@router.delete("/parts/{part_id}")
def delete_part(part_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    _delete_files(db, "part", part_id)
    db.delete(_get_or_404(db, m.SparePart, part_id))
    db.commit()
    return {"ok": True}


@router.get("/shopping-list", response_model=list[s.PartOut])
def shopping_list(_: m.User = Depends(current_user), db: Session = Depends(get_db)):
    """Parts flagged for purchase, plus anything below its minimum stock."""
    parts = db.scalars(select(m.SparePart)).all()
    out = [part_out(p) for p in parts if p.on_shopping_list or (p.min_qty > 0 and p.qty_in_stock < p.min_qty)]
    out.sort(key=lambda p: (p.supplier or "~", p.name))
    return out


@router.post("/parts/{part_id}/bought", response_model=s.PartOut)
def mark_bought(part_id: int, body: Optional[s.PurchaseIn] = None, user: m.User = Depends(current_user),
                db: Session = Depends(get_db)):
    """Register a purchase: adds the quantity to stock, takes it off the shopping list and records the cost."""
    p = _get_or_404(db, m.SparePart, part_id)
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
                   _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(m.Purchase).order_by(m.Purchase.bought_on.desc(), m.Purchase.id.desc())
    if asset_id:
        q = q.where(m.Purchase.asset_id == asset_id)
    if part_id:
        q = q.where(m.Purchase.part_id == part_id)
    return db.scalars(q).all()


@router.delete("/purchases/{purchase_id}")
def delete_purchase(purchase_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    """Undo a purchase: removes the cost and takes the quantity back out of stock."""
    pu = _get_or_404(db, m.Purchase, purchase_id)
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
def list_warranties(_: m.User = Depends(current_user), db: Session = Depends(get_db)):
    ws = db.scalars(select(m.Warranty)).all()
    return sorted([warranty_out(w) for w in ws], key=lambda w: w.end_date or date.max)


@router.post("/assets/{asset_id}/warranties", response_model=s.WarrantyOut)
def create_warranty(asset_id: int, body: s.WarrantyIn, _: m.User = Depends(current_user),
                    db: Session = Depends(get_db)):
    _get_or_404(db, m.Asset, asset_id)
    _check_component(db, asset_id, body.component_id)
    w = m.Warranty(asset_id=asset_id, **body.model_dump())
    db.add(w)
    db.commit()
    db.refresh(w)
    return warranty_out(w)


@router.put("/warranties/{warranty_id}", response_model=s.WarrantyOut)
def update_warranty(warranty_id: int, body: s.WarrantyIn, _: m.User = Depends(current_user),
                    db: Session = Depends(get_db)):
    w = _get_or_404(db, m.Warranty, warranty_id)
    _check_component(db, w.asset_id, body.component_id)
    for k, v in body.model_dump().items():
        setattr(w, k, v)
    db.commit()
    db.refresh(w)
    return warranty_out(w)


@router.delete("/warranties/{warranty_id}")
def delete_warranty(warranty_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    _delete_files(db, "warranty", warranty_id)
    db.delete(_get_or_404(db, m.Warranty, warranty_id))
    db.commit()
    return {"ok": True}


# =============================== attachments ===============================
ENTITY_MODELS = {
    "asset": m.Asset, "component": m.Component, "task": m.Task,
    "completion": m.Completion, "part": m.SparePart, "warranty": m.Warranty, "purchase": m.Purchase,
}


@router.get("/attachments", response_model=list[s.AttachmentOut])
def list_attachments(entity_type: str, entity_id: int, _: m.User = Depends(current_user),
                     db: Session = Depends(get_db)):
    return db.scalars(select(m.Attachment).where(
        m.Attachment.entity_type == entity_type, m.Attachment.entity_id == entity_id
    ).order_by(m.Attachment.uploaded_at.desc())).all()


@router.post("/attachments", response_model=s.AttachmentOut)
async def upload_attachment(
    entity_type: str = Form(...),
    entity_id: int = Form(...),
    file: UploadFile = File(...),
    user: m.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        raise HTTPException(400, "Unknown entity type")
    _get_or_404(db, model, entity_id)
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
def download_attachment(attachment_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    att = _get_or_404(db, m.Attachment, attachment_id)
    path = UPLOAD_DIR / att.stored_name
    if not path.exists():
        raise HTTPException(404, "File missing on disk")
    return FileResponse(path, media_type=att.content_type, filename=att.filename)


@router.delete("/attachments/{attachment_id}")
def delete_attachment(attachment_id: int, _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    att = _get_or_404(db, m.Attachment, attachment_id)
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
                   user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    """Create the template's components and tasks on the asset. Existing items with the same name are reused."""
    asset = _get_or_404(db, m.Asset, asset_id)
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
              user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    """Overview. asset_id limits everything (tasks, costs, recent work, warranties, parts) to one thing."""
    today = date.today()
    q = select(m.Task).where(m.Task.active.is_(True))
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
    cq = select(m.Completion).join(m.Task)
    if asset_id:
        cq = cq.where(m.Task.asset_id == asset_id)
    comps = db.scalars(cq.where(m.Completion.done_on >= year_start)).all()
    pq_cost = select(m.Purchase)
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

    wq = select(m.Warranty).where(m.Warranty.end_date >= today, m.Warranty.end_date <= today + timedelta(days=90))
    pq = select(m.SparePart)
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
        "asset_count": db.scalar(select(func.count(m.Asset.id))),
    }


@router.get("/calendar")
def calendar(start: date, end: date, mine: bool = False, asset_id: Optional[int] = None,
             user: m.User = Depends(current_user), db: Session = Depends(get_db)):
    if (end - start).days > 400:
        raise HTTPException(400, "Range too large")
    return calendar_events(db, start, end, user.id if mine else None, asset_id)


@router.get("/costs")
def costs(year: Optional[int] = None, asset_id: Optional[int] = None,
          _: m.User = Depends(current_user), db: Session = Depends(get_db)):
    """All spending (work done + parts bought), newest first. For export / overview."""
    cq = select(m.Completion).join(m.Task)
    pq = select(m.Purchase)
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
