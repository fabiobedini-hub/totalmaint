"""Small event log for TotalMant Admin: one row per thing worth knowing (who, what, when).

`log()` only adds the row to the session; the caller's commit saves it together with the change.
"""
from typing import Optional

from sqlalchemy.orm import Session

from . import models as m

KINDS = {
    "setup": "First account",
    "signup": "New family registered",
    "family_created": "Extra family created",
    "login": "Log-in",
    "login_blocked": "Blocked account tried to log in",
    "invite_sent": "Invitation",
    "invite_accepted": "Invitation accepted",
    "member_added": "Member added",
    "member_removed": "Member removed",
    "reset_requested": "Password link",
    "reset_done": "Password changed",
    "mail_sent": "E-mail sent",
    "mail_failed": "E-mail failed",
    "reminders": "Reminder run",
    "backup": "Backup",
    "admin": "Admin action",
    "admin_login": "Admin console log-in",
}


def log(db: Session, kind: str, text: str = "", user: Optional[m.User] = None, group_id: Optional[int] = None,
        user_id: Optional[int] = None) -> None:
    db.add(m.Event(kind=kind, text=(text or "")[:300], user_id=user.id if user else user_id, group_id=group_id))
