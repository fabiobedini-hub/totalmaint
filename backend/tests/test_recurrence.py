"""Date and counter rules – pure functions, no database."""
from datetime import date

from app.recurrence import (add_interval, counter_status, next_counter_after_completion,
                            next_due_after_completion, worst_status)


def test_add_interval_units():
    d = date(2026, 3, 10)
    assert add_interval(d, 3, "days") == date(2026, 3, 13)
    assert add_interval(d, 2, "weeks") == date(2026, 3, 24)
    assert add_interval(d, 6, "months") == date(2026, 9, 10)
    assert add_interval(d, 2, "years") == date(2028, 3, 10)


def test_one_off_has_no_next_date():
    assert add_interval(date(2026, 1, 1), 0, "months") is None
    assert add_interval(date(2026, 1, 1), 5, "none") is None


def test_month_end_does_not_overflow():
    assert add_interval(date(2026, 1, 31), 1, "months") == date(2026, 2, 28)
    assert add_interval(date(2028, 2, 29), 1, "years") == date(2029, 2, 28)


def test_next_due_counts_from_the_day_it_was_done():
    # done late (due in May, done in July): next time is counted from July
    assert next_due_after_completion(date(2026, 7, 1), 1, "years") == date(2027, 7, 1)


def test_counter_status():
    assert counter_status(None, 1000, 100) is None
    assert counter_status(800, 1000, 1000) == "ok"
    assert counter_status(905, 1000, 1000) == "due_soon"  # last 10 % of the interval
    assert counter_status(1000, 1000, 1000) == "overdue"
    assert counter_status(970, 1000, 1000, remind_before=20) == "ok"  # explicit margin wins
    assert counter_status(985, 1000, 1000, remind_before=20) == "due_soon"


def test_worst_status_wins():
    assert worst_status("ok", "overdue") == "overdue"
    assert worst_status("due_soon", None) == "due_soon"
    assert worst_status(None, None) is None


def test_next_counter_after_completion():
    assert next_counter_after_completion(1200, 100, 1100) == 1300
    assert next_counter_after_completion(None, 100, 1100) == 1200  # no reading: move one interval
    assert next_counter_after_completion(1200, None, 1100) is None
