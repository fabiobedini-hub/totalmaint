from datetime import date
from typing import Optional

from dateutil.relativedelta import relativedelta

UNITS = ("none", "days", "weeks", "months", "years")


def add_interval(start: date, value: int, unit: str) -> Optional[date]:
    """Return start + interval, or None for one-off tasks."""
    if unit == "none" or not value:
        return None
    return start + relativedelta(**{unit: value})


def next_due_after_completion(done_on: date, value: int, unit: str) -> Optional[date]:
    """Next due date is counted from the day the job was actually done.

    (Counting from the old due date would let an overdue task pile up;
    counting from the completion date matches how maintenance really works.)
    """
    return add_interval(done_on, value, unit)


# ---------------------------------------------------------------- counters (km / engine hours)
_RANK = {"ok": 0, "due_soon": 1, "overdue": 2}


def worst_status(*states: Optional[str]) -> Optional[str]:
    """Combine a date status and a counter status: whichever comes first wins."""
    found = [x for x in states if x in _RANK]
    return max(found, key=_RANK.get) if found else None


def counter_status(current: Optional[float], next_at: Optional[float], interval: Optional[float],
                   remind_before: Optional[float] = None) -> Optional[str]:
    """overdue / due_soon / ok for a counter-based task, None when it can't be judged.

    Without an explicit margin the task is "due soon" in the last 10 % of the interval
    (10 h before a 100 h service, 1 500 km before a 15 000 km service).
    """
    if current is None or next_at is None:
        return None
    margin = remind_before if remind_before is not None else (interval or 0) * 0.1
    if current >= next_at:
        return "overdue"
    if current >= next_at - margin:
        return "due_soon"
    return "ok"


def next_counter_after_completion(reading: Optional[float], interval: Optional[float],
                                  previous_next: Optional[float]) -> Optional[float]:
    """Next counter value at which the task is due, counted from the reading when it was done."""
    if not interval:
        return None
    if reading is not None:
        return reading + interval
    if previous_next is not None:  # nobody wrote the reading: move the target one interval on
        return previous_next + interval
    return None
