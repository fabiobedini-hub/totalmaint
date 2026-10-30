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

from . import events
from . import models as m
from .auth import admin_user
from .permissions import Ctx, require
from .config import (PUBLIC_URL, REMINDER_HOUR, SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT,
                     SMTP_USER)
from .db import SessionLocal, get_db
from .services import counter_text, task_status

log = logging.getLogger("totalmaint.reminders")
router = APIRouter(prefix="/api/reminders")


def collect(db: Session, group_id: int | None = None) -> dict[int, list[m.Task]]:
    """Tasks to remind about, per user id: from the groups the user is in (every role, viewers too).
    Unassigned tasks go to every member of the group. group_id limits it to one group."""
    users = db.scalars(select(m.User).where(m.User.email_reminders.is_(True), m.User.blocked.is_(False))).all()
    tasks = [t for t in db.scalars(select(m.Task).where(m.Task.active.is_(True)))
             if task_status(t) in ("overdue", "due_soon")]
    groups_of: dict[int, set[int]] = {}
    for mem in db.scalars(select(m.Membership)):
        groups_of.setdefault(mem.user_id, set()).add(mem.group_id)
    out: dict[int, list[m.Task]] = {}
    for u in users:
        gids = groups_of.get(u.id, set())
        if group_id is not None:
            gids = gids & {group_id}
        mine = [t for t in tasks if t.asset.group_id in gids and t.assigned_to_id in (None, u.id)]
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
        if SMTP_HOST:
            events.log(db, "mail_sent" if sent else "mail_failed",
                       f"Reminder to {user.email}: {len(tasks)} task(s)" + (f" – {error}" if error else ""), user,
                       msg="mail_reminder", email=user.email, n=len(tasks), error=error or "")
        if sent:  # only mark as reminded when the mail really went out, so a failure is retried
            for t in fresh:
                t.last_reminded_on = today
    sent_n = sum(1 for x in summary if x["sent"])
    events.log(db, "reminders", f"{sent_n} of {len(summary)} reminder e-mail(s) sent"
               + ("" if SMTP_HOST else " (no SMTP: only logged)"),
               msg="reminders_run", sent=sent_n, total=len(summary), nosmtp=not SMTP_HOST)
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


def send_password_reset(user: m.User, link: str, hours: int, lang: str | None = None) -> tuple[bool, str | None]:
    """E-mail a "forgot password" link. Returns (sent, error)."""
    if not SMTP_HOST:
        return False, "SMTP_HOST is not set in .env"
    no = (lang or user.lang) == "no"
    msg = EmailMessage()
    msg["Subject"] = "TotalMaint: nytt passord" if no else "TotalMaint: reset your password"
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = user.email
    if no:
        body = (f"Hei {user.name},\n\nNoen (forhåpentligvis du) ba om å lage nytt passord i TotalMaint.\n\n"
                f"Åpne lenken for å velge et nytt passord:\n{link}\n\n"
                f"Lenken virker én gang i {hours} timer. Ba du ikke om dette, kan du se bort fra e-posten; "
                f"passordet ditt er ikke endret.\n")
    else:
        body = (f"Hi {user.name},\n\nSomeone (hopefully you) asked to reset the password for TotalMaint.\n\n"
                f"Open this link to choose a new password:\n{link}\n\n"
                f"The link works once for {hours} hours. If you didn't ask for this, ignore this e-mail; "
                f"your password has not changed.\n")
    msg.set_content(body)
    try:
        send_mail(msg)
        return True, None
    except Exception as exc:
        log.error("Password reset e-mail to %s failed: %s", user.email, exc)
        return False, f"{type(exc).__name__}: {exc}"


def send_invitation(inv: m.Invitation, lang: str) -> tuple[bool, str | None]:
    """E-mail the invitation link. Returns (sent, error). Without SMTP the link is only shown in the app."""
    if not SMTP_HOST:
        return False, "SMTP_HOST is not set in .env: copy the link and send it yourself"
    no = lang == "no"
    who = inv.invited_by.name if inv.invited_by else "TotalMaint"
    link = f"{PUBLIC_URL}/#/invite/{inv.token}"
    msg = EmailMessage()
    msg["Subject"] = (f"{who} inviterer deg til «{inv.group.name}» i TotalMaint" if no
                      else f"{who} invited you to \"{inv.group.name}\" on TotalMaint")
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = inv.email
    if no:
        body = (f"Hei,\n\n{who} har invitert deg til «{inv.group.name}» i TotalMaint, "
                f"med rollen {inv.role.name}.\n\nÅpne lenken for å bli med:\n{link}\n\n"
                f"Lenken virker én gang og går ut {inv.expires_at:%d.%m.%Y}.\n")
    else:
        body = (f"Hi,\n\n{who} has invited you to \"{inv.group.name}\" on TotalMaint "
                f"as {inv.role.name}.\n\nOpen this link to join:\n{link}\n\n"
                f"The link works once and expires on {inv.expires_at:%Y-%m-%d}.\n")
    msg.set_content(body)
    try:
        send_mail(msg)
        return True, None
    except Exception as exc:
        log.error("Invitation e-mail to %s failed: %s", inv.email, exc)
        return False, f"{type(exc).__name__}: {exc}"


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
def preview(ctx: Ctx = Depends(require("members.manage")), db: Session = Depends(get_db)):
    """What would be sent right now to the members of your group (does not send anything)."""
    return [
        {"user": db.get(m.User, uid).email, "tasks": [f"{t.title} ({t.next_due})" for t in tasks]}
        for uid, tasks in collect(db, ctx.group.id).items()
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
