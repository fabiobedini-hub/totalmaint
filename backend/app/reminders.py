"""Daily reminder run.

Once a day (REMINDER_HOUR) every user with e-mail reminders on gets one e-mail
listing their overdue tasks and tasks inside their reminder window.
Without SMTP settings the run only logs what it would have sent, so you can
test it locally. Push notifications to the PWA can be added here later.
"""
import asyncio
import logging
import smtplib
from datetime import date, datetime, timedelta
from email.message import EmailMessage

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .auth import admin_user
from .config import (PUBLIC_URL, REMINDER_HOUR, SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT,
                     SMTP_USER)
from .db import SessionLocal, get_db
from .services import counter_text, task_status

log = logging.getLogger("totalmaint.reminders")
router = APIRouter(prefix="/api/reminders")


def collect(db: Session) -> dict[int, list[m.Task]]:
    """Tasks to remind about, per user id. Unassigned tasks go to everyone."""
    users = db.scalars(select(m.User).where(m.User.email_reminders.is_(True))).all()
    tasks = [t for t in db.scalars(select(m.Task).where(m.Task.active.is_(True)))
             if task_status(t) in ("overdue", "due_soon")]
    out: dict[int, list[m.Task]] = {}
    for u in users:
        mine = [t for t in tasks if t.assigned_to_id in (None, u.id)]
        if mine:
            out[u.id] = sorted(mine, key=lambda t: t.next_due or date.min)
    return out


def _compose(user: m.User, tasks: list[m.Task]) -> EmailMessage:
    no = user.lang == "no"
    today = date.today()
    lines = []
    for t in tasks:
        parts = []
        if t.next_due is not None:
            days = (t.next_due - today).days
            if days < 0:
                when = f"{-days} dager over frist" if no else f"{-days} days overdue"
            elif days == 0:
                when = "i dag" if no else "today"
            else:
                when = f"om {days} dager" if no else f"in {days} days"
            parts.append(f"{t.next_due:%d.%m.%Y}, {when}")
        ctext = counter_text(t, no) if t.counter_interval else ""
        if ctext:
            parts.append(ctext)
        lines.append(f"• {t.title} – {t.asset.name}" + (f" ({'; '.join(parts)})" if parts else ""))
    msg = EmailMessage()
    msg["Subject"] = (f"Vedlikehold: {len(tasks)} oppgave(r) venter" if no
                      else f"Maintenance: {len(tasks)} task(s) need attention")
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = user.email
    greeting = f"Hei {user.name}," if no else f"Hi {user.name},"
    footer = "Åpne appen" if no else "Open the app"
    msg.set_content(f"{greeting}\n\n" + "\n".join(lines) + f"\n\n{footer}: {PUBLIC_URL}\n")
    return msg


def run_once(db: Session, force: bool = False) -> list[dict]:
    """Send today's reminders. Returns a summary (also used by the preview endpoint)."""
    today = date.today()
    summary = []
    per_user = collect(db)
    for user_id, tasks in per_user.items():
        user = db.get(m.User, user_id)
        fresh = [t for t in tasks if force or t.last_reminded_on != today]
        if not fresh:
            continue
        sent, error = False, None
        if SMTP_HOST:
            try:
                send_mail(_compose(user, tasks))
                sent = True
            except Exception as exc:  # keep the scheduler alive whatever happens
                error = f"{type(exc).__name__}: {exc}"
                log.error("Reminder e-mail to %s failed: %s", user.email, error)
        else:
            error = "SMTP_HOST is not set in .env, so nothing was sent (only logged)"
            log.info("[no SMTP configured] would e-mail %s about %d task(s)", user.email, len(tasks))
        summary.append({"user": user.email, "tasks": [t.title for t in tasks], "sent": sent, "error": error})
        if sent:  # only mark as reminded when the mail really went out, so a failure is retried
            for t in fresh:
                t.last_reminded_on = today
    db.commit()
    return summary


def send_mail(msg: EmailMessage) -> None:
    """Port 465 = SSL from the start; anything else (587, 25) = plain connection upgraded with STARTTLS."""
    if SMTP_PORT == 465:
        smtp = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20)
    else:
        smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
        smtp.ehlo()
        if smtp.has_extn("starttls"):
            smtp.starttls()
            smtp.ehlo()
    with smtp:
        if SMTP_USER:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)


async def scheduler_loop() -> None:
    """Very small scheduler: wakes up every 15 minutes, runs once per day after REMINDER_HOUR."""
    last_run: date | None = None
    while True:
        now = datetime.now()
        if now.hour >= REMINDER_HOUR and last_run != now.date():
            try:
                with SessionLocal() as db:
                    run_once(db)
                last_run = now.date()
            except Exception as exc:
                log.exception("Reminder run failed: %s", exc)
        await asyncio.sleep(15 * 60)


@router.get("/preview")
def preview(_: m.User = Depends(admin_user), db: Session = Depends(get_db)):
    """What would be sent right now (does not send anything)."""
    return [
        {"user": db.get(m.User, uid).email, "tasks": [f"{t.title} ({t.next_due})" for t in tasks]}
        for uid, tasks in collect(db).items()
    ]


@router.post("/test")
def send_test(user: m.User = Depends(admin_user)):
    """Send one test e-mail to yourself, to check the SMTP settings."""
    if not SMTP_HOST:
        return {"ok": False, "error": "SMTP_HOST is not set in .env, so e-mail is switched off"}
    msg = EmailMessage()
    msg["Subject"] = "TotalMaint: test"
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = user.email
    msg.set_content("E-mail from TotalMaint works." if user.lang != "no" else "E-post fra TotalMaint virker.")
    try:
        send_mail(msg)
        return {"ok": True, "to": user.email}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


@router.post("/run")
def run_now(_: m.User = Depends(admin_user), db: Session = Depends(get_db)):
    return {"smtp_configured": bool(SMTP_HOST), "result": run_once(db, force=True)}
