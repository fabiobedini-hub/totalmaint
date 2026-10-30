"""Shared helpers: turning DB rows into API objects, status calculation, calendar projection."""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from . import schemas as s
from .recurrence import add_interval, counter_status, worst_status


def counted(task: m.Task) -> bool:
    """True when the task follows the asset's km / engine-hour counter."""
    unit = task.asset.counter_unit if task.asset else None
    return bool(unit and unit != "none" and task.counter_interval)


def task_status(task: m.Task, today: date | None = None) -> str:
    """By date, by counter, or both – whichever comes first."""
    today = today or date.today()
    if not task.active:
        return "inactive"
    by_date = None
    if task.next_due is not None:
        if task.next_due < today:
            by_date = "overdue"
        elif task.next_due <= today + timedelta(days=task.remind_days_before):
            by_date = "due_soon"
        else:
            by_date = "ok"
    by_counter = None
    if counted(task):
        by_counter = counter_status(task.asset.counter_value, task.counter_next_due,
                                    task.counter_interval, task.counter_remind_before)
    return worst_status(by_date, by_counter) or "none"


def counter_text(task: m.Task, no: bool) -> str:
    """Short text for e-mails: 'at 1200 h (now 1150 h)'."""
    unit = {"km": "km", "hours": "t" if no else "h"}.get(task.asset.counter_unit, "")
    nxt, cur = task.counter_next_due, task.asset.counter_value
    if nxt is None:
        return ""
    txt = f"{'ved' if no else 'at'} {nxt:,.0f} {unit}".replace(",", " ")
    if cur is not None:
        txt += f" ({'nå' if no else 'now'} {cur:,.0f} {unit})".replace(",", " ")
    return txt


def task_out(task: m.Task, detail: bool = False) -> s.TaskOut | s.TaskDetail:
    completions = task.completions
    data = dict(
        id=task.id,
        asset_id=task.asset_id,
        asset_name=task.asset.name if task.asset else "",
        asset_kind=task.asset.kind if task.asset else "",
        component_id=task.component_id,
        component_name=task.component.name if task.component else None,
        title=task.title,
        description=task.description,
        interval_value=task.interval_value,
        interval_unit=task.interval_unit,
        next_due=task.next_due,
        remind_days_before=task.remind_days_before,
        assigned_to_id=task.assigned_to_id,
        assigned_to_name=task.assigned_to.name if task.assigned_to else None,
        vendor_id=task.vendor_id,
        vendor_name=task.vendor.company if task.vendor else None,
        vendor_phone=task.vendor.phone if task.vendor else None,
        vendor_email=task.vendor.email if task.vendor else None,
        created_by_id=task.created_by_id,
        created_by_name=task.created_by.name if task.created_by else None,
        created_at=task.created_at,
        vendor_status=task.vendor_status,
        vendor_requested_on=task.vendor_requested_on,
        vendor_booked_for=task.vendor_booked_for,
        estimated_cost=task.estimated_cost,
        active=task.active,
        status=task_status(task),
        last_done=completions[0].done_on if completions else None,
        total_cost=round(sum(c.cost or 0 for c in completions), 2),
    )
    if counted(task):
        cur, nxt = task.asset.counter_value, task.counter_next_due
        data.update(
            counter_unit=task.asset.counter_unit, counter_interval=task.counter_interval,
            counter_next_due=nxt, counter_remind_before=task.counter_remind_before, counter_current=cur,
            counter_left=round(nxt - cur, 1) if nxt is not None and cur is not None else None,
        )
    elif task.counter_interval:  # keep the setting visible in the form even if the asset has no counter now
        data.update(counter_interval=task.counter_interval, counter_next_due=task.counter_next_due)
    if not detail:
        return s.TaskOut(**data)
    data["completions"] = [completion_out(c) for c in completions]
    return s.TaskDetail(**data)


def completion_out(c: m.Completion) -> s.CompletionOut:
    return s.CompletionOut(
        id=c.id, task_id=c.task_id, done_on=c.done_on, cost=c.cost, notes=c.notes,
        done_by_name=c.done_by.name if c.done_by else None,
        counter_value=c.counter_value, vendor_id=c.vendor_id,
        vendor_name=c.vendor.company if c.vendor else None,
    )


def part_out(p: m.SparePart) -> s.PartOut:
    out = s.PartOut.model_validate(p)
    out.asset_name = p.asset.name if p.asset else ""
    out.component_name = p.component.name if p.component else None
    if p.vendor:  # always show the vendor's current name
        out.supplier = p.vendor.company
    out.below_min = p.min_qty > 0 and p.qty_in_stock < p.min_qty
    return out


def warranty_out(w: m.Warranty) -> s.WarrantyOut:
    out = s.WarrantyOut.model_validate(w)
    out.asset_name = w.asset.name if w.asset else ""
    out.component_name = w.component.name if w.component else None
    out.expired = bool(w.end_date and w.end_date < date.today())
    return out


def asset_total_cost(db: Session, asset_id: int) -> float:
    """Everything spent on an asset: work done (completions) + parts bought (purchases)."""
    work = db.scalars(select(m.Completion).join(m.Task).where(m.Task.asset_id == asset_id)).all()
    parts = db.scalars(select(m.Purchase).where(m.Purchase.asset_id == asset_id)).all()
    return round(sum(c.cost or 0 for c in work) + sum(p.total or 0 for p in parts), 2)


def calendar_events(db: Session, start: date, end: date, user_id: int | None = None,
                    asset_id: int | None = None, group_ids: list[int] | None = None) -> list[dict]:
    """Task due dates (with future recurrences projected), completions and warranty end dates in [start, end].
    group_ids: only things of these groups (always given by the API; None = everything)."""
    events: list[dict] = []
    ids = select(m.Asset.id).where(m.Asset.group_id.in_(group_ids)) if group_ids is not None else None
    q = select(m.Task).where(m.Task.active.is_(True), m.Task.next_due.is_not(None))
    if ids is not None:
        q = q.where(m.Task.asset_id.in_(ids))
    if user_id is not None:
        q = q.where((m.Task.assigned_to_id == user_id) | (m.Task.assigned_to_id.is_(None)))
    if asset_id is not None:
        q = q.where(m.Task.asset_id == asset_id)
    for t in db.scalars(q):
        due = t.next_due
        projected = False
        guard = 0
        while due and due <= end and guard < 400:
            if due >= start:
                events.append({
                    "type": "task", "id": t.id, "date": due.isoformat(),
                    "title": t.title, "asset": t.asset.name, "asset_kind": t.asset.kind,
                    "projected": projected,
                    "status": task_status(t) if not projected else "ok",
                })
            due = add_interval(due, t.interval_value, t.interval_unit)
            projected = True
            guard += 1

    # days agreed with a vendor
    bq = select(m.Task).where(m.Task.active.is_(True), m.Task.vendor_status == "confirmed",
                              m.Task.vendor_booked_for >= start, m.Task.vendor_booked_for <= end)
    if ids is not None:
        bq = bq.where(m.Task.asset_id.in_(ids))
    if user_id is not None:
        bq = bq.where((m.Task.assigned_to_id == user_id) | (m.Task.assigned_to_id.is_(None)))
    if asset_id is not None:
        bq = bq.where(m.Task.asset_id == asset_id)
    for t in db.scalars(bq):
        events.append({
            "type": "booked", "id": t.id, "date": t.vendor_booked_for.isoformat(),
            "title": f"{t.title} – {t.vendor.company}" if t.vendor else t.title,
            "asset": t.asset.name, "asset_kind": t.asset.kind, "projected": False, "status": "booked",
        })

    cq = select(m.Completion).join(m.Task).where(m.Completion.done_on >= start, m.Completion.done_on <= end)
    wq = select(m.Warranty).where(m.Warranty.end_date >= start, m.Warranty.end_date <= end)
    if ids is not None:
        cq = cq.where(m.Task.asset_id.in_(ids))
        wq = wq.where(m.Warranty.asset_id.in_(ids))
    if asset_id is not None:
        cq = cq.where(m.Task.asset_id == asset_id)
        wq = wq.where(m.Warranty.asset_id == asset_id)
    for c in db.scalars(cq):
        events.append({
            "type": "done", "id": c.task_id, "date": c.done_on.isoformat(),
            "title": c.task.title, "asset": c.task.asset.name, "asset_kind": c.task.asset.kind,
            "projected": False, "status": "done",
        })

    for w in db.scalars(wq):
        events.append({
            "type": "warranty", "id": w.id, "asset_id": w.asset_id, "date": w.end_date.isoformat(),
            "title": w.title, "asset": w.asset.name, "asset_kind": w.asset.kind,
            "projected": False, "status": "warranty",
        })
    events.sort(key=lambda e: e["date"])
    return events
