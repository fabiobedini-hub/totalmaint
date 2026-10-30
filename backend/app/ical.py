"""iCal feed: subscribe to it in Outlook, Google Calendar or the iPhone calendar.

The URL contains a private token instead of a password, because calendar apps
can't log in. Reset it from Settings if it ever leaks.
"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .config import PUBLIC_URL
from .db import get_db
from .services import calendar_events

router = APIRouter()


def _esc(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines longer than 75 octets are folded."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, current = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(current) + len(b) > 74:
            parts.append(current.decode("utf-8"))
            current = b
        else:
            current += b
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


@router.get("/ical/{token}.ics")
def ical_feed(token: str, db: Session = Depends(get_db)):
    user = db.scalar(select(m.User).where(m.User.ical_token == token))
    if user is None:
        raise HTTPException(404, "Unknown calendar")
    no = user.lang == "no"
    today = date.today()
    events = calendar_events(db, today - timedelta(days=60), today + timedelta(days=365), user.id)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//TotalMaint//EN", "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH", f"X-WR-CALNAME:{'Vedlikehold' if no else 'Maintenance'}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H", "X-PUBLISHED-TTL:PT6H",
    ]
    for e in events:
        if e["type"] == "done":
            continue
        d = date.fromisoformat(e["date"])
        if e["type"] == "warranty":
            summary = f"{'Garanti utløper' if no else 'Warranty ends'}: {e['title']} ({e['asset']})"
            url = f"{PUBLIC_URL}/#/asset/{e['asset_id']}"
        else:
            summary = f"{e['title']} – {e['asset']}"
            url = f"{PUBLIC_URL}/#/task/{e['id']}"
        uid = f"{e['type']}-{e['id']}-{d.isoformat()}@totalmaint"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
            f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
            f"SUMMARY:{_esc(summary)}",
            f"URL:{url}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    body = "\r\n".join(_fold(line) for line in lines) + "\r\n"
    return Response(body, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'inline; filename="maintenance.ics"'})
